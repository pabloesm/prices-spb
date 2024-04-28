import pickle

from src import db
from src.config.logger import logger
from src.models import ScannedProduct
from src.scraper import get_product_basic

N_TRIES = 80


def get_scanned_products() -> list[ScannedProduct]:
    products: list[ScannedProduct] = []
    cat = ""
    subcat = ""
    tries = 0
    while tries < N_TRIES:
        logger.debug(
            "Current products IDs. Size:%s; cat: %s subcat: %s", len(products), cat, subcat
        )
        products, cat, subcat = get_product_basic.compute(products, cat, subcat)
        tries += 1
        if cat == "" and subcat == "":
            break

    if N_TRIES == tries:
        logger.error("Reached maximum number of tries")
        raise ValueError("Reached maximum number of tries when trying to get product IDs")

    return products


def main():
    products = get_scanned_products()
    with open("scanned_prodcts.pkl", "wb") as f:
        pickle.dump(products, f)

    products_ids = [product.product_id for product in products]

    stored_products_ids = db.get_all_scanned_product_ids()
    num_products = db.count_scanned_products()
    logger.info("Number of stored products: %s", num_products)

    new_products_ids = set(products_ids) - set(stored_products_ids)
    new_products = [product for product in products if product.product_id in new_products_ids]
    logger.info("Number of new products: %s", len(new_products))
    for new_product in new_products:
        logger.debug("Parsing product: %s", new_product.product_id)
        db.insert_scanned_product(new_product)
