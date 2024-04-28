import os
import time

from playwright._impl._api_structures import SetCookieParam
from playwright.sync_api import TimeoutError, sync_playwright

from src.config.logger import logger
from src.models import ScrapedCategory
from src.scraper import utils

if os.getenv("URL_SEED") is None:
    raise ValueError("URL_SEED environment variable not set.")


def categories() -> list[ScrapedCategory]:
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

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, slow_mo=500)
        page = browser.new_page()
        page.context.add_cookies(cookies)
        page.goto(os.getenv("URL_SEED", "default_invalid_url"))
        page.wait_for_load_state("load")

        categories_ = page.locator("css=span.category-menu__header").all()
        logger.debug("Found %s categories", len(categories_))
        data_by_category = []
        product_count = 0
        for category in categories_:
            category.click()
            category_name = category.inner_text()
            page.wait_for_load_state("load")
            page.screenshot(path="screenshot_10_category.png")
            subcategories = page.locator("css=li.open").locator("li").all()
            logger.debug("Found %s subcategories", len(subcategories))
            for subcategory in subcategories:
                subcategory.click()
                subcategory_name = subcategory.inner_text()

                is_last_subcategory = subcategory == subcategories[-1]
                _wait_until_load(page, last_category=is_last_subcategory)

                page.screenshot(path="screenshot_30_subcategory.png")

                buttons_products = page.locator("css=button.product-cell__content-link").all()

                last_try_time = 0.0
                min_time_between_clicks_seconds = 0.05
                for button in buttons_products:
                    product_count += 1
                    # if product_count >= 100:
                    #     product_count = 0
                    #     logger.debug("Waiting every 200 products to avoid blocking")
                    #     page.wait_for_timeout(61 * 1000)
                    #     time.sleep(61)

                    # current_time = time.time()
                    # if current_time - last_try_time < min_time_between_clicks_seconds:
                    #     # Wait for the remaining time
                    #     time_to_wait_ms = (
                    #         min_time_between_clicks_seconds - (current_time - last_try_time) * 1000
                    #     ) * 1000
                    #     logger.debug("Waiting %s ms between clicks", time_to_wait_ms)
                    #     page.wait_for_timeout(time_to_wait_ms)

                    try:
                        button.click()
                        page.wait_for_load_state("load")
                        page.wait_for_url("**/product/**")
                        product_id = utils.extract_product_id_from_url(page.url)
                        logger.info("Official product ID: %s", product_id)
                        page.locator("css=button.modal-content__close").click()
                    except TimeoutError:
                        page.screenshot(path="screenshot_31_product_TimeoutError.png")
                        # time.sleep(61)
                        page.wait_for_timeout(72 * 1000)
                        logger.error("TimeoutError")
                        breakpoint()
                        # raise ValueError("TimeoutError")

                html_content = page.content()
                scraped_category = ScrapedCategory(
                    category_name=category_name,
                    subcategory_name=subcategory_name,
                    html=html_content,
                )
                data_by_category.append(scraped_category)
                logger.info("Scraped category: %s - %s", category_name, subcategory_name)

        browser.close()

    return data_by_category


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
