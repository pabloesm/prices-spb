from pathlib import Path

import httpx

from src.config.environment_vars import EnvironmentVars
from src.config.logger import setup_logger
from src.vpn import Vpn

logger = setup_logger(EnvironmentVars().get_logging_level())

FOLDER_PATH = Path("vpn_configs")


def main():
    vpn = Vpn(configs_folder=FOLDER_PATH)
    try:
        vpn.rotate()
        with httpx.Client() as client:
            response = client.get("https://httpbin.org/ip")
            logger.info(response.json())
    finally:
        vpn.kill()


if __name__ == "__main__":
    main()
