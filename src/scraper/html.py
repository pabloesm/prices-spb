import os

from playwright._impl._api_structures import SetCookieParam
from playwright.sync_api import sync_playwright

from src.config.logger import logger
from src.models import ScrapedCategory

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
            logger.info("Timeout for `%s`", selector)
            if not last_category:
                raise TimeoutError(f"`{selector}` did not load") from exc
        except AttributeError:
            logger.info("Waiting for `%s`", selector)
            page.wait_for_timeout(1000)
