# api/djoyalty/services/social/SocialShareService.py
"""
SocialShareService -- Social share action verification and points reward.
World reference: Smile.io social sharing rewards, Voucherify social campaigns.

Flow:
  1. get_available_rewards() -> rules customer can earn points for
  2. record_share()          -> record action + award points (with daily/total limits)
  3. verify_share()          -> admin marks proof as verified (if requires_proof=True)
"""
import logging
from decimal import Decimal
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)


class SocialShareService:

    @staticmethod
    def get_available_rewards(customer, tenant=None) -> list:
        """
        Get social share reward rules the customer can still earn points for.
        Filters by daily limits and total limits.
        """
        try:
            from ...models.social import SocialShareReward, CustomerSocialAction
            from django.db.models import Q

            qs = SocialShareReward.objects.filter(is_active=True)
            if tenant:
                qs = qs.filter(Q(tenant=tenant) | Q(tenant__isnull=True))

            today = timezone.now().date()
            result = []
            for reward in qs:
                # Daily limit check
                today_count = CustomerSocialAction.objects.filter(
                    customer=customer,
                    reward=reward,
                    action_date__date=today,
                    status__in=['pending', 'verified'],
                ).count()

                if today_count >= reward.max_per_customer_per_day:
                    continue

                # Total limit check
                if reward.max_per_customer_total:
                    total_count = CustomerSocialAction.objects.filter(
                        customer=customer,
                        reward=reward,
                        status__in=['pending', 'verified', 'points_awarded'],
                    ).count()
                    if total_count >= reward.max_per_customer_total:
                        continue

                result.append({
                    'reward_id': reward.id,
                    'platform': reward.platform,
                    'share_type': reward.share_type,
                    'points_reward': str(reward.points_reward),
                    'requires_proof': reward.requires_proof,
                    'share_url': reward.share_url or '',
                    'today_used': today_count,
                    'daily_max': reward.max_per_customer_per_day,
                })
            return result

        except Exception as e:
            logger.error('SocialShareService.get_available_rewards error: %s', e)
            return []

    @staticmethod
    @transaction.atomic
    def record_share(customer, reward_id: int,
                     proof_url: str = '', metadata: dict = None,
                     tenant=None) -> dict:
        """
        Record a social share action. Awards points immediately if no proof required.
        If requires_proof=True, creates action in 'pending' state for admin review.
        Returns: {'success': True, 'action_id': int, 'points_awarded': Decimal, 'pending_review': bool}
        """
        try:
            from ...models.social import SocialShareReward, CustomerSocialAction

            try:
                reward = SocialShareReward.objects.get(id=reward_id, is_active=True)
            except SocialShareReward.DoesNotExist:
                return {'success': False, 'error': 'Social share reward not found'}

            today = timezone.now().date()

            # Daily limit
            today_count = CustomerSocialAction.objects.filter(
                customer=customer,
                reward=reward,
                action_date__date=today,
                status__in=['pending', 'verified', 'points_awarded'],
            ).count()
            if today_count >= reward.max_per_customer_per_day:
                return {'success': False,
                        'error': f'Daily limit reached ({reward.max_per_customer_per_day}/day)'}

            # Total limit
            if reward.max_per_customer_total:
                total_count = CustomerSocialAction.objects.filter(
                    customer=customer,
                    reward=reward,
                    status__in=['pending', 'verified', 'points_awarded'],
                ).count()
                if total_count >= reward.max_per_customer_total:
                    return {'success': False, 'error': 'Total share limit reached'}

            # Determine initial status
            pending_review = reward.requires_proof and not proof_url
            if reward.requires_proof and proof_url:
                # Proof provided -- needs admin verification before points
                initial_status = 'pending_verification'
            elif reward.requires_proof:
                initial_status = 'pending'
            else:
                initial_status = 'verified'

            action = CustomerSocialAction.objects.create(
                customer=customer,
                reward=reward,
                tenant=tenant or getattr(customer, 'tenant', None),
                platform=reward.platform,
                share_type=reward.share_type,
                proof_url=proof_url or '',
                metadata=metadata or {},
                status=initial_status,
                action_date=timezone.now(),
            )

            points_awarded = Decimal('0')
            if initial_status == 'verified':
                # Auto-award points
                points_awarded = reward.points_reward
                SocialShareService._award_points(customer, reward, action, tenant)

            logger.info('SocialShareService.record_share: %s -> %s/%s status=%s',
                        customer.code, reward.platform, reward.share_type, initial_status)

            return {
                'success': True,
                'action_id': action.id,
                'platform': reward.platform,
                'share_type': reward.share_type,
                'points_awarded': str(points_awarded),
                'pending_review': initial_status in ('pending', 'pending_verification'),
                'status': initial_status,
            }

        except Exception as e:
            logger.error('SocialShareService.record_share error: %s', e)
            return {'success': False, 'error': str(e)}

    @staticmethod
    @transaction.atomic
    def verify_share(action_id: int, verified_by: str = 'admin') -> dict:
        """
        Admin verifies a pending social share action and awards points.
        Returns: {'success': True, 'points_awarded': Decimal}
        """
        try:
            from ...models.social import CustomerSocialAction

            try:
                action = CustomerSocialAction.objects.select_for_update().get(id=action_id)
            except CustomerSocialAction.DoesNotExist:
                return {'success': False, 'error': 'Action not found'}

            if action.status == 'points_awarded':
                return {'success': False, 'error': 'Points already awarded for this action'}

            if action.status not in ('pending', 'pending_verification'):
                return {'success': False, 'error': f'Cannot verify action in status: {action.status}'}

            action.status = 'verified'
            action.verified_by = verified_by
            action.verified_at = timezone.now()
            action.save(update_fields=['status', 'verified_by', 'verified_at'])

            SocialShareService._award_points(
                action.customer, action.reward, action,
                getattr(action, 'tenant', None)
            )

            return {
                'success': True,
                'action_id': action_id,
                'points_awarded': str(action.reward.points_reward),
            }

        except Exception as e:
            logger.error('SocialShareService.verify_share error: %s', e)
            return {'success': False, 'error': str(e)}

    # ── Internal ──────────────────────────────────────────────────────────────

    @staticmethod
    def _award_points(customer, reward, action, tenant):
        """Award points for a verified social action."""
        try:
            from ...services.earn.BonusEventService import BonusEventService
            BonusEventService.award_bonus(
                customer, reward.points_reward,
                reason=f'Social {reward.platform}/{reward.share_type}',
                triggered_by='social_share',
                tenant=tenant,
            )
            action.status = 'points_awarded'
            action.points_awarded = reward.points_reward
            action.save(update_fields=['status', 'points_awarded'])
        except Exception as e:
            logger.error('SocialShareService._award_points error: %s', e)

    @staticmethod
    def track_share(customer, platform: str = '', share_type: str = '',
                    reward_id: int = None, proof_url: str = '',
                    metadata: dict = None, tenant=None) -> dict:
        """
        Alias for record_share() -- matches ReceiptSocialViewSet call signature.
        """
        if not reward_id:
            # Try to auto-find reward by platform
            try:
                from ...models.social import SocialShareReward
                reward = SocialShareReward.objects.filter(
                    platform=platform, share_type=share_type, is_active=True
                ).first()
                if reward:
                    reward_id = reward.id
            except Exception:
                pass
        if not reward_id:
            return {'success': False, 'error': 'reward_id required or no matching reward found'}
        return SocialShareService.record_share(
            customer=customer, reward_id=reward_id,
            proof_url=proof_url, metadata=metadata, tenant=tenant,
        )
