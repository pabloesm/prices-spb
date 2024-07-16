import argparse
import asyncio

from src import scan_products, store_products_remote
from src.config.environment_vars import EnvironmentVars
from src.config.logger import setup_logger

logger = setup_logger(EnvironmentVars().get_logging_level())


def main():
    parser = argparse.ArgumentParser(description="Scan and store products.")

    # Define the arguments
    parser.add_argument(
        "--operation",
        "-op",
        type=str,
        choices=["scan", "store"],
        required=True,
        help="Operation to perform: scan or store",
    )
    parser.add_argument(
        "--partial",
        "-p",
        type=str,
        choices=["first_half", "second_half"],
        required=False,
        help="Scan/store only a part of the products",
    )

    # Parse the arguments
    args = parser.parse_args()

    operation = args.operation
    partial = args.partial

    if operation == "scan":
        scan_products.main(partial)
    elif operation == "store":
        asyncio.run(store_products_remote.main(partial))
    else:
        print("Invalid option. Please use 'scan' or 'store'.")


if __name__ == "__main__":
    main()
