import os
import time
from asyncio.exceptions import InvalidStateError
from datetime import datetime

from playwright._impl._api_structures import SetCookieParam
from playwright.sync_api import TimeoutError as pw_TimeoutError
from playwright.sync_api import sync_playwright
from pydantic import BaseModel

from src.config.logger import logger
from src.models import ScannedProduct
from src.scraper import exceptions, utils

if os.getenv("URL_SEED") is None:
    raise ValueError("URL_SEED environment variable not set.")

SLEEP_TIME_SECONDS = 120


class ScanState(BaseModel):
    scanned_products: list[ScannedProduct]
    category_name: str
    subcategory_name: str
    is_finished: bool


def compute(initial_state: ScanState) -> ScanState:
    """Scrapes the website to get basic information the products (ID, category, subcategory)."""

    current_state = initial_state.model_copy(deep=True)

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
            browser = p.chromium.launch(headless=True, slow_mo=500, timeout=15000)
            page = browser.new_page()
            page.context.add_cookies(cookies)
            page.goto(os.getenv("URL_SEED", "default_invalid_url"))
            page.wait_for_load_state("load")

            categories_ = page.locator("css=span.category-menu__header").all()
            logger.debug("Found %s categories", len(categories_))
            if len(categories_) == 0:
                raise exceptions.ScraperException("No categories found")

            category_start = 0
            if current_state.category_name != "":
                for i, category in enumerate(categories_):
                    if category.inner_text() == current_state.category_name:
                        category_start = i
                        break
                # For a non-empty category_name, `category_start` should be different from 0
                # if category_start == 0:
                #     raise ValueError(f"Category `{category_name}` not found")

            n_categories = len(categories_)
            for i_category in range(category_start, n_categories):
                category = categories_[i_category]
                try:
                    category.click()
                except TimeoutError as err:
                    page.screenshot(path="screenshot_05_product_TimeoutError.png")
                    raise TimeoutError from err

                current_state.category_name = category.inner_text()
                page.wait_for_load_state("load")
                page.screenshot(path="screenshot_10_category.png")
                subcategories = page.locator("css=li.open").locator("li").all()
                logger.debug("Found %s subcategories", len(subcategories))

                subcategory_start = 0
                if current_state.subcategory_name != "":
                    for i, subcategory in enumerate(subcategories):
                        if subcategory.inner_text() == current_state.subcategory_name:
                            subcategory_start = i
                            break

                n_subcategories = len(subcategories)
                for i_subcategory in range(subcategory_start, n_subcategories):
                    subcategory = subcategories[i_subcategory]
                    try:
                        subcategory.click()
                    except TimeoutError as err:
                        page.screenshot(path="screenshot_15_product_TimeoutError.png")
                        raise TimeoutError from err

                    current_state.subcategory_name = subcategory.inner_text()

                    is_last_subcategory = subcategory == subcategories[-1]
                    _wait_until_load(page, last_category=is_last_subcategory)

                    page.screenshot(path="screenshot_30_subcategory.png")

                    buttons_products = page.locator("css=button.product-cell__content-link").all()

                    for button in buttons_products:
                        try:
                            button.click()
                        except TimeoutError as err:
                            page.screenshot(path="screenshot_35_product_TimeoutError.png")
                            raise TimeoutError from err

                        page.wait_for_load_state("load")
                        page.wait_for_url("**/product/**")
                        product_id = utils.extract_product_id_from_url(page.url)
                        current_state.scanned_products.append(
                            ScannedProduct(
                                product_id=product_id,
                                category_name=current_state.category_name,
                                subcategory_name=current_state.subcategory_name,
                                scanned_at=datetime.now(),
                            )
                        )
                        logger.info("Official product ID: %s", product_id)
                        try:
                            page.locator("css=button.modal-content__close").click()
                        except TimeoutError as err:
                            page.screenshot(path="screenshot_36_product_TimeoutError.png")
                            raise TimeoutError from err

                    logger.info(
                        "Scraped category: %s - %s",
                        current_state.category_name,
                        current_state.subcategory_name,
                    )
    except pw_TimeoutError:
        time.sleep(SLEEP_TIME_SECONDS)
        logger.exception("TimeoutError")
        return current_state
    except InvalidStateError:
        time.sleep(SLEEP_TIME_SECONDS)
        logger.exception("InvalidStateError")
        return current_state
    except exceptions.ScraperException as exc:
        logger.exception("An error occurred: %s", exc)
        return current_state
    except Exception as exc:
        logger.exception("An unexpected error occurred: %s", exc)
        raise exc

    current_state.is_finished = True
    return current_state


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
                raise TimeoutError(f"`{selector}` did not load") from exc
        except AttributeError:
            logger.debug("Waiting for `%s`", selector)
            page.wait_for_timeout(1000)
