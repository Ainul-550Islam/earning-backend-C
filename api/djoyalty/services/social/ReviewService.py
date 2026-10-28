# api/djoyalty/services/social/ReviewService.py
"""
ReviewService -- Customer review submission and points reward.
World reference: Smile.io review rewards, Yotpo loyalty integration.

Flow:
  1. submit_review()    -> customer writes review, earns points once per product
  2. verify_review()    -> admin/auto verifies review before awarding points
  3. get_review_rules() -> list reward rules available for customer
"""
import logging
from decimal import Decimal
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)


class ReviewService:

    @staticmethod
    def get_review_rules(customer, tenant=None) -> list:
        """
        Get review reward rules available to the customer.
        Filters out platforms the customer has already maxed out.
        """
        try:
            from ...models.social import ReviewReward, CustomerReview
            from django.db.models import Q

            qs = ReviewReward.objects.filter(is_active=True)
            if tenant:
                qs = qs.filter(Q(tenant=tenant) | Q(tenant__isnull=True))

            result = []
            for rule in qs:
                total_reviews = CustomerReview.objects.filter(
                    customer=customer,
                    reward=rule,
                    status__in=['verified', 'points_awarded'],
                ).count()

                max_total = getattr(rule, 'max_per_customer_total', None)
                if max_total and total_reviews >= max_total:
                    continue

                result.append({
                    'rule_id': rule.id,
                    'platform': rule.platform,
                    'points_reward': str(rule.points_reward),
                    'min_rating': getattr(rule, 'min_rating', 3),
                    'min_length': getattr(rule, 'min_review_length', 0),
                    'requires_photo': getattr(rule, 'requires_photo', False),
                    'reviews_submitted': total_reviews,
                    'max_total': max_total,
                })
            return result

        except Exception as e:
            logger.error('ReviewService.get_review_rules error: %s', e)
            return []

    @staticmethod
    @transaction.atomic
    def submit_review(customer, reward_id: int = None,
                       platform: str = '', rating: int = 5,
                       review_text: str = '', product_id: str = '',
                       proof_url: str = '', tenant=None) -> dict:
        """
        Submit a customer review for points.
        Validates rating/length requirements before recording.
        Returns: {'success': True, 'review_id': int, 'pending_review': bool, 'points_awarded': Decimal}
        """
        try:
            from ...models.social import ReviewReward, CustomerReview

            # Find applicable reward rule
            reward = None
            if reward_id:
                try:
                    reward = ReviewReward.objects.get(id=reward_id, is_active=True)
                except ReviewReward.DoesNotExist:
                    return {'success': False, 'error': 'Review reward rule not found'}
            elif platform:
                reward = ReviewReward.objects.filter(
                    platform=platform, is_active=True,
                ).first()

            # Validate rating
            min_rating = getattr(reward, 'min_rating', 1) if reward else 1
            if rating < min_rating:
                return {
                    'success': False,
                    'error': f'Minimum rating of {min_rating} stars required',
                }

            # Validate review length
            min_length = getattr(reward, 'min_review_length', 0) if reward else 0
            if min_length and len(review_text.strip()) < min_length:
                return {
                    'success': False,
                    'error': f'Review must be at least {min_length} characters',
                }

            # Validate photo if required
            requires_photo = getattr(reward, 'requires_photo', False) if reward else False
            if requires_photo and not proof_url:
                return {
                    'success': False,
                    'error': 'Photo proof required for this review reward',
                }

            # Check if already reviewed this product with this rule
            if reward and product_id:
                already = CustomerReview.objects.filter(
                    customer=customer,
                    reward=reward,
                    product_id=product_id,
                    status__in=['pending', 'verified', 'points_awarded'],
                ).exists()
                if already:
                    return {'success': False,
                            'error': 'You have already submitted a review for this product'}

            # Determine initial status
            # If no proof required, auto-verify; otherwise pending
            if reward and getattr(reward, 'requires_verification', True):
                initial_status = 'pending'
            else:
                initial_status = 'verified'

            review = CustomerReview.objects.create(
                customer=customer,
                reward=reward,
                tenant=tenant or getattr(customer, 'tenant', None),
                platform=platform or (reward.platform if reward else 'other'),
                rating=rating,
                review_text=review_text.strip(),
                product_id=product_id or '',
                proof_url=proof_url or '',
                status=initial_status,
                submitted_at=timezone.now(),
            )

            points_awarded = Decimal('0')
            if initial_status == 'verified' and reward:
                points_awarded = ReviewService._award_review_points(
                    customer, reward, review, tenant
                )

            logger.info('ReviewService.submit_review: %s -> platform=%s rating=%s status=%s',
                        customer.code, platform, rating, initial_status)

            return {
                'success': True,
                'review_id': review.id,
                'status': initial_status,
                'points_awarded': str(points_awarded),
                'pending_review': initial_status == 'pending',
            }

        except Exception as e:
            logger.error('ReviewService.submit_review error: %s', e)
            return {'success': False, 'error': str(e)}

    @staticmethod
    @transaction.atomic
    def verify_review(review_id: int, approved: bool = True,
                       verified_by: str = 'admin', reject_reason: str = '') -> dict:
        """
        Admin approves or rejects a pending review.
        If approved -> awards points. If rejected -> marks rejected with reason.
        """
        try:
            from ...models.social import CustomerReview

            try:
                review = CustomerReview.objects.select_for_update().get(id=review_id)
            except CustomerReview.DoesNotExist:
                return {'success': False, 'error': 'Review not found'}

            if review.status not in ('pending',):
                return {'success': False,
                        'error': f'Cannot verify review in status: {review.status}'}

            if approved:
                review.status = 'verified'
                review.verified_at = timezone.now()
                review.verified_by = verified_by
                review.save(update_fields=['status', 'verified_at', 'verified_by'])

                points_awarded = Decimal('0')
                if review.reward:
                    points_awarded = ReviewService._award_review_points(
                        review.customer, review.reward, review,
                        getattr(review, 'tenant', None)
                    )

                return {
                    'success': True,
                    'review_id': review_id,
                    'status': 'verified',
                    'points_awarded': str(points_awarded),
                }
            else:
                review.status = 'rejected'
                review.reject_reason = reject_reason
                review.save(update_fields=['status', 'reject_reason'])
                return {
                    'success': True,
                    'review_id': review_id,
                    'status': 'rejected',
                    'reason': reject_reason,
                }

        except Exception as e:
            logger.error('ReviewService.verify_review error: %s', e)
            return {'success': False, 'error': str(e)}

    # ── Internal ──────────────────────────────────────────────────────────────

    @staticmethod
    def _award_review_points(customer, reward, review, tenant) -> Decimal:
        """Award points for a verified review."""
        try:
            from ...services.earn.BonusEventService import BonusEventService
            pts = reward.points_reward or Decimal('0')
            if pts > 0:
                BonusEventService.award_bonus(
                    customer, pts,
                    reason=f'Review reward: {reward.platform}',
                    triggered_by='review',
                    tenant=tenant,
                )
                review.status = 'points_awarded'
                review.points_awarded = pts
                review.save(update_fields=['status', 'points_awarded'])
            return pts
        except Exception as e:
            logger.error('ReviewService._award_review_points error: %s', e)
            return Decimal('0')

    @staticmethod
    def approve(review=None, review_id: int = None, approved_by: str = 'admin') -> dict:
        """Alias for verify_review(approved=True) -- matches ReceiptSocialViewSet."""
        rid = review_id or (review.id if hasattr(review, 'id') else None)
        if not rid:
            return {'success': False, 'error': 'review_id required'}
        return ReviewService.verify_review(review_id=rid, approved=True, verified_by=approved_by)
