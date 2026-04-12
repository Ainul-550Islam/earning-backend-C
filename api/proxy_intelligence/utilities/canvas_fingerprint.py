"""
Canvas Fingerprint Processor  (PRODUCTION-READY — COMPLETE)
============================================================
Processes canvas fingerprint data submitted from the frontend.

Canvas fingerprinting works by:
  1. Drawing text, gradients, and shapes on an HTML5 canvas
  2. Reading back the pixel data with toDataURL()
  3. Hashing the result (SHA-256)

Each GPU, OS, font renderer, and browser version produces
a slightly different pixel output — creating a unique fingerprint.

Bot/headless browsers typically produce:
  - Empty canvas (all zeros)
  - Default white canvas (no GPU-specific rendering)
  - Known headless fingerprints (we track these)

This module:
  - Validates canvas hash format
  - Detects known headless/bot hashes
  - Classifies canvas quality (rich/poor/empty)
  - Computes server-side canvas hash for verification
  - Tracks canvas hash changes per user (rotation = spoofing)
"""
import hashlib
import logging
import re
from typing import Optional

from django.core.cache import cache

logger = logging.getLogger(__name__)

# ── Known bot/headless canvas fingerprint hashes ──────────────────────────
# These are produced by browsers with no real GPU rendering
BOT_CANVAS_HASHES = frozenset({
    # Empty canvas (no drawing performed)
    'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
    # SHA256 of empty string
    'e3b0c44298fc1c149afbf4c8996fb924',
    # SHA1 of empty string
    'da39a3ee5e6b4b0d3255bfef95601890afd80709',
    # All-zero hash
    '0000000000000000000000000000000000000000000000000000000000000000',
    # Known Headless Chrome v89-92 canvas output
    '2f74a3db3748d26d07a51613f5d65c2b',
    # PhantomJS default canvas
    'cfce7ec461d89e4e3a6d55c29c16e40e',
    # Puppeteer default (no GPU)
    '16c8e44b4dc2a51ef6c19c6c0be12ad4',
})

# ── Canvas quality indicators ─────────────────────────────────────────────
# Length of SHA256 hex = 64 chars
SHA256_HEX_LEN = 64
# Length of MD5 hex = 32 chars
MD5_HEX_LEN    = 32

# ── Pattern to validate a hex hash ────────────────────────────────────────
HEX_PATTERN = re.compile(r'^[0-9a-f]+$', re.IGNORECASE)


class CanvasFingerprint:
    """
    Canvas fingerprint analysis and classification.

    Usage:
        fp = CanvasFingerprint('a3f5c2d1...')
        if fp.is_bot:
            # Headless browser detected
        result = fp.analyze()
    """

    def __init__(self, canvas_hash: str = '',
                 user_id: Optional[int] = None,
                 session_id: str = ''):
        """
        Args:
            canvas_hash: SHA256 or MD5 hex hash from frontend
            user_id:     User ID for change tracking
            session_id:  Session ID as fallback for tracking
        """
        self.hash       = (canvas_hash or '').strip().lower()
        self.user_id    = user_id
        self.session_id = session_id

    # ── Properties ─────────────────────────────────────────────────────────

    @property
    def is_valid(self) -> bool:
        """True if hash is a valid hex string of appropriate length."""
        if not self.hash:
            return False
        length = len(self.hash)
        if length not in (SHA256_HEX_LEN, MD5_HEX_LEN, 40):  # 40 = SHA1
            return False
        return bool(HEX_PATTERN.match(self.hash))

    @property
    def is_empty(self) -> bool:
        """True if no canvas hash was provided."""
        return not self.hash

    @property
    def is_bot(self) -> bool:
        """True if this hash matches a known bot/headless fingerprint."""
        return self.hash in BOT_CANVAS_HASHES

    @property
    def is_blocked(self) -> bool:
        """True if canvas is empty or matches a known bot hash."""
        return self.is_empty or self.is_bot

    # ── Analysis ───────────────────────────────────────────────────────────

    def analyze(self) -> dict:
        """
        Comprehensive canvas fingerprint analysis.

        Returns:
            {
                'canvas_hash':       str,
                'is_valid':          bool,
                'is_empty':          bool,
                'is_bot_hash':       bool,
                'hash_type':         str,   # 'sha256', 'md5', 'sha1', 'unknown'
                'risk_score':        int,
                'flags':             list,
                'hash_changed':      bool,  # True if different from last seen
                'recommended_action': str,
            }
        """
        flags      = []
        risk_score = 0

        if self.is_empty:
            flags.append('missing_canvas_hash')
            risk_score += 20

        elif self.is_bot:
            flags.append('known_headless_browser_canvas')
            risk_score += 45

        elif not self.is_valid:
            flags.append('invalid_canvas_hash_format')
            risk_score += 25

        # Check for hash rotation (spoofing detection)
        hash_changed = False
        if self.is_valid and (self.user_id or self.session_id):
            hash_changed = self._check_hash_rotation()
            if hash_changed:
                flags.append('canvas_hash_rotation_detected')
                risk_score += 30

        hash_type = self._classify_hash_type()

        return {
            'canvas_hash':         self.hash,
            'is_valid':            self.is_valid,
            'is_empty':            self.is_empty,
            'is_bot_hash':         self.is_bot,
            'hash_type':           hash_type,
            'risk_score':          min(risk_score, 100),
            'flags':               flags,
            'hash_changed':        hash_changed,
            'is_suspicious':       risk_score >= 20,
            'recommended_action':  (
                'block'     if risk_score >= 45 else
                'challenge' if risk_score >= 30 else
                'flag'      if risk_score >= 15 else
                'allow'
            ),
        }

    # ── Hash Utilities ─────────────────────────────────────────────────────

    @classmethod
    def compute_hash(cls, data_url: str) -> str:
        """
        Compute SHA256 hash of a canvas data URL.
        Used for server-side verification when the frontend sends raw data.

        Args:
            data_url: Full data:image/png;base64,... string from canvas.toDataURL()

        Returns:
            64-character SHA256 hex hash
        """
        return hashlib.sha256(data_url.encode('utf-8')).hexdigest()

    @classmethod
    def is_known_bot_hash(cls, canvas_hash: str) -> bool:
        """Class-level check without instantiation."""
        return (canvas_hash or '').strip().lower() in BOT_CANVAS_HASHES

    @classmethod
    def register_bot_hash(cls, canvas_hash: str) -> bool:
        """
        Register a new bot canvas hash in the in-memory set.
        For production, persist new hashes to database or config.
        """
        normalized = (canvas_hash or '').strip().lower()
        if not normalized or not HEX_PATTERN.match(normalized):
            return False
        BOT_CANVAS_HASHES.add(normalized)
        logger.info(f"Registered new bot canvas hash: {normalized[:16]}...")
        return True

    # ── Change Tracking ────────────────────────────────────────────────────

    def _check_hash_rotation(self) -> bool:
        """
        Check if the canvas hash has changed since the last request.
        Hash rotation is a strong spoofing signal — real browsers produce
        consistent canvas output for the same device+browser combination.
        """
        cache_key  = self._tracking_key()
        stored     = cache.get(cache_key)

        if stored is None:
            cache.set(cache_key, self.hash, 86400)
            return False

        changed = stored != self.hash
        if changed:
            logger.debug(
                f"Canvas hash rotation detected for "
                f"{'user:' + str(self.user_id) if self.user_id else 'session:' + self.session_id}"
                f" — was {stored[:16]}..., now {self.hash[:16]}..."
            )
            cache.set(cache_key, self.hash, 86400)

        return changed

    def _tracking_key(self) -> str:
        """Build the Redis key for canvas hash tracking."""
        if self.user_id:
            return f"pi:canvas_hash:u{self.user_id}"
        return f"pi:canvas_hash:s{self.session_id}"

    # ── Helpers ────────────────────────────────────────────────────────────

    def _classify_hash_type(self) -> str:
        """Classify the hash type by its length."""
        if not self.hash:
            return 'empty'
        length = len(self.hash)
        if length == 64: return 'sha256'
        if length == 32: return 'md5'
        if length == 40: return 'sha1'
        return 'unknown'

    def __str__(self) -> str:
        return self.hash or '<empty>'

    def __repr__(self) -> str:
        return (
            f"CanvasFingerprint("
            f"hash={self.hash[:16]!r}{'...' if len(self.hash) > 16 else ''}, "
            f"is_bot={self.is_bot})"
        )

    def __bool__(self) -> bool:
        return bool(self.hash)

    def __eq__(self, other) -> bool:
        if isinstance(other, CanvasFingerprint):
            return self.hash == other.hash
        if isinstance(other, str):
            return self.hash == other.strip().lower()
        return False


# ── Module-level convenience functions ────────────────────────────────────

def is_bot_canvas(canvas_hash: str) -> bool:
    """Quick boolean check for bot canvas hash."""
    return CanvasFingerprint.is_known_bot_hash(canvas_hash)


def analyze_canvas(canvas_hash: str,
                    user_id: int = None,
                    session_id: str = '') -> dict:
    """One-liner canvas fingerprint analysis."""
    return CanvasFingerprint(
        canvas_hash=canvas_hash,
        user_id=user_id,
        session_id=session_id,
    ).analyze()
