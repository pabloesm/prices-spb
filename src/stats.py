from src.config.logger import logger
from src.db import count_elements_in_table

tables = ["html_category", "product", "price"]


def table_count():
    for table in tables:
        count = count_elements_in_table(table)
        logger.info("Table %s has %s elements", table, count)
