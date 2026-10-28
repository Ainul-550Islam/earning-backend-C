# api/admin_panel/budget_manager.py
"""Advertiser budget tracking and auto-pause management."""
from __future__ import annotations
import logging
from decimal import Decimal
from typing import Any, Dict, List
from django.utils import timezone
from django.core.cache import cache
from datetime import timedelta

logger = logging.getLogger(__name__)


class BudgetManager:
    """Track and enforce advertiser campaign budgets."""

    @classmethod
    def get_campaign_budget_status(cls, campaign_id: Any) -> Dict:
        cache_key = f'budget:campaign:{campaign_id}'
        cached = cache.get(cache_key)
        if cached:
            return cached
        try:
            from api.promotions.models import Campaign, TaskSubmission
            from django.db.models import Sum
            campaign = Campaign.objects.get(pk=campaign_id)
            total_budget = float(getattr(campaign, 'total_budget', 0) or 0)
            daily_budget = float(getattr(campaign, 'daily_budget', 0) or 0)
            today = timezone.now().date()
            spent_total = float(TaskSubmission.objects.filter(
                campaign_id=campaign_id, status='approved'
            ).aggregate(t=Sum('reward_usd'))['t'] or 0)
            spent_today = float(TaskSubmission.objects.filter(
                campaign_id=campaign_id, status='approved',
                created_at__date=today
            ).aggregate(t=Sum('reward_usd'))['t'] or 0)

            status = {
                'campaign_id': campaign_id,
                'total_budget': total_budget,
                'spent_total':  spent_total,
                'remaining_total': max(0, total_budget - spent_total),
                'total_pct': round(spent_total / max(total_budget, 1) * 100, 1),
                'daily_budget': daily_budget,
                'spent_today':  spent_today,
                'remaining_today': max(0, daily_budget - spent_today),
                'daily_pct': round(spent_today / max(daily_budget, 1) * 100, 1),
                'is_paused': campaign.status == 'paused',
            }
            # Auto-pause if budget exhausted
            if total_budget > 0 and spent_total >= total_budget:
                cls._auto_pause(campaign_id, 'total_budget_exhausted')
                status['auto_paused'] = True
            elif daily_budget > 0 and spent_today >= daily_budget:
                cls._auto_pause(campaign_id, 'daily_budget_exhausted')
                status['daily_auto_paused'] = True

            cache.set(cache_key, status, 60)
            return status
        except Exception as e:
            return {'campaign_id': campaign_id, 'error': str(e)}

    @classmethod
    def get_low_budget_campaigns(cls, threshold_pct: float = 20.0) -> List[Dict]:
        """Get campaigns below budget threshold."""
        results = []
        try:
            from api.promotions.models import Campaign
            from django.db.models import Q
            campaigns = Campaign.objects.filter(status='active').exclude(
                Q(total_budget=0) | Q(total_budget__isnull=True)
            )[:100]
            for c in campaigns:
                status = cls.get_campaign_budget_status(c.pk)
                if status.get('total_pct', 0) >= (100 - threshold_pct):
                    results.append(status)
        except Exception:
            pass
        return results

    @classmethod
    def set_campaign_budget(cls, campaign_id: Any, total_budget: float,
                             daily_budget: float = 0, actor=None) -> bool:
        try:
            from api.promotions.models import Campaign
            Campaign.objects.filter(pk=campaign_id).update(
                total_budget=total_budget, daily_budget=daily_budget
            )
            cache.delete(f'budget:campaign:{campaign_id}')
            if actor:
                from api.admin_panel.models.activity import AdminActivity
                AdminActivity.log(actor=actor, action='set_campaign_budget',
                                  model_name='Campaign', object_id=str(campaign_id),
                                  changes={'total_budget': total_budget, 'daily_budget': daily_budget})
            return True
        except Exception:
            return False

    @classmethod
    def _auto_pause(cls, campaign_id: Any, reason: str) -> None:
        try:
            from api.promotions.models import Campaign
            Campaign.objects.filter(pk=campaign_id, status='active').update(status='paused')
            logger.info(f"[BudgetManager] Auto-paused campaign {campaign_id}: {reason}")
        except Exception:
            pass

budget_manager = BudgetManager()