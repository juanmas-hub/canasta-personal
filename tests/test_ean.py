import pytest

from canasta.ean import gs1_check_digit, is_valid_ean


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ("400638133393", 1),
        ("9638507", 4),
        ("03600029145", 2),
    ],
)
def test_gs1_check_digit(payload: str, expected: int) -> None:
    assert gs1_check_digit(payload) == expected


@pytest.mark.parametrize(
    "code",
    [
        "4006381333931",
        "96385074",
        "036000291452",
        "0000096385074",
        "0000012345670",
    ],
)
def test_valid_codes(code: str) -> None:
    assert is_valid_ean(code)


@pytest.mark.parametrize(
    "code",
    [
        "4006381333932",
        "12345678",
        "0000000000000",
        "not-an-ean",
        "",
        "123",
    ],
)
def test_invalid_codes(code: str) -> None:
    assert not is_valid_ean(code)
