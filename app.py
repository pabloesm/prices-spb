import argparse
import asyncio

from src import scan_products, store_products_remote
from src.config.logger import setup_logger
from src.config.settings import settings

logger = setup_logger(settings.logging_level)


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
        choices=[
            "first_half",
            "second_half",
            "first_quarter",
            "second_quarter",
            "third_quarter",
            "fourth_quarter",
        ],
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
