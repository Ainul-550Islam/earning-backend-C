# =============================================================================
# fraud_detection/apps.py
# =============================================================================
"""
Fraud Detection Django App Configuration — COMPLETE WIRING

Changes vs previous version:
  [NEW] signals_cap imported → capital/regulatory signals now active
  [NEW] INTEGRATION_SYSTEM app-ready hook → bridges initialize on startup
  [NEW] celery_beat_config schedule registered on startup
  [KEPT] signals_kb, hooks, throttling, plugins, registry, caching, model patches
"""

import logging

from django.apps import AppConfig

logger = logging.getLogger(__name__)


class FraudDetectionConfig(AppConfig):
    """Fraud Detection App Configuration."""

    default_auto_field = "django.db.models.BigAutoField"
    name               = "api.fraud_detection"
    label              = "fraud_detection"
    verbose_name       = "Fraud Detection & Prevention"

    def ready(self) -> None:
        """
        Initialize fraud detection subsystems on startup.
        Execution order is intentional — do not reorder.
        """

        # ── 1. Core signal handlers ───────────────────────────────────────────
        self._safe_import("api.fraud_detection.signals",
                          "Core fraud detection signals")

        # ── 2. Additional model/event receivers ───────────────────────────────
        self._safe_import("api.fraud_detection.receivers",
                          "Model event receivers")

        # ── 3. Knowledge-base ML signal handlers ──────────────────────────────
        #    Feeds alert/case data to IsolationForest + risk-vector feature store
        self._safe_import("api.fraud_detection.signals_kb",
                          "Knowledge-base ML signals")

        # ── 4. Capital / regulatory signal handlers ───────────────────────────
        #    Sends major-fraud, regulatory-breach, AML signals.
        #    WAS FLOATING — now properly wired.
        self._safe_import("api.fraud_detection.signals_cap",
                          "Capital & regulatory signals")

        # -- 5. Hooks registry --
        #    Built-in hooks are registered from settings when hooks.py is imported.
        try:
            from api.fraud_detection.hooks import get_hook_registry
            _hr = get_hook_registry()
            logger.info(
                "Hooks ready: %d global, %d point-specific",
                len(_hr.global_hooks),
                sum(len(v) for v in _hr.hooks.values()),
            )
        except ImportError as exc:
            logger.warning("hooks.py not available - hooks disabled: %s", exc)
        except Exception as exc:
            logger.error("Error registering hooks: %s", exc, exc_info=True)

        # ── 6. AdaptiveThrottlingManager ─────────────────────────────────────
        try:
            from api.fraud_detection.throttling import adaptive_throttling_manager  # noqa: F401
            logger.info("AdaptiveThrottlingManager initialized")
        except ImportError as exc:
            logger.warning("throttling.py not available: %s", exc)
        except Exception as exc:
            logger.error("Error initializing throttling: %s", exc, exc_info=True)

        # ── 7. Plugin system ──────────────────────────────────────────────────
        try:
            from api.fraud_detection.plugins import get_plugin_manager
            pm = get_plugin_manager()
            logger.info("Plugin system initialized: %d plugins", len(pm.get_all_status()))
        except ImportError as exc:
            logger.warning("plugins.py not available: %s", exc)
        except Exception as exc:
            logger.error("Error initializing plugins: %s", exc, exc_info=True)

        # -- 8. Component + Configuration registries --
        try:
            from api.fraud_detection.registry import initialize_registries
            initialize_registries()
            logger.info("Component + config registries loaded")
        except ImportError as exc:
            logger.warning("registry.py not available: %s", exc)
        except Exception as exc:
            logger.error("Error initializing registries: %s", exc, exc_info=True)

        # ── 9. Cache warm-up ──────────────────────────────────────────────────
        try:
            from api.fraud_detection.caching import get_redis_cache_manager
            mgr = get_redis_cache_manager()
            if mgr.is_available():
                mgr.warmup_fraud_rules()
                logger.info("Cache warm-up complete")
            else:
                logger.warning("Redis unavailable — cache warm-up skipped")
        except ImportError as exc:
            logger.warning("caching.py not available: %s", exc)
        except Exception as exc:
            logger.error("Error during cache warm-up: %s", exc, exc_info=True)

        # ── 10. Model clean() patches ─────────────────────────────────────────
        try:
            from api.fraud_detection.model_clean_methods import patch_models
            patch_models()
            logger.info("Model clean() methods patched")
        except ImportError:
            pass
        except Exception as exc:
            logger.error("Error patching models: %s", exc, exc_info=True)

        # ── 11. Custom manager patches ────────────────────────────────────────
        try:
            from api.fraud_detection.models_managers_patch import apply_manager_patches
            apply_manager_patches()
            logger.info("Custom model managers patched")
        except ImportError:
            pass
        except Exception as exc:
            logger.error("Error applying manager patches: %s", exc, exc_info=True)

        # ── 12. Celery beat schedule ──────────────────────────────────────────
        #    WAS FLOATING — celery_beat_config.py was never applied.
        try:
            from api.fraud_detection.celery_beat_config import register_fraud_beat_schedule
            register_fraud_beat_schedule()
            logger.info("Celery beat schedule registered")
        except ImportError as exc:
            logger.warning("celery_beat_config.py not available: %s", exc)
        except Exception as exc:
            logger.error("Error registering beat schedule: %s", exc, exc_info=True)

        # ── 13. INTEGRATION_SYSTEM bridges ───────────────────────────────────
        #    WAS FLOATING — bridge.py, auth_bridge.py, data_bridge.py never init'd.
        try:
            from api.fraud_detection.INTEGRATION_SYSTEM.bridge import get_bridge_system
            from api.fraud_detection.INTEGRATION_SYSTEM.auth_bridge import get_auth_bridge
            from api.fraud_detection.INTEGRATION_SYSTEM.data_bridge import get_data_bridge
            # constructors do the setup (lazy singletons); there is no separate initialize()
            get_bridge_system(); get_auth_bridge(); get_data_bridge()
            logger.info("Integration bridges initialized")
        except ImportError as exc:
            logger.warning("INTEGRATION_SYSTEM not available: %s", exc)
        except Exception as exc:
            logger.error("Error initializing integration bridge: %s", exc, exc_info=True)

        # ── 14. Feature flags ─────────────────────────────────────────────────
        #    WAS FLOATING — feature_flags.py was never initialized.
        try:
            from api.fraud_detection.feature_flags import feature_flag_manager  # noqa: F401
            logger.info("Feature flags loaded")
        except ImportError as exc:
            logger.warning("feature_flags.py not available: %s", exc)
        except Exception as exc:
            logger.error("Error loading feature flags: %s", exc, exc_info=True)


        # ── 15. KYC service warm-up ───────────────────────────────────────────
        try:
            from api.fraud_detection.kyc_service import get_kyc_service
            get_kyc_service()  # initialise singleton
            logger.info("KYC service initialised")
        except Exception as exc:
            logger.warning("KYC service init failed: %s", exc)

        # ── 16. MFA service warm-up ───────────────────────────────────────────
        try:
            from api.fraud_detection.mfa_validator import get_mfa_service
            get_mfa_service()
            logger.info("MFA service initialised")
        except Exception as exc:
            logger.warning("MFA service init failed: %s", exc)

        # ── 17. Chargeback service warm-up ────────────────────────────────────
        try:
            from api.fraud_detection.services.ChargebackService import get_chargeback_service
            get_chargeback_service()
            logger.info("ChargebackService initialised")
        except Exception as exc:
            logger.warning("ChargebackService init failed: %s", exc)

        # ── 18. SLA Manager warm-up ───────────────────────────────────────────
        try:
            from api.fraud_detection.sla_manager import get_sla_manager
            get_sla_manager()
            logger.info("SLAManager initialised")
        except Exception as exc:
            logger.warning("SLAManager init failed: %s", exc)

        # ── 19. Feedback service warm-up ──────────────────────────────────────
        try:
            from api.fraud_detection.feedback import get_feedback_service
            get_feedback_service()
            logger.info("FeedbackService initialised")
        except Exception as exc:
            logger.warning("FeedbackService init failed: %s", exc)

        # ── 20. Report scheduler warm-up ──────────────────────────────────────
        try:
            from api.fraud_detection.report_scheduler import get_report_scheduler
            get_report_scheduler()
            logger.info("ReportScheduler initialised")
        except Exception as exc:
            logger.warning("ReportScheduler init failed: %s", exc)

        logger.info("FraudDetectionConfig.ready() completed ✓")

    # ── helper ───────────────────────────────────────────────────────────────
    @staticmethod
    def _safe_import(module_path: str, label: str) -> None:
        """Import a module for its side-effects; log success/failure."""
        try:
            import importlib
            importlib.import_module(module_path)
            logger.info("%s loaded", label)
        except ImportError as exc:
            logger.warning("%s not available: %s", label, exc)
        except Exception as exc:
            logger.error("Error loading %s: %s", label, exc, exc_info=True)
