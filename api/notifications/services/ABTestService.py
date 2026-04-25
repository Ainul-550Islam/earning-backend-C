# earning_backend/api/notifications/services/ABTestService.py
"""
ABTestService — manages A/B tests on notification campaigns.

Responsibilities:
  - Set up A/B test on a campaign (two template variants, split percentage)
  - Assign users to variant A or B (deterministic via user PK hash)
  - Evaluate test winner based on chosen metric
  - Declare winner and update CampaignABTest
"""

import hashlib
import logging
from typing import Dict, List, Optional, Tuple

from django.utils import timezone

logger = logging.getLogger(__name__)


class ABTestService:

    METRIC_CHOICES = ('open_rate', 'click_rate', 'conversion_rate', 'delivery_rate')

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def create_ab_test(
        self,
        campaign_id: int,
        variant_a_template_id: int,
        variant_b_template_id: int,
        split_pct: int = 50,
        winning_metric: str = 'open_rate',
    ) -> Dict:
        """
        Attach an A/B test to a campaign.

        Args:
            campaign_id:            NotificationCampaign (new) PK.
            variant_a_template_id:  Template PK for variant A.
            variant_b_template_id:  Template PK for variant B.
            split_pct:              % of users who get variant A (1-99).
            winning_metric:         Metric used to pick the winner.

        Returns:
            Dict with: success, ab_test_id, error.
        """
        try:
            from notifications.models.campaign import NotificationCampaign, CampaignABTest
            from notifications.models import NotificationTemplate

            campaign = NotificationCampaign.objects.get(pk=campaign_id)
            template_a = NotificationTemplate.objects.get(pk=variant_a_template_id)
            template_b = NotificationTemplate.objects.get(pk=variant_b_template_id)

            if not (1 <= split_pct <= 99):
                return {'success': False, 'error': 'split_pct must be between 1 and 99'}

            if winning_metric not in self.METRIC_CHOICES:
                return {
                    'success': False,
                    'error': f'winning_metric must be one of {self.METRIC_CHOICES}',
                }

            ab_test, created = CampaignABTest.objects.update_or_create(
                campaign=campaign,
                defaults={
                    'variant_a': template_a,
                    'variant_b': template_b,
                    'split_pct': split_pct,
                    'winning_metric': winning_metric,
                    'winner': 'none',
                    'is_active': True,
                },
            )

            return {
                'success': True,
                'ab_test_id': ab_test.pk,
                'created': created,
                'error': '',
            }

        except Exception as exc:
            logger.error(f'ABTestService.create_ab_test: {exc}')
            return {'success': False, 'ab_test_id': None, 'error': str(exc)}

    # ------------------------------------------------------------------
    # User assignment
    # ------------------------------------------------------------------

    def assign_variant(self, user_id: int, split_pct: int = 50) -> str:
        """
        Deterministically assign a user to variant 'a' or 'b'.

        Uses a hash of the user PK so the same user always gets the same
        variant within a test (consistent assignment).

        Args:
            user_id:   User PK (int).
            split_pct: Percentage (0-100) of users who get variant A.

        Returns:
            'a' or 'b'
        """
        digest = hashlib.md5(str(user_id).encode()).hexdigest()
        # Take first 4 hex chars → int → 0-65535 → scale to 0-99
        bucket = int(digest[:4], 16) % 100
        return 'a' if bucket < split_pct else 'b'

    def get_template_for_user(self, campaign_id: int, user_id: int) -> Optional[object]:
        """
        Return the NotificationTemplate assigned to this user for the campaign's
        A/B test. Returns the campaign's default template if no A/B test exists.
        """
        try:
            from notifications.models.campaign import NotificationCampaign, CampaignABTest

            campaign = NotificationCampaign.objects.get(pk=campaign_id)

            ab_test = CampaignABTest.objects.filter(campaign=campaign, is_active=True).first()
            if not ab_test:
                return campaign.template

            variant = self.assign_variant(user_id, ab_test.split_pct)
            return ab_test.variant_a if variant == 'a' else ab_test.variant_b

        except Exception as exc:
            logger.warning(f'ABTestService.get_template_for_user: {exc}')
            return None

    # ------------------------------------------------------------------
    # Evaluation / winner declaration
    # ------------------------------------------------------------------

    def evaluate_test(self, campaign_id: int) -> Dict:
        """
        Evaluate an active A/B test and determine whether a winner can be declared.

        Uses the winning_metric field to compare variant A vs B stats.
        Declares a winner if the difference is statistically meaningful (>= 5%).

        Returns:
            Dict with: success, winner ('a'|'b'|'tie'|'too_early'),
            variant_a_metric, variant_b_metric, ab_test_id, error.
        """
        try:
            from notifications.models.campaign import CampaignABTest

            ab_test = CampaignABTest.objects.select_related('campaign').get(
                campaign_id=campaign_id, is_active=True
            )

            metric = ab_test.winning_metric
            stats_a = ab_test.variant_a_stats or {}
            stats_b = ab_test.variant_b_stats or {}

            val_a = float(stats_a.get(metric, 0))
            val_b = float(stats_b.get(metric, 0))

            # Minimum sample size check
            min_sample = 50
            sample_a = int(stats_a.get('sent', 0))
            sample_b = int(stats_b.get('sent', 0))

            if sample_a < min_sample or sample_b < min_sample:
                return {
                    'success': True,
                    'winner': 'too_early',
                    'variant_a_metric': val_a,
                    'variant_b_metric': val_b,
                    'ab_test_id': ab_test.pk,
                    'error': f'Not enough data yet (need {min_sample} sends per variant)',
                }

            # Determine winner (>= 5% relative difference)
            if val_a == 0 and val_b == 0:
                winner = 'tie'
            elif val_b == 0:
                winner = 'a'
            elif val_a == 0:
                winner = 'b'
            else:
                diff_pct = abs(val_a - val_b) / max(val_a, val_b) * 100
                if diff_pct < 5:
                    winner = 'tie'
                elif val_a > val_b:
                    winner = 'a'
                else:
                    winner = 'b'

            return {
                'success': True,
                'winner': winner,
                'variant_a_metric': val_a,
                'variant_b_metric': val_b,
                'ab_test_id': ab_test.pk,
                'error': '',
            }

        except Exception as exc:
            logger.error(f'ABTestService.evaluate_test campaign #{campaign_id}: {exc}')
            return {'success': False, 'winner': None, 'error': str(exc)}

    def declare_winner(self, campaign_id: int, winner: Optional[str] = None) -> Dict:
        """
        Declare the winner of an A/B test.

        If winner is None, evaluates automatically and declares if possible.

        Returns:
            Dict with: success, winner, ab_test_id, error.
        """
        try:
            from notifications.models.campaign import CampaignABTest

            ab_test = CampaignABTest.objects.get(campaign_id=campaign_id, is_active=True)

            if winner is None:
                eval_result = self.evaluate_test(campaign_id)
                winner = eval_result.get('winner')
                if winner in ('too_early', None):
                    return {
                        'success': False,
                        'winner': winner,
                        'ab_test_id': ab_test.pk,
                        'error': eval_result.get('error', 'Cannot declare winner yet'),
                    }

            if winner not in ('a', 'b', 'tie'):
                return {
                    'success': False,
                    'winner': winner,
                    'ab_test_id': ab_test.pk,
                    'error': "winner must be 'a', 'b', or 'tie'",
                }

            ab_test.declare_winner(winner)
            logger.info(f'ABTestService: campaign #{campaign_id} winner declared: {winner}')

            return {
                'success': True,
                'winner': winner,
                'ab_test_id': ab_test.pk,
                'error': '',
            }

        except Exception as exc:
            logger.error(f'ABTestService.declare_winner campaign #{campaign_id}: {exc}')
            return {'success': False, 'winner': None, 'error': str(exc)}

    def update_variant_stats(self, campaign_id: int, variant: str, stats: Dict) -> Dict:
        """
        Update the stats snapshot for a variant (called by ab_test_tasks.py).
        """
        try:
            from notifications.models.campaign import CampaignABTest
            ab_test = CampaignABTest.objects.get(campaign_id=campaign_id, is_active=True)
            ab_test.update_stats(variant, stats)
            return {'success': True, 'ab_test_id': ab_test.pk, 'error': ''}
        except Exception as exc:
            return {'success': False, 'error': str(exc)}

    def get_ab_test_summary(self, campaign_id: int) -> Dict:
        """Return full A/B test status dict for a campaign."""
        try:
            from notifications.models.campaign import CampaignABTest
            ab_test = CampaignABTest.objects.get(campaign_id=campaign_id)
            return {
                'ab_test_id': ab_test.pk,
                'campaign_id': campaign_id,
                'split_pct': ab_test.split_pct,
                'winning_metric': ab_test.winning_metric,
                'winner': ab_test.winner,
                'is_active': ab_test.is_active,
                'variant_a_template': ab_test.variant_a_id,
                'variant_b_template': ab_test.variant_b_id,
                'variant_a_stats': ab_test.variant_a_stats,
                'variant_b_stats': ab_test.variant_b_stats,
                'winner_declared_at': (
                    ab_test.winner_declared_at.isoformat()
                    if ab_test.winner_declared_at else None
                ),
            }
        except Exception as exc:
            return {'campaign_id': campaign_id, 'error': str(exc)}


    def create_image_ab_test(self, campaign, image_url_a: str, image_url_b: str,
                               notification_type: str = 'push') -> dict:
        """
        Create an A/B test comparing two push notification images.
        Variant A sends push with image_url_a, Variant B with image_url_b.
        Winner determined by click rate.
        """
        try:
            from notifications.models.campaign import CampaignABTest
            ab_test = CampaignABTest.objects.create(
                campaign=campaign,
                test_type='image',
                variant_a_config={
                    'image_url': image_url_a,
                    'label': 'Image A',
                },
                variant_b_config={
                    'image_url': image_url_b,
                    'label': 'Image B',
                },
                winning_metric='click_rate',
                status='pending',
                split_percentage=50,
            )
            return {'success': True, 'ab_test_id': ab_test.pk}
        except Exception as exc:
            return {'success': False, 'error': str(exc)}

    def apply_image_to_notification(self, notification, ab_test, variant: str = 'a') -> dict:
        """Apply the A/B test image to a notification before sending."""
        try:
            config_key = f'variant_{variant}_config'
            config = getattr(ab_test, config_key, {}) or {}
            image_url = config.get('image_url', '')
            if image_url:
                # Store in metadata for provider to use
                metadata = notification.metadata or {}
                metadata['ab_image_url'] = image_url
                metadata['ab_variant'] = variant
                metadata['ab_test_id'] = ab_test.pk
                notification.metadata = metadata
                notification.save(update_fields=['metadata', 'updated_at'])
            return {'success': True, 'image_url': image_url, 'variant': variant}
        except Exception as exc:
            return {'success': False, 'error': str(exc)}


# Singleton
ab_test_service = ABTestService()
