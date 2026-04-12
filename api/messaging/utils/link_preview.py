"""
Link Preview Fetcher — OG/Twitter card metadata extraction.
Used to generate rich link previews like iMessage, Telegram, Slack.
"""
from __future__ import annotations
import logging
import re
from typing import Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

_BLOCKED_DOMAINS = frozenset([
    "localhost", "127.0.0.1", "0.0.0.0", "::1",
])


def extract_urls(text: str) -> list[str]:
    """Extract all URLs from a message text."""
    if not text:
        return []
    pattern = r'https?://[^\s<>"\']+(?:[^\s<>"\'\.,;:!?)\]])'
    return list(dict.fromkeys(re.findall(pattern, text)))[:5]


def fetch_link_preview(url: str) -> dict:
    """
    Fetch OG/Twitter card metadata for a URL.
    Returns dict with: title, description, image_url, site_name, domain, content_type, video_url, favicon_url
    """
    from django.conf import settings
    import requests
    from bs4 import BeautifulSoup

    parsed = urlparse(url)
    domain = parsed.netloc.lower().replace("www.", "")

    if domain in _BLOCKED_DOMAINS or parsed.scheme not in ("http", "https"):
        return {"url": url, "domain": domain, "is_safe": False, "fetch_error": "blocked_domain"}

    timeout = getattr(settings, "LINK_PREVIEW_TIMEOUT_SECONDS", 5)

    try:
        headers = {
            "User-Agent": "MessagingBot/1.0 (link preview fetcher)",
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-US,en;q=0.9",
        }
        resp = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
        resp.raise_for_status()

        content_type = resp.headers.get("Content-Type", "")
        if "text/html" not in content_type:
            return {
                "url": url, "domain": domain,
                "content_type": content_type.split(";")[0],
                "is_safe": True,
            }

        soup = BeautifulSoup(resp.text[:50_000], "html.parser")

        def og(prop: str) -> str:
            tag = soup.find("meta", property=f"og:{prop}") or soup.find("meta", attrs={"name": f"og:{prop}"})
            return (tag.get("content") or "").strip() if tag else ""

        def tw(prop: str) -> str:
            tag = soup.find("meta", attrs={"name": f"twitter:{prop}"})
            return (tag.get("content") or "").strip() if tag else ""

        def meta_desc() -> str:
            tag = soup.find("meta", attrs={"name": "description"})
            return (tag.get("content") or "").strip() if tag else ""

        title = og("title") or tw("title") or (soup.title.string.strip() if soup.title else "") or ""
        description = og("description") or tw("description") or meta_desc()
        image = og("image") or tw("image")
        site_name = og("site_name") or domain
        content_type_str = og("type") or "website"
        video = og("video") or og("video:url") or tw("player")

        favicon = ""
        icon_link = soup.find("link", rel=lambda r: r and ("icon" in r or "shortcut" in r))
        if icon_link:
            href = icon_link.get("href", "")
            if href.startswith("http"):
                favicon = href
            elif href.startswith("//"):
                favicon = f"https:{href}"
            elif href:
                favicon = f"{parsed.scheme}://{parsed.netloc}{href}"

        return {
            "url": url,
            "title": title[:500],
            "description": description[:1000],
            "image_url": image or None,
            "favicon_url": favicon or None,
            "site_name": site_name[:200],
            "domain": domain,
            "content_type": content_type_str[:50],
            "video_url": video or None,
            "is_safe": True,
        }

    except requests.exceptions.Timeout:
        return {"url": url, "domain": domain, "is_safe": True, "fetch_error": "timeout"}
    except requests.exceptions.SSLError:
        return {"url": url, "domain": domain, "is_safe": False, "fetch_error": "ssl_error"}
    except requests.exceptions.RequestException as exc:
        return {"url": url, "domain": domain, "is_safe": True, "fetch_error": str(exc)[:200]}
    except Exception as exc:
        logger.error("fetch_link_preview: unexpected error for %s: %s", url, exc)
        return {"url": url, "domain": domain, "is_safe": True, "fetch_error": str(exc)[:200]}


def check_safe_browsing(url: str) -> bool:
    """
    Check URL against Google Safe Browsing API.
    Returns True if safe, False if flagged.
    Requires GOOGLE_SAFE_BROWSING_KEY in settings.
    """
    from django.conf import settings
    import requests

    api_key = getattr(settings, "GOOGLE_SAFE_BROWSING_KEY", None)
    if not api_key:
        return True

    try:
        payload = {
            "client": {"clientId": "messaging_system", "clientVersion": "1.0"},
            "threatInfo": {
                "threatTypes": ["MALWARE", "SOCIAL_ENGINEERING", "UNWANTED_SOFTWARE", "POTENTIALLY_HARMFUL_APPLICATION"],
                "platformTypes": ["ANY_PLATFORM"],
                "threatEntryTypes": ["URL"],
                "threatEntries": [{"url": url}],
            },
        }
        resp = requests.post(
            f"https://safebrowsing.googleapis.com/v4/threatMatches:find?key={api_key}",
            json=payload,
            timeout=3,
        )
        resp.raise_for_status()
        matches = resp.json().get("matches", [])
        return len(matches) == 0
    except Exception as exc:
        logger.warning("check_safe_browsing: failed for %s: %s", url, exc)
        return True
