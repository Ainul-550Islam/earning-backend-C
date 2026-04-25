# api/payment_gateways/api_versioning.py
# API versioning for payment_gateways
from rest_framework.versioning import URLPathVersioning, NamespaceVersioning
import logging
logger = logging.getLogger(__name__)

class PaymentGatewayVersioning(URLPathVersioning):
    allowed_versions = ['v1', 'v2']
    default_version  = 'v2'
    version_param    = 'version'

CHANGELOG = {
    'v2': {
        'released': '2025-01-01',
        'changes': [
            'Added USDT FastPay support',
            'Multi-currency engine',
            'GEO pricing engine',
            'A/B test engine for SmartLinks',
            'Real-time WebSocket events',
            'OpenAI fraud scoring',
            'Sanctions screening',
            'Compliance engine (GDPR/AML/KYC)',
            'Knowledge Base auto-generation',
            'Content locker widget generator',
        ]
    },
    'v1': {
        'released': '2024-01-01',
        'changes': ['Initial release with 12 gateways']
    }
}

def get_api_version(request):
    return getattr(request, 'version', 'v2')

def is_v2(request):
    return get_api_version(request) in ('v2', None, '')
