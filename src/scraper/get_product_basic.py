"""Scrape Mercadona for basic product info (id, category, subcategory).

DRAFT — this is the rewritten scraper and has NOT yet been verified against a live
run. It must be exercised end-to-end behind the VPN before being relied upon.

Design
------
`compute()` walks the live catalogue top-down: category -> subcategory -> product.
At every level the DOM is re-queried fresh (we never hold Playwright locators across
navigations, which avoids the stale-locator problem the previous implementation had
to work around). Progress is tracked in a `ScanProgress` object so that, when the
outer VPN-rotation loop calls `compute()` again after a failure, already-scanned
products and finished subcategories are skipped.
"""

import time
from asyncio.exceptions import InvalidStateError
from datetime import datetime

from playwright._impl._api_structures import SetCookieParam
from playwright._impl._errors import Error as pw_Error
from playwright.sync_api import TimeoutError as pw_TimeoutError
from playwright.sync_api import sync_playwright
from playwright.sync_api._generated import Locator

from src.config.logger import logger
from src.config.settings import settings
from src.models import ScannedProduct
from src.scraper import exceptions, utils
from src.scraper.scan_progress import ScanProgress

SLEEP_TIME_SECONDS = 1
PW_TIMEOUT_MS = 15000
NAV_TIMEOUT_MS = 30000

# Set True to dump full-page screenshots at each step while debugging the scraper.
DEBUG_SCREENSHOTS = False

CATEGORY_MENU_SELECTOR = "css=span.category-menu__header"
SUBCATEGORY_SELECTOR = "css=li.open"
PRODUCT_BUTTON_SELECTOR = "css=button.product-cell__content-link"
MODAL_CLOSE_SELECTOR = "css=button.modal-content__close"
TOO_MANY_REQUESTS_SELECTOR = 'button:has-text("Entendido")'

COOKIES = [
    SetCookieParam(
        {
            "name": "__mo_da",
            "value": '{"warehouse":"vlc1","postalCode":"46001"}',
            "domain": ".mercadona.es",
            "path": "/",
            "secure": True,
        }
    ),
    SetCookieParam(
        {
            "name": "__mo_ca",
            "value": '{"thirdParty":true,"necessary":true,"version":1}',
            "domain": ".mercadona.es",
            "path": "/",
            "secure": True,
        }
    ),
]


def compute(progress: ScanProgress, partial_scan: str | None = None) -> ScanProgress:
    """Walk the catalogue, recording scanned products into `progress`.

    Returns `progress` with `is_finished=True` once the whole (sampled) catalogue has
    been scanned. On a recoverable error it returns the partial `progress` so the outer
    retry loop can resume; unexpected errors are re-raised.
    """
    try:
        with sync_playwright() as p:
            page = _launch_page(p)
            _goto_catalog(page)

            category_names = _category_names(page, partial_scan)
            if not category_names:
                raise exceptions.ScraperError("No categories found")
            logger.debug("Scanning %s categories", len(category_names))

            for category_name in category_names:
                _scan_category(page, progress, category_name)

    except (pw_TimeoutError, InvalidStateError, exceptions.ScraperError, pw_Error) as exc:
        time.sleep(SLEEP_TIME_SECONDS)
        logger.exception("Recoverable scraping error; will retry next session: %s", exc)
        return progress
    except Exception:
        logger.exception("Unexpected error during scraping")
        raise

    progress.is_finished = True
    return progress


def _scan_category(page, progress: ScanProgress, category_name: str) -> None:
    _open_category(page, category_name)
    page.locator("css=li.open li").first.wait_for(state="attached")

    subcategory_names = [
        item.inner_text() for item in page.locator(SUBCATEGORY_SELECTOR).locator("li").all()
    ]
    logger.debug("Category %s: %s subcategories", category_name, len(subcategory_names))

    for subcategory_name in subcategory_names:
        if progress.is_subcategory_done(category_name, subcategory_name):
            logger.debug("Skip done subcategory: %s / %s", category_name, subcategory_name)
            continue
        _scan_subcategory(page, progress, category_name, subcategory_name)
        progress.mark_subcategory_done(category_name, subcategory_name)


def _scan_subcategory(
    page, progress: ScanProgress, category_name: str, subcategory_name: str
) -> None:
    # Re-open the category so the subcategory is reachable from a known page state.
    _open_category(page, category_name)
    page.locator("css=li.open li").first.wait_for(state="attached")
    _open_subcategory(page, subcategory_name)
    page.wait_for_url("**/categories/**")

    product_names = [button.inner_text() for button in get_products_locators(page)]
    logger.debug(
        "Subcategory %s / %s: %s products", category_name, subcategory_name, len(product_names)
    )

    for product_name in product_names:
        if progress.is_product_scanned(category_name, product_name):
            continue
        _scan_product(page, progress, category_name, subcategory_name, product_name)


def _scan_product(
    page,
    progress: ScanProgress,
    category_name: str,
    subcategory_name: str,
    product_name: str,
) -> None:
    _open_product(page, product_name)
    page.wait_for_url("**/product/**")
    product_id = utils.extract_product_id_from_url(page.url)
    page.locator(MODAL_CLOSE_SELECTOR).click()

    progress.record(
        ScannedProduct(
            product_id=product_id,
            category_name=category_name,
            subcategory_name=subcategory_name,
            scanned_at=datetime.now(),
        ),
        product_name,
    )
    logger.info("Scanned product %s (%s / %s)", product_id, category_name, subcategory_name)


def _launch_page(p):
    browser = p.chromium.launch(
        headless=settings.playwright_headless, slow_mo=None, timeout=PW_TIMEOUT_MS
    )
    page = browser.new_page()
    page.set_default_timeout(PW_TIMEOUT_MS)
    page.set_default_navigation_timeout(PW_TIMEOUT_MS)
    page.context.add_cookies(COOKIES)
    return page


def _goto_catalog(page) -> None:
    logger.info("Navigating to URL_SEED")
    response = page.goto(settings.url_seed, timeout=NAV_TIMEOUT_MS, wait_until="domcontentloaded")
    status = response.status if response is not None else None
    logger.info("goto done: status=%s, final_url=%s", status, page.url)
    _screenshot(page, "after_goto")

    try:
        page.locator(CATEGORY_MENU_SELECTOR).first.wait_for(state="visible", timeout=PW_TIMEOUT_MS)
    except pw_TimeoutError:
        _screenshot(page, "wait_timeout")
        logger.error(
            "Category menu not visible within %dms. Page title=%r, url=%s.",
            PW_TIMEOUT_MS,
            page.title(),
            page.url,
        )
        raise


def _category_names(page, partial_scan: str | None) -> list[str]:
    categories = _sample_categories(page.locator(CATEGORY_MENU_SELECTOR).all(), partial_scan)
    return [category.inner_text() for category in categories]


def _open_category(page, category_name: str) -> None:
    headers = page.locator(CATEGORY_MENU_SELECTOR)
    for i in range(headers.count()):
        header = headers.nth(i)
        if header.inner_text() == category_name:
            header.click()
            check_too_much_requests(page)
            return
    raise exceptions.ScraperError(f"Category not found: {category_name}")


def _open_subcategory(page, subcategory_name: str) -> None:
    items = page.locator(SUBCATEGORY_SELECTOR).locator("li")
    for i in range(items.count()):
        item = items.nth(i)
        if item.inner_text() == subcategory_name:
            item.click()
            check_too_much_requests(page)
            return
    raise exceptions.ScraperError(f"Subcategory not found: {subcategory_name}")


def _open_product(page, product_name: str) -> None:
    for button in get_products_locators(page):
        if button.inner_text() == product_name:
            button.click()
            check_too_much_requests(page)
            return
    raise exceptions.ScraperError(f"Product not found: {product_name}")


def get_products_locators(page) -> list[Locator]:
    buttons = page.locator(PRODUCT_BUTTON_SELECTOR).all()
    tries = 0
    while not buttons and tries < 3:
        tries += 1
        check_too_much_requests(page)
        logger.debug("Waiting for `%s`", PRODUCT_BUTTON_SELECTOR)
        page.wait_for_timeout(1000)
        buttons = page.locator(PRODUCT_BUTTON_SELECTOR).all()

    if not buttons:
        raise exceptions.ScraperError("No products found")
    if not isinstance(buttons, list):
        raise TypeError(f"Unexpected type: {type(buttons)}")
    return buttons


def check_too_much_requests(page) -> bool:
    """Dismiss the "too many requests" dialog if present; return whether it appeared."""
    if page.locator(TOO_MANY_REQUESTS_SELECTOR).count() > 0:
        logger.debug("Dismissing 'Entendido' (too-many-requests) dialog")
        page.locator(TOO_MANY_REQUESTS_SELECTOR).click()
        return True
    return False


def _screenshot(page, name: str) -> None:
    if DEBUG_SCREENSHOTS:
        page.screenshot(path=f"screenshot_{name}.png", full_page=True)


def _sample_categories(
    categories_all: list[Locator],
    partial_scan: str | None = None,
) -> list[Locator]:
    if partial_scan is None:
        return categories_all

    total_len = len(categories_all)
    quarter_size = total_len // 4

    if partial_scan == "first_quarter":
        return categories_all[:quarter_size]
    if partial_scan == "second_quarter":
        return categories_all[quarter_size : 2 * quarter_size]
    if partial_scan == "third_quarter":
        return categories_all[2 * quarter_size : 3 * quarter_size]
    if partial_scan == "fourth_quarter":
        return categories_all[3 * quarter_size :]

    # Keep backward compatibility with old two-part system
    if partial_scan == "first_half":
        return categories_all[: total_len // 2]
    if partial_scan == "second_half":
        return categories_all[total_len // 2 :]

    raise ValueError("Invalid value for `partial_scan`")
