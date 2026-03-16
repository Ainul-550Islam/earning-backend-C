"""middleware.py – Subscription-aware middleware."""
import logging
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger(__name__)


class SubscriptionStatusMiddleware(MiddlewareMixin):
    """
    Attaches the user's active subscription to request.subscription for
    easy access in views and templates without an extra DB query.

    Usage in views:
        subscription = request.subscription  # or None
    Usage in templates:
        {% if request.subscription.is_active %} ... {% endif %}
    """

    def process_request(self, request):
        request.subscription = None
        if request.user.is_authenticated:
            # Avoid circular import by importing lazily
            from .models import UserSubscription
            request.subscription = UserSubscription.objects.get_active_for_user(request.user)

    def process_response(self, request, response):
        return response


class SubscriptionFeatureGateMiddleware(MiddlewareMixin):
    """
    Optional middleware that blocks specific URL prefixes for users
    without an active subscription.

    Configure gated paths in settings:
        SUBSCRIPTION_GATED_PATHS = ["/app/", "/dashboard/"]
        SUBSCRIPTION_REDIRECT_URL = "/pricing/"  # where to redirect
    """
    from django.conf import settings

    def process_request(self, request):
        from django.conf import settings
        from django.shortcuts import redirect

        gated_paths = getattr(settings, "SUBSCRIPTION_GATED_PATHS", [])
        redirect_url = getattr(settings, "SUBSCRIPTION_REDIRECT_URL", "/pricing/")

        if not any(request.path.startswith(p) for p in gated_paths):
            return None  # Not a gated path

        if not request.user.is_authenticated:
            return redirect(settings.LOGIN_URL)

        subscription = getattr(request, "subscription", None)
        if subscription is None:
            # Try fetching (if SubscriptionStatusMiddleware isn't loaded)
            from .models import UserSubscription
            subscription = UserSubscription.objects.get_active_for_user(request.user)

        if not subscription or not subscription.is_active_or_trialing:
            logger.info(
                "FeatureGate: User %s blocked from %s (no active subscription)",
                request.user.pk,
                request.path,
            )
            return redirect(redirect_url)

        return None