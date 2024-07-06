import os

import psycopg2.extensions
from psycopg2 import sql
from psycopg2.pool import SimpleConnectionPool

from src.config.logger import logger
from src.models import (
    Badge,
    Category,
    HtmlCategoryDB,
    NutritionInformation,
    Photo,
    PriceInstruction,
    Product,
    ProductCategory,
    ScannedProduct,
    Supplier,
)

if os.getenv("DATABASE_NEON_URL") is None:
    raise ValueError("DATABASE_NEON_URL environment variable not set.")

# Create a connection pool
connection_pool = SimpleConnectionPool(
    minconn=1,
    maxconn=20,
    dsn=os.getenv("DATABASE_NEON_URL"),
)


def is_connection_valid(connection: psycopg2.extensions.connection) -> bool:
    try:
        with connection.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
            return True
    except (psycopg2.OperationalError, psycopg2.DatabaseError):
        return False


def get_valid_connection() -> psycopg2.extensions.connection:
    conn = connection_pool.getconn()
    while not is_connection_valid(conn):
        connection_pool.putconn(conn)
        conn = connection_pool.getconn()
    return conn  # type: ignore


def insert_product(product: Product) -> float:
    conn = get_valid_connection()
    cursor = conn.cursor()

    try:
        # Check if the product already exists
        cursor.execute("SELECT id FROM product WHERE id = %s", (product.id,))

        existing_id = cursor.fetchone()
        if existing_id:
            return float(existing_id[0])

        # If product doesn't exist, perform insert
        insert_query = sql.SQL(
            """
            INSERT INTO product (
                id,
                ean,
                slug,
                brand,
                limit_value,
                origin,
                packaging,
                published,
                share_url,
                thumbnail,
                display_name,
                unavailable_from,
                is_variable_weight,
                legal_name,
                description,
                counter_info,
                danger_mentions,
                alcohol_by_volume,
                mandatory_mentions,
                product_variant,
                usage_instructions,
                storage_instructions,
                badge_id,
                supplier_id
            )
            VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 
                %s, %s, %s, %s, %s
            )
            RETURNING id
        """
        )
        cursor.execute(
            insert_query,
            (
                product.id,
                product.ean,
                product.slug,
                product.brand,
                product.limit_value,
                product.origin,
                product.packaging,
                product.published,
                product.share_url,
                product.thumbnail,
                product.display_name,
                product.unavailable_from,
                product.is_variable_weight,
                product.legal_name,
                product.description,
                product.counter_info,
                product.danger_mentions,
                product.alcohol_by_volume,
                product.mandatory_mentions,
                product.product_variant,
                product.usage_instructions,
                product.storage_instructions,
                product.badge_id,
                product.supplier_id,
            ),
        )
        result = cursor.fetchone()
        if not result:
            raise ValueError("No ID returned from `product` table")
        new_id = result[0]
        conn.commit()
        logger.info("Inserted product: %s", product.id)
        return float(new_id)

    finally:
        cursor.close()
        connection_pool.putconn(conn)


def insert_badge(badge: Badge) -> int:
    conn = get_valid_connection()
    cursor = conn.cursor()

    try:
        # Check if the badge already exists for the given is_water and requires_age_check
        cursor.execute(
            "SELECT id FROM badge WHERE is_water = %s AND requires_age_check = %s",
            (badge.is_water, badge.requires_age_check),
        )
        existing_id = cursor.fetchone()

        if existing_id:
            return int(existing_id[0])

        # If badge doesn't exist, perform insert
        insert_query = sql.SQL(
            """
            INSERT INTO badge (
                is_water,
                requires_age_check
            )
            VALUES (%s, %s)
            RETURNING id
        """
        )
        cursor.execute(
            insert_query,
            (
                badge.is_water,
                badge.requires_age_check,
            ),
        )
        result = cursor.fetchone()
        if not result:
            raise ValueError("No ID returned from `badge` table")
        new_id = result[0]
        conn.commit()
        logger.info("Inserted badge: %s", new_id)
        return int(new_id)

    finally:
        cursor.close()
        connection_pool.putconn(conn)


def insert_supplier(supplier: Supplier) -> int:
    conn = get_valid_connection()
    cursor = conn.cursor()

    try:
        # Check if the supplier already exists for the given name
        cursor.execute(
            "SELECT id FROM supplier WHERE name = %s",
            (supplier.name,),
        )
        existing_id = cursor.fetchone()

        if existing_id:
            return int(existing_id[0])

        # If supplier doesn't exist, perform insert
        insert_query = sql.SQL(
            """
            INSERT INTO supplier (
                name
            )
            VALUES (%s)
            RETURNING id
        """
        )
        cursor.execute(
            insert_query,
            (supplier.name,),
        )
        result = cursor.fetchone()
        if not result:
            raise ValueError("No ID returned from `supplier` table")
        new_id = result[0]
        conn.commit()
        logger.info("Inserted supplier: %s", new_id)
        return int(new_id)

    finally:
        cursor.close()
        connection_pool.putconn(conn)


def insert_photo(photo: Photo) -> int:
    conn = get_valid_connection()
    cursor = conn.cursor()

    try:
        # Check if the photo already exists for the given product_id and zoom
        cursor.execute(
            "SELECT id FROM photo WHERE product_id = %s AND zoom = %s",
            (photo.product_id, photo.zoom),
        )
        existing_id = cursor.fetchone()

        if existing_id:
            return int(existing_id[0])

        # If photo doesn't exist, perform insert
        insert_query = sql.SQL(
            """
            INSERT INTO photo (
                product_id,
                zoom,
                regular,
                thumbnail,
                perspective
            )
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
        """
        )
        cursor.execute(
            insert_query,
            (
                photo.product_id,
                photo.zoom,
                photo.regular,
                photo.thumbnail,
                photo.perspective,
            ),
        )
        result = cursor.fetchone()
        if not result:
            raise ValueError("No ID returned from `photo` table")
        new_id = result[0]
        conn.commit()
        logger.info("Inserted photo: %s", new_id)
        return int(new_id)

    finally:
        cursor.close()
        connection_pool.putconn(conn)


def insert_category(category: Category) -> int:
    conn = get_valid_connection()
    cursor = conn.cursor()

    try:
        # Check if the category already exists
        cursor.execute(
            "SELECT id FROM category WHERE id = %s",
            (category.id,),
        )
        existing_id = cursor.fetchone()

        if existing_id:
            return int(existing_id[0])

        # If category doesn't exist, perform insert
        insert_query = sql.SQL(
            """
            INSERT INTO category (
                id,
                name,
                level,
                order_value
            )
            VALUES (%s, %s, %s, %s)
            RETURNING id
        """
        )
        cursor.execute(
            insert_query,
            (
                category.id,
                category.name,
                category.level,
                category.order_value,
            ),
        )
        result = cursor.fetchone()
        if not result:
            raise ValueError("No ID returned from `category` table")
        new_id = result[0]
        conn.commit()
        logger.info("Inserted category: %s", new_id)
        return int(new_id)

    finally:
        cursor.close()
        connection_pool.putconn(conn)


def insert_product_category(product_category: ProductCategory) -> None:
    conn = get_valid_connection()
    cursor = conn.cursor()

    try:
        # Check if the product category already exists
        cursor.execute(
            "SELECT COUNT(*) FROM product_category WHERE product_id = %s AND category_id = %s",
            (product_category.product_id, product_category.category_id),
        )

        count = cursor.fetchone()

        if count and count[0] > 0:
            # If the record already exists, do nothing
            logger.info(
                "Product category already exists: %s, %s",
                product_category.product_id,
                product_category.category_id,
            )
            return

        # If product category doesn't exist, perform insert
        insert_query = sql.SQL(
            """
            INSERT INTO product_category (
                product_id,
                category_id
            )
            VALUES (%s, %s)
        """
        )
        cursor.execute(
            insert_query,
            (
                product_category.product_id,
                product_category.category_id,
            ),
        )
        conn.commit()
        logger.info(
            "Inserted product category: %s, %s",
            product_category.product_id,
            product_category.category_id,
        )

    finally:
        cursor.close()
        connection_pool.putconn(conn)


def insert_price_instruction(instruction: PriceInstruction) -> int:
    conn = get_valid_connection()
    cursor = conn.cursor()

    try:
        # Check if the instruction already exists for the given product_id
        check_query = sql.SQL(
            """
            SELECT id
            FROM price_instruction
            WHERE product_id = %s
            AND unit_price = %s
            AND bulk_price = %s
        """
        )
        cursor.execute(
            check_query,
            (
                instruction.product_id,
                instruction.unit_price,
                instruction.bulk_price,
            ),
        )
        existing_id = cursor.fetchone()
        if existing_id:
            return int(existing_id[0])

        # If instruction doesn't exist, perform insert
        insert_query = sql.SQL(
            """
            INSERT INTO price_instruction (
                product_id, iva, is_new, is_pack, pack_size, unit_name, unit_size,
                bulk_price, unit_price, approx_size, size_format, total_units,
                unit_selector, bunch_selector, drained_weight, selling_method,
                price_decreased, reference_price, min_bunch_amount, reference_format,
                previous_unit_price, increment_bunch_amount
            )
            VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s
            )
            RETURNING id
        """
        )
        cursor.execute(
            insert_query,
            (
                instruction.product_id,
                instruction.iva,
                instruction.is_new,
                instruction.is_pack,
                instruction.pack_size,
                instruction.unit_name,
                instruction.unit_size,
                instruction.bulk_price,
                instruction.unit_price,
                instruction.approx_size,
                instruction.size_format,
                instruction.total_units,
                instruction.unit_selector,
                instruction.bunch_selector,
                instruction.drained_weight,
                instruction.selling_method,
                instruction.price_decreased,
                instruction.reference_price,
                instruction.min_bunch_amount,
                instruction.reference_format,
                instruction.previous_unit_price,
                instruction.increment_bunch_amount,
            ),
        )

        result = cursor.fetchone()
        if not result:
            raise ValueError("No ID returned from `price_instruction` table")
        new_id = result[0]
        conn.commit()
        logger.info("Inserted price instruction: %s", new_id)
        return int(new_id)

    finally:
        cursor.close()
        connection_pool.putconn(conn)


def insert_nutrition_information(nutrition_info: NutritionInformation) -> int:
    conn = get_valid_connection()
    cursor = conn.cursor()

    try:
        # Check if the nutrition information already exists for the given product_id
        cursor.execute(
            "SELECT id FROM nutrition_information WHERE product_id = %s",
            (nutrition_info.product_id,),
        )
        existing_id = cursor.fetchone()

        if existing_id:
            return int(existing_id[0])

        # If nutrition information doesn't exist, perform insert
        insert_query = sql.SQL(
            """
            INSERT INTO nutrition_information (
                product_id,
                allergens,
                ingredients
            )
            VALUES (%s, %s, %s)
            RETURNING id
        """
        )
        cursor.execute(
            insert_query,
            (
                nutrition_info.product_id,
                nutrition_info.allergens,
                nutrition_info.ingredients,
            ),
        )
        result = cursor.fetchone()
        if not result:
            raise ValueError("No ID returned from `nutrition_information` table")
        new_id = result[0]
        conn.commit()
        logger.info("Inserted nutrition information: %s", new_id)
        return int(new_id)

    finally:
        cursor.close()
        connection_pool.putconn(conn)


def insert_scanned_product(scanned_product: ScannedProduct) -> int:
    conn = get_valid_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            "SELECT product_id FROM scanned_products WHERE product_id = %s",
            (scanned_product.product_id,),
        )
        existing_id = cursor.fetchone()
        if existing_id:
            return int(existing_id[0])

        insert_query = sql.SQL(
            """
            INSERT INTO scanned_products (product_id, category_name, subcategory_name, scanned_at)
            VALUES (%s, %s, %s, %s)
            RETURNING product_id
        """
        )
        cursor.execute(
            insert_query,
            (
                scanned_product.product_id,
                scanned_product.category_name,
                scanned_product.subcategory_name,
                scanned_product.scanned_at,
            ),
        )

        result = cursor.fetchone()
        if not result:
            raise ValueError("No ID returned from `scanned_products` table")
        new_id = result[0]

        conn.commit()
        logger.info(
            "Inserted scanned product: %s (cat: %s, subcat: %s)",
            scanned_product.product_id,
            scanned_product.category_name,
            scanned_product.subcategory_name,
        )

        return int(new_id)

    finally:
        cursor.close()
        connection_pool.putconn(conn)


def get_all_scanned_product_ids() -> list[float]:
    conn = get_valid_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT product_id FROM scanned_products")
        product_ids = [float(row[0]) for row in cursor.fetchall()]
        return product_ids

    finally:
        cursor.close()
        connection_pool.putconn(conn)


def get_scanned_non_stored_product_ids() -> list[float]:
    conn = get_valid_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            SELECT product_id
            FROM scanned_products
            WHERE product_id NOT IN (
                SELECT id
                FROM product
            )
            """
        )
        product_ids = [float(row[0]) for row in cursor.fetchall()]
        return product_ids

    finally:
        cursor.close()
        connection_pool.putconn(conn)


def count_scanned_products() -> int:
    conn = get_valid_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT COUNT(*) FROM scanned_products")
        result = cursor.fetchone()
        if result is not None:
            count = int(result[0])
            return count
        else:
            return 0

    finally:
        cursor.close()
        connection_pool.putconn(conn)


def insert_html_category(html_category: HtmlCategoryDB) -> int:
    conn = get_valid_connection()
    cursor = conn.cursor()

    try:
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

        logger.info(
            "Inserted HTML category: %s - %s",
            html_category.category_name,
            html_category.subcategory_name,
        )

        return int(new_id)

    finally:
        cursor.close()
        connection_pool.putconn(conn)


def count_elements_in_table(table_name: str) -> int:
    """
    Count the number of elements in a PostgreSQL table.

    Args:
        table_name (str): The name of the table.

    Returns:
        Union[int, None]: The count of elements in the table, or None if an error occurs.
    """
    conn = get_valid_connection()
    cursor = conn.cursor()

    try:
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

    finally:
        cursor.close()
        connection_pool.putconn(conn)
