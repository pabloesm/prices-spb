"""Custom httpx transports that resolve `*.mercadona.es` via public DNS.

Works around VPN/system DNS that fails to resolve Mercadona hosts: the host is
resolved through public nameservers and the original hostname is preserved for
TLS SNI. See https://github.com/encode/httpx/issues/1444.
"""

import dns.resolver
from httpx import AsyncHTTPTransport, HTTPTransport, Request, Response

from src.config.logger import logger

PUBLIC_NAMESERVERS = ["8.8.8.8", "8.8.4.4"]
DNS_TIMEOUT_SECONDS = 5.0


class NameSolver:
    def __init__(self) -> None:
        self._resolver = dns.resolver.Resolver()
        self._resolver.nameservers = PUBLIC_NAMESERVERS
        self._resolver.lifetime = DNS_TIMEOUT_SECONDS

    def get(self, name: str) -> str:
        """Return the resolved IP for a Mercadona host, or "" to fall back to system DNS."""
        if name.endswith(".mercadona.es"):
            try:
                answer = self._resolver.resolve(name, "A")
                return str(answer[0])
            except dns.exception.DNSException as exc:
                logger.warning(
                    "DNS resolution failed for %s: %s. Falling back to system DNS.", name, exc
                )
        return ""

    def resolve(self, request: Request) -> Request:
        host = request.url.host
        ip = self.get(host)

        if ip:
            request.extensions["sni_hostname"] = host
            request.url = request.url.copy_with(host=ip)

        return request


class CustomHost(HTTPTransport):
    def __init__(self, solver: NameSolver, *args, **kwargs) -> None:
        self.solver = solver
        super().__init__(*args, **kwargs)

    def handle_request(self, request: Request) -> Response:
        request = self.solver.resolve(request)
        return super().handle_request(request)


class AsyncCustomHost(AsyncHTTPTransport):
    def __init__(self, solver: NameSolver, *args, **kwargs) -> None:
        self.solver = solver
        super().__init__(*args, **kwargs)

    async def handle_async_request(self, request: Request) -> Response:
        request = self.solver.resolve(request)
        return await super().handle_async_request(request)
