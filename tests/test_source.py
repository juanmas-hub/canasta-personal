from datetime import date

import pytest

from canasta.source import parse_resources, resource_for_date


def test_parse_resources_reads_date_from_description() -> None:
    payload = {
        "result": {
            "resources": [
                {
                    "name": "Martes",
                    "description": "Precios SEPA Minoristas martes, 2026-11-03",
                    "url": "https://example.test/sepa_martes.zip",
                    "size": 319893305,
                    "last_modified": "2026-11-03T16:19:20.252308",
                },
                {
                    "name": "Metadata",
                    "description": "Anexo II sin fecha",
                    "url": "https://example.test/anexo.pdf",
                    "size": 321021,
                },
            ]
        }
    }
    resources = parse_resources(payload)
    assert len(resources) == 1
    assert resources[0].date == date(2026, 11, 3)
    assert resources[0].size == 319893305


def test_resource_for_date_matches_exact_date() -> None:
    payload = {
        "result": {
            "resources": [
                {
                    "name": "Lunes",
                    "description": "Precios SEPA Minoristas lunes, 2026-11-02",
                    "url": "https://example.test/lunes.zip",
                    "size": 1,
                },
                {
                    "name": "Martes",
                    "description": "Precios SEPA Minoristas martes, 2026-11-03",
                    "url": "https://example.test/martes.zip",
                    "size": 1,
                },
            ]
        }
    }
    resources = parse_resources(payload)
    assert resource_for_date(resources, date(2026, 11, 3)).name == "Martes"


def test_resource_for_date_reports_available_dates() -> None:
    resources = parse_resources(
        {
            "result": {
                "resources": [
                    {
                        "name": "Lunes",
                        "description": "Precios SEPA Minoristas lunes, 2026-11-02",
                        "url": "https://example.test/lunes.zip",
                    }
                ]
            }
        }
    )
    with pytest.raises(LookupError, match="2026-11-02"):
        resource_for_date(resources, date(2026, 11, 3))
