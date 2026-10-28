# api/djoyalty/throttles.py
"""
Djoyalty -- custom DRF throttle classes।

FIXED: rate_limiting.py was an orphan (0 imports)।
RateLimitPlan and plan-based rate checking is now wired in via
DjoyaltyPlanThrottle which uses rate_limiting.RateLimitChecker।

Add to DRF settings:
  REST_FRAMEWORK = {
      'DEFAULT_THROTTLE_CLASSES': [
          'djoyalty.throttles.DjoyaltyUserThrottle',
          'djoyalty.throttles.DjoyaltyBurstThrottle',
      ],
      'DEFAULT_THROTTLE_RATES': {
          'djoyalty_user':   '1000/hour',
          'djoyalty_burst':  '60/min',
          'djoyalty_public': '200/hour',
          'djoyalty_admin':  '2000/hour',
          'djoyalty_plan':   None,  # plan-based: dynamic
      }
  }
"""
from rest_framework.throttling import UserRateThrottle, AnonRateThrottle
from .constants import THROTTLE_RATE_USER, THROTTLE_RATE_BURST, THROTTLE_RATE_PUBLIC


class DjoyaltyUserThrottle(UserRateThrottle):
    """
    Authenticated users এর জন্য standard rate limit।
    Default: 1000/hour
    """
    scope = 'djoyalty_user'
    rate  = THROTTLE_RATE_USER


class DjoyaltyBurstThrottle(UserRateThrottle):
    """
    Short burst protection।
    Default: 60/min
    """
    scope = 'djoyalty_burst'
    rate  = THROTTLE_RATE_BURST


class DjoyaltyPublicThrottle(AnonRateThrottle):
    """
    Public/partner API এর জন্য throttle।
    Default: 200/hour
    """
    scope = 'djoyalty_public'
    rate  = THROTTLE_RATE_PUBLIC


class DjoyaltyAdminThrottle(UserRateThrottle):
    """
    Admin actions এর জন্য throttle -- looser rate।
    """
    scope = 'djoyalty_admin'
    rate  = '2000/hour'


# ─── Plan-based throttle (uses rate_limiting.py) ──────────────────────────────
# FIXED: rate_limiting.py defined RateLimitPlan and RATE_LIMIT_PLANS
# but was never imported anywhere। Connected here।

try:
    from .rate_limiting import RateLimitChecker, RATE_LIMIT_PLANS

    class DjoyaltyPlanThrottle(UserRateThrottle):
        """
        Plan-based rate throttle -- different limits for free/basic/pro/enterprise।
        Uses rate_limiting.RateLimitChecker for per-minute/hour/day enforcement।

        FIXED: rate_limiting.py was orphaned। Now wired as a concrete
        throttle class that DRF can use。
        """
        scope = 'djoyalty_plan'

        def allow_request(self, request, view):
            """Override: use RateLimitChecker instead of DRF cache counter।"""
            if not request.user or not request.user.is_authenticated:
                return self._anon_allow(request)

            # Determine customer's plan
            plan_name = 'free'
            try:
                customer = getattr(request, 'loyalty_customer', None)
                if customer:
                    sub = getattr(customer, 'loyalty_subscription', None)
                    plan_name = getattr(sub, 'plan', 'free') if sub else 'free'
            except Exception:
                pass

            # Check rate limit
            key = f'djoyalty_plan:{request.user.pk}'
            try:
                allowed, retry_after = RateLimitChecker.check(key, plan_name)
                if not allowed:
                    self.wait_time = retry_after
                    return False
                return True
            except Exception:
                # Fail open -- never block due to rate_limiting error
                return True

        def _anon_allow(self, request):
            """Fallback to public throttle for unauthenticated requests।"""
            plan = RATE_LIMIT_PLANS.get('free')
            key  = f'djoyalty_anon:{self.get_ident(request)}'
            try:
                allowed, _ = RateLimitChecker.check(key, 'free')
                return allowed
            except Exception:
                return True

        def wait(self):
            return getattr(self, 'wait_time', None)

except ImportError:
    # rate_limiting.py not available in this environment
    class DjoyaltyPlanThrottle(UserRateThrottle):
        """Fallback: standard user throttle when rate_limiting unavailable।"""
        scope = 'djoyalty_plan'
        rate  = THROTTLE_RATE_USER
