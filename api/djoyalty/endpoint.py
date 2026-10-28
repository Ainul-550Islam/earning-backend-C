# api/djoyalty/endpoint.py
"""
Djoyalty Endpoint -- Public API endpoint helpers and documentation।
Standard response envelopes, versioning, rate info।
"""
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny


class LoyaltyAPIRootView(APIView):
    """
    GET /api/loyalty/
    Returns API information and available endpoints।
    """
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({
            'name': 'Djoyalty API',
            'version': '2.0',
            'status': 'operational',
            'endpoints': {
                'customers':      '/api/loyalty/customers/',
                'points':         '/api/loyalty/points/',
                'tiers':          '/api/loyalty/tiers/',
                'earn_rules':     '/api/loyalty/earn-rules/',
                'redemptions':    '/api/loyalty/redemptions/',
                'vouchers':       '/api/loyalty/vouchers/',
                'badges':         '/api/loyalty/badges/',
                'challenges':     '/api/loyalty/challenges/',
                'leaderboard':    '/api/loyalty/leaderboard/',
                'campaigns':      '/api/loyalty/campaigns/',
                'offerwalls':     '/api/loyalty/offerwalls/',
                'cashout':        '/api/loyalty/cashout/',
                'referral':       '/api/loyalty/referral/',
                'notifications':  '/api/loyalty/notifications/',
                'catalog':        '/api/loyalty/catalog/',
                'partners':       '/api/loyalty/partners/',
                'health':         '/api/loyalty/health/',
            },
            'documentation': 'https://github.com/your-org/djoyalty',
        })


def standard_response(data=None, message='', success=True,
                        status_code=200, errors=None) -> Response:
    """Build a standard Djoyalty API response envelope।"""
    body = {'success': success}
    if message:
        body['message'] = message
    if data is not None:
        body['data'] = data
    if errors:
        body['errors'] = errors
    return Response(body, status=status_code)
