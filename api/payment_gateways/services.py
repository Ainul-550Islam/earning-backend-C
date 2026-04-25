# api/payment_gateways/services.py
# Root services module — full service registry and convenience imports
# "Do not summarize or skip any logic. Provide the full code."

import logging
logger = logging.getLogger(__name__)

# ── Core Services ──────────────────────────────────────────────────────────────
from api.payment_gateways.services.PaymentFactory        import PaymentFactory
from api.payment_gateways.services.PaymentProcessor      import PaymentProcessor
from api.payment_gateways.services.PaymentValidator      import PaymentValidator
from api.payment_gateways.services.ReceiptGenerator      import ReceiptGenerator

# ── Deposit & Withdrawal ───────────────────────────────────────────────────────
from api.payment_gateways.services.DepositService        import DepositService
from api.payment_gateways.services.WithdrawalGatewayService import WithdrawalGatewayService

# ── Routing & Fallback ─────────────────────────────────────────────────────────
from api.payment_gateways.services.GatewayRouterService  import GatewayRouterService
from api.payment_gateways.services.GatewayFallbackService import GatewayFallbackService

# ── Monitoring ────────────────────────────────────────────────────────────────
from api.payment_gateways.services.GatewayHealthService  import GatewayHealthService
from api.payment_gateways.services.GatewayAnalyticsService import GatewayAnalyticsService
from api.payment_gateways.services.ReconciliationService import ReconciliationService

# ── Security ──────────────────────────────────────────────────────────────────
from api.payment_gateways.services.WebhookVerifierService import WebhookVerifierService

# ── Currency & Pricing ────────────────────────────────────────────────────────
from api.payment_gateways.services.MultiCurrencyEngine   import MultiCurrencyEngine
from api.payment_gateways.services.GeoPricingEngine      import GeoPricingEngine

# ── BD Gateway Services ────────────────────────────────────────────────────────
try:
    from api.payment_gateways.services.BkashService      import BkashService
except ImportError as e:
    logger.debug(f'BkashService not available: {e}')
    BkashService = None

try:
    from api.payment_gateways.services.NagadService      import NagadService
except ImportError as e:
    logger.debug(f'NagadService not available: {e}')
    NagadService = None

try:
    from api.payment_gateways.services.SSLCommerzService import SSLCommerzService
except ImportError as e:
    logger.debug(f'SSLCommerzService not available: {e}')
    SSLCommerzService = None

try:
    from api.payment_gateways.services.AmarPayService    import AmarPayService
except ImportError as e:
    logger.debug(f'AmarPayService not available: {e}')
    AmarPayService = None

try:
    from api.payment_gateways.services.UpayService       import UpayService
except ImportError as e:
    logger.debug(f'UpayService not available: {e}')
    UpayService = None

try:
    from api.payment_gateways.services.ShurjoPayService  import ShurjoPayService
except ImportError as e:
    logger.debug(f'ShurjoPayService not available: {e}')
    ShurjoPayService = None

# ── International Gateway Services ────────────────────────────────────────────
try:
    from api.payment_gateways.services.StripeService     import StripeService
except ImportError as e:
    logger.debug(f'StripeService not available: {e}')
    StripeService = None

try:
    from api.payment_gateways.services.PayPalService     import PayPalService
except ImportError as e:
    logger.debug(f'PayPalService not available: {e}')
    PayPalService = None

try:
    from api.payment_gateways.services.PayoneerService   import PayoneerService
except ImportError as e:
    logger.debug(f'PayoneerService not available: {e}')
    PayoneerService = None

try:
    from api.payment_gateways.services.WireTransferService import WireTransferService
except ImportError as e:
    logger.debug(f'WireTransferService not available: {e}')
    WireTransferService = None

try:
    from api.payment_gateways.services.ACHService        import ACHService
except ImportError as e:
    logger.debug(f'ACHService not available: {e}')
    ACHService = None

try:
    from api.payment_gateways.services.CryptoService     import CryptoService
except ImportError as e:
    logger.debug(f'CryptoService not available: {e}')
    CryptoService = None


# ── Convenience function: get any gateway service ─────────────────────────────
def get_gateway_service(gateway_name: str):
    """
    Get instantiated service object for a gateway.

    Args:
        gateway_name: Gateway identifier ('bkash', 'stripe', etc.)

    Returns:
        Service instance with process_deposit/process_withdrawal methods

    Raises:
        ValueError: If gateway is not registered

    Example:
        svc = get_gateway_service('bkash')
        result = svc.process_deposit(user=user, amount=Decimal('500'))
    """
    from api.payment_gateways.registry import gateway_registry
    return gateway_registry.get_instance(gateway_name)


def get_deposit_service() -> DepositService:
    """Get DepositService instance."""
    return DepositService()


def get_withdrawal_service() -> WithdrawalGatewayService:
    """Get WithdrawalGatewayService instance."""
    return WithdrawalGatewayService()


def get_health_service() -> GatewayHealthService:
    """Get GatewayHealthService instance."""
    return GatewayHealthService()


def get_validator() -> PaymentValidator:
    """Get PaymentValidator instance."""
    return PaymentValidator()


def get_receipt_generator() -> ReceiptGenerator:
    """Get ReceiptGenerator instance."""
    return ReceiptGenerator()


def get_currency_engine() -> MultiCurrencyEngine:
    """Get MultiCurrencyEngine instance."""
    return MultiCurrencyEngine()


def get_geo_engine() -> GeoPricingEngine:
    """Get GeoPricingEngine instance."""
    return GeoPricingEngine()


def get_router() -> GatewayRouterService:
    """Get GatewayRouterService instance."""
    return GatewayRouterService()


def get_webhook_verifier() -> WebhookVerifierService:
    """Get WebhookVerifierService instance."""
    return WebhookVerifierService()


# ── All available gateway names ────────────────────────────────────────────────
BD_GATEWAYS     = ['bkash', 'nagad', 'sslcommerz', 'amarpay', 'upay', 'shurjopay']
GLOBAL_GATEWAYS = ['stripe', 'paypal', 'payoneer', 'wire', 'ach', 'crypto']
ALL_GATEWAYS    = BD_GATEWAYS + GLOBAL_GATEWAYS


__all__ = [
    # Core
    'PaymentFactory', 'PaymentProcessor', 'PaymentValidator', 'ReceiptGenerator',
    # Operations
    'DepositService', 'WithdrawalGatewayService',
    # Routing
    'GatewayRouterService', 'GatewayFallbackService',
    # Monitoring
    'GatewayHealthService', 'GatewayAnalyticsService', 'ReconciliationService',
    # Security
    'WebhookVerifierService',
    # Currency
    'MultiCurrencyEngine', 'GeoPricingEngine',
    # BD Gateways
    'BkashService', 'NagadService', 'SSLCommerzService',
    'AmarPayService', 'UpayService', 'ShurjoPayService',
    # International
    'StripeService', 'PayPalService', 'PayoneerService',
    'WireTransferService', 'ACHService', 'CryptoService',
    # Convenience
    'get_gateway_service', 'get_deposit_service', 'get_withdrawal_service',
    'get_health_service', 'get_validator', 'get_receipt_generator',
    'get_currency_engine', 'get_geo_engine', 'get_router', 'get_webhook_verifier',
    # Constants
    'BD_GATEWAYS', 'GLOBAL_GATEWAYS', 'ALL_GATEWAYS',
]
