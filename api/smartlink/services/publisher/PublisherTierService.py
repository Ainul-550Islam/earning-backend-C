"""
SmartLink Publisher Tier Service
Automatically evaluates publisher quality and assigns tiers.
Gold/Silver/Bronze/Standard/Under Review
"""
import logging
from django.utils import timezone
import datetime

logger = logging.getLogger('smartlink.publisher_tier')


class PublisherTierService:
    """Evaluate and manage publisher quality tiers."""

    TIER_THRESHOLDS = {
        'gold':         {'quality_rate': 95, 'unique_rate': 80, 'min_clicks': 1000},
        'silver':       {'quality_rate': 88, 'unique_rate': 65, 'min_clicks': 500},
        'bronze':       {'quality_rate': 75, 'unique_rate': 50, 'min_clicks': 100},
        'standard':     {'quality_rate': 0,  'unique_rate': 0,  'min_clicks': 0},
        'under_review': {'quality_rate': -1, 'unique_rate': -1, 'min_clicks': -1},
    }

    TIER_BENEFITS = {
        'gold':         {'max_smartlinks': 1000, 'max_domains': 5,  'bonus_pct': 5.0,  'ml_rotation': True,  'ab_test': True,  'pre_landers': True},
        'silver':       {'max_smartlinks': 500,  'max_domains': 3,  'bonus_pct': 3.0,  'ml_rotation': True,  'ab_test': True,  'pre_landers': True},
        'bronze':       {'max_smartlinks': 200,  'max_domains': 2,  'bonus_pct': 1.0,  'ml_rotation': True,  'ab_test': False, 'pre_landers': True},
        'standard':     {'max_smartlinks': 100,  'max_domains': 1,  'bonus_pct': 0.0,  'ml_rotation': False, 'ab_test': False, 'pre_landers': False},
        'under_review': {'max_smartlinks': 10,   'max_domains': 0,  'bonus_pct': 0.0,  'ml_rotation': False, 'ab_test': False, 'pre_landers': False},
    }

    def evaluate_publisher(self, publisher) -> dict:
        """
        Evaluate publisher traffic quality and assign tier.
        Called weekly by Celery task.
        """
        from ...models import Click
        from ...services.antifraud.ClickQualityScore import ClickQualityScore

        quality_svc = ClickQualityScore()
        report = quality_svc.get_publisher_quality_report(publisher.pk, days=30)

        total          = report.get('total_clicks', 0)
        quality_rate   = report.get('quality_rate', 0)
        unique_rate    = report.get('unique_rate', 0)
        fraud_rate     = report.get('fraud_rate', 0)

        # Determine tier
        if fraud_rate > 30:
            new_tier = 'under_review'
        elif total >= 1000 and quality_rate >= 95 and unique_rate >= 80:
            new_tier = 'gold'
        elif total >= 500 and quality_rate >= 88 and unique_rate >= 65:
            new_tier = 'silver'
        elif total >= 100 and quality_rate >= 75 and unique_rate >= 50:
            new_tier = 'bronze'
        else:
            new_tier = 'standard'

        # Update tier record
        self._update_tier(publisher, new_tier, quality_rate)

        logger.info(
            f"Publisher#{publisher.pk} tier: {new_tier} "
            f"(quality={quality_rate:.1f}% unique={unique_rate:.1f}%)"
        )

        return {
            'publisher_id':  publisher.pk,
            'tier':          new_tier,
            'quality_rate':  quality_rate,
            'unique_rate':   unique_rate,
            'fraud_rate':    fraud_rate,
            'total_clicks':  total,
            'benefits':      self.TIER_BENEFITS[new_tier],
        }

    def get_tier(self, publisher) -> str:
        """Get publisher's current tier."""
        try:
            from ...models.extensions.smartlink_schedule import PublisherTier
            return PublisherTier.objects.get(publisher=publisher).tier
        except Exception:
            return 'standard'

    def get_benefits(self, publisher) -> dict:
        """Get publisher's current tier benefits."""
        tier = self.get_tier(publisher)
        return self.TIER_BENEFITS.get(tier, self.TIER_BENEFITS['standard'])

    def _update_tier(self, publisher, tier: str, quality_score: float):
        """Update publisher tier record."""
        from ...models.extensions.smartlink_schedule import PublisherTier
        benefits = self.TIER_BENEFITS[tier]
        now      = timezone.now()
        next_eval = now + datetime.timedelta(days=7)

        PublisherTier.objects.update_or_create(
            publisher=publisher,
            defaults={
                'tier':                  tier,
                'max_smartlinks':        benefits['max_smartlinks'],
                'max_custom_domains':    benefits['max_domains'],
                'can_use_ml_rotation':   benefits['ml_rotation'],
                'can_use_ab_testing':    benefits['ab_test'],
                'can_use_pre_landers':   benefits['pre_landers'],
                'payout_bonus_percent':  benefits['bonus_pct'],
                'last_quality_score':    quality_score,
                'last_evaluated_at':     now,
                'next_evaluation_at':    next_eval,
            }
        )
