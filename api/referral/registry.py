# api/referral/registry.py
# Centralized model and service registry for the referral module
# Single place to look up all registered models, services, viewsets
# ============================================================

import logging
from typing import Any, Dict, List, Optional, Type

logger = logging.getLogger(__name__)


class ReferralRegistry:
    """
    Central registry for all referral module components.
    Provides dynamic model/service lookup without tight coupling.

    Usage:
        from api.referral.registry import registry
        Model = registry.get_model('Referral')
        service = registry.get_service('ReferralService')
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._models    = {}
            cls._instance._services  = {}
            cls._instance._viewsets  = {}
            cls._instance._tasks     = {}
            cls._instance._signals   = {}
        return cls._instance

    # ── Model Registry ────────────────────────────────────────────────────────

    def register_model(self, name: str, model_class: Type) -> None:
        self._models[name] = model_class
        logger.debug(f'[Registry] Model registered: {name}')

    def get_model(self, name: str) -> Optional[Type]:
        model = self._models.get(name)
        if not model:
            try:
                from django.apps import apps
                model = apps.get_model('referral', name)
                self._models[name] = model
            except Exception:
                pass
        return model

    def list_models(self) -> List[str]:
        return list(self._models.keys())

    # ── Service Registry ──────────────────────────────────────────────────────

    def register_service(self, name: str, service_class: Type) -> None:
        self._services[name] = service_class

    def get_service(self, name: str) -> Optional[Type]:
        return self._services.get(name)

    # ── ViewSet Registry ──────────────────────────────────────────────────────

    def register_viewset(self, name: str, viewset_class: Type) -> None:
        self._viewsets[name] = viewset_class

    def get_viewset(self, name: str) -> Optional[Type]:
        return self._viewsets.get(name)

    # ── Status ────────────────────────────────────────────────────────────────

    def get_status(self) -> Dict:
        return {
            'models':   list(self._models.keys()),
            'services': list(self._services.keys()),
            'viewsets': list(self._viewsets.keys()),
            'total_models': len(self._models),
        }


def _populate_registry(r: ReferralRegistry) -> None:
    """Auto-register all referral models. Called from apps.py ready()."""
    model_names = [
        'Referral', 'ReferralChain', 'ReferralSettings', 'ReferralEarning',
        'ReferralLeaderboard', 'ReferralCode', 'ReferralLink', 'ReferralRelationship',
        'ReferralTree', 'ReferralCampaign', 'ReferralBonus', 'ReferralContest',
        'CommissionLog', 'CommissionRule', 'CommissionHold', 'CommissionClawback',
        'CommissionPayout', 'ReferralFraudRule', 'ReferralFraudLog', 'SuspiciousReferral',
        'ReferralInsight', 'TopReferrer', 'ReferralLTV', 'ReferralSubID',
        'GeoCommissionRate', 'ReferralQRCode', 'ReferralEmailInvitation',
        'ReferralSocialShare', 'DoubleSidedBonusConfig', 'CommissionExpiryRule',
        'RecurringCommissionLog', 'UserPayoutPreference', 'ViralCoefficient',
        'UserStreakTracker', 'ReferralStreakBonus', 'ReferralSurgeBonus',
        'CommissionTierProgression', 'UserCommissionTier', 'AffiliateProfile',
        'ReferralCreditBalance', 'ReferralCreditTransaction',
    ]
    for name in model_names:
        try:
            from django.apps import apps
            model = apps.get_model('referral', name)
            r.register_model(name, model)
        except Exception:
            pass
    logger.info(f'[Registry] {len(r._models)} models registered')


# ── Global Singleton ──────────────────────────────────────────────────────────

registry = ReferralRegistry()