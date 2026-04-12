"""
click_tracking/click_fingerprint.py
─────────────────────────────────────
Device fingerprinting for click fraud detection.
Generates a deterministic fingerprint from browser/device signals
to identify returning devices even without cookies.

Signals used:
  - IP address
  - User-Agent string
  - Device ID (from app SDK, if available)
  - Screen resolution (from JS, passed in request)
  - Accept-Language header
  - Platform / OS
"""
from __future__ import annotations
import hashlib
import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)


class ClickFingerprinter:

    def generate(
        self,
        ip: str = "",
        user_agent: str = "",
        device_id: str = "",
        accept_language: str = "",
        screen_resolution: str = "",
        platform: str = "",
    ) -> str:
        """
        Generate a deterministic device fingerprint.
        Returns a 64-char hex string (SHA-256).
        """
        if not any([ip, user_agent, device_id]):
            return ""

        # Normalise user-agent (remove version numbers for stability)
        ua_normalised = self._normalise_ua(user_agent)

        # Build fingerprint components
        components = [
            ip,
            ua_normalised,
            device_id,
            accept_language,
            screen_resolution,
            platform,
        ]
        raw = "|".join(c.strip().lower() for c in components if c)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def generate_partial(self, ip: str, user_agent: str) -> str:
        """
        Quick fingerprint using only IP + UA (for fast fraud checks).
        Less stable than full fingerprint but always available.
        """
        raw = f"{ip.strip()}:{self._normalise_ua(user_agent)}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]

    def match(self, fp1: str, fp2: str) -> bool:
        """Check if two fingerprints match (exact or partial)."""
        if not fp1 or not fp2:
            return False
        return fp1 == fp2 or fp1.startswith(fp2) or fp2.startswith(fp1)

    @staticmethod
    def _normalise_ua(user_agent: str) -> str:
        """Remove rapidly-changing version numbers from UA string."""
        if not user_agent:
            return ""
        # Remove exact version numbers like /120.0.1234.5
        ua = re.sub(r'/[\d.]+', '/x', user_agent)
        # Remove build IDs
        ua = re.sub(r'\s+Build/\S+', '', ua)
        return ua.strip()

    def extract_os(self, user_agent: str) -> str:
        """Extract OS name from user-agent."""
        ua = user_agent.lower()
        if "windows nt 10" in ua:
            return "Windows 10"
        elif "windows" in ua:
            return "Windows"
        elif "iphone os" in ua:
            return "iOS"
        elif "ipad" in ua:
            return "iPadOS"
        elif "android" in ua:
            return "Android"
        elif "mac os x" in ua:
            return "macOS"
        elif "linux" in ua:
            return "Linux"
        return "Unknown"

    def extract_browser(self, user_agent: str) -> str:
        """Extract browser name from user-agent."""
        ua = user_agent.lower()
        if "edg/" in ua or "edge" in ua:
            return "Edge"
        elif "firefox" in ua:
            return "Firefox"
        elif "opr" in ua or "opera" in ua:
            return "Opera"
        elif "chrome" in ua:
            return "Chrome"
        elif "safari" in ua:
            return "Safari"
        return "Unknown"


# Module-level singleton
click_fingerprinter = ClickFingerprinter()
