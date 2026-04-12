# =============================================================================
# promotions/offer_feed/feed_generator.py
# Offer Feed — XML/JSON feed for external trackers (Voluum, BeMob, HasOffers)
# Publisher pulls offers into their tracker via API
# =============================================================================
from decimal import Decimal
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.http import HttpResponse
import json


class OfferFeedGenerator:
    def generate_json_feed(self, api_key: str, country: str = 'US',
                            category: str = None, limit: int = 100) -> dict:
        from api.promotions.models import Campaign
        qs = Campaign.objects.filter(status='active').select_related('category')[:limit]
        offers = []
        for c in qs:
            offers.append({
                'offer_id': c.id, 'name': c.title,
                'description': (c.description or '')[:300],
                'payout': float(c.per_task_reward),
                'currency': 'USD',
                'category': c.category.name if c.category else 'other',
                'countries': ['ALL'],
                'tracking_url': f'https://yourplatform.com/api/promotions/go/{c.id}/?sub1={{sub1}}&sub2={{sub2}}',
                'preview_url': f'https://yourplatform.com/offers/{c.id}/',
                'conversion_type': 'CPA',
                'is_active': True,
                'last_updated': c.updated_at.isoformat() if c.updated_at else timezone.now().isoformat(),
            })
        return {
            'api_version': '2.0', 'generated_at': timezone.now().isoformat(),
            'total': len(offers), 'country': country, 'offers': offers,
        }

    def generate_xml_feed(self, api_key: str, country: str = 'US') -> str:
        feed = self.generate_json_feed(api_key, country)
        lines = ['<?xml version="1.0" encoding="UTF-8"?>', '<offers>']
        for o in feed['offers']:
            lines.append(f'''  <offer>
    <id>{o["offer_id"]}</id>
    <name><![CDATA[{o["name"]}]]></name>
    <payout>{o["payout"]}</payout>
    <currency>{o["currency"]}</currency>
    <category>{o["category"]}</category>
    <tracking_url><![CDATA[{o["tracking_url"]}]]></tracking_url>
  </offer>''')
        lines.append('</offers>')
        return '\n'.join(lines)


@api_view(['GET'])
@permission_classes([AllowAny])
def json_feed_view(request):
    api_key = request.query_params.get('api_key', '')
    gen = OfferFeedGenerator()
    data = gen.generate_json_feed(
        api_key=api_key,
        country=request.query_params.get('country', 'US'),
        limit=int(request.query_params.get('limit', 100)),
    )
    return Response(data)


@api_view(['GET'])
@permission_classes([AllowAny])
def xml_feed_view(request):
    api_key = request.query_params.get('api_key', '')
    gen = OfferFeedGenerator()
    xml = gen.generate_xml_feed(api_key=api_key, country=request.query_params.get('country', 'US'))
    return HttpResponse(xml, content_type='application/xml')
