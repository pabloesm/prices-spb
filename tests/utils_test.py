import pytest

from src.scraper.utils import extract_product_id_from_url


def test_extract_product_id_from_url():
    # Test cases with various URLs
    test_cases = [
        ("https://tienda.mercadona.es/product/3505.2/14-sandia-baja-semillas-14-pieza", 3505.2),
        ("https://tienda.mercadona.es/product/15691.1/hogaza-centeno-50", 15691.1),
        ("https://tienda.mercadona.es/product/3529/sandia-baja-semillas-pieza", 3529),
        ("https://tienda.mercadona.es/product/3236/limones-malla", 3236),
    ]

    for url, expected_product_id in test_cases:
        assert extract_product_id_from_url(url) == expected_product_id


def test_invalid_url():
    # Test case for an invalid URL
    with pytest.raises(ValueError):
        extract_product_id_from_url("invalid_url")
