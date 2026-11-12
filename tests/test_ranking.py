from canasta.basket import BasketItem
from canasta.ranking import rank_chains


def item(ean: str, qty: float) -> BasketItem:
    return BasketItem(ean=ean, label=ean, qty_per_month=qty)


def test_ranking_y_ahorro() -> None:
    items = [item("A", 2), item("B", 1)]
    prices = {
        "Super A": {"A": 10.0, "B": 20.0},
        "Super B": {"A": 9.0, "B": 25.0},
        "Super C": {"A": 8.0},
    }

    result = rank_chains(prices, items)

    assert result.mejor_cadena == "Super A"
    assert result.costo_mejor_cadena == 40.0
    assert result.costo_surtido == 36.0
    assert result.ahorro_potencial == 4.0
    assert result.cobertura_surtido == 100.0
    assert [row.cadena for row in result.cadenas[:2]] == ["Super A", "Super B"]
    assert result.cadenas[0].ranking == 1
    assert result.cadenas[2].ranking is None


def test_ranking_sin_cadena_completa() -> None:
    result = rank_chains({"Super A": {"A": 10.0}}, [item("A", 1), item("B", 1)])

    assert result.mejor_cadena is None
    assert result.costo_mejor_cadena is None
    assert result.costo_surtido == 10.0
    assert result.cobertura_surtido == 50.0
    assert result.ahorro_potencial is None
    assert result.cadenas[0].ranking is None


def test_ranking_vacio() -> None:
    result = rank_chains({}, [])

    assert result.cadenas == ()
    assert result.mejor_cadena is None
    assert result.cobertura_surtido == 0.0
