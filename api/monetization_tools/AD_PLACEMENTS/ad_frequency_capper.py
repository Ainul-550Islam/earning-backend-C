"""AD_PLACEMENTS/ad_frequency_capper.py — Per-user frequency capping."""
from django.core.cache import cache


class AdFrequencyCapper:
    """Limits how many times a user sees an ad per day/session."""

    KEY_TEMPLATE = "mt:freq:{user_id}:{unit_id}:{date}"

    @classmethod
    def _key(cls, user_id, unit_id: int, date_str: str) -> str:
        return cls.KEY_TEMPLATE.format(
            user_id=user_id, unit_id=unit_id, date_str=date_str
        )

    @classmethod
    def get_count(cls, user_id, unit_id: int) -> int:
        from django.utils import timezone
        key = cls._key(user_id, unit_id, timezone.now().date().isoformat())
        return int(cache.get(key, 0))

    @classmethod
    def increment(cls, user_id, unit_id: int) -> int:
        from django.utils import timezone
        date_str = timezone.now().date().isoformat()
        key = cls._key(user_id, unit_id, date_str)
        try:
            return cache.incr(key)
        except ValueError:
            cache.set(key, 1, timeout=86400)
            return 1

    @classmethod
    def is_capped(cls, user_id, unit_id: int, cap: int) -> bool:
        if cap <= 0:
            return False
        return cls.get_count(user_id, unit_id) >= cap

    @classmethod
    def reset(cls, user_id, unit_id: int):
        from django.utils import timezone
        key = cls._key(user_id, unit_id, timezone.now().date().isoformat())
        cache.delete(key)
