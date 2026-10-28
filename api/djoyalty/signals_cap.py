# api/djoyalty/signals_cap.py
"""
Djoyalty Signals Capabilities -- Extended signal features।
Deferred signals, signal replay, signal monitoring।

AUDIT FIX (v2 -- Signal Map Completeness):
  DeferredSignalManager._flush() previously only mapped 3 of the 6 custom
  signals defined in signals/__init__.py:
    Mapped:   points_earned, tier_changed, badge_unlocked
    Missing:  points_redeemed, cashout_approved, fraud_detected

  If any service called DeferredSignalManager.defer('cashout_approved', ...)
  the deferred item was silently dropped -- sig_map.get() returned None and
  the `if sig:` guard skipped it without logging, so downstream receivers
  (notifications, webhook dispatch, wallet ledger) never fired।

  FIX: All 6 signals from signals/__init__.py are now mapped।  Each missing
  signal entry now resolves correctly at flush time।
"""
import logging
import threading
from typing import Callable, Dict, List

logger = logging.getLogger(__name__)

_deferred: List[dict] = []
_deferred_lock = threading.Lock()


class DeferredSignalManager:
    """
    Defers signal firing until transaction commits।
    Prevents phantom signals if DB transaction rolls back।

    Usage:
        with DeferredSignalManager():
            customer.save()
            # signals fire AFTER this block completes
    """

    def __enter__(self):
        self._active = True
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._active = False
        if not exc_type:
            self._flush()
        else:
            with _deferred_lock:
                _deferred.clear()
        return False

    @staticmethod
    def defer(signal_name: str, **kwargs):
        """Queue a signal for deferred firing।"""
        with _deferred_lock:
            _deferred.append({'signal': signal_name, 'kwargs': kwargs})

    @staticmethod
    def _flush():
        """
        Fire all deferred signals।

        AUDIT FIX (v2): Added the 3 missing signals to sig_map।
        Previously points_redeemed, cashout_approved, and fraud_detected
        were silently dropped when deferred।
        """
        with _deferred_lock:
            items = list(_deferred)
            _deferred.clear()

        for item in items:
            try:
                # AUDIT FIX (v2): Import all 6 signals, not just 3।
                # All signals defined in signals/__init__.py must be mapped here।
                from .signals import (
                    points_earned,
                    points_redeemed,   # FIX: was missing
                    tier_changed,
                    badge_unlocked,
                    cashout_approved,  # FIX: was missing
                    fraud_detected,    # FIX: was missing
                )
                sig_map = {
                    'points_earned':    points_earned,
                    'points_redeemed':  points_redeemed,   # FIX: added
                    'tier_changed':     tier_changed,
                    'badge_unlocked':   badge_unlocked,
                    'cashout_approved': cashout_approved,  # FIX: added
                    'fraud_detected':   fraud_detected,    # FIX: added
                }
                sig = sig_map.get(item['signal'])
                if sig:
                    sig.send(sender=None, **item['kwargs'])
                else:
                    logger.warning(
                        'DeferredSignalManager._flush: unknown signal name %r -- dropped',
                        item['signal'],
                    )
            except Exception as e:
                logger.error('DeferredSignalManager._flush error: %s', e)


class SignalMonitor:
    """Monitor signal fires for debugging।"""

    _stats: Dict[str, int] = {}

    @classmethod
    def record(cls, signal_name: str):
        cls._stats[signal_name] = cls._stats.get(signal_name, 0) + 1

    @classmethod
    def get_stats(cls) -> dict:
        return dict(cls._stats)

    @classmethod
    def reset(cls):
        cls._stats.clear()
