import logging
from ...models import LandingPage, PreLander, SmartLink
from ...utils import build_tracking_url, sanitize_sub_id

logger = logging.getLogger('smartlink.landing_page')


class LandingPageService:
    """
    Pre-lander and landing page logic.
    Selects which landing page to show before the offer redirect.
    Supports traffic split between multiple landing pages.
    """

    def select_landing_page(self, smartlink: SmartLink) -> "Optional[LandingPage]":
        """
        Select a landing page for this SmartLink using weighted traffic split.
        Returns None if no landing pages are configured.
        """
        pages = list(smartlink.landing_pages.filter(is_active=True))
        if not pages:
            return None

        # If only one page (or default), return it directly
        active_defaults = [p for p in pages if p.is_default]
        if active_defaults and len(pages) == 1:
            return active_defaults[0]

        # Weighted selection by traffic_split
        import random
        total = sum(p.traffic_split for p in pages)
        if total == 0:
            return pages[0]

        rand = random.uniform(0, total)
        cumulative = 0
        for page in pages:
            cumulative += page.traffic_split
            if rand <= cumulative:
                return page

        return pages[-1]

    def select_pre_lander(self, smartlink: SmartLink) -> "Optional[PreLander]":
        """Select an active pre-lander for this SmartLink."""
        return smartlink.pre_landers.filter(is_active=True).first()

    def build_landing_page_url(self, landing_page: LandingPage, context: dict) -> str:
        """Append tracking params to landing page URL."""
        params = {}
        for i in range(1, 6):
            val = context.get(f'sub{i}', '')
            if val:
                params[f'sub{i}'] = sanitize_sub_id(str(val))
        params['sl'] = context.get('slug', '')
        return build_tracking_url(landing_page.url, params)

    def build_pre_lander_url(self, pre_lander: PreLander, context: dict) -> str:
        """Append tracking params to pre-lander URL if pass_through_params is enabled."""
        if not pre_lander.pass_through_params:
            return pre_lander.url
        params = {}
        for i in range(1, 6):
            val = context.get(f'sub{i}', '')
            if val:
                params[f'sub{i}'] = sanitize_sub_id(str(val))
        return build_tracking_url(pre_lander.url, params)

    def record_landing_page_view(self, landing_page: LandingPage):
        """Increment view counter (thread-safe F() update)."""
        from django.db.models import F
        LandingPage.objects.filter(pk=landing_page.pk).update(views=F('views') + 1)

    def record_pre_lander_view(self, pre_lander: PreLander):
        """Increment view counter for pre-lander."""
        from django.db.models import F
        PreLander.objects.filter(pk=pre_lander.pk).update(views=F('views') + 1)

    def record_pass_through(self, pre_lander: PreLander):
        """Record that user passed through the pre-lander to the offer."""
        from django.db.models import F
        PreLander.objects.filter(pk=pre_lander.pk).update(
            pass_through_count=F('pass_through_count') + 1
        )
