# api/payment_gateways/integrations_adapters/FraudAdapter.py
# Bridge between payment_gateways and api.fraud_detection

from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


class FraudAdapter:
    """
    Bridges payment_gateways with your existing api.fraud_detection app.
    Calls YOUR fraud detection system instead of the built-in one.
    """

    def check(self, user, amount: Decimal, gateway: str,
              ip_address: str = '', **kwargs) -> dict:
        """
        Run fraud check using your existing fraud_detection app.
        Falls back to payment_gateways internal fraud if unavailable.
        """
        # Try your existing fraud detection app first
        try:
            from api.fraud_detection.services import FraudDetectionService
            result = FraudDetectionService().check_transaction(
                user=user,
                amount=float(amount),
                gateway=gateway,
                ip_address=ip_address,
            )
            # Normalize to payment_gateways format
            return {
                'risk_score': result.get('risk_score', 0),
                'risk_level': result.get('risk_level', 'low'),
                'action':     result.get('action', 'allow'),
                'reasons':    result.get('reasons', []),
            }
        except ImportError:
            pass

        # Fallback to payment_gateways internal fraud detector
        try:
            from api.payment_gateways.fraud.FraudDetector import FraudDetector
            return FraudDetector().check(user, amount, gateway, ip_address=ip_address)
        except Exception as e:
            logger.warning(f'FraudAdapter check failed: {e}')
            return {'risk_score': 0, 'risk_level': 'low', 'action': 'allow', 'reasons': []}
