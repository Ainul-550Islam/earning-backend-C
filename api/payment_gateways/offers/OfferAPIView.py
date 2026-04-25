# api/payment_gateways/offers/OfferAPIView.py
# Publisher CPA/CPI Offer API — like CPAlead's offer API endpoint
# Publishers can fetch live offers programmatically

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db.models import Q


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def offer_feed(request):
    """
    Publisher Offer Feed API — returns all active eligible offers.

    Query params:
        type         — cpa | cpi | cpc | cpl (filter by type)
        country      — US | GB | BD etc. (filter by GEO)
        device       — mobile | desktop | tablet
        category     — gaming | finance | health | mobile | shopping
        min_payout   — minimum payout filter
        format       — json (default) | csv
        limit        — max results (default 100, max 500)
        page         — pagination

    Response example:
        {
          "count": 142,
          "offers": [
            {
              "id": 1,
              "name": "My Game App",
              "type": "cpi",
              "payout": 1.50,
              "currency": "USD",
              "countries": ["US","CA"],
              "devices": ["mobile"],
              "tracking_link": "https://yourdomain.com/tracking/click/1/?sub1={YOUR_ID}",
              "postback_url": "https://yourdomain.com/tracking/postback/?click_id={click_id}&payout={payout}",
              "preview_url": "...",
              "epc": 0.085,
              "cr": "5.6%",
              "category": "gaming"
            }
          ]
        }
    """
    from .models import Offer

    user        = request.user
    offer_type  = request.GET.get('type')
    country     = request.GET.get('country', '').upper()
    device      = request.GET.get('device')
    category    = request.GET.get('category')
    min_payout  = request.GET.get('min_payout')
    limit       = min(int(request.GET.get('limit', 100)), 500)
    page        = int(request.GET.get('page', 1))

    qs = Offer.objects.filter(status='active').filter(
        Q(is_public=True) | Q(allowed_publishers=user)
    ).exclude(blocked_publishers=user)

    if offer_type:
        qs = qs.filter(offer_type=offer_type)
    if category:
        qs = qs.filter(category=category)
    if min_payout:
        qs = qs.filter(publisher_payout__gte=min_payout)
    if country:
        qs = qs.filter(
            Q(target_countries=[]) | Q(target_countries__contains=[country])
        ).exclude(blocked_countries__contains=[country])
    if device:
        qs = qs.filter(Q(target_devices=[]) | Q(target_devices__contains=[device]))

    qs = qs.order_by('-epc', '-publisher_payout')

    total   = qs.count()
    offset  = (page - 1) * limit
    offers  = qs[offset:offset + limit]

    base_url = getattr(__import__('django.conf', fromlist=['settings']).settings, 'SITE_URL', 'https://yourdomain.com')

    offers_data = []
    for o in offers:
        tracking_link = f'{base_url}/api/payment/tracking/click/{o.id}/?sub1={{YOUR_PUBLISHER_ID}}&sub2={{YOUR_CAMPAIGN}}'
        postback_url  = f'{base_url}/api/payment/tracking/postback/?click_id={{click_id}}&payout={{payout}}&status=approved'

        offers_data.append({
            'id':            o.id,
            'name':          o.name,
            'type':          o.offer_type,
            'description':   o.short_desc or '',
            'payout':        float(o.publisher_payout),
            'currency':      o.currency,
            'countries':     o.target_countries or [],
            'blocked_countries': o.blocked_countries or [],
            'devices':       o.target_devices or [],
            'os':            o.target_os or [],
            'category':      o.category,
            'tracking_link': tracking_link,
            'postback_url':  postback_url,
            'preview_url':   o.preview_url or '',
            'app_icon':      o.app_icon_url or '',
            'epc':           float(o.epc),
            'cr':            f'{float(o.conversion_rate or 0)*100:.1f}%',
            'daily_cap':     o.daily_cap,
            'requires_approval': o.requires_approval,
        })

    return Response({
        'success':     True,
        'total':       total,
        'page':        page,
        'limit':       limit,
        'pages':       (total + limit - 1) // limit,
        'offers':      offers_data,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def offer_detail_api(request, offer_id):
    """Get single offer details with tracking setup guide."""
    from .models import Offer
    from django.conf import settings as dj_settings

    try:
        offer = Offer.objects.get(id=offer_id, status='active')
    except Offer.DoesNotExist:
        return Response({'success': False, 'error': 'Offer not found'}, status=404)

    base   = getattr(dj_settings, 'SITE_URL', 'https://yourdomain.com')
    return Response({
        'success': True,
        'offer': {
            'id':           offer.id,
            'name':         offer.name,
            'description':  offer.description,
            'type':         offer.offer_type,
            'payout':       float(offer.publisher_payout),
            'currency':     offer.currency,
            'countries':    offer.target_countries,
            'devices':      offer.target_devices,
        },
        'tracking_setup': {
            'your_tracking_link':   f'{base}/api/payment/tracking/click/{offer.id}/?sub1=YOUR_ID',
            'postback_to_enter':    f'{base}/api/payment/tracking/postback/?click_id={{click_id}}&payout={{payout}}&status=approved',
            'macros':              ['{click_id}', '{payout}', '{cost}', '{status}', '{sub1}'],
            'test_postback':        f'{base}/api/payment/tracking/postback/?click_id=TEST123&payout={offer.publisher_payout}&status=approved',
        },
    })
