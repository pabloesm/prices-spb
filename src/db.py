import os

import psycopg2
from psycopg2 import sql

from src.config.logger import logger
from src.models import HtmlCategoryDB, PriceDB, ProductDB

if os.getenv("DATABASE_NEON_URL") is None:
    raise ValueError("DATABASE_NEON_URL environment variable not set.")


def insert_html_category(html_category: HtmlCategoryDB) -> int:
    conn = psycopg2.connect(os.getenv("DATABASE_NEON_URL"))
    cursor = conn.cursor()

    # Return existing ID if hash_value already exists
    cursor.execute(
        "SELECT id FROM html_category WHERE hash_value = %s", (html_category.hash_value,)
    )
    existing_id = cursor.fetchone()
    if existing_id:
        return int(existing_id[0])

    # If hash_value doesn't exist, perform insert
    insert_query = sql.SQL(
        """
        INSERT INTO html_category (html, category_name, subcategory_name, hash_value)
        VALUES (%s, %s, %s, %s)
        RETURNING id
    """
    )
    cursor.execute(
        insert_query,
        (
            html_category.html,
            html_category.category_name,
            html_category.subcategory_name,
            html_category.hash_value,
        ),
    )

    result = cursor.fetchone()
    if not result:
        raise ValueError("No ID returned from `html_category` table")
    new_id = result[0]

    conn.commit()
    cursor.close()
    conn.close()

    logger.info(
        "Inserted HTML category: %s - %s",
        html_category.category_name,
        html_category.subcategory_name,
    )

    return int(new_id)


def insert_product(product: ProductDB) -> int:
    conn = psycopg2.connect(os.getenv("DATABASE_NEON_URL"))
    cursor = conn.cursor()

    # Check if the product already exists based on multiple fields
    cursor.execute(
        """
        SELECT id 
        FROM product 
        WHERE name = %s 
        AND unit = %s 
        AND image_url = %s 
        AND category_name = %s 
        AND subcategory_name = %s 
        AND section_name = %s
    """,
        (
            product.name,
            product.unit,
            product.image_url,
            product.category_name,
            product.subcategory_name,
            product.section_name,
        ),
    )

    existing_id = cursor.fetchone()
    if existing_id:
        return int(existing_id[0])

    # If product doesn't exist, perform insert
    insert_query = sql.SQL(
        """
        INSERT INTO product (name, unit, image_url, category_name, subcategory_name, section_name)
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING id
    """
    )
    cursor.execute(
        insert_query,
        (
            product.name,
            product.unit,
            product.image_url,
            product.category_name,
            product.subcategory_name,
            product.section_name,
        ),
    )

    result = cursor.fetchone()
    if not result:
        raise ValueError("No ID returned from `product` table")
    new_id = result[0]

    conn.commit()
    cursor.close()
    conn.close()

    logger.info("Inserted product: %s (%s)", product.name, product.subcategory_name)

    return int(new_id)


def insert_price(price: PriceDB) -> int:
    conn = psycopg2.connect(os.getenv("DATABASE_NEON_URL"))
    cursor = conn.cursor()

    # Check if the price already exists based on multiple fields
    cursor.execute(
        """
        SELECT id 
        FROM price 
        WHERE price = %s 
        AND (previous_price = %s OR (previous_price IS NULL AND %s IS NULL))
        AND currency = %s 
        AND price_quantity = %s 
        AND html_category_id = %s 
        AND product_id = %s
    """,
        (
            price.price,
            price.previous_price,
            price.previous_price,
            price.currency,
            price.price_quantity,
            price.html_category_id,
            price.product_id,
        ),
    )

    existing_id = cursor.fetchone()
    if existing_id:
        return int(existing_id[0])

    # If price doesn't exist, perform insert
    insert_query = sql.SQL(
        """
        INSERT INTO price (
            price, 
            previous_price, 
            currency, 
            price_quantity, 
            html_category_id, 
            product_id
        )
        VALUES (
            %s, 
            %s, 
            %s, 
            %s, 
            %s, 
            %s
        )
        RETURNING id
        """
    )
    cursor.execute(
        insert_query,
        (
            price.price,
            price.previous_price,
            price.currency,
            price.price_quantity,
            price.html_category_id,
            price.product_id,
        ),
    )

    result = cursor.fetchone()
    if not result:
        raise ValueError("No ID returned from `price` table")
    new_id = result[0]

    conn.commit()
    cursor.close()
    conn.close()

    logger.info(
        "Inserted price: %s (prod. id %s, html id %s)",
        price.price,
        price.product_id,
        price.html_category_id,
    )

    return int(new_id)


def count_elements_in_table(table_name: str) -> int:
    """
    Count the number of elements in a PostgreSQL table.

    Args:
        table_name (str): The name of the table.

    Returns:
        Union[int, None]: The count of elements in the table, or None if an error occurs.
    """
    conn = psycopg2.connect(os.getenv("DATABASE_NEON_URL"))
    cursor = conn.cursor()

    query = f"SELECT COUNT(*) FROM {table_name};"

    cursor.execute(query)

    # count = cursor.fetchone()[0]
    result = cursor.fetchone()
    if not result:
        raise ValueError(f"No count returned from table `{table_name}`.")
    count = result[0]

    # Close the cursor and connection
    cursor.close()
    conn.close()

    return int(count)
