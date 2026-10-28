from typing import Dict, List, Any, Optional, Tuple, Union
# api/cms/viewsets/NewFeatureViewSets.py
"""
Professional ViewSets for new CMS features.
Each uses: throttling, pagination, filtering, proper permissions.
"""
import logging
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import (
    IsAuthenticated, IsAdminUser, AllowAny, IsAuthenticatedOrReadOnly
)
from rest_framework_simplejwt.authentication import JWTAuthentication

from .cms_viewset_base import (
    CMSViewSetMixin, CMSPagePagination, CMSSmallPagination,
    CMSAnonThrottle, CMSUserThrottle, CMSWriteThrottle,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# Referral ViewSet
# ─────────────────────────────────────────────

class ReferralViewSet(CMSViewSetMixin, viewsets.GenericViewSet):
    """
    GET  /api/cms/referral/stats/       — My referral stats + code
    GET  /api/cms/referral/referred/    — List of referred users
    POST /api/cms/referral/apply/       — Apply a referral code
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    pagination_class = CMSSmallPagination

    @action(detail=False, methods=['get'])
    def stats(self, request):
        from api.cms.services_new.ReferralService import ReferralService
        data = ReferralService.get_referral_stats(request.user)
        return Response(data)

    @action(detail=False, methods=['get'])
    def referred(self, request):
        from api.cms.services_new.ReferralService import ReferralService
        limit = int(request.query_params.get('limit', 50))
        users = ReferralService.get_referred_users(request.user, limit=limit)
        return Response({'results': users, 'count': len(users)})

    @action(detail=False, methods=['post'])
    def apply(self, request):
        code = request.data.get('code', '').strip()
        if not code:
            return Response({'error': 'code is required'}, status=status.HTTP_400_BAD_REQUEST)
        from api.cms.services_new.ReferralService import ReferralService
        result = ReferralService.apply_referral(request.user, code)
        if result['success']:
            return Response(result, status=status.HTTP_201_CREATED)
        return Response({'error': result.get('reason', 'unknown')},
                        status=status.HTTP_400_BAD_REQUEST)


# ─────────────────────────────────────────────
# Leaderboard ViewSet
# ─────────────────────────────────────────────

class LeaderboardViewSet(CMSViewSetMixin, viewsets.GenericViewSet):
    """
    GET /api/cms/leaderboard/top/        — Top 10 earners
    GET /api/cms/leaderboard/my_rank/    — My rank + score
    GET /api/cms/leaderboard/streak/     — My streak info
    GET /api/cms/leaderboard/milestones/ — Upcoming streak milestones
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticatedOrReadOnly]
    throttle_classes = [CMSAnonThrottle, CMSUserThrottle]

    @action(detail=False, methods=['get'], permission_classes=[AllowAny])
    def top(self, request):
        from api.cms.services_new.LeaderboardService import LeaderboardService
        period_type = request.query_params.get('period', 'weekly')
        category = request.query_params.get('category', 'earnings')
        limit = min(int(request.query_params.get('limit', 10)), 100)
        if period_type not in ('daily', 'weekly', 'monthly', 'alltime'):
            return Response({'error': 'invalid period'}, status=status.HTTP_400_BAD_REQUEST)
        data = LeaderboardService.get_top(period_type, category, limit)
        return Response({'results': data, 'period': period_type, 'category': category})

    @action(detail=False, methods=['get'])
    def my_rank(self, request):
        from api.cms.services_new.LeaderboardService import LeaderboardService
        all_ranks = LeaderboardService.get_all_ranks(request.user)
        return Response(all_ranks)

    @action(detail=False, methods=['get'])
    def streak(self, request):
        from api.cms.services_new.LeaderboardService import StreakService
        return Response(StreakService.get_streak_info(request.user))

    @action(detail=False, methods=['get'])
    def milestones(self, request):
        from api.cms.services_new.LeaderboardService import StreakService
        return Response(StreakService.get_upcoming_milestones(request.user))


# ─────────────────────────────────────────────
# Quiz ViewSet
# ─────────────────────────────────────────────

class QuizViewSet(CMSViewSetMixin, viewsets.GenericViewSet):
    """
    GET  /api/cms/quiz/                      — List quizzes
    GET  /api/cms/quiz/{slug}/               — Get quiz + questions
    POST /api/cms/quiz/{id}/start/           — Start attempt
    POST /api/cms/quiz/attempts/{id}/submit/ — Submit answers
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [AllowAny]
    pagination_class = CMSSmallPagination

    @action(detail=False, methods=['get'])
    def list_quizzes(self, request):
        from api.cms.services_new.QuizService import QuizService
        data = QuizService.list_quizzes(active_only=True, limit=50)
        return Response({'results': data, 'count': len(data)})

    @action(detail=False, methods=['get'], url_path='by-slug/(?P<slug>[^/.]+)')
    def by_slug(self, request, slug=None):
        from api.cms.services_new.QuizService import QuizService
        quiz = QuizService.get_quiz(slug)
        if not quiz:
            return Response({'error': 'Quiz not found'}, status=status.HTTP_404_NOT_FOUND)
        from api.cms.serializers import QuizTemplateSerializer
        return Response(QuizTemplateSerializer(quiz).data)

    @action(detail=True, methods=['post'])
    def start(self, request, pk=None):
        from api.cms.services_new.QuizService import QuizService
        ip = request.META.get('REMOTE_ADDR', '')
        user = request.user if request.user.is_authenticated else None
        session_key = request.session.session_key or ''
        result = QuizService.start_attempt(int(pk), user=user, session_key=session_key, ip=ip)
        if 'error' in result:
            return Response(result, status=status.HTTP_400_BAD_REQUEST)
        return Response(result, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='attempts/(?P<attempt_id>[0-9]+)/submit')
    def submit(self, request, pk=None, attempt_id=None):
        from api.cms.services_new.QuizService import QuizService
        answers = request.data.get('answers', {})
        if not answers:
            return Response({'error': 'answers required'}, status=status.HTTP_400_BAD_REQUEST)
        result = QuizService.submit_answers(int(attempt_id), answers)
        if 'error' in result:
            return Response(result, status=status.HTTP_400_BAD_REQUEST)
        return Response(result)


# ─────────────────────────────────────────────
# SmartLink ViewSet
# ─────────────────────────────────────────────

class SmartLinkViewSet(CMSViewSetMixin, viewsets.GenericViewSet):
    """
    GET  /api/cms/smartlinks/                      — List (admin)
    GET  /api/cms/smartlinks/{slug}/resolve/       — Resolve → redirect URL
    GET  /api/cms/smartlinks/{slug}/analytics/     — Stats
    POST /api/cms/smartlinks/                      — Create (admin)
    """
    authentication_classes = [JWTAuthentication]
    pagination_class = CMSSmallPagination

    def get_permissions(self):
        if self.action == 'resolve':
            return [AllowAny()]
        if self.action == 'analytics':
            return [IsAdminUser()]
        return [IsAdminUser()]

    @action(detail=False, methods=['get'], url_path='(?P<slug>[^/.]+)/resolve',
            permission_classes=[AllowAny])
    def resolve(self, request, slug=None):
        from api.cms.services_new.SmartLinkService import SmartLinkService
        ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR', '')).split(',')[0].strip()
        user = request.user if request.user.is_authenticated else None
        result = SmartLinkService.resolve(
            slug=slug, ip=ip,
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            user=user, session_key=request.session.session_key or '',
        )
        if 'error' in result:
            return Response(result, status=status.HTTP_404_NOT_FOUND)
        # Return redirect URL — frontend handles the redirect
        return Response({'redirect_url': result['redirect_url'],
                         'offer_title': result.get('offer_title', ''),
                         'payout_usd': result.get('payout_usd', 0)})

    @action(detail=False, methods=['get'],
            url_path='(?P<slug>[^/.]+)/analytics', permission_classes=[IsAdminUser])
    def analytics(self, request, slug=None):
        from api.cms.services_new.SmartLinkService import SmartLinkService
        days = int(request.query_params.get('days', 7))
        data = SmartLinkService.get_analytics(slug, days=days)
        return Response(data)


# ─────────────────────────────────────────────
# Withdrawal ViewSet
# ─────────────────────────────────────────────

class WithdrawalViewSet(CMSViewSetMixin, viewsets.GenericViewSet):
    """
    GET  /api/cms/withdrawals/              — My history
    POST /api/cms/withdrawals/request/      — Request payout
    GET  /api/cms/withdrawals/methods/      — My saved payment methods
    POST /api/cms/withdrawals/add_method/   — Add payment method
    GET  /api/cms/withdrawals/stats/        — My withdrawal stats
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    pagination_class = CMSSmallPagination
    throttle_classes = [CMSWriteThrottle]

    def get_throttles(self):
        if self.action == 'request_payout':
            from api.cms.throttling import CMSWithdrawalThrottle
            return [CMSWithdrawalThrottle()]
        return super().get_throttles()

    @action(detail=False, methods=['get'])
    def history(self, request):
        from api.cms.services_new.WithdrawalService import WithdrawalService
        limit = min(int(request.query_params.get('limit', 50)), 200)
        data = WithdrawalService.get_history(request.user, limit=limit)
        return Response({'results': data, 'count': len(data)})

    @action(detail=False, methods=['post'])
    def request_payout(self, request):
        from api.cms.services_new.WithdrawalService import WithdrawalService
        from decimal import Decimal
        method = request.data.get('method', '')
        account_id = request.data.get('account_id', '').strip()
        coins_raw = request.data.get('coins_amount', 0)
        if not method or not account_id:
            return Response({'error': 'method and account_id required'},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            coins = Decimal(str(coins_raw))
        except Exception:
            return Response({'error': 'invalid coins_amount'},
                            status=status.HTTP_400_BAD_REQUEST)
        result = WithdrawalService.request_withdrawal(
            request.user, method, account_id, coins
        )
        if result['success']:
            return Response(result, status=status.HTTP_201_CREATED)
        return Response({'error': result.get('error', 'Failed')},
                        status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'])
    def methods(self, request):
        from api.cms.services_new.WithdrawalService import WithdrawalService
        return Response(WithdrawalService.get_user_methods(request.user))

    @action(detail=False, methods=['post'])
    def add_method(self, request):
        from api.cms.services_new.WithdrawalService import WithdrawalService
        method = request.data.get('method', '')
        account_id = request.data.get('account_id', '').strip()
        if not method or not account_id:
            return Response({'error': 'method and account_id required'},
                            status=status.HTTP_400_BAD_REQUEST)
        result = WithdrawalService.add_method(
            request.user, method, account_id,
            account_name=request.data.get('account_name', ''),
            set_default=request.data.get('set_default', False),
        )
        if result['success']:
            return Response(result, status=status.HTTP_201_CREATED)
        return Response(result, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'])
    def stats(self, request):
        from api.cms.services_new.WithdrawalService import WithdrawalService
        return Response(WithdrawalService.get_withdrawal_stats(request.user))


# ─────────────────────────────────────────────
# UserProfile ViewSet
# ─────────────────────────────────────────────

class UserProfileViewSet(CMSViewSetMixin, viewsets.GenericViewSet):
    """
    GET   /api/cms/profile/            — My full dashboard
    PATCH /api/cms/profile/update/     — Update display_name, avatar, etc.
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get'])
    def dashboard(self, request):
        from api.cms.services_new.WithdrawalService import UserProfileService
        data = UserProfileService.get_dashboard(request.user)
        return Response(data)

    @action(detail=False, methods=['patch', 'put'])
    def update_profile(self, request):
        from api.cms.services_new.WithdrawalService import UserProfileService
        from api.cms.serializers import UserProfileSerializer
        profile = UserProfileService.get_or_create(request.user)
        serializer = UserProfileSerializer(profile, data=request.data, partial=True)
        if serializer.is_valid():
            allowed_fields = ['display_name', 'avatar_url', 'bio',
                              'email_notifications', 'push_notifications',
                              'show_on_leaderboard', 'preferred_currency', 'country']
            for field in allowed_fields:
                if field in serializer.validated_data:
                    setattr(profile, field, serializer.validated_data[field])
            profile.save(update_fields=[f for f in allowed_fields
                                         if f in serializer.validated_data] + ['updated_at'])
            return Response(UserProfileSerializer(profile).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ─────────────────────────────────────────────
# SiteConfig ViewSet (admin)
# ─────────────────────────────────────────────

class SiteConfigViewSet(CMSViewSetMixin, viewsets.GenericViewSet):
    """
    GET  /api/cms/site-config/          — Public site config
    GET  /api/cms/site-config/admin/    — Full config (admin)
    PUT  /api/cms/site-config/update/   — Update (admin)
    """
    authentication_classes = [JWTAuthentication]

    @action(detail=False, methods=['get'], permission_classes=[AllowAny])
    def public(self, request):
        from api.cms.services_new.WithdrawalService import SiteConfigService
        domain = request.get_host().split(':')[0]
        return Response(SiteConfigService.get_config(domain))

    @action(detail=False, methods=['get'], permission_classes=[IsAdminUser])
    def admin_full(self, request):
        from api.cms.models_new.site_config import SiteConfig
        from api.cms.serializers import SiteConfigSerializer
        config = SiteConfig.get_active()
        if not config:
            return Response({'message': 'No site config found'}, status=404)
        return Response(SiteConfigSerializer(config).data)

    @action(detail=False, methods=['put', 'patch'], permission_classes=[IsAdminUser])
    def update_config(self, request):
        from api.cms.models_new.site_config import SiteConfig
        from api.cms.serializers import SiteConfigSerializer
        config = SiteConfig.get_active()
        if not config:
            return Response({'error': 'No config found'}, status=404)
        ser = SiteConfigSerializer(config, data=request.data, partial=True)
        if ser.is_valid():
            ser.save()
            return Response(ser.data)
        return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)


# ─────────────────────────────────────────────
# FormBuilder ViewSet
# ─────────────────────────────────────────────

class FormBuilderViewSet(CMSViewSetMixin, viewsets.GenericViewSet):
    """
    GET  /api/cms/forms/{slug}/         — Get form schema
    POST /api/cms/forms/{id}/submit/    — Submit form
    GET  /api/cms/forms/{id}/submissions/ — List submissions (admin)
    """
    authentication_classes = [JWTAuthentication]
    pagination_class = CMSSmallPagination

    def get_permissions(self):
        if self.action in ('schema', 'submit'):
            return [AllowAny()]
        return [IsAdminUser()]

    @action(detail=False, methods=['get'], url_path='(?P<slug>[^/.]+)/schema',
            permission_classes=[AllowAny])
    def schema(self, request, slug=None):
        from api.cms.services_new.FormBuilderService import FormBuilderService
        form = FormBuilderService.get_form(slug)
        if not form:
            return Response({'error': 'Form not found'}, status=404)
        if form.requires_login and not request.user.is_authenticated:
            return Response({'error': 'Login required'}, status=401)
        return Response(FormBuilderService.get_form_schema(form))

    @action(detail=True, methods=['post'], permission_classes=[AllowAny])
    def submit(self, request, pk=None):
        from api.cms.services_new.FormBuilderService import FormBuilderService
        ip = request.META.get('REMOTE_ADDR', '')
        user = request.user if request.user.is_authenticated else None
        result = FormBuilderService.submit_form(
            form_id=int(pk), data=request.data,
            user=user, session_key=request.session.session_key or '',
            ip=ip, user_agent=request.META.get('HTTP_USER_AGENT', ''),
        )
        if result['success']:
            return Response(result, status=status.HTTP_201_CREATED)
        return Response(result, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['get'], permission_classes=[IsAdminUser])
    def submissions(self, request, pk=None):
        from api.cms.services_new.FormBuilderService import FormBuilderService
        limit = min(int(request.query_params.get('limit', 100)), 1000)
        data = FormBuilderService.get_submissions(int(pk), limit=limit)
        return Response({'results': data, 'count': len(data)})


# ─────────────────────────────────────────────
# Content Block ViewSet
# ─────────────────────────────────────────────

class ContentBlockViewSet(CMSViewSetMixin, viewsets.GenericViewSet):
    """
    GET    /api/cms/blocks/{parent_type}/{parent_id}/  — Get all blocks
    POST   /api/cms/blocks/                            — Add block
    PUT    /api/cms/blocks/{id}/                       — Update block
    DELETE /api/cms/blocks/{id}/                       — Delete block
    POST   /api/cms/blocks/reorder/                    — Reorder blocks
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAdminUser]

    @action(detail=False, methods=['get'],
            url_path='(?P<parent_type>[^/.]+)/(?P<parent_id>[0-9]+)',
            permission_classes=[AllowAny])
    def list_blocks(self, request, parent_type=None, parent_id=None):
        from api.cms.services_new.ContentBlockService import ContentBlockService
        blocks = ContentBlockService.get_blocks(parent_type, int(parent_id))
        return Response({'results': blocks, 'count': len(blocks)})

    @action(detail=False, methods=['post'])
    def add_block(self, request):
        from api.cms.services_new.ContentBlockService import ContentBlockService
        parent_type = request.data.get('parent_type', 'page')
        parent_id = request.data.get('parent_id')
        block_type = request.data.get('block_type', 'rich_text')
        data = request.data.get('data', {})
        if not parent_id:
            return Response({'error': 'parent_id required'}, status=400)
        block = ContentBlockService.add_block(
            parent_type, int(parent_id), block_type, data, user=request.user
        )
        return Response(block, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['put', 'patch'])
    def update_block(self, request, pk=None):
        from api.cms.services_new.ContentBlockService import ContentBlockService
        block = ContentBlockService.update_block(
            int(pk),
            data=request.data.get('data'),
            order=request.data.get('order'),
            is_visible=request.data.get('is_visible'),
        )
        if not block:
            return Response({'error': 'Block not found'}, status=404)
        return Response(block)

    @action(detail=True, methods=['delete'])
    def delete_block(self, request, pk=None):
        from api.cms.services_new.ContentBlockService import ContentBlockService
        success = ContentBlockService.delete_block(int(pk))
        if not success:
            return Response({'error': 'Block not found'}, status=404)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=['post'])
    def reorder(self, request):
        from api.cms.services_new.ContentBlockService import ContentBlockService
        parent_type = request.data.get('parent_type', 'page')
        parent_id = request.data.get('parent_id')
        block_ids = request.data.get('block_ids', [])
        if not parent_id or not block_ids:
            return Response({'error': 'parent_id and block_ids required'}, status=400)
        success = ContentBlockService.reorder_blocks(parent_type, int(parent_id), block_ids)
        return Response({'success': success})
