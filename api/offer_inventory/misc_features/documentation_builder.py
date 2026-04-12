# api/offer_inventory/misc_features/documentation_builder.py
"""
Documentation Builder — Auto-generate API docs from code.
Generates Postman collections, OpenAPI specs, and SDK guides.
"""
import logging
import json
from django.utils import timezone

logger = logging.getLogger(__name__)


class DocumentationBuilder:
    """Auto-generate API documentation from urls and models."""

    @staticmethod
    def get_all_endpoints() -> list:
        """Introspect all registered URL patterns."""
        from api.offer_inventory.urls import urlpatterns
        from django.urls import URLPattern, URLResolver
        endpoints = []

        def extract(patterns, prefix=''):
            for p in patterns:
                if isinstance(p, URLPattern):
                    endpoints.append({
                        'url'  : f'/api/offer-inventory/{prefix}{str(p.pattern)}',
                        'name' : p.name or '',
                    })
                elif isinstance(p, URLResolver):
                    extract(p.url_patterns, prefix + str(p.pattern))

        try:
            extract(urlpatterns)
        except Exception as e:
            logger.debug(f'Endpoint extraction error: {e}')
        return endpoints

    @staticmethod
    def generate_postman_collection() -> dict:
        """Generate a Postman v2.1 collection JSON."""
        base_url = '{{base_url}}'
        items    = [
            # ── Offers ───────────────────────────────────────
            {'name': 'List Offers',        'method': 'GET',  'url': f'{base_url}/api/offer-inventory/offers/', 'auth': True},
            {'name': 'Offer Detail',       'method': 'GET',  'url': f'{base_url}/api/offer-inventory/offers/{{id}}/', 'auth': True},
            {'name': 'Record Click',       'method': 'POST', 'url': f'{base_url}/api/offer-inventory/offers/{{id}}/click/', 'auth': True},
            # ── SmartLink ─────────────────────────────────────
            {'name': 'SmartLink Redirect', 'method': 'GET',  'url': f'{base_url}/api/offer-inventory/go/{{slug}}/', 'auth': False},
            # ── Postback ─────────────────────────────────────
            {'name': 'S2S Postback',       'method': 'POST', 'url': f'{base_url}/api/offer-inventory/postback/', 'auth': False},
            # ── User ─────────────────────────────────────────
            {'name': 'My Profile',         'method': 'GET',  'url': f'{base_url}/api/offer-inventory/me/profile/', 'auth': True},
            {'name': 'My Wallet',          'method': 'GET',  'url': f'{base_url}/api/offer-inventory/me/wallet/', 'auth': True},
            {'name': 'My Conversions',     'method': 'GET',  'url': f'{base_url}/api/offer-inventory/me/conversions/', 'auth': True},
            {'name': 'My KYC',             'method': 'GET',  'url': f'{base_url}/api/offer-inventory/me/kyc/', 'auth': True},
            {'name': 'My Referrals',       'method': 'GET',  'url': f'{base_url}/api/offer-inventory/me/referrals/', 'auth': True},
            # ── Withdrawal ────────────────────────────────────
            {'name': 'Request Withdrawal', 'method': 'POST', 'url': f'{base_url}/api/offer-inventory/withdrawals/', 'auth': True},
            # ── Analytics ─────────────────────────────────────
            {'name': 'Platform KPIs',      'method': 'GET',  'url': f'{base_url}/api/offer-inventory/analytics/kpis/', 'auth': True},
            {'name': 'Revenue Forecast',   'method': 'GET',  'url': f'{base_url}/api/offer-inventory/analytics/revenue-forecast/', 'auth': True},
            # ── System ────────────────────────────────────────
            {'name': 'Health Check',       'method': 'GET',  'url': f'{base_url}/api/offer-inventory/health/', 'auth': False},
        ]

        return {
            'info': {
                'name'   : 'Offer Inventory API v2',
                'version': '2.0.0',
                'schema' : 'https://schema.getpostman.com/json/collection/v2.1.0/collection.json',
            },
            'variable': [{'key': 'base_url', 'value': 'https://yourplatform.com'}],
            'auth'    : {
                'type'  : 'bearer',
                'bearer': [{'key': 'token', 'value': '{{jwt_token}}', 'type': 'string'}]
            },
            'item': [
                {
                    'name'   : item['name'],
                    'request': {
                        'method': item['method'],
                        'url'   : {'raw': item['url']},
                        'auth'  : {'type': 'bearer'} if item.get('auth') else {'type': 'noauth'},
                    },
                }
                for item in items
            ],
        }

    @staticmethod
    def get_api_changelog() -> list:
        """API version changelog."""
        return [
            {
                'version': '2.0.0',
                'date'   : '2025-01-01',
                'changes': [
                    'Added marketing/ module — campaigns, push, loyalty, referral',
                    'Added business/ module — KPI, billing, compliance, advertiser portal',
                    'Added affiliate_advanced/ — 12 advanced affiliate features',
                    'Bulletproof conversion tracking with Redis + DB locks',
                    '100% Decimal financial calculations — zero float operations',
                    'AI SmartLink — EPC × CVR × Availability scoring',
                    'Circuit breaker for offerwall integration',
                    'S2S postback: IP whitelist + HMAC-SHA256 + replay protection',
                ],
            },
            {
                'version': '1.5.0',
                'date'   : '2024-07-01',
                'changes': [
                    'Multi-layer conversion deduplication (4-layer)',
                    'GDPR compliance — export + right to erasure',
                    'KYC verification workflow',
                    'Bangladesh tax calculator',
                ],
            },
            {
                'version': '1.0.0',
                'date'   : '2024-01-01',
                'changes': [
                    'Initial release: 99 DB models',
                    'Full offer lifecycle management',
                    'Fraud detection and security modules',
                    'bKash, Nagad, Rocket withdrawal support',
                ],
            },
        ]

    @staticmethod
    def create_snippet(slug: str, title: str, content: str,
                        category: str = '', language: str = 'bn') -> object:
        """Create or update a documentation snippet in DB."""
        from api.offer_inventory.models import DocumentationSnippet
        obj, created = DocumentationSnippet.objects.update_or_create(
            slug=slug,
            defaults={
                'title'      : title,
                'content'    : content,
                'category'   : category,
                'language'   : language,
                'is_published': True,
            }
        )
        action = 'Created' if created else 'Updated'
        logger.info(f'{action} doc snippet: {slug}')
        return obj

    @staticmethod
    def get_snippet(slug: str, language: str = 'en') -> dict:
        """Get a published documentation snippet."""
        from api.offer_inventory.models import DocumentationSnippet
        try:
            doc = DocumentationSnippet.objects.get(slug=slug, is_published=True)
            return {
                'title'   : doc.title,
                'content' : doc.content,
                'category': doc.category,
                'language': language,
            }
        except DocumentationSnippet.DoesNotExist:
            return {'error': f'Documentation not found: {slug}'}
