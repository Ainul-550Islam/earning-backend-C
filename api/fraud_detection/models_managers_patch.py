# =============================================================================
# fraud_detection/models_managers_patch.py
# =============================================================================
"""
Connects custom Manager classes (managers.py) to their models at runtime.

Two usage modes:

  MODE A — called from apps.py ready() (recommended):
      from api.fraud_detection.models_managers_patch import apply_manager_patches
      apply_manager_patches()

  MODE B — add directly to each model class in models.py:
      class FraudRule(TimeStampedModel):
          objects = FraudRuleManager()
          ...

This module implements Mode A so models.py does NOT need to be modified.

Manager → Model mapping:
  FraudRuleManager        → FraudRule
  FraudCaseManager        → FraudCase
  FraudAlertManager       → FraudAlert
  FraudRiskProfileManager → UserRiskProfile
  DeviceFingerprintManager→ DeviceFingerprint
  FraudSuspiciousIPManager→ IPReputation
  BaseIntegrityManager    → FraudWhitelist, FraudCaseEvidence, FraudCaseAction
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_PATCHES_APPLIED = False


def apply_manager_patches() -> None:
    """
    Attach all custom managers to their models.
    Idempotent — calling twice is safe.
    """
    global _PATCHES_APPLIED
    if _PATCHES_APPLIED:
        return

    errors = []

    # ── Import managers ───────────────────────────────────────────────────────
    try:
        from api.fraud_detection.managers import (
            FraudRuleManager,
            FraudCaseManager,
            FraudAlertManager,
            FraudRiskProfileManager,
            DeviceFingerprintManager,
            FraudSuspiciousIPManager,
            BaseIntegrityManager,
        )
    except ImportError as exc:
        logger.error(
            "models_managers_patch: could not import managers — patch skipped: %s", exc
        )
        return

    # ── Import models ─────────────────────────────────────────────────────────
    try:
        from api.fraud_detection.models import (
            FraudRule,
            FraudCase,
            FraudAlert,
            UserRiskProfile,
            DeviceFingerprint,
            IPReputation,
            FraudWhitelist,
            FraudCaseEvidence,
            FraudCaseAction,
            FraudAttempt,
            FraudNotification,
            OfferCompletion,
            FraudPattern,
            FraudSettings,
        )
    except ImportError as exc:
        logger.error(
            "models_managers_patch: could not import models — patch skipped: %s", exc
        )
        return

    # ── Patch mapping ─────────────────────────────────────────────────────────
    patches = [
        (FraudRule,          FraudRuleManager,          'FraudRuleManager'),
        (FraudCase,          FraudCaseManager,          'FraudCaseManager'),
        (FraudAlert,         FraudAlertManager,         'FraudAlertManager'),
        (UserRiskProfile,    FraudRiskProfileManager,   'FraudRiskProfileManager'),
        (DeviceFingerprint,  DeviceFingerprintManager,  'DeviceFingerprintManager'),
        (IPReputation,       FraudSuspiciousIPManager,  'FraudSuspiciousIPManager'),
        (FraudWhitelist,     BaseIntegrityManager,      'BaseIntegrityManager'),
        (FraudCaseEvidence,  BaseIntegrityManager,      'BaseIntegrityManager'),
        (FraudCaseAction,    BaseIntegrityManager,      'BaseIntegrityManager'),
    ]

    patched = 0
    for model_cls, manager_cls, manager_name in patches:
        try:
            # Only patch if the model still uses the default Manager
            current = model_cls.__dict__.get('objects')
            if current is None or type(current).__name__ == 'Manager':
                mgr_instance = manager_cls()
                mgr_instance.auto_created = True
                # Django manager contribute_to_class wires the manager properly
                mgr_instance.contribute_to_class(model_cls, 'objects')
                patched += 1
                logger.debug(
                    "models_managers_patch: %s.objects → %s",
                    model_cls.__name__, manager_name,
                )
            else:
                logger.debug(
                    "models_managers_patch: %s already has custom manager (%s) — skipped",
                    model_cls.__name__, type(current).__name__,
                )
        except Exception as exc:
            err_msg = f"{model_cls.__name__} → {manager_name}: {exc}"
            errors.append(err_msg)
            logger.warning("models_managers_patch error: %s", err_msg)

    if errors:
        logger.warning(
            "models_managers_patch: %d patches failed, %d succeeded. Errors: %s",
            len(errors), patched, '; '.join(errors),
        )
    else:
        logger.info(
            "models_managers_patch: %d manager(s) patched successfully", patched
        )

    _PATCHES_APPLIED = True


# =============================================================================
# Querysets patch — wire querysets.py custom querysets to the patched managers
# =============================================================================

def apply_queryset_patches() -> None:
    """
    Wire FraudDetectionQuerySet, FraudCaseQuerySet etc. from querysets.py
    to their respective model managers as the base queryset.

    Called from apply_manager_patches() after managers are attached.
    """
    try:
        from api.fraud_detection import querysets as qs_module
        from api.fraud_detection.models import (
            FraudRule, FraudCase, FraudAlert,
            UserRiskProfile, DeviceFingerprint,
            IPReputation, FraudAttempt, FraudWhitelist,
        )

        qs_map = {
            'FraudDetectionQuerySet': FraudAttempt,
            'FraudCaseQuerySet':      FraudCase,
            'FraudAlertQuerySet':     FraudAlert,
            'FraudRuleQuerySet':      FraudRule,
            'UserRiskProfileQuerySet': UserRiskProfile,
            'DeviceFingerprintQuerySet': DeviceFingerprint,
            'IPReputationQuerySet':   IPReputation,
            'FraudWhitelistQuerySet': FraudWhitelist,
        }

        patched = 0
        for qs_name, model_cls in qs_map.items():
            qs_cls = getattr(qs_module, qs_name, None)
            if qs_cls is None:
                continue
            try:
                mgr = model_cls.objects
                if hasattr(mgr, '_queryset_class'):
                    mgr._queryset_class = qs_cls
                    patched += 1
                    logger.debug(
                        "apply_queryset_patches: %s.objects queryset → %s",
                        model_cls.__name__, qs_name,
                    )
            except Exception as exc:
                logger.debug(
                    "apply_queryset_patches: %s → %s failed: %s",
                    model_cls.__name__, qs_name, exc,
                )

        if patched:
            logger.info("apply_queryset_patches: %d queryset(s) wired", patched)

    except ImportError as exc:
        logger.warning("querysets.py not available — queryset patch skipped: %s", exc)
    except Exception as exc:
        logger.error("apply_queryset_patches error: %s", exc)


# =============================================================================
# Convenience: run both patches together
# =============================================================================

def patch_all() -> None:
    """Apply manager patches + queryset patches in one call."""
    apply_manager_patches()
    apply_queryset_patches()
