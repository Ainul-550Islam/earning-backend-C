"""
Messaging AppConfig — connects all receivers and signals on startup.

Wires:
  - messaging.receivers      (general messaging signal handlers)
  - messaging.receivers_cpa  (CPA platform signal handlers)

Both are loaded inside ready() so signal dispatch works correctly
from the very first request / Celery task.
"""
from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class MessagingConfig(AppConfig):
    name = "api.messaging"
    label = "messaging"
    verbose_name = _("Messaging")
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        """
        Import signal receivers so Django registers them.

        Called once by Django when the app registry is fully populated.
        Must import both receiver modules here — importing them anywhere
        else (e.g. top of views.py) risks running before models are ready.
        """
        import logging
        log = logging.getLogger(__name__)

        # ── General messaging receivers ───────────────────────────────────────
        try:
            from . import receivers  # noqa: F401
            log.debug("MessagingConfig: general receivers connected.")
        except Exception as exc:
            log.error(
                "MessagingConfig.ready(): failed to import receivers: %s", exc,
                exc_info=True,
            )

        # ── CPA platform receivers ────────────────────────────────────────────
        try:
            from . import receivers_cpa  # noqa: F401
            log.debug("MessagingConfig: CPA receivers connected.")
        except Exception as exc:
            log.error(
                "MessagingConfig.ready(): failed to import receivers_cpa: %s", exc,
                exc_info=True,
            )

        # ── Validate middleware classes are wired (warn, do not crash) ─────────
        try:
            from django.conf import settings as _s
            mw_list = getattr(_s, "MIDDLEWARE", [])
            required_mw = [
                "api.messaging.middleware.InboxUnreadCountMiddleware",
                "api.messaging.middleware.MessagingRequestTimingMiddleware",
                "api.messaging.middleware.WebSocketRateLimitMiddleware",
            ]
            missing_mw = [m for m in required_mw if m not in mw_list]
            if missing_mw:
                log.warning(
                    "MessagingConfig: %d messaging middleware class(es) not in "
                    "settings.MIDDLEWARE — unread counts, request timing, and WS "
                    "rate limiting will NOT work.\n"
                    "Fix: add to settings.py MIDDLEWARE list:\n    %s",
                    len(missing_mw),
                    "\n    ".join(missing_mw),
                )
        except Exception:
            pass  # Never crash ready()

        # ── Validate Celery beat schedule is wired (warn, do not crash) ───────
        try:
            from django.conf import settings
            beat = getattr(settings, "CELERY_BEAT_SCHEDULE", {})
            required_tasks = [
                "api.messaging.send_scheduled_messages",
                "api.messaging.cleanup_presence",
                "api.messaging.expire_disappearing_messages",
                "api.messaging.send_scheduled_broadcasts",
                "api.messaging.send_scheduled_cpa_broadcasts",
                "api.messaging.send_payout_reminders",
            ]
            _have = set(beat) | {str(v.get("task")) for v in beat.values() if isinstance(v, dict)}
            missing = [t for t in required_tasks if t not in _have and t.replace("api.", "", 1) not in _have]
            if missing:
                log.warning(
                    "MessagingConfig: %d periodic task(s) not found in "
                    "CELERY_BEAT_SCHEDULE. Scheduled messages, broadcasts and "
                    "cleanup jobs will NOT run automatically.\n"
                    "Fix: add to settings.py:\n"
                    "    from api.messaging.celery_beat_config import MESSAGING_BEAT_SCHEDULE\n"
                    "    CELERY_BEAT_SCHEDULE.update(MESSAGING_BEAT_SCHEDULE)\n"
                    "Missing: %s",
                    len(missing),
                    missing,
                )
        except Exception:
            pass  # Never crash ready() due to a settings check

        # ── Validate WS Origin-validator has a non-empty allowlist somewhere
        #    in its fallback chain (warn, do not crash) ─────────────────────
        try:
            from django.conf import settings as _s
            has_explicit = bool(getattr(_s, "MESSAGING_WS_ALLOWED_ORIGINS", None))
            has_cors = bool(getattr(_s, "CORS_ALLOWED_ORIGINS", None))
            has_allowed_hosts = bool(getattr(_s, "ALLOWED_HOSTS", None))
            if not (has_explicit or has_cors or has_allowed_hosts) and not getattr(_s, "DEBUG", False):
                log.warning(
                    "MessagingConfig: MESSAGING_WS_ALLOWED_ORIGINS, "
                    "CORS_ALLOWED_ORIGINS, and ALLOWED_HOSTS are all empty "
                    "with DEBUG=False. messaging.routing.application's Origin "
                    "validator fails safe by denying ALL WebSocket connections "
                    "in this state, rather than allowing them - fix by setting "
                    "at least one of the three."
                )
        except Exception:
            pass  # Never crash ready() due to a settings check

        # ── Validate Elasticsearch index (warn only) ──────────────────────────
        try:
            from django.conf import settings
            if getattr(settings, "ELASTICSEARCH_URL", None) and getattr(settings, "MESSAGING_ES_CHECK_ON_STARTUP", False):
                from .utils.search_engine import ensure_index_exists
                ensure_index_exists()
        except Exception as exc:
            log.debug("MessagingConfig: ES index check skipped: %s", exc)
