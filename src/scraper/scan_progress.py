from src.models import ScannedProduct


class ScanProgress:
    """Tracks which products have been scanned so a scan can resume across sessions.

    The scraper runs inside a VPN-rotation retry loop (see `scan_products.py`): each
    `compute()` call is a fresh browser session. The only state that must survive
    between sessions is *what has already been scanned* — Playwright locators are
    session-bound and are always re-derived from the live page, never persisted.

    Dedup/skip keys:
    - a product is keyed by ``(category_name, product_name)``. The same product can
      legitimately appear under multiple top-level categories and is scanned once per
      category (this mirrors the previous behaviour).
    - a subcategory is keyed by ``(category_name, subcategory_name)`` once fully walked,
      so finished subcategories are skipped wholesale on resume.
    """

    def __init__(self) -> None:
        self.scanned: list[ScannedProduct] = []
        self._scanned_keys: set[tuple[str, str]] = set()
        self._done_subcategories: set[tuple[str, str]] = set()
        self.is_finished = False

    def is_product_scanned(self, category_name: str, product_name: str) -> bool:
        return (category_name, product_name) in self._scanned_keys

    def record(self, scanned_product: ScannedProduct, product_name: str) -> None:
        key = (scanned_product.category_name, product_name)
        if key in self._scanned_keys:
            return
        self.scanned.append(scanned_product)
        self._scanned_keys.add(key)

    def is_subcategory_done(self, category_name: str, subcategory_name: str) -> bool:
        return (category_name, subcategory_name) in self._done_subcategories

    def mark_subcategory_done(self, category_name: str, subcategory_name: str) -> None:
        self._done_subcategories.add((category_name, subcategory_name))

    def get_scanned_products(self) -> list[ScannedProduct]:
        return self.scanned
