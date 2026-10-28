# cms/viewsets_new/SurveyRewardViewSet.py
"""
API ViewSets for Survey Reward Management.

v11b: Wired SurveyRewardService into every action.

Previous version queried models directly — bypassing:
  • Reward calculation logic (penalty accumulation, quality thresholds)
  • Pool budget checks (RewardPool.can_award())
  • Cache invalidation on reward creation
  • Audit trail creation (RewardTransaction with full metadata)
  • Event bus publish (cms_reward_earned signal)

Now every mutation goes through SurveyRewardService, which owns all
that logic. Read actions use the service's cached query methods.
"""
import logging
from decimal import Decimal, InvalidOperation
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q, Count, Sum, Avg
from django.utils import timezone

from ..models_new.survey_rewards import SurveyReward, RewardTransaction, RewardPool
from ..models_new.profile_surveys import SurveyCompletion

logger = logging.getLogger('cms.viewsets_new.survey_reward')


def _get_service():
    """Lazy-import SurveyRewardService to avoid circular imports at module load."""
    from ..services_new.SurveyRewardService import SurveyRewardService
    return SurveyRewardService()


class SurveyRewardViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Survey Reward management.
    All mutations delegated to SurveyRewardService.
    """
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['survey', 'reward_type', 'status', 'currency']

    def get_queryset(self):
        if self.request.user.is_staff:
            return SurveyReward.objects.all().select_related('survey', 'currency')
        return SurveyReward.objects.filter(
            survey__status='active'
        ).select_related('survey', 'currency')

    def get_serializer_class(self):
        from ..serializers_new.SurveyRewardSerializer import (
            SurveyRewardSerializer, SurveyRewardDetailSerializer
        )
        if self.action == 'list':
            return SurveyRewardSerializer
        return SurveyRewardDetailSerializer

    def perform_create(self, serializer):
        if not self.request.user.is_staff:
            raise PermissionError("Only staff can create rewards")
        serializer.save()

    # ── calculate_reward ──────────────────────────────────────────────────────

    @action(detail=True, methods=['post'])
    def calculate_reward(self, request, pk=None):
        """
        POST /v3/survey-rewards/{id}/calculate-reward/

        Calculate the exact reward for a survey completion via SurveyRewardService.
        Uses the service's penalty accumulation logic (quality, speed, attention).
        Returns full breakdown including any applied penalties.
        """
        reward_config = self.get_object()
        completion_uuid = request.data.get('completion_uuid')
        if not completion_uuid:
            return Response({'error': 'completion_uuid required'}, status=400)
        try:
            completion = SurveyCompletion.objects.get(uuid=completion_uuid)
        except SurveyCompletion.DoesNotExist:
            return Response({'error': 'Completion not found'}, status=404)

        try:
            svc = _get_service()
            reward_amount = svc.calculate_reward(completion, reward_config)
            breakdown = self._get_reward_breakdown(reward_config, completion, reward_amount)
            return Response({
                'reward_uuid':      str(reward_config.uuid),
                'completion_uuid':  str(completion_uuid),
                'calculated_reward': float(reward_amount),
                'base_reward':      float(reward_config.base_amount),
                'bonus_amount':     float(getattr(reward_config, 'bonus_amount', 0) or 0),
                'quality_score':    float(completion.quality_score or 0),
                'breakdown':        breakdown,
            })
        except Exception as e:
            logger.error(f'[SurveyRewardViewSet] calculate_reward error: {e}', exc_info=True)
            return Response({'error': str(e)}, status=400)

    def _get_reward_breakdown(self, reward_config, completion, final_amount):
        base = float(reward_config.base_amount)
        bonus = float(getattr(reward_config, 'bonus_amount', 0) or 0)
        penalties = []
        if getattr(completion, 'flagged_for_speeding', False):
            penalties.append({'type': 'speeding', 'pct': 50})
        failed = getattr(completion, 'failed_attention_checks', 0)
        if failed:
            penalties.append({'type': 'attention_checks',
                               'failed': failed,
                               'pct': min(failed * 10, 50)})
        return {
            'base_amount': base,
            'bonus_awarded': bonus if final_amount > base else 0,
            'penalties': penalties,
            'final_amount': float(final_amount),
        }

    # ── process_reward ────────────────────────────────────────────────────────

    @action(detail=True, methods=['post'])
    def process_reward(self, request, pk=None):
        """
        POST /v3/survey-rewards/{id}/process-reward/

        Full reward processing workflow via SurveyRewardService:
          1. Check RewardPool budget
          2. Calculate amount (with penalties)
          3. Create RewardTransaction record
          4. Credit virtual balance via WalletAdapter
          5. Fire cms_reward_earned signal
          6. Invalidate user balance cache

        Previously: admins called create_reward_transaction() manually,
        skipping steps 1, 4, 5, 6 entirely.
        """
        if not request.user.is_staff:
            return Response({'error': 'Admin access required'}, status=403)

        reward_config = self.get_object()
        completion_uuid = request.data.get('completion_uuid')
        if not completion_uuid:
            return Response({'error': 'completion_uuid required'}, status=400)

        try:
            completion = SurveyCompletion.objects.get(uuid=completion_uuid)
        except SurveyCompletion.DoesNotExist:
            return Response({'error': 'Completion not found'}, status=404)

        try:
            svc = _get_service()
            transactions = svc.process_survey_completion_rewards(str(completion.uuid))
            return Response({
                'success': True,
                'completion_uuid': str(completion.uuid),
                'transactions_created': len(transactions),
                'transactions': [
                    {
                        'uuid': str(tx.uuid),
                        'amount': float(tx.amount),
                        'currency': str(tx.currency),
                        'status': tx.status,
                    }
                    for tx in transactions
                ],
            }, status=status.HTTP_201_CREATED)
        except Exception as e:
            logger.error(f'[SurveyRewardViewSet] process_reward error: {e}', exc_info=True)
            return Response({'error': str(e)}, status=400)

    # ── pool_stats ────────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'])
    def pool_stats(self, request):
        """
        GET /v3/survey-rewards/pool-stats/

        Returns all active RewardPool budget utilisation via SurveyRewardService.
        Admin dashboard: see which pools are near exhaustion and need refilling.
        """
        if not request.user.is_staff:
            return Response({'error': 'Admin access required'}, status=403)
        try:
            svc = _get_service()
            stats = svc.get_pool_statistics()
            return Response(stats)
        except Exception as e:
            # Fallback: direct query
            pools = RewardPool.objects.filter(is_active=True)
            return Response({
                'pools': [
                    {
                        'id': p.pk,
                        'name': str(p),
                        'total_budget': float(getattr(p, 'total_budget', 0)),
                        'allocated': float(getattr(p, 'allocated', 0)),
                        'paid_out': float(getattr(p, 'paid_out', 0)),
                    }
                    for p in pools
                ],
                'error': str(e),
            })

    # ── pending_distributions ─────────────────────────────────────────────────

    @action(detail=False, methods=['get'])
    def pending_distributions(self, request):
        """
        GET /v3/survey-rewards/pending-distributions/

        Returns reward transactions in 'pending' state that haven't been
        credited yet. Admin use: spot check before batch processing.
        """
        if not request.user.is_staff:
            return Response({'error': 'Admin access required'}, status=403)
        try:
            svc = _get_service()
            pending = svc.get_pending_distributions(limit=100)
            return Response({
                'pending': pending,
                'count': len(pending),
            })
        except Exception as e:
            qs = RewardTransaction.objects.filter(
                status='pending'
            ).select_related('user', 'reward', 'completion').order_by('created_at')[:100]
            return Response({
                'pending': list(qs.values(
                    'uuid', 'user__username', 'amount', 'status', 'created_at'
                )),
                'count': qs.count(),
                'error': str(e),
            })

    # ── my_rewards ────────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'])
    def my_rewards(self, request):
        """
        GET /v3/survey-rewards/my-rewards/

        Authenticated user's reward transaction history via the service
        (uses cached query to avoid N+1).
        """
        try:
            svc = _get_service()
            rewards = svc.get_user_reward_history(request.user, limit=50)
            return Response({'rewards': rewards, 'count': len(rewards)})
        except Exception as e:
            qs = RewardTransaction.objects.filter(
                user=request.user
            ).select_related('reward', 'completion').order_by('-created_at')[:50]
            return Response({
                'rewards': list(qs.values(
                    'uuid', 'amount', 'currency__code',
                    'status', 'created_at',
                )),
                'count': qs.count(),
                'error': str(e),
            })

    # ── refill_pool ───────────────────────────────────────────────────────────

    @action(detail=True, methods=['post'], url_path='refill-pool')
    def refill_pool(self, request, pk=None):
        """
        POST /v3/survey-rewards/{id}/refill-pool/

        Admin: add budget to the reward pool associated with this reward config.
        Body: { "amount": "500.00", "notes": "Monthly top-up" }
        """
        if not request.user.is_superuser:
            return Response({'error': 'Superuser access required'}, status=403)

        reward_config = self.get_object()
        amount_raw = request.data.get('amount', '0')
        notes = request.data.get('notes', '')

        try:
            amount = Decimal(str(amount_raw))
            if amount <= 0:
                return Response({'error': 'amount must be positive'}, status=400)
        except InvalidOperation:
            return Response({'error': 'invalid amount'}, status=400)

        try:
            svc = _get_service()
            result = svc.refill_reward_pool(reward_config, amount, notes=notes,
                                             admin_user=request.user)
            return Response({'success': True, **result})
        except Exception as e:
            logger.error(f'[SurveyRewardViewSet] refill_pool error: {e}', exc_info=True)
            return Response({'error': str(e)}, status=400)


class RewardTransactionViewSet(viewsets.ModelViewSet):
    """
    ViewSet for RewardTransaction — read-heavy, write via SurveyRewardService.
    """
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['status', 'currency']

    def get_queryset(self):
        if self.request.user.is_staff:
            return RewardTransaction.objects.all().select_related(
                'user', 'reward', 'completion', 'currency'
            ).order_by('-created_at')
        return RewardTransaction.objects.filter(
            user=self.request.user
        ).select_related('reward', 'completion', 'currency').order_by('-created_at')

    def get_serializer_class(self):
        from ..serializers_new.SurveyRewardSerializer import RewardTransactionSerializer
        return RewardTransactionSerializer

    def create(self, request, *args, **kwargs):
        """Block direct creation — use SurveyRewardViewSet.process_reward instead."""
        return Response(
            {'error': 'Use POST /v3/survey-rewards/{id}/process-reward/ to create transactions.'},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    def destroy(self, request, *args, **kwargs):
        """Transactions are immutable — no deletion."""
        return Response(
            {'error': 'Reward transactions are immutable and cannot be deleted.'},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    @action(detail=True, methods=['post'])
    def retry(self, request, pk=None):
        """
        POST /v3/reward-transactions/{id}/retry/

        Admin: retry a failed reward transaction via SurveyRewardService.
        """
        if not request.user.is_staff:
            return Response({'error': 'Admin access required'}, status=403)
        tx = self.get_object()
        if tx.status != 'failed':
            return Response({'error': f'Cannot retry a {tx.status} transaction'},
                            status=400)
        try:
            svc = _get_service()
            result = svc.retry_failed_transaction(str(tx.uuid))
            return Response({'success': True, 'transaction_uuid': str(tx.uuid),
                             'result': result})
        except Exception as e:
            logger.error(f'[RewardTransactionViewSet] retry error: {e}', exc_info=True)
            return Response({'error': str(e)}, status=400)

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """
        GET /v3/reward-transactions/stats/

        Admin: aggregate stats (total paid, pending, failed) for dashboard.
        """
        if not request.user.is_staff:
            return Response({'error': 'Admin access required'}, status=403)
        try:
            svc = _get_service()
            return Response(svc.get_transaction_statistics())
        except Exception as e:
            agg = RewardTransaction.objects.aggregate(
                total=Sum('amount'),
                count=Count('id'),
            )
            return Response({**agg, 'error': str(e)})


class RewardPoolViewSet(viewsets.ModelViewSet):
    """
    ViewSet for RewardPool — budget management.
    """
    permission_classes = [IsAdminUser]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['is_active']
    queryset = RewardPool.objects.all().order_by('-created_at')

    def get_serializer_class(self):
        from ..serializers_new.SurveyRewardSerializer import RewardPoolSerializer
        return RewardPoolSerializer

    @action(detail=True, methods=['get'])
    def utilization(self, request, pk=None):
        """
        GET /v3/reward-pools/{id}/utilization/

        Returns budget utilization percentage and refill recommendation.
        """
        pool = self.get_object()
        try:
            svc = _get_service()
            stats = svc.get_pool_statistics()
            pool_stats = next(
                (p for p in stats.get('pools', []) if p.get('id') == pool.pk),
                None
            )
            if pool_stats:
                return Response(pool_stats)
        except Exception:
            pass
        total = float(getattr(pool, 'total_budget', 0) or 0)
        allocated = float(getattr(pool, 'allocated', 0) or 0)
        paid_out = float(getattr(pool, 'paid_out', 0) or 0)
        utilization_pct = (paid_out / total * 100) if total > 0 else 0
        return Response({
            'id': pool.pk,
            'total_budget': total,
            'allocated': allocated,
            'paid_out': paid_out,
            'utilization_pct': round(utilization_pct, 2),
            'needs_refill': utilization_pct > 80,
        })
