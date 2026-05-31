import random
import socket
import subprocess
import time
from pathlib import Path
from threading import Thread

import httpx

from src.config.logger import logger
from src.config.settings import settings


def extract_hostname_from_ovpn(config_file_path: str | Path) -> str | None:
    """Extract the hostname from the 'remote' directive of an .ovpn file."""
    with open(config_file_path, encoding="utf-8") as f:
        for line in f:
            if line.strip().startswith("remote "):
                parts = line.strip().split()
                if len(parts) >= 2:
                    return parts[1]
    return None


def check_hostname_resolution(hostname: str) -> bool:
    """Check if a hostname can be resolved via DNS."""
    try:
        socket.getaddrinfo(hostname, None)
        return True
    except (socket.gaierror, OSError):
        return False


class Vpn:
    """Class to manage VPN connections and rotations."""

    def __init__(
        self,
        config_file_path: str | Path | None = None,
        configs_folder: str | Path | None = None,
        check_interval: int = 60,
    ):
        self._disabled = False
        if not config_file_path and not configs_folder:
            self._disabled = True
            logger.warning("VPN connection is disabled. No configuration provided.")
            return

        self.config_file_path = config_file_path
        self.configs_folder = configs_folder
        self.vpn_process = None
        self.host_ip = self.get_public_ip()

        self.rotate_index = 0
        if self.configs_folder:
            self.config_file_paths = get_ovpn_files(self.configs_folder)
            self.config_file_path = self.config_file_paths[self.rotate_index]

        self.check_interval = check_interval
        self.start_periodic_check()

    def connect(self) -> bool:
        if self._disabled:
            logger.warning("VPN connection is disabled. No configuration provided.")
            return False

        if not self.config_file_path:
            return False

        hostname = extract_hostname_from_ovpn(self.config_file_path)
        if hostname and not check_hostname_resolution(hostname):
            logger.warning(
                "DNS resolution failed for %s (config: %s). Skipping.",
                hostname,
                self.config_file_path,
            )
            return False

        self.vpn_process = connect_to_vpn(self.config_file_path)
        public_ip = self.get_public_ip()
        if public_ip and public_ip != self.host_ip:
            logger.info("Connected to VPN with public IP: %s", public_ip)
            return True

        return False

    def rotate(self):
        if self._disabled:
            logger.warning("VPN connection is disabled. No configuration provided.")
            return

        self.rotate_index = (self.rotate_index + 1) % len(self.config_file_paths)
        self.config_file_path = self.config_file_paths[self.rotate_index]
        logger.info("Rotating VPN configuration to: %s", self.config_file_path)

        current_ip = self.get_public_ip()
        is_already_connected = current_ip != self.host_ip
        if is_already_connected:
            self.kill()

        tries = 0
        while tries < 10:
            self.connect()
            new_ip = self.get_public_ip()
            if new_ip and new_ip != current_ip:
                logger.info("Rotated VPN configuration to: %s", self.config_file_path)
                return True
            logger.warning("IP address %s not updated after rotation. Try %s.", new_ip, tries)
            self.kill()
            self.rotate_index = (self.rotate_index + 1) % len(self.config_file_paths)
            self.config_file_path = self.config_file_paths[self.rotate_index]
            logger.info("Rotating VPN configuration to: %s", self.config_file_path)
            tries += 1

        raise ValueError("Failed to rotate VPN configuration")

    def get_public_ip(self):
        return get_public_ip()

    def kill(self):
        if self._disabled:
            logger.warning("VPN connection is disabled. No configuration provided.")
            return

        kill_vpn()

    def check_internet_connection(self):
        """Check if the internet connection is active."""
        try:
            with httpx.Client() as client:
                response = client.get("https://www.google.com", timeout=5)
                logger.debug("Internet connection confirmed.")
                return response.status_code == 200
        except httpx.RequestError:
            return False

    def periodic_check(self):
        """Periodically check the internet connection and rotate VPN if disconnected."""
        while True:
            if not self.check_internet_connection():
                logger.warning("Internet connection lost. Rotating VPN.")
                self.rotate()
            time.sleep(self.check_interval)

    def start_periodic_check(self):
        """Start the periodic internet connection check in a separate thread."""
        if not self._disabled:
            thread = Thread(target=self.periodic_check, daemon=True)
            thread.start()


def connect_to_vpn(config_file_path):
    try:
        username = settings.vpn_username
        password = settings.vpn_password

        if not username or not password:
            raise ValueError("VPN_USERNAME or VPN_PASSWORD environment variables not set")

        # Command to start OpenVPN with the provided configuration file and authentication
        command = ["openvpn", "--config", config_file_path, "--auth-user-pass", "credentials.txt"]

        # Create a temporary credentials file with username and password
        credentials_file = Path("credentials.txt")
        credentials_file.write_text(f"{username}\n{password}", encoding="utf-8")

        # Execute the command in background using Popen and redirect output for monitoring
        vpn_process = subprocess.Popen(
            command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )

        # Monitor the process output to detect successful connection
        start_time = time.time()
        timeout = 30  # Set a timeout for connection attempt
        connected = False

        while True:
            # Check if process has output a line
            if not vpn_process.stdout:
                break

            output = vpn_process.stdout.readline()
            if output:
                logger.debug("openvpn: %s", output.strip())

                if "Initialization Sequence Completed" in output:
                    connected = True
                    break

            if vpn_process.poll() is not None:
                raise subprocess.CalledProcessError(vpn_process.returncode, command)

            if time.time() - start_time > timeout:
                raise TimeoutError("Timed out waiting for VPN connection")

        return vpn_process if connected else None

    except (subprocess.CalledProcessError, TimeoutError, ValueError) as e:
        logger.error("Error connecting to VPN: %s", e)
        return None

    finally:
        # Remove the temporary credentials file
        if credentials_file.exists():
            credentials_file.unlink()


def get_public_ip():
    try:
        with httpx.Client() as client:
            response = client.get("https://api.ipify.org")
            if response.status_code == 200:
                return response.text
            else:
                logger.warning("Failed to retrieve public IP: %s", response.status_code)
    except httpx.RequestError as e:
        logger.warning("Error retrieving public IP: %s", e)


def kill_vpn():
    # Execute command to kill all openvpn processes
    command = ["killall", "openvpn"]
    _ = subprocess.Popen(command)
    time.sleep(1)


def get_ovpn_files(folder_path: str | Path) -> list[Path]:
    folder_path = Path(folder_path)
    ovpn_files = list(folder_path.glob("*.ovpn"))
    random.shuffle(ovpn_files)
    return ovpn_files
