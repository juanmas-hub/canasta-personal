"""SEPA source discovery and download.

The dataset publishes seven rotating ZIP resources (one per weekday), so the
date must be read from each resource's ``description``, not from its name.
"""

from __future__ import annotations

import logging
import os
import random
import re
import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

CKAN_URL = "https://datos.produccion.gob.ar/api/3/action/package_show"
PACKAGE_ID = "sepa-precios"
USER_AGENT = "canasta-personal/0.1 (+https://github.com/juanmas-hub/canasta-personal)"
DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")


@dataclass(frozen=True)
class SepaResource:
    name: str
    description: str
    url: str
    size: int | None
    last_modified: str
    date: date


def _client() -> httpx.Client:
    return httpx.Client(
        headers={"User-Agent": USER_AGENT},
        follow_redirects=True,
        timeout=httpx.Timeout(connect=20.0, read=180.0, write=60.0, pool=30.0),
    )


def _sleep(attempt: int, retry_after: str | None = None) -> None:
    if retry_after:
        try:
            time.sleep(min(float(retry_after), 120.0))
            return
        except ValueError:
            pass
    time.sleep(min(2**attempt, 60) + random.uniform(0.0, 1.0))


def parse_resources(payload: dict[str, object]) -> list[SepaResource]:
    """Parse a CKAN ``package_show`` payload into dated resources."""
    result = payload["result"]
    if not isinstance(result, dict):
        raise ValueError("unexpected CKAN payload: result is not an object")
    raw_resources = result.get("resources")
    if not isinstance(raw_resources, list):
        raise ValueError("unexpected CKAN payload: resources is not a list")

    resources: list[SepaResource] = []
    for raw in raw_resources:
        if not isinstance(raw, dict):
            continue
        description = str(raw.get("description") or "")
        match = DATE_RE.search(description)
        if not match:
            continue
        resources.append(
            SepaResource(
                name=str(raw["name"]),
                description=description,
                url=str(raw["url"]),
                size=int(raw["size"]) if raw.get("size") is not None else None,
                last_modified=str(raw.get("last_modified") or ""),
                date=date.fromisoformat(match.group(1)),
            )
        )
    return resources


def fetch_resources(max_attempts: int = 6) -> list[SepaResource]:
    """Fetch and parse the CKAN package metadata."""
    last_error: Exception | None = None
    with _client() as client:
        for attempt in range(1, max_attempts + 1):
            try:
                response = client.get(CKAN_URL, params={"id": PACKAGE_ID})
                response.raise_for_status()
                resources = parse_resources(response.json())
                logger.info("event=ckan_ok resources=%d", len(resources))
                return resources
            except (httpx.HTTPError, KeyError, ValueError) as exc:
                last_error = exc
                logger.warning("event=ckan_retry attempt=%d error=%r", attempt, exc)
                _sleep(attempt)
    raise RuntimeError(f"CKAN metadata unavailable after {max_attempts} attempts: {last_error}")


def resource_for_date(resources: list[SepaResource], target: date) -> SepaResource:
    matches = [resource for resource in resources if resource.date == target]
    if not matches:
        available = ", ".join(sorted({r.date.isoformat() for r in resources}))
        raise LookupError(f"No SEPA resource for {target}. Available dates: {available}")
    return matches[0]


def download_resource(
    resource: SepaResource,
    dest: Path,
    max_attempts: int = 8,
    progress_every_bytes: int = 50 * 1024 * 1024,
) -> dict[str, float | int | str]:
    """Download a ZIP resource to ``dest``.

    The origin advertises ``accept-ranges`` but answers Range requests with 200
    and the full body, so there is no reliable resume. A partial download is
    removed and retried from scratch.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_suffix(dest.suffix + ".part")
    last_error: Exception | None = None

    for attempt in range(1, max_attempts + 1):
        part.unlink(missing_ok=True)
        started = time.monotonic()
        downloaded = 0
        last_report = 0
        retry_after: str | None = None
        try:
            with _client() as client, client.stream("GET", resource.url) as response:
                if response.status_code in (429, 500, 502, 503, 504):
                    retry_after = response.headers.get("Retry-After")
                    raise httpx.HTTPStatusError(
                        f"HTTP {response.status_code}", request=response.request, response=response
                    )
                response.raise_for_status()
                with part.open("wb") as handle:
                    for chunk in response.iter_bytes(chunk_size=1024 * 1024):
                        handle.write(chunk)
                        downloaded += len(chunk)
                        if downloaded - last_report >= progress_every_bytes:
                            last_report = downloaded
                            logger.info(
                                "event=download_progress bytes=%d elapsed_s=%.1f",
                                downloaded,
                                time.monotonic() - started,
                            )
            if resource.size is not None and part.stat().st_size != resource.size:
                raise OSError(f"size mismatch: got {part.stat().st_size}, expected {resource.size}")
            os.replace(part, dest)
            elapsed = time.monotonic() - started
            logger.info(
                "event=download_ok bytes=%d elapsed_s=%.1f url=%s",
                downloaded,
                elapsed,
                resource.url,
            )
            return {
                "bytes": downloaded,
                "elapsed_s": round(elapsed, 3),
                "url": resource.url,
                "last_modified": resource.last_modified,
            }
        except (httpx.HTTPError, OSError) as exc:
            last_error = exc
            logger.warning("event=download_retry attempt=%d error=%r", attempt, exc)
            _sleep(attempt, retry_after)
            retry_after = None
        finally:
            part.unlink(missing_ok=True)

    raise RuntimeError(f"download failed after {max_attempts} attempts: {last_error}")
