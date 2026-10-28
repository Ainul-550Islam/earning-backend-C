# api/cms/services/PopupService.py
"""
PopupService: CRUD, rule evaluation, stats recording, A/B test management.
"""
import logging
from datetime import timedelta
from typing import List, Dict, Optional, Any

from django.db import transaction
from django.db.models import Q, F, Sum, Avg, Count
from django.utils import timezone
from django.core.cache import cache

logger = logging.getLogger(__name__)


class PopupService:
    """Service class for popup management."""

    # ────────────────────────────────────────────────────
    # CRUD
    # ────────────────────────────────────────────────────

    @staticmethod
    def create_popup(data: Dict[str, Any]) -> Optional[Any]:
        """Create a new popup."""
        from api.cms.models_new.popup import Popup
        try:
            popup = Popup.objects.create(**data)
            logger.info(f"Created popup '{popup.name}' (id={popup.id})")
            return popup
        except Exception as e:
            logger.error(f"Error creating popup: {e}", exc_info=True)
            return None

    @staticmethod
    def update_popup(popup, data: Dict[str, Any]) -> bool:
        """Update popup fields."""
        try:
            for field, value in data.items():
                if hasattr(popup, field):
                    setattr(popup, field, value)
            popup.save()
            return True
        except Exception as e:
            logger.error(f"Error updating popup {popup.id}: {e}", exc_info=True)
            return False

    @staticmethod
    def delete_popup(popup, hard: bool = False) -> bool:
        """Delete or deactivate a popup."""
        try:
            if hard:
                popup.delete()
            else:
                popup.status = 'archived'
                popup.is_active = False
                popup.save(update_fields=['status', 'is_active'])
            return True
        except Exception as e:
            logger.error(f"Error deleting popup {popup.id}: {e}", exc_info=True)
            return False

    @staticmethod
    def get_active_popups(
        user=None,
        page_url: str = '',
        context: Optional[Dict] = None
    ) -> List[Any]:
        """
        Get active popups for a page/user.

        Args:
            user: Requesting user
            page_url: Current page URL
            context: Additional context dict

        Returns:
            List of active Popup objects
        """
        from api.cms.models_new.popup import Popup
        try:
            now = timezone.now()
            q = Q(is_active=True, status='active') & (
                Q(start_date__isnull=True) | Q(start_date__lte=now)
            ) & (
                Q(end_date__isnull=True) | Q(end_date__gte=now)
            )

            # Visibility filtering
            if user and user.is_authenticated:
                q &= Q(show_to_logged_in=True)
            else:
                q &= Q(show_to_anonymous=True)

            popups = Popup.objects.filter(q).order_by('-priority')

            result = []
            for popup in popups:
                if PopupService._should_show_popup(popup, user, page_url, context):
                    result.append(popup)

            return result
        except Exception as e:
            logger.error(f"Error getting active popups: {e}", exc_info=True)
            return []

    @staticmethod
    def _should_show_popup(popup, user, page_url: str, context: Optional[Dict]) -> bool:
        """Check if popup should be shown based on rules and targeting."""
        try:
            # Check user level
            if popup.min_user_level > 0:
                user_level = getattr(user, 'level', 0) if user else 0
                if user_level < popup.min_user_level:
                    return False

            # Check target pages
            if popup.target_pages:
                matches = any(
                    pattern in page_url for pattern in popup.target_pages
                )
                if not matches:
                    return False

            # Check exclude pages
            if popup.exclude_pages:
                excluded = any(
                    pattern in page_url for pattern in popup.exclude_pages
                )
                if excluded:
                    return False

            # Evaluate trigger rules
            rules = popup.rules.filter(is_active=True).order_by('-priority')
            if rules.exists():
                ctx = context or {}
                triggered = any(rule.evaluate(ctx) for rule in rules)
                if not triggered:
                    return False

            return True
        except Exception as e:
            logger.error(f"Error evaluating popup {popup.id}: {e}")
            return False

    # ────────────────────────────────────────────────────
    # STATS RECORDING
    # ────────────────────────────────────────────────────

    @staticmethod
    def record_view(popup) -> None:
        """Record a popup view."""
        from api.cms.models_new.popup import PopupStat
        try:
            popup.record_view()
            PopupStat.record_view(popup)
        except Exception as e:
            logger.warning(f"Error recording popup view: {e}")

    @staticmethod
    def record_click(popup) -> None:
        """Record a popup CTA click."""
        from api.cms.models_new.popup import PopupStat
        try:
            popup.record_click()
            PopupStat.record_click(popup)
        except Exception as e:
            logger.warning(f"Error recording popup click: {e}")

    @staticmethod
    def record_dismissal(popup) -> None:
        """Record a popup dismissal."""
        from api.cms.models_new.popup import PopupStat
        try:
            popup.record_dismissal()
            PopupStat.record_dismissal(popup)
        except Exception as e:
            logger.warning(f"Error recording popup dismissal: {e}")

    @staticmethod
    def record_conversion(popup) -> None:
        """Record a popup conversion."""
        try:
            popup.record_conversion()
        except Exception as e:
            logger.warning(f"Error recording popup conversion: {e}")

    # ────────────────────────────────────────────────────
    # STATISTICS
    # ────────────────────────────────────────────────────

    @staticmethod
    def get_popup_stats(popup, days: int = 30) -> Dict[str, Any]:
        """Get popup statistics for last N days."""
        from api.cms.models_new.popup import PopupStat
        try:
            period_stats = PopupStat.get_period_stats(popup, days=days)
            return {
                'popup_id': popup.id,
                'popup_name': popup.name,
                'all_time': {
                    'total_views': popup.total_views,
                    'total_clicks': popup.total_clicks,
                    'total_dismissals': popup.total_dismissals,
                    'total_conversions': popup.total_conversions,
                    'ctr': popup.click_through_rate,
                    'conversion_rate': popup.conversion_rate,
                    'dismissal_rate': popup.dismissal_rate,
                },
                'period': {
                    'days': days,
                    **{k: (v or 0) for k, v in (period_stats or {}).items()},
                }
            }
        except Exception as e:
            logger.error(f"Error getting popup stats: {e}", exc_info=True)
            return {}

    @staticmethod
    def get_all_popup_stats() -> List[Dict[str, Any]]:
        """Get stats for all active popups."""
        from api.cms.models_new.popup import Popup
        popups = Popup.objects.filter(is_active=True).order_by('-total_views')
        return [PopupService.get_popup_stats(p) for p in popups]

    # ────────────────────────────────────────────────────
    # RULES
    # ────────────────────────────────────────────────────

    @staticmethod
    def add_rule(popup, trigger_type: str, conditions: Optional[Dict] = None) -> Optional[Any]:
        """Add a trigger rule to a popup."""
        from api.cms.models_new.popup import PopupRule
        try:
            rule = PopupRule.objects.create(
                popup=popup,
                trigger_type=trigger_type,
                conditions=conditions or {},
            )
            return rule
        except Exception as e:
            logger.error(f"Error adding popup rule: {e}", exc_info=True)
            return None

    @staticmethod
    def remove_rule(rule) -> bool:
        """Remove a popup trigger rule."""
        try:
            rule.delete()
            return True
        except Exception as e:
            logger.error(f"Error removing popup rule: {e}", exc_info=True)
            return False

    # ────────────────────────────────────────────────────
    # A/B TESTING
    # ────────────────────────────────────────────────────

    @staticmethod
    def create_ab_test(popup, name: str, variant_a: str, variant_b: str, split_pct: float = 50.0) -> Optional[Any]:
        """Create an A/B test for a popup."""
        from api.cms.models_new.popup import PopupABTest
        try:
            test = PopupABTest.objects.create(
                popup=popup,
                name=name,
                variant_a=variant_a,
                variant_b=variant_b,
                split_pct=split_pct,
                status='running',
            )
            logger.info(f"Created A/B test '{name}' for popup {popup.id}")
            return test
        except Exception as e:
            logger.error(f"Error creating A/B test: {e}", exc_info=True)
            return None

    @staticmethod
    def end_ab_test(test, winner: Optional[str] = None) -> bool:
        """End an A/B test."""
        try:
            test.end_test(winner=winner)
            return True
        except Exception as e:
            logger.error(f"Error ending A/B test {test.id}: {e}", exc_info=True)
            return False

    @staticmethod
    def get_ab_test_result(test) -> Dict[str, Any]:
        """Get A/B test results."""
        return {
            'test_id': test.id,
            'name': test.name,
            'status': test.status,
            'split_pct': test.split_pct,
            'variant_a': {
                'name': test.variant_a_name,
                'views': test.variant_a_views,
                'conversions': test.variant_a_conversions,
                'conversion_rate': test.variant_a_conversion_rate,
            },
            'variant_b': {
                'name': test.variant_b_name,
                'views': test.variant_b_views,
                'conversions': test.variant_b_conversions,
                'conversion_rate': test.variant_b_conversion_rate,
            },
            'winner': test.winner,
            'has_sufficient_data': test.has_sufficient_data,
            'ended_at': test.ended_at,
        }

    # ────────────────────────────────────────────────────
    # DAILY ANALYTICS AGGREGATION
    # ────────────────────────────────────────────────────

    @staticmethod
    def aggregate_daily_stats() -> int:
        """Aggregate popup daily stats (call from celery task)."""
        from api.cms.models_new.popup import Popup, PopupStat
        today = timezone.now().date()
        popups = Popup.objects.filter(is_active=True)
        updated = 0
        for popup in popups:
            try:
                stat, _ = PopupStat.objects.get_or_create(popup=popup, date=today)
                # Recalculate conversion rate
                if stat.clicks > 0:
                    stat.conversion_rate = round((stat.conversions / stat.clicks) * 100, 2)
                    stat.save(update_fields=['conversion_rate'])
                updated += 1
            except Exception as e:
                logger.error(f"Error aggregating stats for popup {popup.id}: {e}")
        return updated
