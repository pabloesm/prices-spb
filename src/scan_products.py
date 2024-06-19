import pickle
from pathlib import Path

from src import db
from src.config.logger import logger
from src.models import ScannedProduct
from src.scraper import get_product_basic
from src.scraper.get_product_basic import ProductsState
from src.vpn import Vpn

N_TRIES = 120

FOLDER_PATH: Path | None = Path("vpn_configs")


def get_scanned_products() -> list[ScannedProduct]:
    products_state = ProductsState()
    tries = 0
    vpn = Vpn(configs_folder=FOLDER_PATH)
    try:
        while tries < N_TRIES:
            logger.debug("Try number: %s", tries)
            vpn.rotate()
            products_state = get_product_basic.compute(products_state)
            tries += 1
            if products_state.is_finished:
                break
    finally:
        vpn.kill()

    if N_TRIES == tries:
        logger.error("Reached maximum number of tries")
        raise ValueError("Reached maximum number of tries when trying to get product IDs")

    return products_state.get_scanned_products()


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
        db.insert_scanned_product(new_product)
