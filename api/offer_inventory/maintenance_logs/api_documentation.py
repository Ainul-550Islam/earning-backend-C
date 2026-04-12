# api/offer_inventory/maintenance_logs/api_documentation.py
"""API Documentation Manager — Manage docs, changelogs, and snippets."""
import logging
from django.utils import timezone

logger = logging.getLogger(__name__)


class APIDocumentationManager:
    """Manage API documentation snippets and changelog in DB."""

    @staticmethod
    def create_snippet(slug: str, title: str, content: str,
                        category: str = '', language: str = 'bn') -> object:
        """Create or update a documentation snippet."""
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
            return {'error': f'Not found: {slug}'}

    @staticmethod
    def list_snippets(category: str = None, language: str = 'en') -> list:
        """List all published documentation snippets."""
        from api.offer_inventory.models import DocumentationSnippet
        qs = DocumentationSnippet.objects.filter(is_published=True)
        if category:
            qs = qs.filter(category=category)
        return list(qs.values('slug', 'title', 'category', 'language').order_by('category', 'slug'))

    @staticmethod
    def get_api_changelog() -> list:
        """Return API version changelog."""
        return [
            {
                'version': '2.0.0',
                'date'   : '2025-01-01',
                'changes': [
                    'Added marketing/ — campaigns, push, loyalty, referral',
                    'Added business/ — KPI, billing, compliance, advertiser portal',
                    'Added affiliate_advanced/ — 12 modules',
                    'Bulletproof dedup: Redis lock + DB select_for_update + 4-layer',
                    '100% Decimal financial calculations',
                    'AI SmartLink: EPC × CVR × Availability',
                    'Circuit breaker for offerwall',
                    'S2S postback: IP whitelist + HMAC-SHA256',
                ],
            },
            {
                'version': '1.5.0',
                'date'   : '2024-07-01',
                'changes': [
                    'GDPR data export + right to erasure',
                    'KYC verification workflow',
                    'Bangladesh tax calculator',
                    'AML checks for large withdrawals',
                ],
            },
            {
                'version': '1.0.0',
                'date'   : '2024-01-01',
                'changes': [
                    'Initial release: 99 DB models',
                    'Offer lifecycle, fraud detection, bKash/Nagad withdrawal',
                ],
            },
        ]

    @staticmethod
    def get_postman_collection() -> dict:
        """Generate Postman v2.1 collection JSON."""
        base = '{{base_url}}'
        return {
            'info': {
                'name'  : 'Offer Inventory API v2',
                'version': '2.0.0',
                'schema': 'https://schema.getpostman.com/json/collection/v2.1.0/collection.json',
            },
            'variable': [{'key': 'base_url', 'value': 'https://yourplatform.com'}],
            'item': [
                {'name': 'List Offers',      'request': {'method': 'GET',  'url': {'raw': f'{base}/api/offer-inventory/offers/'}}},
                {'name': 'Record Click',     'request': {'method': 'POST', 'url': {'raw': f'{base}/api/offer-inventory/offers/{{id}}/click/'}}},
                {'name': 'S2S Postback',     'request': {'method': 'POST', 'url': {'raw': f'{base}/api/offer-inventory/postback/'}}},
                {'name': 'My Wallet',        'request': {'method': 'GET',  'url': {'raw': f'{base}/api/offer-inventory/me/wallet/'}}},
                {'name': 'Withdraw',         'request': {'method': 'POST', 'url': {'raw': f'{base}/api/offer-inventory/withdrawals/'}}},
                {'name': 'Platform KPIs',    'request': {'method': 'GET',  'url': {'raw': f'{base}/api/offer-inventory/analytics/kpis/'}}},
                {'name': 'Health Check',     'request': {'method': 'GET',  'url': {'raw': f'{base}/api/offer-inventory/health/'}}},
            ],
        }
