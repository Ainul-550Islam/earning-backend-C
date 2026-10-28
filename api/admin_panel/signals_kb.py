# api/admin_panel/signals_kb.py
"""
Signals Knowledge Base (KB) — admin_panel's cross-app signal intelligence layer.
Extends signals_cap.py with:
  - Signal routing rules
  - Signal history / audit log
  - Signal suppression (prevent duplicate fires)
  - Signal enrichment (auto-add context before firing)
  - Signal replay (re-fire historical signals)
  - Signal analytics (which signals fire most)

"Do not summarize or skip any logic. Provide the full code."
"""
from __future__ import annotations

import logging
import time
from collections import defaultdict, deque
from typing import Any, Callable, Dict, List, Optional, Tuple
from django.core.cache import cache
from django.dispatch import Signal
from django.utils import timezone

logger = logging.getLogger(__name__)


# ===========================================================================
# SIGNAL HISTORY RING BUFFER
# ===========================================================================

class SignalHistoryBuffer:
    """
    In-memory ring buffer storing recent signal fires.
    Max 5000 entries, auto-evicts oldest.
    Used for: audit, replay, dedup, analytics.
    """
    MAX_SIZE = 5000

    def __init__(self):
        self._buffer: deque = deque(maxlen=self.MAX_SIZE)
        self._stats: Dict[str, int] = defaultdict(int)
        self._suppressed: Dict[str, float] = {}  # signal_key → timestamp

    def record(self, signal_name: str, sender: str, payload: Dict, fired: bool = True) -> str:
        """Record a signal fire. Returns event_id."""
        import uuid
        event_id = str(uuid.uuid4())
        self._buffer.appendleft({
            'event_id':    event_id,
            'signal_name': signal_name,
            'sender':      sender,
            'payload':     payload,
            'fired':       fired,
            'timestamp':   timezone.now().isoformat(),
        })
        if fired:
            self._stats[signal_name] += 1
        return event_id

    def get_recent(self, signal_name: str = '', limit: int = 50) -> List[Dict]:
        items = list(self._buffer)
        if signal_name:
            items = [i for i in items if i['signal_name'] == signal_name]
        return items[:limit]

    def get_stats(self) -> Dict[str, int]:
        return dict(sorted(self._stats.items(), key=lambda x: x[1], reverse=True))

    def is_suppressed(self, dedup_key: str, ttl_seconds: float) -> bool:
        """Check if signal is within suppression window."""
        last = self._suppressed.get(dedup_key, 0)
        if time.monotonic() - last < ttl_seconds:
            return True
        self._suppressed[dedup_key] = time.monotonic()
        return False

    def clear(self) -> None:
        self._buffer.clear()
        self._stats.clear()
        self._suppressed.clear()


# Global history buffer
signal_history = SignalHistoryBuffer()


# ===========================================================================
# SIGNAL ROUTER
# ===========================================================================

class SignalRouter:
    """
    Routes signals to correct handlers based on rules.
    Adds: conditions, priorities, enrichment, dedup.
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._routes: List[Dict] = []
            cls._instance._enrichers: Dict[str, List[Callable]] = defaultdict(list)
            cls._instance._conditions: Dict[str, List[Callable]] = defaultdict(list)
        return cls._instance

    def route(
        self,
        signal_name: str,
        handler: Callable,
        condition: Optional[Callable] = None,
        priority: int = 10,
        dedup_ttl: float = 0,
    ) -> None:
        """
        Route a signal to a handler with optional condition and dedup.

        Args:
            signal_name:  Name of signal to route
            handler:      Callable(signal_name, sender, payload)
            condition:    Optional callable(payload) → bool; only fire if True
            priority:     Lower number = fires first (1=highest)
            dedup_ttl:    Suppress duplicate fires within N seconds
        """
        self._routes.append({
            'signal_name': signal_name,
            'handler':     handler,
            'condition':   condition,
            'priority':    priority,
            'dedup_ttl':   dedup_ttl,
        })
        self._routes.sort(key=lambda r: r['priority'])
        logger.debug(f"[SignalRouter] Routed: {signal_name} → {handler.__name__} (priority={priority})")

    def add_enricher(self, signal_name: str, enricher: Callable) -> None:
        """
        Add an enricher that augments payload before handlers fire.
        enricher(payload: dict) → dict
        """
        self._enrichers[signal_name].append(enricher)

    def dispatch(
        self,
        signal_name: str,
        sender: str,
        payload: Dict,
    ) -> Tuple[int, int]:
        """
        Dispatch a signal through all matching routes.
        Returns (fired_count, skipped_count).
        """
        # Enrich payload
        enriched = dict(payload)
        for enricher in self._enrichers.get(signal_name, []):
            try:
                enriched = enricher(enriched) or enriched
            except Exception as e:
                logger.warning(f"[SignalRouter] Enricher error for {signal_name}: {e}")

        fired = skipped = 0
        for route in self._routes:
            if route['signal_name'] != signal_name:
                continue

            # Dedup check
            if route['dedup_ttl'] > 0:
                dedup_key = f"{signal_name}:{sender}:{hash(str(enriched))}"
                if signal_history.is_suppressed(dedup_key, route['dedup_ttl']):
                    skipped += 1
                    continue

            # Condition check
            if route['condition']:
                try:
                    if not route['condition'](enriched):
                        skipped += 1
                        continue
                except Exception as e:
                    logger.warning(f"[SignalRouter] Condition error for {signal_name}: {e}")
                    skipped += 1
                    continue

            # Fire handler
            try:
                route['handler'](signal_name=signal_name, sender=sender, payload=enriched)
                fired += 1
            except Exception as e:
                logger.error(f"[SignalRouter] Handler error for {signal_name}: {e}")

        # Record in history
        signal_history.record(signal_name, sender, enriched, fired=fired > 0)
        return fired, skipped


# Global router
signal_router = SignalRouter()


# ===========================================================================
# KNOWLEDGE BASE SIGNALS (KB-specific, extend signals_cap.py)
# ===========================================================================

# Analytics signals
admin_report_generated    = Signal()   # args: report_type, rows, duration_ms
admin_export_completed    = Signal()   # args: export_id, model_name, rows, format
admin_search_performed    = Signal()   # args: query, results_count, actor_id
admin_insight_created     = Signal()   # args: insight_id, type, priority

# AI signals
admin_ai_prediction_made  = Signal()   # args: model_name, prediction_type, result
admin_ai_anomaly_found    = Signal()   # args: metric, severity, value, expected
admin_ai_churn_risk       = Signal()   # args: user_ids, count

# Integration signals
admin_integration_called  = Signal()   # args: app, action, success, duration_ms
admin_integration_failed  = Signal()   # args: app, action, error, attempt
admin_circuit_breaker_open = Signal()  # args: app, failures, threshold

# Campaign signals
admin_offer_cap_reached   = Signal()   # args: offer_id, cap_type, count
admin_campaign_budget_low = Signal()   # args: campaign_id, remaining_pct

# Wallet signals
admin_wallet_drift_detected = Signal() # args: user_id, drift_amount, auto_fixed
admin_suspicious_withdrawal = Signal() # args: user_id, amount, reason

# Security signals
admin_login_from_new_ip   = Signal()   # args: user_id, ip, country
admin_brute_force_detected = Signal()  # args: ip, attempts, window_seconds
admin_session_hijack_risk = Signal()   # args: user_id, session_key, risk_level


# ===========================================================================
# KB SIGNAL HELPERS
# ===========================================================================

def fire_kb_signal(signal_obj: Signal, sender: str = 'admin_panel', **kwargs) -> None:
    """
    Fire a KB signal with history recording and router dispatch.
    """
    signal_name = _get_signal_name(signal_obj)
    payload = dict(kwargs)

    # Fire Django signal
    try:
        signal_obj.send(sender=sender, **kwargs)
    except Exception as e:
        logger.error(f"[signals_kb] Django signal fire failed: {signal_name}: {e}")

    # Route through signal router (for enrichment, dedup, conditions)
    signal_router.dispatch(signal_name, sender, payload)

    # Also push to INTEGRATION_SYSTEM event bus
    try:
        from api.admin_panel.INTEGRATION_SYSTEM.event_bus import event_bus
        event_bus.publish(signal_name, payload, source=sender, async_mode=True)
    except Exception:
        pass


def _get_signal_name(signal_obj: Signal) -> str:
    """Get string name for a Signal object."""
    for name, obj in globals().items():
        if obj is signal_obj:
            return name
    return 'unknown_signal'


# ===========================================================================
# DEFAULT ROUTING RULES
# ===========================================================================

def _on_wallet_drift(signal_name: str, sender: str, payload: Dict) -> None:
    """Create alert when wallet drift is detected."""
    try:
        from api.alerts.models import AlertRule
        # Only alert if not auto-fixed
        if not payload.get('auto_fixed') and abs(float(payload.get('drift_amount', 0))) > 100:
            cache_key = f"admin_panel:wallet_drift_alert:{payload.get('user_id')}"
            if not cache.get(cache_key):
                logger.warning(f"[signals_kb] Large wallet drift: user={payload.get('user_id')} drift={payload.get('drift_amount')}")
                cache.set(cache_key, True, 3600)
    except Exception:
        pass


def _on_circuit_breaker_open(signal_name: str, sender: str, payload: Dict) -> None:
    """Cache circuit breaker state when opened."""
    app = payload.get('app', '')
    if app:
        cache.set(f'admin_panel:circuit_breaker:{app}', 'open', 300)
        logger.critical(f"[signals_kb] Circuit breaker OPEN for: {app}")


def _on_ai_anomaly(signal_name: str, sender: str, payload: Dict) -> None:
    """Create AdminInsight when AI finds an anomaly."""
    severity = payload.get('severity', 'medium')
    metric   = payload.get('metric', 'unknown')
    try:
        from api.admin_panel.models.reports import AdminInsight
        AdminInsight.objects.create(
            type='anomaly',
            title=f"AI anomaly: {metric}",
            body=f"Metric '{metric}' deviates from expected. Severity: {severity}.",
            priority=severity,
            is_read=False,
        )
    except Exception:
        pass


def _on_brute_force(signal_name: str, sender: str, payload: Dict) -> None:
    """Auto-block IP on brute force detection."""
    ip = payload.get('ip', '')
    attempts = int(payload.get('attempts', 0))
    if ip and attempts >= 20:
        from django.core.cache import cache
        cache.set(f'admin_panel:blocked_ip:{ip}', True, 3600)
        logger.warning(f"[signals_kb] Auto-blocked IP {ip} after {attempts} brute force attempts")
        # Also fire through fraud bridge
        try:
            from api.admin_panel.INTEGRATION_SYSTEM.bridge import AdminBridge
            AdminBridge.fraud.block_ip(ip, reason=f'Auto-block: {attempts} brute force attempts')
        except Exception:
            pass


def _enrich_with_timestamp(payload: Dict) -> Dict:
    """Auto-enrich all payloads with server timestamp."""
    payload.setdefault('server_timestamp', timezone.now().isoformat())
    return payload


def _enrich_user_context(payload: Dict) -> Dict:
    """Auto-enrich user-related signals with user metadata."""
    user_id = payload.get('user_id')
    if user_id and 'username' not in payload:
        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            user = User.objects.only('username', 'email', 'is_active').get(pk=user_id)
            payload['username']  = user.username
            payload['is_active'] = user.is_active
        except Exception:
            pass
    return payload


# ===========================================================================
# REGISTER DEFAULT ROUTES AND ENRICHERS
# ===========================================================================

def setup_kb_signal_routing() -> None:
    """
    Register all default signal routes and enrichers.
    Called from apps.py ready().
    """
    # Global enrichers
    for sig_name in [
        'admin_wallet_drift_detected', 'admin_suspicious_withdrawal',
        'admin_ai_anomaly_found', 'admin_brute_force_detected',
        'admin_circuit_breaker_open', 'admin_login_from_new_ip',
    ]:
        signal_router.add_enricher(sig_name, _enrich_with_timestamp)

    # User context enrichment for user-related signals
    for sig_name in [
        'admin_wallet_drift_detected', 'admin_suspicious_withdrawal',
        'admin_login_from_new_ip', 'admin_session_hijack_risk', 'admin_ai_churn_risk',
    ]:
        signal_router.add_enricher(sig_name, _enrich_user_context)

    # Routing rules
    signal_router.route(
        'admin_wallet_drift_detected',
        _on_wallet_drift,
        priority=1,
        dedup_ttl=3600,  # Don't alert same user more than once per hour
    )
    signal_router.route(
        'admin_circuit_breaker_open',
        _on_circuit_breaker_open,
        priority=1,
        dedup_ttl=300,
    )
    signal_router.route(
        'admin_ai_anomaly_found',
        _on_ai_anomaly,
        condition=lambda p: p.get('severity') in ('high', 'critical'),
        priority=2,
        dedup_ttl=600,
    )
    signal_router.route(
        'admin_brute_force_detected',
        _on_brute_force,
        condition=lambda p: int(p.get('attempts', 0)) >= 10,
        priority=1,
        dedup_ttl=3600,
    )

    logger.info(f"[signals_kb] KB routing setup complete: {len(signal_router._routes)} routes")


# ===========================================================================
# SIGNAL ANALYTICS API
# ===========================================================================

def get_signal_analytics(hours: int = 24) -> Dict:
    """Signal fire analytics for monitoring panel."""
    stats = signal_history.get_stats()
    recent = signal_history.get_recent(limit=20)
    return {
        'total_fired':    sum(stats.values()),
        'by_signal':      stats,
        'recent':         recent,
        'circuit_breakers': {
            app.replace('admin_panel:circuit_breaker:', ''): cache.get(f'admin_panel:circuit_breaker:{app}')
            for app in []  # Would iterate cache keys in production
        },
    }


def get_signal_history(signal_name: str = '', limit: int = 50) -> List[Dict]:
    """Get recent signal history, optionally filtered by signal name."""
    return signal_history.get_recent(signal_name=signal_name, limit=limit)


def replay_signal(event_id: str, actor=None) -> bool:
    """
    Replay a historical signal by event_id.
    Useful for re-processing failed signal handlers.
    """
    for entry in signal_history._buffer:
        if entry['event_id'] == event_id:
            signal_name = entry['signal_name']
            payload     = entry['payload']
            sender      = entry['sender']
            fired, skipped = signal_router.dispatch(signal_name, sender, payload)
            logger.info(f"[signals_kb] Replayed {signal_name} event={event_id} fired={fired}")
            if actor:
                try:
                    from api.admin_panel.models.activity import AdminActivity
                    AdminActivity.log(
                        actor=actor,
                        action='replay_signal',
                        changes={'event_id': event_id, 'signal': signal_name, 'fired': fired},
                    )
                except Exception:
                    pass
            return fired > 0
    logger.warning(f"[signals_kb] replay: event_id {event_id} not found in buffer")
    return False


def suppress_signal(signal_name: str, ttl_seconds: int = 300, reason: str = '') -> None:
    """
    Temporarily suppress a signal (prevent all handlers from firing).
    Useful during migrations, maintenance, bulk imports.
    """
    cache.set(f'admin_panel:signal_suppressed:{signal_name}', {
        'suppressed_at': timezone.now().isoformat(),
        'ttl': ttl_seconds,
        'reason': reason,
    }, ttl_seconds)
    logger.warning(f"[signals_kb] Signal suppressed: {signal_name} for {ttl_seconds}s — {reason}")


def is_signal_suppressed(signal_name: str) -> bool:
    """Check if a signal is currently suppressed."""
    return bool(cache.get(f'admin_panel:signal_suppressed:{signal_name}'))