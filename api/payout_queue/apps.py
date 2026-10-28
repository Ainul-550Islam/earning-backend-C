"""
payout_queue/apps.py  ← v8 PRODUCTION UPDATE

CHANGES v8 (Production Gap #1 — Monitoring):

  ① Sentry SDK initialization added to ready()

     Before:  Exceptions were only written to the Python logger.
              In production, a batch processing failure at 2 AM had no alert,
              no stack trace capture, no context — developers found out from
              user reports, not from error tracking.

     After:   _init_sentry() is called in ready(). It reads SENTRY_DSN from
              settings (which reads from .env). If the DSN is set:
                - DjangoIntegration: captures unhandled view/middleware errors
                - CeleryIntegration: captures unhandled Celery task errors
                  (process_batch_async, deliver_webhook_event, etc.)
                - LoggingIntegration: forwards ERROR+ log records to Sentry
              If SENTRY_DSN is not set (dev/test), initialization is silently
              skipped — no crash, no noise.

     Setup:
        1. pip install sentry-sdk[django,celery]
        2. Add to .env: SENTRY_DSN=https://xxx@oXXX.ingest.sentry.io/XXX
        3. Add to settings: SENTRY_DSN = env("SENTRY_DSN", default="")
        4. Deploy — Sentry will auto-capture all unhandled exceptions.

Original fixes preserved:
  - Merged duplicate ready() (bug: two def ready() — Python only kept the 2nd)
  - Signal receiver import
  - Admin force-register
"""

from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _

import logging

logger = logging.getLogger(__name__)

class PayoutQueueConfig(AppConfig):
    name                = "api.payout_queue"
    label               = "payout_queue"
    verbose_name        = _("Payout Queue")
    default_auto_field  = "django.db.models.BigAutoField"

    def ready(self) -> None:
        # ── Step 1: Sentry (v8) ──────────────────────────────────────────────
        self._init_sentry()

        # ── Step 2: Signal receivers ─────────────────────────────────────────
        # FIX (original): Two `def ready()` methods existed — Python kept only
        # the second, so receivers were never imported and signals never fired.
        # Both bodies are now merged into this single ready().
        try:
            from . import receivers  # noqa: F401
        except Exception as exc:
            logger.error(
                "PayoutQueueConfig.ready(): failed to import receivers: %s", exc
            )

        # ── Step 3: Admin force-register ─────────────────────────────────────
        try:
            from api.payout_queue.admin import _force_register_payout_queue
            _force_register_payout_queue()
        except Exception:
            pass

    # -------------------------------------------------------------------------

    def _init_sentry(self) -> None:
        """
        Initialize Sentry SDK for error tracking and performance monitoring.

        Reads from settings:
            SENTRY_DSN              (str)  — required for init; empty = disabled
            SENTRY_ENVIRONMENT      (str)  — default "production"
            SENTRY_RELEASE          (str)  — default None (git SHA if available)
            SENTRY_TRACES_RATE      (float)— default 0.05 (5% of transactions)
            SENTRY_PROFILES_RATE    (float)— default 0.0  (disabled by default)
            SENTRY_SEND_PII         (bool) — default False (GDPR safe)

        Integrations enabled:
            DjangoIntegration  — views, middleware, DB queries, signals
            CeleryIntegration  — Celery tasks (process_batch_async, webhooks)
            LoggingIntegration — ERROR+ log records forwarded to Sentry
        """
        from django.conf import settings as _settings

        dsn: str = getattr(_settings, "SENTRY_DSN", "") or ""
        if not dsn:
            logger.debug(
                "_init_sentry: SENTRY_DSN not set — Sentry disabled. "
                "Add SENTRY_DSN to .env to enable error tracking."
            )
            return

        try:
            import sentry_sdk
            from sentry_sdk.integrations.django import DjangoIntegration
            from sentry_sdk.integrations.celery import CeleryIntegration
            from sentry_sdk.integrations.logging import LoggingIntegration

            import logging as _logging

            logging_integration = LoggingIntegration(
                level=_logging.INFO,      # Capture INFO and above as breadcrumbs
                event_level=_logging.ERROR,  # Send ERROR+ as Sentry events
            )

            # Determine release from settings or git
            release: str = getattr(_settings, "SENTRY_RELEASE", "") or ""
            if not release:
                try:
                    import subprocess
                    release = subprocess.check_output(
                        ["git", "rev-parse", "--short", "HEAD"],
                        stderr=subprocess.DEVNULL,
                    ).decode().strip()
                except Exception:
                    release = "unknown"

            sentry_sdk.init(
                dsn=dsn,
                environment=getattr(_settings, "SENTRY_ENVIRONMENT", "production"),
                release=release,
                integrations=[
                    DjangoIntegration(
                        transaction_style="url",
                        middleware_spans=True,
                        signals_spans=False,   # Avoid noise from Django signals
                        cache_spans=True,
                    ),
                    CeleryIntegration(
                        monitor_beat_tasks=True,
                        propagate_traces=True,
                    ),
                    logging_integration,
                ],
                # Performance monitoring
                traces_sample_rate=float(
                    getattr(_settings, "SENTRY_TRACES_RATE", 0.05)
                ),
                profiles_sample_rate=float(
                    getattr(_settings, "SENTRY_PROFILES_RATE", 0.0)
                ),
                # Privacy
                send_default_pii=bool(
                    getattr(_settings, "SENTRY_SEND_PII", False)
                ),
                # Attach request body to events (safe — no PII in payout_queue requests)
                request_bodies="medium",
                # Filter out health check and static file noise
                traces_sampler=_sentry_traces_sampler,
            )

            logger.info(
                "PayoutQueueConfig._init_sentry: Sentry initialized. "
                "env=%s release=%s traces=%.0f%% profiles=%.0f%%",
                getattr(_settings, "SENTRY_ENVIRONMENT", "production"),
                release,
                float(getattr(_settings, "SENTRY_TRACES_RATE", 0.05)) * 100,
                float(getattr(_settings, "SENTRY_PROFILES_RATE", 0.0)) * 100,
            )

        except ImportError:
            logger.warning(
                "_init_sentry: sentry-sdk is not installed. "
                "Run: pip install 'sentry-sdk[django,celery]' "
                "to enable error tracking."
            )
        except Exception as exc:
            # Never crash startup because Sentry failed to initialize.
            logger.error(
                "_init_sentry: Sentry initialization failed: %s. "
                "Error tracking is disabled. Check SENTRY_DSN in .env.",
                exc,
            )

def _sentry_traces_sampler(sampling_context: dict) -> float:
    """
    Custom Sentry traces sampler.
    Drops health-check and static-file transactions (zero business value),
    samples everything else at SENTRY_TRACES_RATE.
    """
    from django.conf import settings as _settings

    wsgi_environ = sampling_context.get("wsgi_environ", {})
    path = wsgi_environ.get("PATH_INFO", "")

    # Drop health check, static files, and media — they create noise
    if any(path.startswith(prefix) for prefix in (
        "/payout-queue/health/",
        "/static/",
        "/media/",
        "/favicon.ico",
    )):
        return 0.0

    return float(getattr(_settings, "SENTRY_TRACES_RATE", 0.05))
