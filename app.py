import asyncio
import sys

from src import scan_products, store_products_remote
from src.config.environment_vars import EnvironmentVars
from src.config.logger import setup_logger

logger = setup_logger(EnvironmentVars().get_logging_level())


def main():
    if len(sys.argv) != 2:
        print("Usage: python app.py <option>")
        return

    option = sys.argv[1]

    if option == "scan":
        scan_products.main()
    elif option == "store":
        asyncio.run(store_products_remote.main())
    else:
        print("Invalid option. Please use 'scan' or 'store'.")


if __name__ == "__main__":
    main()
