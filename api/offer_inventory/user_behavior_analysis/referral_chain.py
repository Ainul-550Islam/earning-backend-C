# api/offer_inventory/user_behavior_analysis/referral_chain.py
"""
Referral Chain Analyzer — Multi-level referral chain analysis and fraud detection.
"""
import logging
from decimal import Decimal
from django.db.models import Sum, Count
from django.utils import timezone

logger = logging.getLogger(__name__)


class ReferralChainAnalyzer:
    """Analyze referral chains for performance and fraud."""

    @staticmethod
    def get_chain(user, max_depth: int = 5) -> dict:
        """
        Get upward referral chain for a user.
        Returns chain list from direct referrer up to max_depth.
        """
        from api.offer_inventory.models import UserReferral
        chain   = []
        current = user
        for _ in range(max_depth):
            try:
                ref = UserReferral.objects.select_related('referrer').get(referred=current)
                chain.append({
                    'user'              : ref.referrer.username,
                    'user_id'           : str(ref.referrer.id),
                    'level'             : len(chain) + 1,
                    'total_earnings_gen': float(ref.total_earnings_generated),
                })
                current = ref.referrer
            except UserReferral.DoesNotExist:
                break
        return {
            'user'  : user.username,
            'chain' : chain,
            'depth' : len(chain),
        }

    @staticmethod
    def get_downline_stats(user) -> dict:
        """Stats for all users referred by this user (direct downline)."""
        from api.offer_inventory.models import UserReferral
        direct = UserReferral.objects.filter(referrer=user)
        direct_count = direct.count()
        converted    = direct.filter(is_converted=True).count()
        total_gen    = direct.aggregate(t=Sum('total_earnings_generated'))['t'] or Decimal('0')

        return {
            'direct_referrals'        : direct_count,
            'converted'               : converted,
            'conversion_rate_pct'     : round(converted / max(direct_count, 1) * 100, 1),
            'total_earnings_generated': float(total_gen),
        }

    @staticmethod
    def get_top_referrers(limit: int = 20) -> list:
        """Top referrers by downline earnings generated."""
        from api.offer_inventory.models import UserReferral
        return list(
            UserReferral.objects.values('referrer__username')
            .annotate(
                referrals  =Count('id'),
                converted  =Count('id', filter=__import__('django.db.models', fromlist=['Q']).Q(is_converted=True)),
                total_earned=Sum('total_earnings_generated'),
            )
            .order_by('-total_earned')[:limit]
        )

    @staticmethod
    def detect_referral_fraud(user) -> dict:
        """
        Detect suspicious referral patterns.
        Checks: bulk registrations, same-IP referrals, no conversions.
        """
        from api.offer_inventory.models import UserReferral
        from datetime import timedelta

        refs  = UserReferral.objects.filter(referrer=user)
        count = refs.count()
        if count < 5:
            return {'suspicious': False, 'reason': 'insufficient_data', 'count': count}

        # Check if all referrals registered within 2 hours of each other
        from django.db.models import Max, Min
        time_agg = refs.aggregate(earliest=Min('created_at'), latest=Max('created_at'))
        if time_agg['earliest'] and time_agg['latest']:
            span_hours = (
                time_agg['latest'] - time_agg['earliest']
            ).total_seconds() / 3600
            if count >= 10 and span_hours < 2:
                return {
                    'suspicious': True,
                    'reason'    : f'{count} referrals registered within {span_hours:.1f}h',
                    'count'     : count,
                    'action'    : 'review',
                }

        # Check zero-conversion referrals (all fake accounts?)
        zero_conv  = refs.filter(is_converted=False).count()
        zero_ratio = zero_conv / count
        if count >= 20 and zero_ratio > 0.95:
            return {
                'suspicious': True,
                'reason'    : f'{zero_ratio*100:.0f}% of referrals never converted',
                'count'     : count,
                'action'    : 'review',
            }

        return {'suspicious': False, 'reason': 'ok', 'count': count}

    @staticmethod
    def get_referral_network_graph(user, depth: int = 2) -> dict:
        """
        Get multi-level referral network for visualization.
        Returns nodes and edges for graph rendering.
        """
        from api.offer_inventory.models import UserReferral
        nodes = {user.username: {'level': 0, 'conversions': 0}}
        edges = []

        def traverse(referrer, current_depth):
            if current_depth >= depth:
                return
            refs = UserReferral.objects.filter(
                referrer=referrer
            ).select_related('referred')[:50]
            for ref in refs:
                name = ref.referred.username
                nodes[name] = {
                    'level'      : current_depth + 1,
                    'converted'  : ref.is_converted,
                    'earnings'   : float(ref.total_earnings_generated),
                }
                edges.append({
                    'from': referrer.username,
                    'to'  : name,
                })
                if current_depth + 1 < depth:
                    traverse(ref.referred, current_depth + 1)

        traverse(user, 0)
        return {'nodes': nodes, 'edges': edges, 'depth': depth}
