from contextlib import contextmanager

import psycopg2.extensions
from psycopg2 import sql
from psycopg2.pool import SimpleConnectionPool

from src.config.logger import logger
from src.config.settings import settings
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

# NOTE: product ids are floats by schema (e.g. "64.1"); other table ids are ints.

# Create a connection pool
connection_pool = SimpleConnectionPool(
    minconn=1,
    maxconn=20,
    dsn=settings.database_neon_url,
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


@contextmanager
def cursor():
    """Yield a cursor on a healthy pooled connection.

    Commits on clean exit, rolls back on error (so a failed transaction never returns
    to the pool in an aborted state), and always returns the connection to the pool.
    """
    conn = get_valid_connection()
    cur = conn.cursor()
    try:
        yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        connection_pool.putconn(conn)


def _fetch_id(cur, table: str):
    """Return the id from the last RETURNING/SELECT row, or raise if none came back."""
    row = cur.fetchone()
    if not row:
        raise ValueError(f"No ID returned from `{table}` table")
    return row[0]


def insert_product(product: Product) -> float:
    with cursor() as cur:
        cur.execute("SELECT id FROM product WHERE id = %s", (product.id,))
        existing_id = cur.fetchone()
        if existing_id:
            return float(existing_id[0])

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
        cur.execute(
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
        new_id = _fetch_id(cur, "product")
        logger.info("Inserted product: %s", product.id)
        return float(new_id)


def insert_badge(badge: Badge) -> int:
    with cursor() as cur:
        cur.execute(
            "SELECT id FROM badge WHERE is_water = %s AND requires_age_check = %s",
            (badge.is_water, badge.requires_age_check),
        )
        existing_id = cur.fetchone()
        if existing_id:
            return int(existing_id[0])

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
        cur.execute(insert_query, (badge.is_water, badge.requires_age_check))
        new_id = _fetch_id(cur, "badge")
        logger.info("Inserted badge: %s", new_id)
        return int(new_id)


def insert_supplier(supplier: Supplier) -> int:
    with cursor() as cur:
        cur.execute("SELECT id FROM supplier WHERE name = %s", (supplier.name,))
        existing_id = cur.fetchone()
        if existing_id:
            return int(existing_id[0])

        insert_query = sql.SQL(
            """
            INSERT INTO supplier (
                name
            )
            VALUES (%s)
            RETURNING id
        """
        )
        cur.execute(insert_query, (supplier.name,))
        new_id = _fetch_id(cur, "supplier")
        logger.info("Inserted supplier: %s", new_id)
        return int(new_id)


def insert_photo(photo: Photo) -> int:
    with cursor() as cur:
        cur.execute(
            "SELECT id FROM photo WHERE product_id = %s AND zoom = %s",
            (photo.product_id, photo.zoom),
        )
        existing_id = cur.fetchone()
        if existing_id:
            return int(existing_id[0])

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
        cur.execute(
            insert_query,
            (
                photo.product_id,
                photo.zoom,
                photo.regular,
                photo.thumbnail,
                photo.perspective,
            ),
        )
        new_id = _fetch_id(cur, "photo")
        logger.info("Inserted photo: %s", new_id)
        return int(new_id)


def insert_category(category: Category) -> int:
    with cursor() as cur:
        cur.execute("SELECT id FROM category WHERE id = %s", (category.id,))
        existing_id = cur.fetchone()
        if existing_id:
            return int(existing_id[0])

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
        cur.execute(
            insert_query,
            (category.id, category.name, category.level, category.order_value),
        )
        new_id = _fetch_id(cur, "category")
        logger.info("Inserted category: %s", new_id)
        return int(new_id)


def insert_product_category(product_category: ProductCategory) -> None:
    with cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) FROM product_category WHERE product_id = %s AND category_id = %s",
            (product_category.product_id, product_category.category_id),
        )
        count = cur.fetchone()
        if count and count[0] > 0:
            logger.info(
                "Product category already exists: %s, %s",
                product_category.product_id,
                product_category.category_id,
            )
            return

        insert_query = sql.SQL(
            """
            INSERT INTO product_category (
                product_id,
                category_id
            )
            VALUES (%s, %s)
        """
        )
        cur.execute(
            insert_query,
            (product_category.product_id, product_category.category_id),
        )
        logger.info(
            "Inserted product category: %s, %s",
            product_category.product_id,
            product_category.category_id,
        )


def insert_price_instruction(instruction: PriceInstruction) -> int:
    with cursor() as cur:
        check_query = sql.SQL(
            """
            SELECT id
            FROM price_instruction
            WHERE product_id = %s
            AND unit_price = %s
            AND bulk_price = %s
        """
        )
        cur.execute(
            check_query,
            (instruction.product_id, instruction.unit_price, instruction.bulk_price),
        )
        existing_id = cur.fetchone()
        if existing_id:
            return int(existing_id[0])

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
        cur.execute(
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
        new_id = _fetch_id(cur, "price_instruction")
        logger.info("Inserted price instruction: %s", new_id)
        return int(new_id)


def insert_nutrition_information(nutrition_info: NutritionInformation) -> int:
    with cursor() as cur:
        cur.execute(
            "SELECT id FROM nutrition_information WHERE product_id = %s",
            (nutrition_info.product_id,),
        )
        existing_id = cur.fetchone()
        if existing_id:
            return int(existing_id[0])

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
        cur.execute(
            insert_query,
            (
                nutrition_info.product_id,
                nutrition_info.allergens,
                nutrition_info.ingredients,
            ),
        )
        new_id = _fetch_id(cur, "nutrition_information")
        logger.info("Inserted nutrition information: %s", new_id)
        return int(new_id)


def insert_scanned_product(scanned_product: ScannedProduct) -> int:
    with cursor() as cur:
        cur.execute(
            "SELECT product_id FROM scanned_products WHERE product_id = %s",
            (scanned_product.product_id,),
        )
        existing_id = cur.fetchone()
        if existing_id:
            return int(existing_id[0])

        insert_query = sql.SQL(
            """
            INSERT INTO scanned_products (product_id, category_name, subcategory_name, scanned_at)
            VALUES (%s, %s, %s, %s)
            RETURNING product_id
        """
        )
        cur.execute(
            insert_query,
            (
                scanned_product.product_id,
                scanned_product.category_name,
                scanned_product.subcategory_name,
                scanned_product.scanned_at,
            ),
        )
        new_id = _fetch_id(cur, "scanned_products")
        logger.info(
            "Inserted scanned product: %s (cat: %s, subcat: %s)",
            scanned_product.product_id,
            scanned_product.category_name,
            scanned_product.subcategory_name,
        )
        return int(new_id)


def get_all_scanned_product_ids() -> list[float]:
    with cursor() as cur:
        cur.execute("SELECT product_id FROM scanned_products")
        return [float(row[0]) for row in cur.fetchall()]


def get_scanned_non_stored_product_ids() -> list[float]:
    with cursor() as cur:
        cur.execute(
            """
            SELECT product_id
            FROM scanned_products
            WHERE product_id NOT IN (
                SELECT id
                FROM product
            )
            """
        )
        return [float(row[0]) for row in cur.fetchall()]


def count_scanned_products() -> int:
    with cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM scanned_products")
        result = cur.fetchone()
        return int(result[0]) if result is not None else 0


def insert_html_category(html_category: HtmlCategoryDB) -> int:
    with cursor() as cur:
        cur.execute(
            "SELECT id FROM html_category WHERE hash_value = %s", (html_category.hash_value,)
        )
        existing_id = cur.fetchone()
        if existing_id:
            return int(existing_id[0])

        insert_query = sql.SQL(
            """
            INSERT INTO html_category (html, category_name, subcategory_name, hash_value)
            VALUES (%s, %s, %s, %s)
            RETURNING id
        """
        )
        cur.execute(
            insert_query,
            (
                html_category.html,
                html_category.category_name,
                html_category.subcategory_name,
                html_category.hash_value,
            ),
        )
        new_id = _fetch_id(cur, "html_category")
        logger.info(
            "Inserted HTML category: %s - %s",
            html_category.category_name,
            html_category.subcategory_name,
        )
        return int(new_id)


def count_elements_in_table(table_name: str) -> int:
    """Count the number of rows in a table."""
    with cursor() as cur:
        cur.execute(sql.SQL("SELECT COUNT(*) FROM {}").format(sql.Identifier(table_name)))
        result = cur.fetchone()
        if not result:
            raise ValueError(f"No count returned from table `{table_name}`.")
        return int(result[0])
