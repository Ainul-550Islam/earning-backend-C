"""CORE_FILES/plugins.py — Re-exports plugin registry."""
from ..plugins import (
    BasePaymentGatewayPlugin, register_payment_gateway, get_payment_gateway,
    BaseFraudDetectorPlugin, register_fraud_detector, get_fraud_detectors,
    BaseRewardEnginePlugin, register_reward_engine, get_reward_engine,
    list_payment_gateways,
)
