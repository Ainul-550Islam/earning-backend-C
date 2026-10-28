# api/referral/search.py
# Search functionality for referral module
# Admin can search referrals, codes, users by various criteria
# ============================================================

import logging
from typing import Dict, List, Optional
from django.db.models import Q

logger = logging.getLogger(__name__)


class ReferralSearch:
    """
    Search across referral data.
    Used by admin views and API endpoints.
    """

    @staticmethod
    def search_referrals(query: str, limit: int = 50) -> List[Dict]:
        """
        Search referrals by referrer username, referred username, or IP.
        """
        from api.referral.models import Referral
        if not query or len(query) < 2:
            return []

        qs = Referral.objects.filter(
            Q(referrer__username__icontains=query) |
            Q(referred_user__username__icontains=query) |
            Q(referrer__email__icontains=query) |
            Q(referred_user__email__icontains=query) |
            Q(registration_ip__icontains=query)
        ).select_related('referrer', 'referred_user').order_by('-created_at')[:limit]

        return [
            {
                'id':            r.id,
                'referrer':      r.referrer.username,
                'referred_user': r.referred_user.username,
                'level':         r.level,
                'is_suspicious': r.is_suspicious,
                'created_at':    r.created_at.isoformat(),
            }
            for r in qs
        ]

    @staticmethod
    def search_codes(query: str, limit: int = 20) -> List[Dict]:
        """
        Search referral codes by code, custom code, or username.
        """
        from api.referral.models import ReferralCode
        if not query or len(query) < 2:
            return []

        qs = ReferralCode.objects.filter(
            Q(code__icontains=query) |
            Q(custom_code__icontains=query) |
            Q(user__username__icontains=query)
        ).select_related('user').order_by('-conversions')[:limit]

        return [
            {
                'id':          c.id,
                'code':        c.code,
                'custom_code': c.custom_code,
                'user':        c.user.username,
                'is_active':   c.is_active,
                'conversions': c.conversions,
                'clicks':      c.clicks,
            }
            for c in qs
        ]

    @staticmethod
    def search_commissions(query: str, limit: int = 50) -> List[Dict]:
        """
        Search commission logs by username or wallet transaction ID.
        """
        from api.referral.models import CommissionLog
        if not query or len(query) < 2:
            return []

        qs = CommissionLog.objects.filter(
            Q(user__username__icontains=query) |
            Q(referred_user__username__icontains=query) |
            Q(wallet_transaction_id__icontains=query) |
            Q(source_reference__icontains=query)
        ).select_related('user', 'referred_user').order_by('-created_at')[:limit]

        return [
            {
                'id':             c.id,
                'user':           c.user.username,
                'referred_user':  c.referred_user.username,
                'amount':         float(c.amount),
                'level':          c.level,
                'status':         c.status,
                'created_at':     c.created_at.isoformat(),
            }
            for c in qs
        ]

    @staticmethod
    def search_suspicious(query: str, limit: int = 20) -> List[Dict]:
        """Search suspicious referrals."""
        from api.referral.models import SuspiciousReferral
        if not query or len(query) < 2:
            return []

        qs = SuspiciousReferral.objects.filter(
            Q(referral__referrer__username__icontains=query) |
            Q(referral__referred_user__username__icontains=query)
        ).select_related(
            'referral__referrer', 'referral__referred_user'
        ).order_by('-fraud_score')[:limit]

        return [
            {
                'id':            sr.id,
                'referrer':      sr.referral.referrer.username,
                'referred_user': sr.referral.referred_user.username,
                'fraud_score':   sr.fraud_score,
                'status':        sr.status,
                'detected_at':   sr.detected_at.isoformat(),
            }
            for sr in qs
        ]

    @staticmethod
    def global_search(query: str) -> Dict:
        """
        Search across all referral entities simultaneously.
        """
        return {
            'referrals':   ReferralSearch.search_referrals(query, limit=10),
            'codes':       ReferralSearch.search_codes(query, limit=10),
            'commissions': ReferralSearch.search_commissions(query, limit=10),
            'suspicious':  ReferralSearch.search_suspicious(query, limit=10),
            'query':       query,
        }