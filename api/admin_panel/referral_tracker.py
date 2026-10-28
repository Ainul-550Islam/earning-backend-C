# api/admin_panel/referral_tracker.py
"""Multi-level referral tracking and commission admin."""
from __future__ import annotations
import logging
from typing import Any, Dict, List
from django.utils import timezone
from django.db.models import Sum, Count
from datetime import timedelta

logger = logging.getLogger(__name__)

class ReferralTrackerAdmin:
    @classmethod
    def get_referral_stats(cls, days: int = 30) -> Dict:
        cutoff = timezone.now() - timedelta(days=days)
        try:
            from api.referral.models import Referral
            return {
                'total': Referral.objects.count(),
                'active': Referral.objects.filter(is_active=True).count(),
                'new_period': Referral.objects.filter(created_at__gte=cutoff).count(),
                'commissions_paid': 0,
            }
        except Exception as e: return {'error': str(e)}

    @classmethod
    def get_top_referrers(cls, limit: int = 20, days: int = 30) -> List[Dict]:
        cutoff = timezone.now() - timedelta(days=days)
        try:
            from api.referral.models import Referral
            return list(Referral.objects.filter(created_at__gte=cutoff)
                .values('referrer_id', 'referrer__username')
                .annotate(referred_count=Count('id')).order_by('-referred_count')[:limit])
        except Exception: return []

    @classmethod
    def adjust_commission_rate(cls, referrer_id: Any, rate: float, actor=None) -> bool:
        try:
            from api.referral.models import ReferralSettings
            ReferralSettings.objects.filter(user_id=referrer_id).update(commission_rate=rate)
            if actor:
                from api.admin_panel.models.activity import AdminActivity
                AdminActivity.log(actor=actor, action='adjust_referral_commission',
                                  changes={'user_id': referrer_id, 'rate': rate})
            return True
        except Exception: return False

    @classmethod
    def get_referral_chain(cls, user_id: Any, depth: int = 3) -> Dict:
        try:
            from api.referral.models import Referral
            chain = {'user_id': user_id, 'referrals': []}
            refs = Referral.objects.filter(referrer_id=user_id).values('referred_id', 'created_at')[:50]
            chain['referrals'] = list(refs)
            chain['total'] = len(chain['referrals'])
            return chain
        except Exception as e: return {'user_id': user_id, 'error': str(e)}

referral_tracker_admin = ReferralTrackerAdmin()