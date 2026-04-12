"""
api/monetization_tools/plugins.py
====================================
Plugin registry — allows third-party apps to extend
monetization_tools (e.g., custom payment gateways,
custom fraud detectors, custom reward engines).
"""

import logging
from typing import Dict, Type

logger = logging.getLogger(__name__)

_payment_gateways: Dict[str, object]   = {}
_fraud_detectors:  Dict[str, object]   = {}
_reward_engines:   Dict[str, object]   = {}


# ---------------------------------------------------------------------------
# Payment Gateway plugins
# ---------------------------------------------------------------------------

class BasePaymentGatewayPlugin:
    """Subclass this to add a new payment gateway."""

    name: str = 'base'

    def initiate(self, user, amount, currency, **kwargs) -> dict:
        raise NotImplementedError

    def verify(self, gateway_txn_id: str, **kwargs) -> dict:
        raise NotImplementedError

    def refund(self, gateway_txn_id: str, amount=None, **kwargs) -> dict:
        raise NotImplementedError


def register_payment_gateway(cls: Type[BasePaymentGatewayPlugin]) -> Type[BasePaymentGatewayPlugin]:
    """Decorator: register a payment gateway plugin."""
    instance = cls()
    _payment_gateways[cls.name] = instance
    logger.info("Payment gateway plugin registered: %s", cls.name)
    return cls


def get_payment_gateway(name: str) -> BasePaymentGatewayPlugin:
    gw = _payment_gateways.get(name)
    if not gw:
        raise KeyError(f"Payment gateway plugin '{name}' not registered.")
    return gw


def list_payment_gateways() -> list:
    return list(_payment_gateways.keys())


# ---------------------------------------------------------------------------
# Fraud Detector plugins
# ---------------------------------------------------------------------------

class BaseFraudDetectorPlugin:
    """Subclass this to plug in a custom fraud detection engine."""

    name: str = 'base'

    def score(self, completion) -> int:
        """Return a fraud score 0-100 for an OfferCompletion."""
        return 0

    def signals(self, completion) -> list:
        """Return a list of fraud signal strings."""
        return []


def register_fraud_detector(cls: Type[BaseFraudDetectorPlugin]) -> Type[BaseFraudDetectorPlugin]:
    instance = cls()
    _fraud_detectors[cls.name] = instance
    logger.info("Fraud detector plugin registered: %s", cls.name)
    return cls


def get_fraud_detectors() -> list:
    return list(_fraud_detectors.values())


# ---------------------------------------------------------------------------
# Reward Engine plugins
# ---------------------------------------------------------------------------

class BaseRewardEnginePlugin:
    """Subclass to customise how rewards are calculated for an offer."""

    name: str = 'base'

    def calculate_reward(self, offer, user) -> float:
        """Return the reward (coins) for completing this offer by this user."""
        return float(offer.point_value)


def register_reward_engine(cls: Type[BaseRewardEnginePlugin]) -> Type[BaseRewardEnginePlugin]:
    instance = cls()
    _reward_engines[cls.name] = instance
    logger.info("Reward engine plugin registered: %s", cls.name)
    return cls


def get_reward_engine(name: str = 'base') -> BaseRewardEnginePlugin:
    return _reward_engines.get(name, BaseRewardEnginePlugin())
