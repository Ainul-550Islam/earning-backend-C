"""
api/offerwall/b2b/middleware.py

B2B Quota Middleware

Intercepts every request to /api/offerwall/ and:
  1. Identifies if the caller is a B2B publisher (via X-Publisher-Key header)
  2. Checks their monthly API call quota
  3. Increments the counter atomically
  4. Returns 429 if quota exceeded

Add to Django settings:
    MIDDLEWARE = [
        ...
        'api.offerwall.b2b.middleware.B2BQuotaMiddleware',
    ]
"""
import logging
from django.http import JsonResponse
from django.utils import timezone

logger = logging.getLogger(__name__)

OFFERWALL_PREFIX = '/api/offerwall/'
EXEMPT_PATHS = [
    '/api/offerwall/b2b/plans/',          # public pricing page
    '/api/offerwall/webhooks/',           # provider webhooks use their own auth
    '/api/offerwall/public/',             # public offer listing
]


class B2BQuotaMiddleware:
    """
    Applied only when X-Publisher-Key header is present.
    Session-authenticated requests (admin/user) bypass quota.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if self._should_check(request):
            raw_key = request.headers.get('X-Publisher-Key', '')
            if raw_key:
                response = self._check_quota(request, raw_key)
                if response:
                    return response

        return self.get_response(request)

    def _should_check(self, request):
        path = request.path
        if not path.startswith(OFFERWALL_PREFIX):
            return False
        for exempt in EXEMPT_PATHS:
            if path.startswith(exempt):
                return False
        return True

    def _check_quota(self, request, raw_key):
        try:
            from api.offerwall.publisher import PublisherAPIKey
            from .models import B2BClient, B2BUsageRecord

            user = PublisherAPIKey.authenticate(raw_key)
            if not user:
                return None  # let DRF handle auth failure

            try:
                client = user.b2b_client
            except B2BClient.DoesNotExist:
                return None  # not a B2B client — let through

            if client.status != 'active':
                return JsonResponse(
                    {'error': 'client_not_active',
                     'detail': f'B2B client status: {client.status}'},
                    status=403)

            can_call, reason = client.can_make_api_call()
            if not can_call:
                return JsonResponse(
                    {'error': 'quota_exceeded',
                     'detail': 'Monthly API call quota reached. Upgrade your plan.',
                     'plan':   client.plan.plan_type if client.plan else None,
                     'upgrade_url': '/api/offerwall/b2b/upgrade/'},
                    status=429)

            # Atomically increment usage
            now = timezone.now()
            record, _ = B2BUsageRecord.objects.get_or_create(
                client=client,
                period_year=now.year,
                period_month=now.month,
            )
            record.increment('api_calls')

            # Attach client to request for downstream use
            request.b2b_client = client

        except Exception as e:
            logger.warning(f'[B2BQuota] middleware error: {e}')

        return None  # proceed normally
