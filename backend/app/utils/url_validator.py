"""Validate that a user-supplied job posting URL is suitable for retrieval."""

from __future__ import annotations

import ipaddress
from urllib.parse import urlparse, urlunparse


class InvalidJobUrl(ValueError):
    """Raised when a URL is not a public HTTP(S) job-posting URL."""


def validate_public_job_url(value: str) -> str:
    """Return normalized public HTTP(S) URL or raise ``InvalidJobUrl``.

    DNS is deliberately not resolved here: Jina Reader retrieves the remote URL,
    and resolving it locally would add a TOCTOU/DNS-rebinding concern.
    """
    candidate = value.strip()
    if not candidate or len(candidate) > 2_048:
        raise InvalidJobUrl("Please send a valid public http(s) job URL.")
    parsed = urlparse(candidate)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        raise InvalidJobUrl("Please send a public URL beginning with http:// or https://.")
    if parsed.username or parsed.password:
        raise InvalidJobUrl("URLs containing credentials are not accepted.")
    host = parsed.hostname
    if not host or host.lower() == "localhost" or host.lower().endswith(".local"):
        raise InvalidJobUrl("Please send a public job-posting URL, not a local address.")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    if address and (address.is_private or address.is_loopback or address.is_link_local or address.is_reserved):
        raise InvalidJobUrl("Please send a public job-posting URL, not a private address.")
    return urlunparse((parsed.scheme.lower(), parsed.netloc, parsed.path or "/", "", parsed.query, ""))
