# api/offer_inventory/affiliate_advanced/landing_page_rotator.py
"""Landing Page Rotator — A/B test offer landing pages."""
import logging

logger = logging.getLogger(__name__)


class LandingPageRotator:
    """Route users to different landing pages for A/B testing."""

    @staticmethod
    def get_page(offer, user_id=None):
        """Get the appropriate landing page for a user."""
        from api.offer_inventory.models import OfferLandingPage
        from api.offer_inventory.ai_optimization.a_b_testing import ABTestingEngine

        pages = list(OfferLandingPage.objects.filter(offer=offer, is_active=True))
        if not pages:
            return None
        if len(pages) == 1:
            return pages[0]

        test_name = f'landing_{offer.id}'
        variant   = ABTestingEngine.get_variant(test_name, str(user_id) if user_id else 'anon')
        idx       = 0 if variant == 'A' else 1
        page      = pages[idx % len(pages)]
        ABTestingEngine.record_event(test_name, variant, 'impression')
        return page

    @staticmethod
    def record_conversion(offer_id: str, user_id=None):
        """Record that user converted from a landing page."""
        from api.offer_inventory.ai_optimization.a_b_testing import ABTestingEngine
        test_name = f'landing_{offer_id}'
        variant   = ABTestingEngine.get_variant(test_name, str(user_id) if user_id else 'anon')
        ABTestingEngine.record_event(test_name, variant, 'conversion')

    @staticmethod
    def get_performance(offer_id: str) -> dict:
        """A/B test results for an offer's landing pages."""
        from api.offer_inventory.ai_optimization.a_b_testing import ABTestingEngine
        test_name = f'landing_{offer_id}'
        return ABTestingEngine.get_results(test_name)

    @staticmethod
    def add_page(offer_id: str, url: str, title: str = '',
                  variant_key: str = 'A') -> object:
        """Add a landing page variant to an offer."""
        from api.offer_inventory.models import OfferLandingPage, Offer
        offer = Offer.objects.get(id=offer_id)
        return OfferLandingPage.objects.create(
            offer      =offer,
            url        =url,
            title      =title or f'Variant {variant_key}',
            variant_key=variant_key,
            is_active  =True,
        )
