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
        logger.info("Starting VPN rotation...")
        for i in range(25):
            vpn.rotate()
            with httpx.Client() as client:
                response = client.get("https://httpbin.org/ip")
                logger.info(response.json())
    finally:
        vpn.kill()
        logger.info("VPN killed!")


if __name__ == "__main__":
    main()
