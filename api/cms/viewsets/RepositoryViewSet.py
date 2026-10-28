# cms/viewsets/RepositoryViewSet.py
"""
RepositoryViewSet — exposes cms/repositories.py as admin REST endpoints.

Business value:
  The repository pattern provides optimised, cached, typed access to every
  data entity.  Previously services bypassed repositories and queried models
  directly, losing caching + query optimisation benefits.

  This ViewSet provides admin endpoints so ops can:
  • Inspect live data via the clean repository API
  • Trigger repository-level operations (mark conversion, update status)
  • View click deduplication stats
  • Audit notification delivery counts
  • Inspect form submission data

  Normal user-facing data is NOT exposed here — repositories are admin/ops only.
"""
import logging
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser
from rest_framework_simplejwt.authentication import JWTAuthentication
from .cms_viewset_base import CMSUserThrottle, CMSWriteThrottle

logger = logging.getLogger('cms.viewsets.repository')


class RepositoryViewSet(viewsets.GenericViewSet):
    """
    Admin-only repository operations.
    All data access goes through the repository layer for caching + type safety.
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAdminUser]

    # ─────────────────────────────────────────────────────────────────────────
    # UserRepository
    # ─────────────────────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'], throttle_classes=[CMSUserThrottle])
    def user_lookup(self, request):
        """
        GET /api/cms/repo/user-lookup/?user_id=42
        GET /api/cms/repo/user-lookup/?username=johndoe

        Lookup a user via the optimised UserRepository.
        """
        user_id  = request.query_params.get('user_id')
        username = request.query_params.get('username', '').strip()
        try:
            from api.cms.repositories import UserRepository
            if user_id:
                user = UserRepository.get_by_id(int(user_id))
            elif username:
                user = UserRepository.get_by_username(username)
            else:
                return Response({'error': 'user_id or username required'}, status=400)

            if not user:
                return Response({'error': 'User not found'}, status=404)
            return Response({
                'id': user.pk,
                'username': user.username,
                'email': user.email,
                'is_active': user.is_active,
                'date_joined': str(user.date_joined),
            })
        except Exception as e:
            return Response({'error': str(e)}, status=500)

    @action(detail=False, methods=['get'], throttle_classes=[CMSUserThrottle])
    def user_exists(self, request):
        """
        GET /api/cms/repo/user-exists/?user_id=42

        Check if user exists via repository (uses cache).
        Useful for integration health checks.
        """
        user_id = request.query_params.get('user_id')
        if not user_id:
            return Response({'error': 'user_id required'}, status=400)
        try:
            from api.cms.repositories import UserRepository
            exists = UserRepository.exists(int(user_id))
            return Response({'user_id': int(user_id), 'exists': exists})
        except Exception as e:
            return Response({'error': str(e)}, status=500)

    # ─────────────────────────────────────────────────────────────────────────
    # VirtualBalanceRepository
    # ─────────────────────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'], throttle_classes=[CMSUserThrottle])
    def user_balance(self, request):
        """
        GET /api/cms/repo/user-balance/?user_id=42

        Returns user's virtual balance via VirtualBalanceRepository.
        """
        user_id = request.query_params.get('user_id')
        if not user_id:
            return Response({'error': 'user_id required'}, status=400)
        try:
            from api.cms.repositories import UserRepository, VirtualBalanceRepository
            from django.contrib.auth import get_user_model
            user = get_user_model().objects.get(pk=int(user_id))
            vb, created = VirtualBalanceRepository.get_or_create(user)
            return Response({
                'user_id': int(user_id),
                'balance': str(getattr(vb, 'balance', 0)),
                'total_earned': str(getattr(vb, 'total_earned', 0)),
                'created': created,
            })
        except Exception as e:
            return Response({'error': str(e)}, status=500)

    @action(detail=False, methods=['post'], throttle_classes=[CMSWriteThrottle])
    def admin_add_coins(self, request):
        """
        POST /api/cms/repo/add-coins/

        Body: { "user_id": 42, "amount": 500, "description": "Manual bonus" }

        Admin: add coins to a user via VirtualBalanceRepository.
        Creates a full audit trail unlike a direct model update.
        """
        user_id     = request.data.get('user_id')
        amount      = request.data.get('amount', 0)
        description = request.data.get('description', 'Admin adjustment')
        if not user_id or not amount:
            return Response({'error': 'user_id and amount required'}, status=400)
        try:
            from decimal import Decimal
            from django.contrib.auth import get_user_model
            from api.cms.repositories import VirtualBalanceRepository
            user = get_user_model().objects.get(pk=int(user_id))
            ok = VirtualBalanceRepository.add_coins(
                user=user,
                amount=Decimal(str(amount)),
                source_id=f'admin_{request.user.pk}',
                description=description,
            )
            return Response({'success': ok, 'user_id': int(user_id), 'coins_added': amount})
        except Exception as e:
            return Response({'error': str(e)}, status=500)

    # ─────────────────────────────────────────────────────────────────────────
    # ConversionLogRepository
    # ─────────────────────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'], throttle_classes=[CMSUserThrottle])
    def lead_exists(self, request):
        """
        GET /api/cms/repo/lead-exists/?lead_id=xyz123

        Check if a lead_id has already been processed (deduplication check).
        Useful for CPAlead integration debugging.
        """
        lead_id = request.query_params.get('lead_id', '').strip()
        if not lead_id:
            return Response({'error': 'lead_id required'}, status=400)
        try:
            from api.cms.repositories import ConversionLogRepository
            exists = ConversionLogRepository.exists_by_lead_id(lead_id)
            return Response({'lead_id': lead_id, 'already_processed': exists})
        except Exception as e:
            return Response({'error': str(e)}, status=500)

    @action(detail=False, methods=['get'], throttle_classes=[CMSUserThrottle])
    def user_conversions(self, request):
        """
        GET /api/cms/repo/user-conversions/?user_id=42&limit=20

        Returns conversion history via ConversionLogRepository.
        """
        user_id = request.query_params.get('user_id')
        limit   = min(int(request.query_params.get('limit', 20)), 100)
        if not user_id:
            return Response({'error': 'user_id required'}, status=400)
        try:
            from django.contrib.auth import get_user_model
            from api.cms.repositories import ConversionLogRepository
            user = get_user_model().objects.get(pk=int(user_id))
            qs = ConversionLogRepository.get_by_user(user, limit=limit)
            return Response({
                'conversions': list(qs.values(
                    'id', 'payout_usd', 'virtual_awarded', 'status',
                    'lead_id', 'created_at',
                )),
                'user_stats': ConversionLogRepository.get_stats_for_user(user),
            })
        except Exception as e:
            return Response({'error': str(e)}, status=500)

    @action(detail=False, methods=['post'], throttle_classes=[CMSWriteThrottle])
    def mark_conversion_approved(self, request):
        """
        POST /api/cms/repo/mark-conversion-approved/

        Body: { "conversion_id": 42, "virtual_amount": 200 }

        Admin: mark a conversion as approved via the repository
        (triggers cache invalidation + downstream effects).
        """
        conv_id        = request.data.get('conversion_id')
        virtual_amount = request.data.get('virtual_amount', 0)
        if not conv_id:
            return Response({'error': 'conversion_id required'}, status=400)
        try:
            from decimal import Decimal
            from api.cms.repositories import ConversionLogRepository
            ok = ConversionLogRepository.mark_approved(
                conversion_id=int(conv_id),
                virtual_amount=Decimal(str(virtual_amount)),
            )
            return Response({'success': ok, 'conversion_id': int(conv_id)})
        except Exception as e:
            return Response({'error': str(e)}, status=500)

    # ─────────────────────────────────────────────────────────────────────────
    # ClickLogRepository
    # ─────────────────────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'], throttle_classes=[CMSUserThrottle])
    def click_ip_count(self, request):
        """
        GET /api/cms/repo/click-ip-count/?ip=1.2.3.4&hours=1

        Returns click count from a given IP in the last N hours.
        Fraud detection tool: identify click farms.
        """
        ip    = request.query_params.get('ip', '').strip()
        hours = int(request.query_params.get('hours', 1))
        if not ip:
            return Response({'error': 'ip required'}, status=400)
        try:
            from api.cms.repositories import ClickLogRepository
            count = ClickLogRepository.count_by_ip(ip, window_hours=hours)
            suspicious = count > 10
            return Response({
                'ip': ip,
                'click_count': count,
                'window_hours': hours,
                'suspicious': suspicious,
            })
        except Exception as e:
            return Response({'error': str(e)}, status=500)

    # ─────────────────────────────────────────────────────────────────────────
    # WithdrawalRepository
    # ─────────────────────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'], throttle_classes=[CMSUserThrottle])
    def pending_withdrawals(self, request):
        """
        GET /api/cms/repo/pending-withdrawals/?limit=50

        Returns pending withdrawal requests via WithdrawalRepository.
        Payout queue for finance team.
        """
        limit = min(int(request.query_params.get('limit', 50)), 200)
        try:
            from api.cms.repositories import WithdrawalRepository
            qs = WithdrawalRepository.get_pending(limit=limit)
            return Response({
                'withdrawals': list(qs.values(
                    'id', 'user__username', 'amount_usd',
                    'method', 'created_at',
                )),
                'count': qs.count(),
            })
        except Exception as e:
            return Response({'error': str(e)}, status=500)

    @action(detail=False, methods=['post'], throttle_classes=[CMSWriteThrottle])
    def update_withdrawal_status(self, request):
        """
        POST /api/cms/repo/update-withdrawal-status/

        Body: { "request_id": 42, "status": "approved", "note": "..." }

        Update withdrawal status via repository (creates audit trail).
        """
        request_id = request.data.get('request_id')
        new_status = request.data.get('status', '')
        valid = ('pending', 'approved', 'paid', 'rejected', 'failed')
        if not request_id or new_status not in valid:
            return Response({'error': f'request_id and status ({valid}) required'}, status=400)
        try:
            from api.cms.repositories import WithdrawalRepository
            ok = WithdrawalRepository.update_status(
                request_id=int(request_id),
                status=new_status,
                processed_by_id=request.user.pk,
            )
            return Response({'success': ok, 'request_id': int(request_id),
                             'new_status': new_status})
        except Exception as e:
            return Response({'error': str(e)}, status=500)

    # ─────────────────────────────────────────────────────────────────────────
    # ReferralRepository
    # ─────────────────────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'], throttle_classes=[CMSUserThrottle])
    def referral_relationship(self, request):
        """
        GET /api/cms/repo/referral-relationship/?user_id=42

        Returns the referral relationship for a given user.
        """
        user_id = request.query_params.get('user_id')
        if not user_id:
            return Response({'error': 'user_id required'}, status=400)
        try:
            from django.contrib.auth import get_user_model
            from api.cms.repositories import ReferralRepository
            user = get_user_model().objects.get(pk=int(user_id))
            rel  = ReferralRepository.get_relationship(user)
            code = ReferralRepository.get_code(user)
            return Response({
                'user_id': int(user_id),
                'referral_code': getattr(code, 'code', None),
                'referred_by': getattr(
                    getattr(rel, 'referrer', None), 'username', None
                ) if rel else None,
            })
        except Exception as e:
            return Response({'error': str(e)}, status=500)

    # ─────────────────────────────────────────────────────────────────────────
    # NotificationRepository
    # ─────────────────────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'], throttle_classes=[CMSUserThrottle])
    def user_notifications(self, request):
        """
        GET /api/cms/repo/user-notifications/?user_id=42&limit=20

        Returns unread notifications via NotificationRepository.
        """
        user_id = request.query_params.get('user_id')
        limit   = min(int(request.query_params.get('limit', 20)), 100)
        if not user_id:
            return Response({'error': 'user_id required'}, status=400)
        try:
            from django.contrib.auth import get_user_model
            from api.cms.repositories import NotificationRepository
            user = get_user_model().objects.get(pk=int(user_id))
            qs   = NotificationRepository.get_unread(user, limit=limit)
            return Response({
                'notifications': list(qs.values(
                    'id', 'notification_type', 'title', 'message', 'created_at',
                )),
                'unread_count': qs.count(),
            })
        except Exception as e:
            return Response({'error': str(e)}, status=500)

    # ─────────────────────────────────────────────────────────────────────────
    # FormSubmissionRepository
    # ─────────────────────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'], throttle_classes=[CMSUserThrottle])
    def form_submissions(self, request):
        """
        GET /api/cms/repo/form-submissions/?form_id=5&limit=50

        Returns submissions for a specific dynamic form.
        """
        form_id = request.query_params.get('form_id')
        limit   = min(int(request.query_params.get('limit', 50)), 500)
        if not form_id:
            return Response({'error': 'form_id required'}, status=400)
        try:
            from api.cms.repositories import FormSubmissionRepository
            qs = FormSubmissionRepository.get_for_page(
                parent_type='form', parent_id=int(form_id)
            )
            return Response({
                'submissions': list(qs.values(
                    'id', 'user__username', 'data', 'created_at',
                )[:limit]),
                'count': qs.count(),
            })
        except Exception as e:
            return Response({'error': str(e)}, status=500)

    # ─────────────────────────────────────────────────────────────────────────
    # EnhancedRepositoryManager — health overview
    # ─────────────────────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'], throttle_classes=[CMSUserThrottle])
    def health(self, request):
        """
        GET /api/cms/repo/health/

        Returns repository layer health stats.
        Ops dashboard: see which repositories are responding.
        """
        repos = [
            'UserRepository', 'VirtualBalanceRepository',
            'ConversionLogRepository', 'ClickLogRepository',
            'WithdrawalRepository', 'ReferralRepository',
            'NotificationRepository', 'ContentBlockRepository',
            'FormSubmissionRepository', 'SmartLinkRepository',
            'UserProfileRepository', 'SurveyRepository',
            'RewardRepository',
        ]
        statuses = {}
        for repo_name in repos:
            try:
                import importlib
                mod = importlib.import_module('api.cms.repositories')
                getattr(mod, repo_name)
                statuses[repo_name] = 'ok'
            except Exception as e:
                statuses[repo_name] = f'error: {e}'

        all_ok = all(v == 'ok' for v in statuses.values())
        return Response({
            'status': 'ok' if all_ok else 'degraded',
            'repositories': statuses,
            'total': len(repos),
            'healthy': sum(1 for v in statuses.values() if v == 'ok'),
        })
