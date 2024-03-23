import os

import psycopg2

if os.getenv("DATABASE_NEON_URL") is None:
    raise ValueError("DATABASE_NEON_URL environment variable not set.")


def drop_tables() -> None:
    conn = psycopg2.connect(os.getenv("DATABASE_NEON_URL"))
    cur = conn.cursor()

    cur.execute(
        """
        DROP TABLE IF EXISTS html_category CASCADE;
        DROP TABLE IF EXISTS product CASCADE;
        DROP TABLE IF EXISTS price CASCADE;
        """
    )

    conn.commit()

    cur.close()
    conn.close()


def create_tables() -> None:
    conn = psycopg2.connect(os.getenv("DATABASE_NEON_URL"))

    # Create a cursor object using the connection
    cur = conn.cursor()

    # Define SQL statements for table creation
    create_table_queries = [
        """
        CREATE TABLE html_category (
            id SERIAL PRIMARY KEY,
            html TEXT NOT NULL,
            category_name VARCHAR(255) NOT NULL,
            subcategory_name VARCHAR(255) NOT NULL,
            hash_value  VARCHAR(64) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE product (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            unit VARCHAR(50) NOT NULL,
            image_url TEXT NOT NULL,
            category_name VARCHAR(255) NOT NULL,
            subcategory_name VARCHAR(255) NOT NULL,
            section_name VARCHAR(255) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE price (
            id SERIAL PRIMARY KEY,
            price NUMERIC(12, 2) NOT NULL,
            previous_price NUMERIC(12, 2),
            currency VARCHAR(10) NOT NULL,
            price_quantity VARCHAR(255) NOT NULL,
            html_category_id INT REFERENCES html_category(id) ON DELETE CASCADE,
            product_id INT REFERENCES product(id) ON DELETE CASCADE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
    ]

    # Execute each SQL statement for table creation
    for query in create_table_queries:
        cur.execute(query)
        print("Table created successfully")

    # Commit the transaction and close the cursor and connection
    conn.commit()
    cur.close()
    conn.close()


if __name__ == "__main__":
    drop_tables()
    create_tables()
