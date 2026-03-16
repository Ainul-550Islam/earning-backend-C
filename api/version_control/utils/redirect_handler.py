# =============================================================================
# version_control/utils/redirect_handler.py
# =============================================================================
"""
Utility functions for resolving and building platform redirect URLs.
"""

from __future__ import annotations

import logging
from urllib.parse import urlencode, urlparse

logger = logging.getLogger(__name__)

# Mapping of well-known store URL patterns for quick validation
STORE_URL_PATTERNS: dict[str, str] = {
    "ios":     "apps.apple.com",
    "android": "play.google.com",
}


def is_valid_redirect_url(url: str) -> bool:
    """
    Return True if `url` is an absolute HTTP/HTTPS URL.
    """
    try:
        parsed = urlparse(url)
        return parsed.scheme in ("http", "https") and bool(parsed.netloc)
    except Exception:
        return False


def looks_like_store_url(platform: str, url: str) -> bool:
    """
    Best-effort check that an iOS/Android URL points to the right store.
    Returns True for other platforms (no known pattern).
    """
    expected_domain = STORE_URL_PATTERNS.get(platform)
    if not expected_domain:
        return True
    try:
        return expected_domain in urlparse(url).netloc
    except Exception:
        return False


def build_deep_link(base_url: str, params: dict[str, str]) -> str:
    """
    Append query parameters to `base_url` safely.

    Example::
        build_deep_link("myapp://update", {"version": "2.0.0"})
        # → "myapp://update?version=2.0.0"
    """
    if not params:
        return base_url
    separator = "&" if "?" in base_url else "?"
    return f"{base_url}{separator}{urlencode(params)}"


def sanitise_redirect_url(url: str) -> str:
    """
    Strip whitespace and trailing slashes; enforce https scheme.
    Raises ValueError if the URL is not valid after sanitisation.
    """
    url = url.strip().rstrip("/")
    parsed = urlparse(url)
    if parsed.scheme == "http" and parsed.netloc not in ("localhost", "127.0.0.1"):
        # Upgrade http → https for non-local URLs
        url = "https" + url[4:]
    if not is_valid_redirect_url(url):
        raise ValueError(f"Invalid redirect URL after sanitisation: {url!r}")
    return url
