from datetime import date

from canasta.basket import BasketItem
from canasta.index import build_index


def item(ean: str, qty: float) -> BasketItem:
    return BasketItem(ean=ean, label=ean, qty_per_month=qty)


def test_index_base_y_carry_forward() -> None:
    items = [item("A", 2), item("B", 1)]
    prices = {
        date(2026, 11, 1): {"A": 10.0, "B": 20.0},
        date(2026, 11, 2): {"A": 11.0, "B": 22.0},
        date(2026, 11, 3): {"A": 12.0},
        date(2026, 11, 4): {"A": 13.0},
        date(2026, 11, 5): {"A": 14.0},
        date(2026, 11, 6): {"A": 15.0},
    }

    result = build_index(prices, items)

    assert result.base_fecha == date(2026, 11, 1)
    assert result.base_costo == 40.0
    assert result.rows[0].indice == 100.0
    assert result.rows[1].indice == 110.0
    assert result.rows[2].costo == 46.0
    assert result.rows[2].indice == 115.0
    assert result.rows[4].completo is True
    assert result.rows[5].completo is False
    assert result.rows[5].n_items_con_precio == 1
    assert result.rows[5].cobertura < 90


def test_index_sin_cobertura_suficiente_no_fija_base() -> None:
    result = build_index({date(2026, 11, 1): {"A": 10.0}}, [item("A", 2), item("B", 1)])

    assert result.base_fecha is None
    assert result.rows[0].indice is None
    assert result.rows[0].completo is False


def test_index_vacio() -> None:
    result = build_index({}, [])

    assert result.rows == ()
    assert result.base_fecha is None
