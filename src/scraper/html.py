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

        categories = page.locator("css=span.category-menu__header").all()
        data_by_category = []
        for category in categories:
            category.click()
            category_name = category.inner_text()
            page.wait_for_load_state("load")
            subcategories = page.locator("css=li.open").locator("li").all()
            for subcategory in subcategories:
                subcategory.click()
                subcategory_name = subcategory.inner_text()

                is_last_subcategory = subcategory == subcategories[-1]
                _wait_until_load(page, last_category=is_last_subcategory)

                # page.screenshot(path=f"tests/fixtures/{category_name}_{subcategory_name}.png")
                html_content = page.content()
                scraped_category = ScrapedCategory(
                    category_name=category_name,
                    subcategory_name=subcategory_name,
                    html=html_content,
                )
                data_by_category.append(scraped_category)
                logger.info(f"Scraped category: {category_name} - {subcategory_name}")

        browser.close()

    return data_by_category


def _wait_until_load(page, last_category: bool = False) -> None:
    # Waiting logic
    page.wait_for_load_state("load")
    page.wait_for_load_state("networkidle")
    tries = 0
    while tries < 5:
        tries += 1
        try:
            # This is the last element to load ("Next subcategory" button)
            page.query_selector("button.category-detail__next-subcategory").wait_for_element_state(
                "stable", timeout=3000
            )
            break
        except TimeoutError:
            if not last_category:
                raise TimeoutError(f"Subcategory did not load")
        except AttributeError:
            logger.info("Waiting for next subcategory to load")
            page.wait_for_timeout(1000)
