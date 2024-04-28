import re

import validators


def extract_product_id_from_url(url: str) -> float:
    if not validators.url(url):
        raise ValueError(f"Invalid URL: {url}")

    # pattern = r"/product/(\d+)/"
    pattern = r"/product/(\d+(?:\.\d+)*)/"
    match = re.search(pattern, url)

    if match:
        return float(match.group(1))
    else:
        raise ValueError(f"Product ID not found in URL: {url}")
