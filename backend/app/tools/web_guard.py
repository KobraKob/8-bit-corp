import ipaddress
import re
import socket
from urllib.parse import urlparse, urljoin, urlencode
import httpx

from app.core.errors import SecurityViolationError


def is_private_or_loopback_host(hostname: str) -> bool:
    """Check if a hostname resolves to a private, loopback, or reserved IP address."""
    if not hostname:
        return True

    # Immediate string checks
    lower = hostname.lower()
    if lower in ("localhost", "127.0.0.1", "0.0.0.0", "::1", "local"):
        return True

    try:
        ip = ipaddress.ip_address(hostname)
        return ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved
    except ValueError:
        pass

    try:
        # Check every resolved address family. Treat non-global ranges as unsafe.
        resolved_ips = socket.getaddrinfo(hostname, None)
        if not resolved_ips:
            return True
        for family, socktype, proto, canonname, sockaddr in resolved_ips:
            ip = ipaddress.ip_address(sockaddr[0])
            if not ip.is_global:
                return True
    except Exception:
        # If unresolvable or error, treat as unsafe.
        return True

    return False


def validate_url_safe(url: str) -> None:
    """Validate that the URL is HTTP/HTTPS and not pointing to private/internal IPs."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise SecurityViolationError(f"Disallowed URL scheme: '{parsed.scheme}'. Only http and https allowed.")

    if not parsed.hostname:
        raise SecurityViolationError(f"Invalid URL host in '{url}'")

    if is_private_or_loopback_host(parsed.hostname):
        raise SecurityViolationError(f"Access to private or local network is blocked (SSRF guard): '{parsed.hostname}'")


async def safe_fetch_url(url: str, max_bytes: int = 50000, timeout_sec: float = 10.0) -> str:
    """Safely fetch web page text with SSRF validation, size cap, and timeout."""
    current_url = url
    async with httpx.AsyncClient(timeout=timeout_sec, follow_redirects=False, trust_env=False) as client:
        for _ in range(6):
            validate_url_safe(current_url)
            response = await client.get(current_url)
            if response.is_redirect:
                location = response.headers.get("location")
                if not location:
                    raise SecurityViolationError("Redirect response did not include a location.")
                current_url = urljoin(current_url, location)
                continue
            response.raise_for_status()
            page_text = response.text[:max_bytes]
            clean_text = re.sub(r"<[^>]+>", " ", page_text)
            return re.sub(r"\s+", " ", clean_text).strip()

    raise SecurityViolationError("Too many redirects while fetching the requested URL.")


async def search_web(query: str, max_results: int = 5) -> list[dict]:
    """Execute search query. Uses DuckDuckGo HTML or returns structured mockup if offline."""
    # Free search simulation or DuckDuckGo if reachable
    try:
        url = "https://html.duckduckgo.com/html/?" + urlencode({"q": query})
        validate_url_safe(url)
        async with httpx.AsyncClient(timeout=5.0, follow_redirects=False, trust_env=False) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                # Basic scrape
                titles = re.findall(r'<a class="result__snippet[^>]*>(.*?)</a>', resp.text)
                return [{"title": f"Result {i+1}", "snippet": re.sub(r"<[^>]+>", "", t).strip()} for i, t in enumerate(titles[:max_results])]
    except Exception:
        pass

    # Never fabricate search results when the provider is unavailable.
    return []
