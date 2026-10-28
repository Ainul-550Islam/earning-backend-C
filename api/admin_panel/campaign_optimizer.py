# api/admin_panel/campaign_optimizer.py
"""Auto-optimize campaign settings via ML recommendations."""
from __future__ import annotations
import logging
from typing import Any, Dict, List
from django.utils import timezone
from django.core.cache import cache
from datetime import timedelta

logger = logging.getLogger(__name__)


class CampaignOptimizer:
    """AI-driven campaign optimization engine."""

    @classmethod
    def get_optimization_recommendations(cls, campaign_id: Any) -> Dict:
        """Get AI recommendations for a campaign."""
        cutoff = timezone.now() - timedelta(days=7)
        try:
            from api.promotions.models import Campaign, TaskSubmission
            from django.db.models import Count, Avg
            campaign = Campaign.objects.get(pk=campaign_id)
            stats = TaskSubmission.objects.filter(
                campaign_id=campaign_id, created_at__gte=cutoff
            ).aggregate(total=Count('id'), approved=Count('id', filter=__import__('django.db.models', fromlist=['Q']).Q(status='approved')))
            total = stats['total'] or 0
            approved = stats['approved'] or 0
            cr = approved / max(total, 1) * 100
            recommendations = []
            if cr < 20:
                recommendations.append({'type': 'low_cr', 'action': 'Simplify offer requirements', 'cr': round(cr, 1)})
            if total < 10:
                recommendations.append({'type': 'low_traffic', 'action': 'Increase payout or promote offer'})
            return {'campaign_id': campaign_id, 'stats': stats, 'cr': round(cr, 1), 'recommendations': recommendations}
        except Exception as e:
            return {'campaign_id': campaign_id, 'error': str(e)}

    @classmethod
    def auto_adjust_payout(cls, campaign_id: Any, target_cr: float, actor) -> Dict:
        """Automatically adjust payout to hit target conversion rate."""
        recs = cls.get_optimization_recommendations(campaign_id)
        current_cr = recs.get('cr', 0)
        try:
            from api.promotions.models import Campaign
            campaign = Campaign.objects.get(pk=campaign_id)
            current_payout = float(campaign.reward_usd or 0)
            if current_cr < target_cr and current_payout > 0:
                new_payout = current_payout * 1.1  # Increase by 10%
                campaign.reward_usd = new_payout
                campaign.save(update_fields=['reward_usd'])
                from api.admin_panel.models.activity import AdminActivity
                AdminActivity.log(actor=actor, action='auto_adjust_payout',
                                  model_name='Campaign', object_id=str(campaign_id),
                                  changes={'old_payout': current_payout, 'new_payout': new_payout, 'cr': current_cr})
                return {'success': True, 'old_payout': current_payout, 'new_payout': round(new_payout, 2)}
            return {'success': False, 'reason': 'CR target already met or payout is 0'}
        except Exception as e:
            return {'success': False, 'error': str(e)}

campaign_optimizer = CampaignOptimizer()