import os
import time
from asyncio.exceptions import InvalidStateError
from datetime import datetime

from playwright._impl._api_structures import SetCookieParam
from playwright._impl._errors import Error as pw_Error
from playwright.sync_api import TimeoutError as pw_TimeoutError
from playwright.sync_api import sync_playwright
from playwright.sync_api._generated import Locator
from pydantic import BaseModel

from src.config.logger import logger
from src.models import ScannedProduct
from src.scraper import exceptions, utils
from src.scraper.product_state import ProductsState

if os.getenv("URL_SEED") is None:
    raise ValueError("URL_SEED environment variable not set.")

SLEEP_TIME_SECONDS = 1
PW_TIMEOUT_MS = 5000


class ScanState(BaseModel):
    scanned_products: list[ScannedProduct]
    category_name: str
    subcategory_name: str
    is_started: bool
    is_finished: bool
    pending_prodcuts: list[str] = []
    done_products: list[str] = []


def compute(products_state: ProductsState) -> ProductsState:
    """Scrapes the website to get basic information the products (ID, category, subcategory).

    Main steps:
    -
    """

    cookies = [
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

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, slow_mo=None, timeout=PW_TIMEOUT_MS)
            page = browser.new_page()
            page.set_default_timeout(PW_TIMEOUT_MS)
            page.set_default_navigation_timeout(PW_TIMEOUT_MS)
            page.context.add_cookies(cookies)
            page.goto(os.getenv("URL_SEED", "default_invalid_url"))
            page.wait_for_load_state("load")
            page.wait_for_load_state("domcontentloaded")
            page.wait_for_load_state("networkidle")

            logger.debug("Fresh start")
            # Add/sync categories
            categories_ = page.locator("css=span.category-menu__header").all()
            products_state.add_categories(categories_)
            logger.debug("Found %s categories", len(categories_))
            if len(categories_) == 0:
                raise exceptions.ScraperException("No categories found")

            # Add/sync subcategories
            pending_cats = products_state.get_pending_categories()
            pending_cats[0].click()
            _ = check_too_much_requests(page)
            page.wait_for_load_state("load")

            subcategories = page.locator("css=li.open").locator("li").all()
            products_state.add_subcategories(pending_cats[0], subcategories)
            pending_subcats = products_state.get_pending_subcategories(pending_cats[0])

            # Add/sync products
            pending_subcats[0].click()
            _ = check_too_much_requests(page)
            page.wait_for_load_state("load")
            page.wait_for_url("**/categories/**")
            buttons_products = get_products_locators(page)

            products_state.add_products(pending_cats[0], pending_subcats[0], buttons_products)
            pending_products = products_state.get_pending_products(
                pending_cats[0], pending_subcats[0]
            )

            while pending_products:
                logger.debug("Iter to the next product")
                pending_products[0].click()
                _ = check_too_much_requests(page)
                page.wait_for_load_state("load")
                page.wait_for_url("**/product/**")
                product_id = utils.extract_product_id_from_url(page.url)
                page.locator("css=button.modal-content__close").click()

                products_state.add_scanned_product(
                    pending_cats[0],
                    pending_subcats[0],
                    pending_products[0],
                    ScannedProduct(
                        product_id=product_id,
                        category_name=pending_cats[0].inner_text(),
                        subcategory_name=pending_subcats[0].inner_text(),
                        scanned_at=datetime.now(),
                    ),
                )
                logger.info("Official product ID: %s", product_id)

                current_cat = pending_cats[0]
                current_subcat = pending_subcats[0]

                pending_cats = products_state.get_pending_categories()
                if pending_cats:
                    pending_subcats = products_state.get_pending_subcategories(pending_cats[0])
                else:
                    # No more categories to scan
                    break
                if pending_subcats:
                    pending_products = products_state.get_pending_products(
                        pending_cats[0], pending_subcats[0]
                    )

                if current_cat != pending_cats[0] or len(pending_subcats) == 0:
                    # The current category is finished, we need to load the next one (and the
                    # corresponding subcategories)
                    logger.debug("Load next category")
                    pending_cats[0].click()
                    _ = check_too_much_requests(page)
                    page.wait_for_load_state("load")
                    _wait_until_load(page, last_category=False)
                    subcategories = page.locator("css=li.open").locator("li").all()
                    products_state.add_subcategories(pending_cats[0], subcategories)
                    pending_subcats = products_state.get_pending_subcategories(pending_cats[0])

                if current_subcat != pending_subcats[0]:
                    # The current subcategory is finished, we need to load the next one (and the
                    # corresponding products)
                    logger.debug("Load next subcategory")
                    pending_subcats[0].click()
                    _ = check_too_much_requests(page)
                    page.wait_for_load_state("load")
                    _wait_until_load(page, last_category=False)
                    page.wait_for_url("**/categories/**")
                    buttons_products = get_products_locators(page)
                    products_state.add_products(
                        pending_cats[0], pending_subcats[0], buttons_products
                    )
                    pending_products = products_state.get_pending_products(
                        pending_cats[0], pending_subcats[0]
                    )

    except pw_TimeoutError:
        time.sleep(SLEEP_TIME_SECONDS)
        logger.exception("TimeoutError")
        return products_state
    except InvalidStateError:
        time.sleep(SLEEP_TIME_SECONDS)
        logger.exception("InvalidStateError")
        return products_state
    except exceptions.ScraperException as exc:
        logger.exception("An error occurred: %s", exc)
        return products_state
    except pw_Error as exc:
        logger.exception("An error occurred: %s", exc)
        return products_state
    except Exception as exc:
        logger.exception("An unexpected error occurred: %s", exc)
        raise exc

    products_state.is_finished = True
    return products_state


def _wait_until_load(page, last_category: bool = False) -> None:
    # Waiting logic
    page.screenshot(path="screenshot_20_wait.png")
    page.wait_for_load_state("load")
    page.screenshot(path="screenshot_21_wait.png")
    page.wait_for_load_state("networkidle")
    page.screenshot(path="screenshot_22_wait.png")
    tries = 0
    selector = "button.category-detail__next-subcategory"
    while tries < 3:
        page.screenshot(path=f"screenshot_23_{tries}_wait.png")
        tries += 1
        try:
            # This is the last element to load ("Next subcategory" button)
            page.query_selector(selector).wait_for_element_state("stable", timeout=3000)
            break
        except TimeoutError as exc:
            logger.debug("Timeout for `%s`", selector)
            if not last_category:
                raise pw_TimeoutError(f"`{selector}` did not load") from exc
        except AttributeError:
            logger.debug("Waiting for `%s`", selector)
            page.wait_for_timeout(1000)


def get_products_locators(page) -> list[Locator]:
    page.screenshot(path="screenshot_30_before_locate.png")
    selector = "css=button.product-cell__content-link"
    buttons_products = page.locator(selector).all()
    page.screenshot(path="screenshot_31_after_locate.png")
    tries = 0
    while not buttons_products and tries < 3:
        tries += 1
        page.screenshot(path="screenshot_32_before_wait.png")
        _ = check_too_much_requests(page)
        logger.debug("Waiting for `%s`", selector)
        page.wait_for_timeout(1000)
        page.screenshot(path="screenshot_33_after_wait.png")
        buttons_products = page.locator(selector).all()

    if not buttons_products:
        raise exceptions.ScraperException("No products found")

    if not isinstance(buttons_products, list):
        raise TypeError(f"Unexpected type: {type(buttons_products)}")

    return buttons_products


def check_too_much_requests(page) -> bool:
    # Selector to find the button with text "Entendido"
    button_selector = 'button:has-text("Entendido")'

    # Check if the button exists
    button_exists = page.locator(button_selector).count() > 0
    if button_exists:
        logger.debug("Button 'Entendido' exists: %s", button_exists)
        page.locator(button_selector).click()
        return True

    return False
