# publisher_tools/views_abtest.py
# ============================================================
# NEW FILE — ABTestViewSet
# A/B Testing management for publishers.
#
# Register in urls.py:
#   from .views_abtest import ABTestViewSet
#   router.register(r'ab-tests', ABTestViewSet, basename='ab-test')
# ============================================================
from decimal import Decimal
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from .mixins import PublisherViewMixin, AdminScriptViewMixin, AdminOnlyMixin, ErrorHandlingMixin

from core.views import BaseViewSet
from .models import ABTest, ABTestVariant, AdUnit
from .permissions import IsPublisher
from .serializers_abtest import (
    ABTestListSerializer,
    ABTestDetailSerializer,
    ABTestCreateSerializer,
    ABTestVariantSerializer,
    ABTestResultSerializer,
)


class ABTestViewSet(BaseViewSet):
    """
    A/B Test Management।
    Ad unit configuration-এর statistical A/B tests চালানোর জন্য।

    Actions:
      list        — publisher-এর সব tests
      create      — নতুন test তৈরি
      retrieve    — test detail + variant stats
      update      — test config update (draft only)
      destroy     — test delete (draft only)
      start       — test start (draft → running)
      pause       — running → paused
      resume      — paused → running
      complete    — manual completion
      results     — full statistical analysis
      declare_winner — winner declare করো
    """
    serializer_class   = ABTestDetailSerializer
    permission_classes = [IsAuthenticated, IsPublisher]

    def get_queryset(self):
        user = self.request.user
        qs = ABTest.objects.select_related(
            'publisher', 'ad_unit', 'winner_variant'
        ).prefetch_related('variants').all()

        if not user.is_staff:
            try:
                qs = qs.filter(publisher=user.publisher_profile)
            except Exception:
                return ABTest.objects.none()

        # Filters
        status_f   = self.request.query_params.get('status')
        test_type  = self.request.query_params.get('test_type')
        ad_unit_id = self.request.query_params.get('ad_unit_id')

        if status_f:
            qs = qs.filter(status=status_f)
        if test_type:
            qs = qs.filter(test_type=test_type)
        if ad_unit_id:
            qs = qs.filter(ad_unit__unit_id=ad_unit_id)

        return qs.order_by('-created_at')

    def get_serializer_class(self):
        if self.action == 'list':
            return ABTestListSerializer
        if self.action == 'create':
            return ABTestCreateSerializer
        if self.action == 'results':
            return ABTestResultSerializer
        return ABTestDetailSerializer

    def _check_publisher_ownership(self, test):
        user = self.request.user
        if user.is_staff:
            return
        try:
            if test.publisher != user.publisher_profile:
                from rest_framework.exceptions import PermissionDenied
                raise PermissionDenied('You do not own this A/B test.')
        except AttributeError:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('No publisher profile found.')

    def perform_create(self, serializer):
        try:
            publisher = self.request.user.publisher_profile
        except Exception:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('No active publisher profile found.')

        # Validate ad_unit ownership
        ad_unit = serializer.validated_data.get('ad_unit')
        if ad_unit and ad_unit.publisher != publisher:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('You do not own this ad unit.')

        # Generate test_id
        import uuid
        test_id = 'ABT' + uuid.uuid4().hex[:6].upper()
        serializer.save(publisher=publisher, test_id=test_id)

    # ── START ─────────────────────────────────────────────────────────────────

    @action(detail=True, methods=['post'], url_path='start')
    def start(self, request, pk=None):
        """
        Test start করে (draft → running)।
        POST /ab-tests/{id}/start/
        """
        test = self.get_object()
        self._check_publisher_ownership(test)

        if test.status != 'draft':
            return self.error_response(
                f'Cannot start a test in {test.status!r} status. Only draft tests can be started.',
                status_code=400,
            )

        # Validate variants exist and traffic splits sum to 100
        variants = list(test.variants.all())
        if len(variants) < 2:
            return self.error_response(
                'A test requires at least 2 variants (1 control + 1 treatment).',
                status_code=400,
            )

        total_split = sum(v.traffic_split for v in variants)
        if abs(total_split - Decimal('100.00')) > Decimal('0.01'):
            return self.error_response(
                f'Traffic splits must sum to 100%. Current total: {total_split}%',
                status_code=400,
            )

        test.status     = 'running'
        test.start_date = timezone.now()
        test.save(update_fields=['status', 'start_date', 'updated_at'])

        return self.success_response(
            data=ABTestDetailSerializer(test).data,
            message=f'A/B test {test.test_id!r} started.',
        )

    # ── PAUSE ─────────────────────────────────────────────────────────────────

    @action(detail=True, methods=['post'], url_path='pause')
    def pause(self, request, pk=None):
        """
        Running test pause করে।
        POST /ab-tests/{id}/pause/
        """
        test = self.get_object()
        self._check_publisher_ownership(test)

        if test.status != 'running':
            return self.error_response(
                f'Only running tests can be paused. Current status: {test.status!r}',
                status_code=400,
            )

        test.status = 'paused'
        test.save(update_fields=['status', 'updated_at'])

        return self.success_response(
            data=ABTestDetailSerializer(test).data,
            message='Test paused.',
        )

    # ── RESUME ────────────────────────────────────────────────────────────────

    @action(detail=True, methods=['post'], url_path='resume')
    def resume(self, request, pk=None):
        """
        Paused test resume করে।
        POST /ab-tests/{id}/resume/
        """
        test = self.get_object()
        self._check_publisher_ownership(test)

        if test.status != 'paused':
            return self.error_response(
                f'Only paused tests can be resumed. Current status: {test.status!r}',
                status_code=400,
            )

        test.status = 'running'
        test.save(update_fields=['status', 'updated_at'])

        return self.success_response(
            data=ABTestDetailSerializer(test).data,
            message='Test resumed.',
        )

    # ── COMPLETE ──────────────────────────────────────────────────────────────

    @action(detail=True, methods=['post'], url_path='complete')
    def complete(self, request, pk=None):
        """
        Test manually complete করে।
        POST /ab-tests/{id}/complete/
        """
        test = self.get_object()
        self._check_publisher_ownership(test)

        if test.status not in ('running', 'paused'):
            return self.error_response(
                f'Cannot complete a test in {test.status!r} status.',
                status_code=400,
            )

        test.status       = 'completed'
        test.end_date     = timezone.now()
        test.concluded_at = timezone.now()
        test.save(update_fields=['status', 'end_date', 'concluded_at', 'updated_at'])

        return self.success_response(
            data=ABTestDetailSerializer(test).data,
            message='Test completed.',
        )

    # ── RESULTS ───────────────────────────────────────────────────────────────

    @action(detail=True, methods=['get'], url_path='results')
    def results(self, request, pk=None):
        """
        Full statistical analysis।
        GET /ab-tests/{id}/results/
        """
        test = self.get_object()
        self._check_publisher_ownership(test)

        try:
            from .a_b_testing import analyze_test_results, is_statistically_significant
            analysis = analyze_test_results(test)
            is_sig   = is_statistically_significant(test)
        except (ImportError, Exception):
            # Fallback: basic variant comparison
            variants = list(test.variants.all())
            analysis = {
                'test_id':   test.test_id,
                'status':    test.status,
                'variants': [
                    {
                        'id':           str(v.id),
                        'name':         v.name,
                        'is_control':   v.is_control,
                        'impressions':  v.total_impressions,
                        'revenue':      float(v.total_revenue),
                        'ecpm':         float(v.ecpm),
                        'ctr':          float(v.ctr),
                        'fill_rate':    float(v.fill_rate),
                    }
                    for v in variants
                ],
                'winner':       None,
                'is_significant': False,
                'message':      'Statistical analysis module unavailable.',
            }
            is_sig = False

        return self.success_response(data={
            **analysis,
            'is_statistically_significant': is_sig,
        })

    # ── DECLARE WINNER ────────────────────────────────────────────────────────

    @action(detail=True, methods=['post'], url_path='declare-winner')
    def declare_winner(self, request, pk=None):
        """
        Winner variant declare করে।
        POST /ab-tests/{id}/declare-winner/
        Body: {"variant_id": "<uuid>", "reason": "highest_ecpm"}
        """
        test = self.get_object()
        self._check_publisher_ownership(test)

        if test.status not in ('running', 'completed'):
            return self.error_response(
                'Winner can only be declared for running or completed tests.',
                status_code=400,
            )

        variant_id = request.data.get('variant_id')
        reason     = request.data.get('reason', 'manual')

        if not variant_id:
            # Auto-select winner using a_b_testing module
            try:
                from .a_b_testing import get_winner_recommendation
                recommendation = get_winner_recommendation(test)
                variant_id = recommendation.get('variant_id')
                reason     = recommendation.get('reason', 'statistical_sig')
            except (ImportError, Exception):
                # Fallback: highest eCPM
                best = test.variants.order_by('-ecpm').first()
                if best:
                    variant_id = str(best.id)
                    reason     = 'highest_ecpm'

        if not variant_id:
            return self.error_response(
                'Could not determine a winner. Please specify variant_id.',
                status_code=400,
            )

        try:
            winner = test.variants.get(id=variant_id)
        except ABTestVariant.DoesNotExist:
            return self.error_response('Variant not found.', status_code=404)

        test.winner_variant  = winner
        test.winner_reason   = reason
        test.status          = 'completed'
        test.end_date        = test.end_date or timezone.now()
        test.concluded_at    = timezone.now()
        test.save(update_fields=[
            'winner_variant', 'winner_reason', 'status',
            'end_date', 'concluded_at', 'updated_at',
        ])

        return self.success_response(
            data={
                'test_id':    test.test_id,
                'winner':     ABTestVariantSerializer(winner).data,
                'reason':     reason,
                'concluded_at': test.concluded_at.isoformat(),
            },
            message=f'Winner declared: {winner.name}',
        )
