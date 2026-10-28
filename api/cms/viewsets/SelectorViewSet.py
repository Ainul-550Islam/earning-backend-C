# cms/viewsets/SelectorViewSet.py
"""
SelectorViewSet — exposes every Selector class in cms/selectors.py
as a clean, cached REST query endpoint.

Business value:
  • /selectors/top-earners/         — Leaderboard data (user-facing)
  • /selectors/user-stats/          — My stats overview (user-facing)
  • /selectors/conversion-stats/    — Admin revenue dashboard
  • /selectors/daily-conversions/   — Admin daily revenue chart
  • /selectors/active-offers/       — Offer feed with targeting
  • /selectors/referral-stats/      — Referral program analytics
  • /selectors/withdrawal-history/  — Admin payout queue

Previously: all these Selectors existed with caching + optimised queries
but ViewSets were bypassing them and re-writing inline querysets — leading
to N+1 queries and cache misses.
"""
import logging
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework_simplejwt.authentication import JWTAuthentication
from .cms_viewset_base import CMSUserThrottle, CMSSmallPagination

logger = logging.getLogger('cms.viewsets.selector')


class SelectorViewSet(viewsets.GenericViewSet):
    """
    Read-only optimised query endpoints backed by cms/selectors.py.
    All responses are cached at the selector layer.
    """
    authentication_classes = [JWTAuthentication]
    pagination_class = CMSSmallPagination

    # ─────────────────────────────────────────────────────────────────────────
    # User Selectors
    # ─────────────────────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'],
            permission_classes=[IsAuthenticated],
            throttle_classes=[CMSUserThrottle])
    def top_earners(self, request):
        """
        GET /api/cms/selectors/top-earners/?limit=10

        Returns top earners sorted by total USD earned.
        User-facing: leaderboard screen.
        """
        limit = min(int(request.query_params.get('limit', 10)), 50)
        try:
            from api.cms.selectors import UserSelector
            earners = UserSelector.get_top_earners(limit=limit)
            return Response({'top_earners': earners, 'count': len(earners)})
        except Exception as e:
            logger.error(f'[Selector] top_earners error: {e}')
            return Response({'top_earners': [], 'count': 0})

    @action(detail=False, methods=['get'],
            permission_classes=[IsAuthenticated],
            throttle_classes=[CMSUserThrottle])
    def my_stats(self, request):
        """
        GET /api/cms/selectors/my-stats/

        Returns comprehensive stats for the authenticated user:
        earnings, conversions, streak, referrals, level.
        User-facing: profile / dashboard overview.
        """
        try:
            from api.cms.selectors import UserSelector
            stats = UserSelector.get_user_stats(user_id=request.user.pk)
            return Response(stats)
        except Exception as e:
            logger.error(f'[Selector] my_stats error: {e}')
            return Response({'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'],
            permission_classes=[IsAdminUser],
            throttle_classes=[CMSUserThrottle])
    def user_stats_for(self, request):
        """
        GET /api/cms/selectors/user-stats/?user_id=42

        Admin: stats for any user.
        """
        user_id = request.query_params.get('user_id')
        if not user_id:
            return Response({'error': 'user_id required'}, status=400)
        try:
            from api.cms.selectors import UserSelector
            stats = UserSelector.get_user_stats(user_id=int(user_id))
            return Response(stats)
        except Exception as e:
            return Response({'error': str(e)}, status=500)

    @action(detail=False, methods=['get'],
            permission_classes=[IsAdminUser],
            throttle_classes=[CMSUserThrottle])
    def search_users(self, request):
        """
        GET /api/cms/selectors/search-users/?q=john&limit=20

        Admin: fast user search by username/email.
        """
        q     = request.query_params.get('q', '').strip()
        limit = min(int(request.query_params.get('limit', 20)), 100)
        if len(q) < 2:
            return Response({'error': 'query must be at least 2 chars'}, status=400)
        try:
            from api.cms.selectors import UserSelector
            users = UserSelector.search_users(q, limit=limit)
            from django.contrib.auth import get_user_model
            return Response({
                'results': [
                    {'id': u.pk, 'username': u.username, 'email': u.email}
                    for u in users
                ],
                'count': len(users),
            })
        except Exception as e:
            return Response({'error': str(e)}, status=500)

    @action(detail=False, methods=['get'],
            permission_classes=[IsAdminUser],
            throttle_classes=[CMSUserThrottle])
    def active_users(self, request):
        """
        GET /api/cms/selectors/active-users/?days=30

        Admin: users active in last N days (for targeted campaigns).
        """
        days = int(request.query_params.get('days', 30))
        try:
            from api.cms.selectors import UserSelector
            users = UserSelector.get_active_users(days=days)
            return Response({
                'active_users': [
                    {'id': u.pk, 'username': u.username}
                    for u in users[:200]
                ],
                'count': len(users),
                'days': days,
            })
        except Exception as e:
            return Response({'error': str(e)}, status=500)

    # ─────────────────────────────────────────────────────────────────────────
    # Virtual Currency Selectors
    # ─────────────────────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'],
            permission_classes=[IsAuthenticated],
            throttle_classes=[CMSUserThrottle])
    def my_balance(self, request):
        """
        GET /api/cms/selectors/my-balance/

        Returns full balance details including today's earnings.
        Optimised query with caching — use instead of raw model query.
        """
        try:
            from api.cms.selectors import VirtualCurrencySelector
            balance  = VirtualCurrencySelector.get_user_balance(request.user)
            today    = VirtualCurrencySelector.get_user_today_earnings(request.user)
            history  = VirtualCurrencySelector.get_user_transaction_history(
                request.user, limit=5
            )
            return Response({
                'balance': str(balance),
                'today_earnings': str(today),
                'recent_transactions': history,
            })
        except Exception as e:
            return Response({'error': str(e)}, status=500)

    # ─────────────────────────────────────────────────────────────────────────
    # Conversion / Revenue Selectors
    # ─────────────────────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'],
            permission_classes=[IsAdminUser],
            throttle_classes=[CMSUserThrottle])
    def conversion_stats(self, request):
        """
        GET /api/cms/selectors/conversion-stats/?days=30

        Admin: aggregated conversion stats (count, total revenue,
        avg payout, approval rate).
        Revenue dashboard use.
        """
        days = int(request.query_params.get('days', 30))
        try:
            from api.cms.selectors import ConversionSelector
            stats = ConversionSelector.get_conversion_stats(days=days)
            return Response(stats)
        except Exception as e:
            return Response({'error': str(e)}, status=500)

    @action(detail=False, methods=['get'],
            permission_classes=[IsAdminUser],
            throttle_classes=[CMSUserThrottle])
    def daily_conversions(self, request):
        """
        GET /api/cms/selectors/daily-conversions/?days=30

        Admin: daily conversion counts and revenue for charting.
        """
        days = int(request.query_params.get('days', 30))
        try:
            from api.cms.selectors import ConversionSelector
            data = ConversionSelector.get_daily_conversions(days=days)
            return Response({'daily': data, 'days': days})
        except Exception as e:
            return Response({'error': str(e)}, status=500)

    @action(detail=False, methods=['get'],
            permission_classes=[IsAuthenticated],
            throttle_classes=[CMSUserThrottle])
    def my_conversions(self, request):
        """
        GET /api/cms/selectors/my-conversions/?status=approved&limit=20

        Returns the authenticated user's conversion history.
        User-facing: earnings history screen.
        """
        conv_status = request.query_params.get('status', None)
        limit = min(int(request.query_params.get('limit', 20)), 100)
        try:
            from api.cms.selectors import ConversionSelector
            qs = ConversionSelector.get_user_conversions(
                request.user, status=conv_status, limit=limit
            )
            return Response({
                'conversions': list(qs.values(
                    'id', 'payout_usd', 'virtual_awarded',
                    'status', 'lead_id', 'created_at',
                )),
                'count': qs.count(),
            })
        except Exception as e:
            return Response({'error': str(e)}, status=500)

    # ─────────────────────────────────────────────────────────────────────────
    # Offer / Locker Selectors
    # ─────────────────────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'],
            permission_classes=[IsAuthenticated],
            throttle_classes=[CMSUserThrottle])
    def active_offers(self, request):
        """
        GET /api/cms/selectors/active-offers/?country=BD&device=mobile&limit=20

        Returns targeted active offers for the current user.
        Optimised: uses OfferSelector with caching by country+device.
        User-facing: main offerwall feed.
        """
        country = request.query_params.get('country', '')
        limit   = min(int(request.query_params.get('limit', 20)), 50)
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        from api.cms.logic import detect_device_type
        device = request.query_params.get('device', detect_device_type(user_agent))
        try:
            from api.cms.selectors import OfferSelector
            offers = OfferSelector.get_active_offers(
                country=country, device=device, limit=limit
            )
            return Response({'offers': offers, 'count': len(offers),
                             'country': country, 'device': device})
        except Exception as e:
            return Response({'error': str(e)}, status=500)

    @action(detail=False, methods=['get'],
            permission_classes=[IsAuthenticated],
            throttle_classes=[CMSUserThrottle])
    def locker_status(self, request):
        """
        GET /api/cms/selectors/locker-status/?locker_id=5

        Returns whether a content locker is unlocked for the current user.
        User-facing: content gate check before rendering locked content.
        """
        locker_id = request.query_params.get('locker_id')
        if not locker_id:
            return Response({'error': 'locker_id required'}, status=400)
        try:
            from api.cms.selectors import LockerSelector
            locker    = LockerSelector.get_locker(int(locker_id))
            unlocked  = LockerSelector.is_unlocked_for_user(
                int(locker_id),
                user=request.user,
                session_key=request.session.session_key or '',
            )
            return Response({
                'locker_id': int(locker_id),
                'is_unlocked': unlocked,
                'locker_type': getattr(locker, 'locker_type', 'standard') if locker else None,
            })
        except Exception as e:
            return Response({'error': str(e)}, status=500)

    # ─────────────────────────────────────────────────────────────────────────
    # Referral Selectors
    # ─────────────────────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'],
            permission_classes=[IsAuthenticated],
            throttle_classes=[CMSUserThrottle])
    def my_referral_stats(self, request):
        """
        GET /api/cms/selectors/my-referral-stats/

        Returns referral code, relationship count, and earnings.
        User-facing: referral program screen.
        """
        try:
            from api.cms.selectors import ReferralSelector
            code     = ReferralSelector.get_referral_code(request.user)
            earnings = ReferralSelector.get_referral_earnings(
                request.user, limit=20
            )
            return Response({
                'referral_code': code,
                'earnings': earnings,
                'total_earnings': sum(
                    float(e.get('amount', 0)) for e in earnings
                ),
            })
        except Exception as e:
            return Response({'error': str(e)}, status=500)

    # ─────────────────────────────────────────────────────────────────────────
    # Withdrawal / Admin Selectors
    # ─────────────────────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'],
            permission_classes=[IsAdminUser],
            throttle_classes=[CMSUserThrottle])
    def pending_withdrawals(self, request):
        """
        GET /api/cms/selectors/pending-withdrawals/?limit=50

        Admin: pending withdrawal requests sorted by oldest first.
        Admin panel: payout queue.
        """
        limit = min(int(request.query_params.get('limit', 50)), 200)
        try:
            from api.cms.selectors import WithdrawalSelector
            qs = WithdrawalSelector.get_pending(limit=limit)
            return Response({
                'withdrawals': list(qs.values(
                    'id', 'user__username', 'amount_usd',
                    'method', 'status', 'created_at',
                )),
                'count': qs.count(),
            })
        except Exception as e:
            return Response({'error': str(e)}, status=500)

    @action(detail=False, methods=['get'],
            permission_classes=[IsAuthenticated],
            throttle_classes=[CMSUserThrottle])
    def my_withdrawals(self, request):
        """
        GET /api/cms/selectors/my-withdrawals/

        User's own withdrawal history with status.
        """
        try:
            from api.cms.selectors import WithdrawalSelector
            qs = WithdrawalSelector.get_user_history(request.user, limit=50)
            return Response({
                'withdrawals': list(qs.values(
                    'id', 'amount_usd', 'fee_usd',
                    'net_usd', 'method', 'status', 'created_at',
                )),
                'count': qs.count(),
            })
        except Exception as e:
            return Response({'error': str(e)}, status=500)

    # ─────────────────────────────────────────────────────────────────────────
    # Leaderboard Selector
    # ─────────────────────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'],
            permission_classes=[IsAuthenticated],
            throttle_classes=[CMSUserThrottle])
    def leaderboard(self, request):
        """
        GET /api/cms/selectors/leaderboard/?period=weekly&limit=10

        Returns leaderboard entries from the optimised LeaderboardSelector.
        Cached at selector layer — preferred over raw LeaderboardEntry query.
        """
        period = request.query_params.get('period', 'weekly')
        limit  = min(int(request.query_params.get('limit', 10)), 100)
        try:
            from api.cms.selectors import LeaderboardSelector
            entries = LeaderboardSelector.get_top(period=period, limit=limit)
            my_rank = LeaderboardSelector.get_user_rank(request.user, period=period)
            return Response({
                'period': period,
                'entries': entries,
                'count': len(entries),
                'my_rank': my_rank,
            })
        except Exception as e:
            return Response({'error': str(e)}, status=500)

    # ─────────────────────────────────────────────────────────────────────────
    # Blog Selector
    # ─────────────────────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'],
            permission_classes=[IsAuthenticated],
            throttle_classes=[CMSUserThrottle])
    def trending_posts(self, request):
        """
        GET /api/cms/selectors/trending-posts/?limit=5

        Returns most-viewed blog posts from BlogSelector.
        User-facing: "Trending" section on homepage.
        """
        limit = min(int(request.query_params.get('limit', 5)), 20)
        try:
            from api.cms.selectors import BlogSelector
            posts = BlogSelector.get_trending(limit=limit)
            return Response({'posts': posts, 'count': len(posts)})
        except Exception as e:
            return Response({'posts': [], 'count': 0})
