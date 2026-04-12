import random
import hashlib
import logging
from django.core.cache import cache
from ...models import SmartLink
from ...constants import SLUG_ALLOWED_CHARS, SLUG_DEFAULT_LENGTH, SLUG_RESERVED_WORDS
from ...exceptions import SlugConflict

logger = logging.getLogger('smartlink.slug')
SLUG_LOCK_TTL = 10  # seconds


class SlugGeneratorService:
    """
    Generate short, unique, collision-free SmartLink slugs.
    Supports random generation, custom slugs, and sequential fallback.
    """

    def generate_unique(self, length: int = SLUG_DEFAULT_LENGTH, max_attempts: int = 10) -> str:
        """
        Generate a random slug and ensure it does not already exist.
        Uses Redis-based locking to prevent race conditions.
        """
        for attempt in range(max_attempts):
            slug = self._random_slug(length)
            lock_key = f"slug_lock:{slug}"

            # Try to acquire a short Redis lock to prevent concurrent slug claim
            if cache.add(lock_key, '1', SLUG_LOCK_TTL):
                if not SmartLink.objects.filter(slug=slug).exists():
                    logger.debug(f"Generated slug: {slug} (attempt {attempt + 1})")
                    return slug
                cache.delete(lock_key)

            # Increase length on repeated collision
            if attempt >= 3:
                length += 1

        raise SlugConflict("Failed to generate a unique slug after multiple attempts.")

    def generate_custom(self, requested_slug: str) -> str:
        """
        Validate and return a custom slug requested by a publisher.
        Raises SlugConflict or SlugReserved if not available.
        """
        slug = requested_slug.lower().strip()

        if slug in SLUG_RESERVED_WORDS:
            from ...exceptions import SlugReserved
            raise SlugReserved(f'"{slug}" is reserved.')

        if SmartLink.objects.filter(slug=slug).exists():
            raise SlugConflict(f'"{slug}" is already taken.')

        return slug

    def generate_from_name(self, name: str, length: int = SLUG_DEFAULT_LENGTH) -> str:
        """
        Generate a slug derived from a SmartLink name.
        Falls back to random if derived slug is taken.
        Example: 'My Campaign 2024' → 'my-campaign-2024' or 'mycampai'
        """
        import re
        base = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')
        base = base[:SLUG_DEFAULT_LENGTH]

        if base and not SmartLink.objects.filter(slug=base).exists() and base not in SLUG_RESERVED_WORDS:
            return base

        return self.generate_unique(length=length)

    def generate_batch(self, count: int) -> list:
        """Generate multiple unique slugs at once (used by management command)."""
        slugs = []
        attempts = 0
        max_attempts = count * 5

        while len(slugs) < count and attempts < max_attempts:
            slug = self._random_slug(SLUG_DEFAULT_LENGTH)
            if slug not in slugs and not SmartLink.objects.filter(slug=slug).exists():
                slugs.append(slug)
            attempts += 1

        if len(slugs) < count:
            logger.warning(f"Could only generate {len(slugs)}/{count} unique slugs.")

        return slugs

    def is_available(self, slug: str) -> bool:
        """Check if a slug is available (not taken and not reserved)."""
        if slug.lower() in SLUG_RESERVED_WORDS:
            return False
        return not SmartLink.objects.filter(slug=slug).exists()

    # ── Private ─────────────────────────────────────────────────────

    def _random_slug(self, length: int) -> str:
        return ''.join(random.choices(SLUG_ALLOWED_CHARS, k=length))
