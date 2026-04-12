"""AD_PLACEMENTS/ad_sequencing.py — Sequential ad delivery logic."""
from typing import List, Optional


class AdSequencer:
    """Delivers ads in a predefined sequence — used for retargeting funnels."""

    def __init__(self, sequence: List[dict]):
        """
        sequence: list of dicts like:
          [{"unit_id": 1, "delay_sec": 0}, {"unit_id": 2, "delay_sec": 60}, ...]
        """
        self.sequence = sequence
        self._position_key = "mt:seq:{user_id}:{campaign_id}"

    def get_next(self, user_id: str, campaign_id: int) -> Optional[dict]:
        """Return the next ad in the sequence for this user."""
        from django.core.cache import cache
        key = self._position_key.format(user_id=user_id, campaign_id=campaign_id)
        pos = int(cache.get(key, 0))
        if pos >= len(self.sequence):
            return None
        return self.sequence[pos]

    def advance(self, user_id: str, campaign_id: int):
        from django.core.cache import cache
        key = self._position_key.format(user_id=user_id, campaign_id=campaign_id)
        pos = int(cache.get(key, 0)) + 1
        cache.set(key, pos, timeout=86400 * 30)  # 30 days

    def reset(self, user_id: str, campaign_id: int):
        from django.core.cache import cache
        key = self._position_key.format(user_id=user_id, campaign_id=campaign_id)
        cache.delete(key)
