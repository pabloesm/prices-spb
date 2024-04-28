import os

import psycopg2

if os.getenv("DATABASE_NEON_URL") is None:
    raise ValueError("DATABASE_NEON_URL environment variable not set.")


def create_tables_from_script(script_file: str) -> None:
    conn = psycopg2.connect(os.getenv("DATABASE_NEON_URL"))
    cur = conn.cursor()

    with open(script_file, "r", encoding="utf-8") as f:
        sql_script = f.read()

    # Remove SQL comments
    sql_script = "\n".join(
        line for line in sql_script.splitlines() if not line.strip().startswith("--")
    )

    # Split script into individual SQL statements
    sql_commands = sql_script.split(";")

    for command in sql_commands:
        # Skip empty commands
        if not command.strip():
            continue
        try:
            cur.execute(command)
            print(f"Command executed successfully: {command}")
        except Exception as e:
            print(f"Error executing SQL: {e}")
            print(f"Command causing error: {command}")

    # Commit and close connection
    conn.commit()
    cur.close()
    conn.close()


if __name__ == "__main__":
    create_tables_from_script("scripts/create_db.sql")
