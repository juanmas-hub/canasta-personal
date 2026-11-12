"""Command line entry point: ``canasta ingest --date YYYY-MM-DD``."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import date
from pathlib import Path

from canasta.config import load_settings
from canasta.ingest import run_ingest
from canasta.marts import write_marts
from canasta.retention import prune_raw
from canasta.source import fetch_resources


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="canasta")
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)

    ingest = sub.add_parser("ingest", help="ingest one SEPA day into Parquet")
    ingest.add_argument("--date", type=date.fromisoformat, required=True)
    ingest.add_argument("--zip", type=Path, help="use a local outer ZIP instead of downloading")
    ingest.add_argument("--keep-temp", action="store_true")

    source = sub.add_parser("source", help="list the dates currently published")
    source.add_argument("--json", action="store_true")

    marts = sub.add_parser("marts", help="materialize dashboard marts from DuckDB")
    marts.add_argument("--basket", type=Path, help="basket YAML (default: basket.yml or example)")

    sub.add_parser("prune", help="delete raw partitions older than the configured retention")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    try:
        if args.command == "source":
            resources = fetch_resources()
            rows = [
                {"date": r.date.isoformat(), "name": r.name, "bytes": r.size, "url": r.url}
                for r in sorted(resources, key=lambda r: r.date, reverse=True)
            ]
            if args.json:
                print(json.dumps(rows, indent=2, ensure_ascii=False))
            else:
                for row in rows:
                    print(f"{row['date']}  {row['name']:<20}  {row['bytes']}")
            return 0

        settings = load_settings()
        if args.command == "marts":
            marts_result = write_marts(settings, basket_path=args.basket)
            print(json.dumps(marts_result, indent=2, ensure_ascii=False))
            return 0
        if args.command == "prune":
            print(json.dumps(prune_raw(settings), indent=2, ensure_ascii=False))
            return 0
        result = run_ingest(
            target_date=args.date,
            settings=settings,
            zip_path=args.zip,
            keep_temp=args.keep_temp,
        )
        print(json.dumps(result.as_dict(), indent=2, ensure_ascii=False))
        return 0
    except LookupError as exc:
        logging.error("SOURCE_NOT_PUBLISHED %s", exc)
        return 2
    except Exception:
        logging.exception("ingest failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
