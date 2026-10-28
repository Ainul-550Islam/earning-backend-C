"""
tasks/integration/event_bus.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Central Event Bus — Decoupled Inter-Task Communication
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Allows any task to emit events without knowing who will handle them.
Handlers are registered and executed automatically.

Event naming convention: 'domain.action'
Examples:
  user.registered         → welcome email, onboarding tasks, referral check
  task.completed          → wallet credit, gamification, analytics
  payment.withdrawal      → fraud check, gateway dispatch, notification
  offer.converted         → publisher credit, advertiser billing, stats update
  cpi.installed           → MMP verification, publisher payout, fraud scan
  fraud.detected          → account suspend, alert admin, reverse transactions
"""

import logging
import traceback
import re
from typing import Callable, Dict, List, Any, Optional
from django.core.cache import cache
from django.utils import timezone
from django.contrib.auth import get_user_model
from rest_framework.exceptions import PermissionDenied

logger = logging.getLogger(__name__)

# ─── Event Registry ────────────────────────────────────────────────────

_HANDLERS: Dict[str, List[Callable]] = {}
_ASYNC_HANDLERS: Dict[str, List[str]] = {}  # event → [celery task names]

# Security: Track handler registrations for audit
_HANDLER_REGISTRY: Dict[str, Dict[str, Any]] = {}
_ALLOWED_EVENTS = {
    'user.registered', 'user.updated', 'user.deleted',
    'task.started', 'task.completed', 'task.failed', 'task.verified',
    'offer.converted', 'offer.clicked', 'offer.impression',
    'payment.withdrawal_requested', 'payment.withdrawal_processed',
    'fraud.detected', 'fraud.flagged',
    'publisher.tier_changed', 'publisher.registered',
    'survey.completed', 'cpi.installed'
}


class EventBus:
    """
    Central pub/sub event bus.
    Supports:
    - Synchronous handlers (run inline, fast operations)
    - Async handlers (dispatched to Celery workers)
    - Wildcard handlers (domain.* catches all domain events)
    - Event history in cache for debugging
    """

    HISTORY_KEY     = 'event_bus_history'
    HISTORY_TTL     = 3600  # 1 hour
    HISTORY_MAX_LEN = 500

    # ─── Emitting ──────────────────────────────────────────────────────────────

    @classmethod
    def emit(
        cls,
        event: str,
        payload: Dict[str, Any] = None,
        async_dispatch: bool = True,
        priority: str = 'normal',
        validate: bool = True,
    ) -> int:
        """
        Emit an event to all registered handlers.

        Args:
            event:          Event name e.g. 'user.task_completed'
            payload:        Data dict passed to all handlers
            async_dispatch: True = dispatch Celery tasks; False = run sync
            priority:       'high' | 'normal' | 'low' (affects Celery queue)
            validate:       True = validate payload; False = skip validation

        Returns: Number of handlers triggered
        """
        # Security: Validate and sanitize payload
        if validate:
            try:
                payload = cls._validate_payload(event, payload or {})
            except Exception as e:
                logger.error(f"[EventBus] Payload validation failed ({event}): {e}")
                return 0
        else:
            payload = payload or {}

        # Add security metadata
        payload['_event']     = event
        payload['_emitted_at'] = timezone.now().isoformat()
        payload['_emitted_by'] = cls._get_current_user()

        # Security: Rate limiting check
        if cls._is_rate_limited(event):
            logger.warning(f"[EventBus] Rate limited event: {event}")
            return 0

        logger.debug(f"[EventBus] emit: {event} payload_keys={list(payload.keys())}")

        triggered = 0

        # Find matching handlers (exact + wildcard)
        matching_events = cls._resolve_handlers(event)

        for handler_event in matching_events:
            # Sync handlers
            for handler in _HANDLERS.get(handler_event, []):
                try:
                    handler(event, payload)
                    triggered += 1
                except Exception as e:
                    logger.error(f"[EventBus] sync handler error ({event}): {e}")
                    # Security: Log handler errors for audit
                    cls._log_handler_error('sync', event, handler.__name__, str(e))

            # Async handlers (Celery tasks)
            if async_dispatch:
                queue_map = {'high': 'high', 'normal': 'default', 'low': 'low'}
                queue     = queue_map.get(priority, 'default')

                for task_name in _ASYNC_HANDLERS.get(handler_event, []):
                    try:
                        from celery import current_app
                        current_app.send_task(
                            task_name,
                            kwargs={'event': event, 'payload': payload},
                            queue=queue,
                        )
                        triggered += 1
                    except Exception as e:
                        logger.error(f"[EventBus] async handler error ({task_name}): {e}")
                        # Security: Log handler errors for audit
                        cls._log_handler_error('async', event, task_name, str(e))

        # Store in history
        cls._record_history(event, payload, triggered)

        return triggered

    @classmethod
    def emit_high(cls, event: str, payload: Dict = None) -> int:
        """Emit with high priority (→ 'high' Celery queue)."""
        return cls.emit(event, payload, async_dispatch=True, priority='high')

    @classmethod
    def emit_sync(cls, event: str, payload: Dict = None) -> int:
        """Emit synchronously — no Celery dispatch, runs inline."""
        return cls.emit(event, payload, async_dispatch=False)

    # ─── Registration ──────────────────────────────────────────────────────────

    @classmethod
    def on(cls, event: str, handler: Callable, require_auth: bool = True) -> None:
        """Register a synchronous handler for an event."""
        # Security: Validate event and authorize handler
        if require_auth and not cls._is_authorized():
            raise PermissionDenied("Unauthorized handler registration")
        
        if not cls._is_event_allowed(event):
            logger.warning(f"[EventBus] Blocked handler registration for restricted event: {event}")
            raise PermissionDenied(f"Event '{event}' is restricted")
        
        # Security: Prevent wildcard abuse
        if event.endswith('.*') and not cls._is_wildcard_allowed(handler):
            logger.warning(f"[EventBus] Blocked wildcard handler registration: {event}")
            raise PermissionDenied("Wildcard handlers require special permissions")
        
        _HANDLERS.setdefault(event, []).append(handler)
        
        # Security: Audit trail
        _HANDLER_REGISTRY[f"sync_{event}_{handler.__name__}"] = {
            'type': 'sync',
            'event': event,
            'handler': handler.__name__,
            'registered_at': timezone.now().isoformat(),
            'user': cls._get_current_user()
        }
        
        logger.debug(f"[EventBus] registered sync handler for '{event}': {handler.__name__}")

    @classmethod
    def on_async(cls, event: str, celery_task_name: str, require_auth: bool = True) -> None:
        """Register a Celery task to handle an event asynchronously."""
        # Security: Validate event and authorize handler
        if require_auth and not cls._is_authorized():
            raise PermissionDenied("Unauthorized async handler registration")
        
        if not cls._is_event_allowed(event):
            logger.warning(f"[EventBus] Blocked async handler registration for restricted event: {event}")
            raise PermissionDenied(f"Event '{event}' is restricted")
        
        _ASYNC_HANDLERS.setdefault(event, []).append(celery_task_name)
        
        # Security: Audit trail
        _HANDLER_REGISTRY[f"async_{event}_{celery_task_name}"] = {
            'type': 'async',
            'event': event,
            'task': celery_task_name,
            'registered_at': timezone.now().isoformat(),
            'user': cls._get_current_user()
        }
        
        logger.debug(f"[EventBus] registered async handler for '{event}': {celery_task_name}")

    @classmethod
    def off(cls, event: str, handler: Callable) -> None:
        """Unregister a handler."""
        handlers = _HANDLERS.get(event, [])
        if handler in handlers:
            handlers.remove(handler)

    # ─── Querying ──────────────────────────────────────────────────────────────

    @classmethod
    def get_history(cls, limit: int = 50) -> List[Dict]:
        """Return recent event history for debugging."""
        history = cache.get(cls.HISTORY_KEY) or []
        return history[-limit:]

    @classmethod
    def get_handlers(cls) -> Dict[str, Any]:
        """Return all registered handlers."""
        return {
            'sync':  {k: [h.__name__ for h in v] for k, v in _HANDLERS.items()},
            'async': dict(_ASYNC_HANDLERS),
        }

    @classmethod
    def clear_handlers(cls, event: str = None) -> None:
        """Clear handlers (useful in tests)."""
        if event:
            _HANDLERS.pop(event, None)
            _ASYNC_HANDLERS.pop(event, None)
        else:
            _HANDLERS.clear()
            _ASYNC_HANDLERS.clear()

    # ─── Private helpers ───────────────────────────────────────────────────────

    @classmethod
    def _resolve_handlers(cls, event: str) -> List[str]:
        """Return all event keys that match: exact + wildcard."""
        matches = [event]
        parts   = event.split('.')
        # Add wildcards: 'user.*', '*'
        for i in range(len(parts)):
            wildcard = '.'.join(parts[:i]) + '.*' if i > 0 else '*'
            if wildcard in _HANDLERS or wildcard in _ASYNC_HANDLERS:
                matches.append(wildcard)
        return matches

    @classmethod
    def _record_history(cls, event: str, payload: Dict, triggered: int) -> None:
        try:
            history = cache.get(cls.HISTORY_KEY) or []
            history.append({
                'event': event,
                'triggered': triggered,
                'ts': timezone.now().isoformat(),
                'keys': list(payload.keys()),
                'user': cls._get_current_user(),
            })
            if len(history) > cls.HISTORY_MAX_LEN:
                history = history[-cls.HISTORY_MAX_LEN:]
            cache.set(cls.HISTORY_KEY, history, timeout=cls.HISTORY_TTL)
        except Exception:
            pass

    # ─── Security Helper Methods ───────────────────────────────────────────────

    @classmethod
    def _is_authorized(cls) -> bool:
        """Check if current user is authorized to register handlers."""
        try:
            from django.contrib.auth import get_user_model
            from rest_framework.permissions import IsAuthenticated
            
            user = get_user_model().objects.get(pk=cls._get_current_user())
            return user.is_authenticated and (
                user.is_staff or 
                user.has_perm('tasks.register_event_handlers')
            )
        except Exception:
            return False

    @classmethod
    def _is_event_allowed(cls, event: str) -> bool:
        """Check if event is in allowed list."""
        return event in _ALLOWED_EVENTS or not _ALLOWED_EVENTS

    @classmethod
    def _is_wildcard_allowed(cls, handler: Callable) -> bool:
        """Check if handler is allowed to use wildcards."""
        try:
            from django.contrib.auth import get_user_model
            user = get_user_model().objects.get(pk=cls._get_current_user())
            return user.is_superuser or user.has_perm('tasks.use_wildcard_handlers')
        except Exception:
            return False

    @classmethod
    def _get_current_user(cls) -> Optional[int]:
        """Get current user ID safely."""
        try:
            # Try to get from thread local (common in Django)
            import threading
            local_data = getattr(threading.current_thread(), 'user', None)
            if local_data and hasattr(local_data, 'id'):
                return local_data.id
            
            # Fallback to a safe default
            return 1  # Use system user as fallback
        except Exception:
            return None

    @classmethod
    def _validate_payload(cls, event: str, payload: Dict) -> Dict:
        """Validate and sanitize event payload."""
        if not isinstance(payload, dict):
            raise ValueError(f"Payload must be dict, got {type(payload)}")
        
        # Remove dangerous keys
        dangerous_keys = ['__class__', '__module__', '__dict__', '_state']
        sanitized = {k: v for k, v in payload.items() if k not in dangerous_keys}
        
        # Validate event-specific fields
        if event.startswith('payment.'):
            if 'amount' in sanitized:
                try:
                    sanitized['amount'] = float(sanitized['amount'])
                    if sanitized['amount'] < 0:
                        raise ValueError("Payment amount cannot be negative")
                except (ValueError, TypeError):
                    raise ValueError("Invalid payment amount format")
        
        if event.startswith('user.'):
            if 'user_id' in sanitized:
                try:
                    sanitized['user_id'] = int(sanitized['user_id'])
                    if sanitized['user_id'] <= 0:
                        raise ValueError("Invalid user_id")
                except (ValueError, TypeError):
                    raise ValueError("Invalid user_id format")
        
        return sanitized

    @classmethod
    def _is_rate_limited(cls, event: str) -> bool:
        """Check if event is rate limited."""
        try:
            rate_key = f"event_rate_{event}"
            count = cache.get(rate_key, 0)
            if count >= 100:  # Max 100 events per minute
                return True
            cache.set(rate_key, count + 1, timeout=60)
            return False
        except Exception:
            return False

    @classmethod
    def _log_handler_error(cls, handler_type: str, event: str, handler_name: str, error: str) -> None:
        """Log handler errors for security audit."""
        error_log = {
            'type': handler_type,
            'event': event,
            'handler': handler_name,
            'error': error,
            'timestamp': timezone.now().isoformat(),
            'user': cls._get_current_user()
        }
        cache.set(f"handler_error_{handler_name}_{int(timezone.now().timestamp())}", error_log, timeout=3600)

    @classmethod
    def get_security_audit(cls) -> Dict[str, Any]:
        """Return security audit information."""
        return {
            'registered_handlers': len(_HANDLER_REGISTRY),
            'sync_handlers': sum(len(handlers) for handlers in _HANDLERS.values()),
            'async_handlers': sum(len(handlers) for handlers in _ASYNC_HANDLERS.values()),
            'allowed_events': list(_ALLOWED_EVENTS),
            'recent_registrations': sorted(
                [v for v in _HANDLER_REGISTRY.values()], 
                key=lambda x: x['registered_at'], 
                reverse=True
            )[:10],
            'security_level': 'ENHANCED' if cls._is_authorized() else 'BASIC',
            'wildcard_handlers': len([k for k in _HANDLERS.keys() if k.endswith('.*')]),
            'rate_limit_status': 'ACTIVE'
        }


# ─── Default Event Handler Registration ────────────────────────────────────────

def _register_default_async(*args, **kwargs):
    """Startup registration of built-in handlers. No request/user exists at ready() time,
    so skip the per-user auth gate and don't let one policy-blocked event abort the rest."""
    kwargs.setdefault('require_auth', False)
    try:
        EventBus.on_async(*args, **kwargs)
    except PermissionDenied as exc:
        logger.warning('[EventBus] default handler %s skipped: %s', args[:2], exc)


def register_default_handlers():
    """
    Register the default event→task mappings.
    Called from tasks/apps.py ready().
    """

    # user.registered → welcome, onboarding, referral
    _register_default_async('user.registered',
                      'tasks.user_lifecycle_tasks.send_welcome_sequence')
    _register_default_async('user.registered',
                      'tasks.user_lifecycle_tasks.assign_onboarding_tasks')

    # task.completed → wallet, gamification, analytics, fraud
    _register_default_async('task.completed',
                      'tasks.gamification_tasks.update_streak_status')
    _register_default_async('task.completed',
                      'tasks.gamification_tasks.award_badges')
    _register_default_async('task.completed',
                      'tasks.gamification_tasks.process_milestone_rewards')
    _register_default_async('task.completed',
                      'tasks.fraud_detection_tasks.run_fraud_detection_scan')

    # offer.converted → credit publisher, update stats, CPA postback
    _register_default_async('offer.converted',
                      'tasks.cpalead_tasks.cpalead_credit_publisher')
    _register_default_async('offer.converted',
                      'tasks.cpalead_tasks.cpalead_update_offer_stats')

    # cpi.installed → verify, pay, fraud scan
    _register_default_async('cpi.installed',
                      'tasks.cpi_tasks.process_app_install_event')

    # payment.withdrawal_requested → fraud check, gateway
    _register_default_async('payment.withdrawal_requested',
                      'tasks.payment_tasks.process_withdrawal_requests')
    _register_default_async('payment.withdrawal_requested',
                      'tasks.fraud_detection_tasks.flag_suspicious_withdrawal')

    # fraud.detected → alert admins, suspend
    _register_default_async('fraud.detected',
                      'tasks.notification_tasks.send_bulk_push_notifications')

    # publisher.tier_changed → adjust revenue share
    _register_default_async('publisher.tier_changed',
                      'tasks.publisher_tasks.adjust_revenue_share')

    # survey.completed → verify, payout
    _register_default_async('survey.completed',
                      'tasks.survey_tasks.verify_survey_completion')

    logger.info("[EventBus] Default handlers registered")
