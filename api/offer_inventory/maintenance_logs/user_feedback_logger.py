# api/offer_inventory/maintenance_logs/user_feedback_logger.py
"""User Feedback Logger — Capture and analyze user feedback."""
import logging
from datetime import timedelta
from django.utils import timezone
from django.db.models import Count, Avg, Q

logger = logging.getLogger(__name__)


class UserFeedbackLogger:
    """Log and analyze user feedback for product improvement."""

    @staticmethod
    def log(user, feedback_type: str, subject: str, message: str,
             rating: int = None, offer=None) -> object:
        """Log a piece of user feedback."""
        from api.offer_inventory.models import UserFeedback
        return UserFeedback.objects.create(
            user         =user,
            feedback_type=feedback_type,
            subject      =subject,
            message      =message,
            rating       =rating,
            offer        =offer,
        )

    @staticmethod
    def get_summary(days: int = 30) -> dict:
        """Feedback summary for a period."""
        from api.offer_inventory.models import UserFeedback
        since = timezone.now() - timedelta(days=days)
        agg   = UserFeedback.objects.filter(created_at__gte=since).aggregate(
            total      =Count('id'),
            avg_rating =Avg('rating'),
            bugs       =Count('id', filter=Q(feedback_type='bug')),
            features   =Count('id', filter=Q(feedback_type='feature')),
            complaints =Count('id', filter=Q(feedback_type='complaint')),
        )
        return {
            'total'        : agg['total'],
            'avg_rating'   : round(float(agg['avg_rating'] or 0), 1),
            'bugs'         : agg['bugs'],
            'feature_reqs' : agg['features'],
            'complaints'   : agg['complaints'],
            'period_days'  : days,
        }

    @staticmethod
    def get_top_feature_requests(limit: int = 10) -> list:
        """Most requested features."""
        from api.offer_inventory.models import UserFeedback
        return list(
            UserFeedback.objects.filter(feedback_type='feature')
            .values('subject')
            .annotate(count=Count('id'))
            .order_by('-count')[:limit]
        )

    @staticmethod
    def get_unresolved_bugs(limit: int = 50) -> list:
        """Open bug reports."""
        from api.offer_inventory.models import UserFeedback
        return list(
            UserFeedback.objects.filter(
                feedback_type='bug', status='open'
            )
            .select_related('user')
            .values('id', 'subject', 'message', 'user__username', 'created_at')
            .order_by('-created_at')[:limit]
        )

    @staticmethod
    def get_low_rated_feedback(max_rating: int = 2) -> list:
        """Feedback with low ratings (dissatisfied users)."""
        from api.offer_inventory.models import UserFeedback
        return list(
            UserFeedback.objects.filter(
                rating__lte=max_rating, rating__isnull=False
            )
            .select_related('user', 'offer')
            .values('subject', 'rating', 'user__username', 'created_at')
            .order_by('-created_at')[:50]
        )

    @staticmethod
    def resolve(feedback_id: str, admin_note: str = '') -> bool:
        """Mark feedback as resolved."""
        from api.offer_inventory.models import UserFeedback
        updated = UserFeedback.objects.filter(id=feedback_id).update(
            status='resolved',
            admin_note=admin_note,
            resolved_at=timezone.now(),
        )
        return updated > 0
