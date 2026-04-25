# api/payment_gateways/rtb/views.py
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .BiddingEngine import BiddingEngine
from api.payment_gateways.offers.serializers import OfferListSerializer

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def best_offer(request):
    """RTB: Get single best offer for visitor profile."""
    engine  = BiddingEngine()
    result  = engine.find_best_offer(
        publisher   = request.user,
        country     = request.GET.get('country', ''),
        device      = request.GET.get('device', 'desktop'),
        os_name     = request.GET.get('os', ''),
        offer_type  = request.GET.get('type'),
        category    = request.GET.get('category'),
    )
    if not result['offer']:
        return Response({'success': False, 'message': 'No matching offers', 'data': None})
    return Response({
        'success': True,
        'data': {
            'offer':        OfferListSerializer(result['offer']).data,
            'bid':          str(result['bid']),
            'alternatives': OfferListSerializer(result['alternatives'], many=True).data,
        }
    })

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def offerwall_offers(request):
    """RTB: Get ranked offer list for offerwall."""
    engine  = BiddingEngine()
    limit   = min(int(request.GET.get('limit', 20)), 50)
    offers  = engine.find_offers_for_offerwall(
        publisher = request.user,
        country   = request.GET.get('country', ''),
        device    = request.GET.get('device', 'desktop'),
        limit     = limit,
    )
    return Response({
        'success': True,
        'count':   len(offers),
        'data':    OfferListSerializer(offers, many=True).data,
    })
