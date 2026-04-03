content = open('api/offerwall/views.py', encoding='utf-8').read()

new_code = '''

# ============================================================
# PUBLIC OFFER API - No auth required (for landing page)
# ============================================================
from rest_framework.views import APIView

class PublicOfferListView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        from .models import Offer
        offers = Offer.objects.filter(
            status='active'
        ).order_by('-is_featured', '-reward_amount', '-created_at')

        seen = set()
        unique_offers = []
        for offer in offers:
            key = offer.title.lower().strip()
            if key not in seen:
                seen.add(key)
                unique_offers.append(offer)

        unique_offers = unique_offers[:100]

        data = []
        for offer in unique_offers:
            data.append({
                'id': offer.id,
                'title': offer.title,
                'description': offer.short_description or offer.description[:200],
                'offer_type': offer.offer_type,
                'payout': str(offer.payout),
                'currency': offer.currency,
                'reward_amount': str(offer.reward_amount),
                'reward_currency': offer.reward_currency,
                'countries': offer.countries,
                'image_url': offer.image_url or offer.thumbnail_url or offer.icon_url,
                'click_url': offer.click_url,
                'is_featured': offer.is_featured,
                'created_at': offer.created_at.strftime('%Y-%m-%d'),
                'category': offer.category.name if offer.category else 'General',
            })

        return Response({'count': len(data), 'results': data})
'''

content = content + new_code
open('api/offerwall/views.py', 'w', encoding='utf-8').write(content)
print('SUCCESS')
