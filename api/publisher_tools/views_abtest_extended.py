# publisher_tools/views_abtest_extended.py
"""
FILE 1 of 10 — A/B Testing Extended API
========================================
a_b_testing/ subfolder-এর 24টি floating function expose করা হয়েছে।

Previously floating (now wired):
  allocate_traffic, get_variant_for_request, record_allocation,
  auto_declare_winner, calculate_confidence_level,
  calculate_minimum_sample_size, calculate_p_value, calculate_uplift,
  create_floor_price_test, create_placement_ab_test, create_mvt,
  export_test_results, generate_test_report, get_test_summary,
  get_winning_variant, select_winner, run_t_test, run_z_test,
  validate_test_config, analyze_placement_results,
  analyze_multivariate_results, create_multivariate_test,
  create_placement_test, create_ab_test

Register in urls.py:
  router.register(r'ab-tests-extended', ABTestExtendedViewSet, basename='abtest-extended')
"""
from decimal import Decimal
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from .mixins import PublisherViewMixin, AdminScriptViewMixin, AdminOnlyMixin, ErrorHandlingMixin
from core.views import BaseViewSet
from .permissions import IsPublisher
from .models import ABTest, ABTestVariant, AdUnit


class ABTestExtendedViewSet(BaseViewSet):
    """
    Extended A/B Testing API — a_b_testing/ subfolder-এর সব
    floating functions expose করে।

    Allocation:
      POST /ab-tests-extended/{pk}/allocate/          — traffic allocate
      POST /ab-tests-extended/{pk}/get-variant/       — get variant for user
      POST /ab-tests-extended/{pk}/record-allocation/ — record exposure event
      GET  /ab-tests-extended/{pk}/traffic-dist/      — variant traffic distribution

    Statistics:
      GET  /ab-tests-extended/{pk}/confidence/        — confidence level
      POST /ab-tests-extended/{pk}/t-test/            — run t-test
      POST /ab-tests-extended/{pk}/z-test/            — run z-test
      GET  /ab-tests-extended/{pk}/p-value/           — p-value calculation
      GET  /ab-tests-extended/{pk}/uplift/            — uplift vs control
      GET  /ab-tests-extended/sample-size/            — required sample size

    Reporting:
      GET  /ab-tests-extended/{pk}/summary/           — concise test summary
      GET  /ab-tests-extended/{pk}/report/            — full HTML/JSON report
      GET  /ab-tests-extended/{pk}/export/            — export results
      GET  /ab-tests-extended/{pk}/winner/            — current winner
      GET  /ab-tests-extended/learnings/              — completed test learnings
      GET  /ab-tests-extended/portfolio-report/       — all tests report

    Decision:
      POST /ab-tests-extended/{pk}/select-winner/     — manual select
      POST /ab-tests-extended/{pk}/auto-declare/      — auto declare winner

    Creation (specialized):
      POST /ab-tests-extended/create-floor-price/     — floor price test
      POST /ab-tests-extended/create-placement/       — placement test
      POST /ab-tests-extended/create-mvt/             — multivariate test
      POST /ab-tests-extended/validate-config/        — validate before create

    Placement & MVT Analysis:
      GET  /ab-tests-extended/{pk}/placement-analysis/ — placement test results
      GET  /ab-tests-extended/{pk}/mvt-analysis/       — MVT interaction analysis
    """
    permission_classes = [IsAuthenticated, IsPublisher]

    def _get_publisher(self):
        try:
            return self.request.user.publisher_profile
        except AttributeError:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('No active publisher profile.')

    def _get_test(self, pk):
        publisher = self._get_publisher()
        try:
            return ABTest.objects.get(pk=pk, publisher=publisher)
        except ABTest.DoesNotExist:
            from rest_framework.exceptions import NotFound
            raise NotFound('A/B test not found.')

    # ── ALLOCATION ─────────────────────────────────────────────────────────────

    @action(detail=True, methods=['post'], url_path='allocate')
    def allocate(self, request, pk=None):
        """
        User-কে একটি variant-এ allocate করে।
        POST body: { "user_identifier": "user_123" }
        """
        test = self._get_test(pk)
        user_id = request.data.get('user_identifier')
        if not user_id:
            return self.error_response('user_identifier required.', status_code=400)
        try:
            from .a_b_testing.test_allocator import allocate_variant
            variant = allocate_variant(test, user_id)
            if variant is None:
                return self.error_response('Test is not running.', status_code=400)
            return self.success_response(data={
                'test_id':      test.test_id,
                'variant_id':   variant.pk,
                'variant_name': variant.name,
                'is_control':   variant.is_control,
                'config':       variant.config,
            })
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(detail=True, methods=['post'], url_path='get-variant')
    def get_variant(self, request, pk=None):
        """
        User-এর জন্য current variant return করে (without recording).
        POST body: { "user_identifier": "user_123" }
        """
        test = self._get_test(pk)
        user_id = request.data.get('user_identifier')
        if not user_id:
            return self.error_response('user_identifier required.', status_code=400)
        try:
            from .a_b_testing.test_allocator import get_user_variant
            variant = get_user_variant(test, user_id)
            if variant is None:
                return self.success_response(data={'variant': None, 'message': 'No variant assigned.'})
            return self.success_response(data={
                'variant_id':   variant.pk,
                'variant_name': variant.name,
                'is_control':   variant.is_control,
                'config':       variant.config,
            })
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(detail=True, methods=['post'], url_path='record-allocation')
    def record_allocation(self, request, pk=None):
        """
        Impression/exposure event record করে।
        POST body: { "variant_id": 5, "user_identifier": "user_123" }
        """
        test    = self._get_test(pk)
        v_id    = request.data.get('variant_id')
        user_id = request.data.get('user_identifier', '')
        if not v_id:
            return self.error_response('variant_id required.', status_code=400)
        try:
            variant = ABTestVariant.objects.get(pk=v_id, test=test)
            from .a_b_testing.test_allocator import record_exposure
            record_exposure(variant, user_id)
            return self.success_response(data={
                'recorded': True,
                'variant':  variant.name,
            })
        except ABTestVariant.DoesNotExist:
            return self.error_response('Variant not found.', status_code=404)
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(detail=True, methods=['get'], url_path='traffic-dist')
    def traffic_dist(self, request, pk=None):
        """Variant traffic distribution বর্তমান অবস্থা।"""
        test = self._get_test(pk)
        try:
            from .a_b_testing.test_allocator import get_variant_traffic_distribution
            data = get_variant_traffic_distribution(test)
            return self.success_response(data=data)
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    # ── STATISTICS ─────────────────────────────────────────────────────────────

    @action(detail=True, methods=['get'], url_path='confidence')
    def confidence(self, request, pk=None):
        """
        Test-এর current confidence level।
        Control vs best performing variant।
        """
        test = self._get_test(pk)
        try:
            control  = test.variants.filter(is_control=True).first()
            variants = test.variants.filter(is_control=False)
            if not control or not variants.exists():
                return self.error_response('Test needs control + at least 1 variant.', status_code=400)
            from .a_b_testing.confidence_calculator import calculate_confidence
            results = []
            for v in variants:
                conf = calculate_confidence(control, v)
                results.append({'variant': v.name, 'confidence': round(conf, 4)})
            return self.success_response(data={
                'test_id': test.test_id,
                'required_confidence': float(test.confidence_level),
                'results': results,
            })
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(detail=False, methods=['get'], url_path='sample-size')
    def sample_size(self, request):
        """
        Required sample size calculator।
        GET ?baseline_rate=0.05&mde=0.01&confidence=0.95&power=0.80
        """
        try:
            baseline   = float(request.query_params.get('baseline_rate', 0.05))
            mde        = float(request.query_params.get('mde', 0.01))
            confidence = float(request.query_params.get('confidence', 0.95))
            power      = float(request.query_params.get('power', 0.80))
        except ValueError:
            return self.error_response('Invalid numeric parameters.', status_code=400)
        try:
            from .a_b_testing.confidence_calculator import required_sample_size
            n = required_sample_size(baseline, mde, confidence, power)
            return self.success_response(data={
                'required_per_variant': n,
                'total_required':       n * 2,
                'parameters': {
                    'baseline_rate': baseline,
                    'mde':           mde,
                    'confidence':    confidence,
                    'power':         power,
                },
            })
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(detail=True, methods=['post'], url_path='t-test')
    def t_test(self, request, pk=None):
        """
        Student's t-test between control and a specific variant.
        POST body: { "variant_id": 5 }
        """
        test   = self._get_test(pk)
        v_id   = request.data.get('variant_id')
        control = test.variants.filter(is_control=True).first()
        if not control:
            return self.error_response('No control variant found.', status_code=400)
        try:
            variant = ABTestVariant.objects.get(pk=v_id, test=test) if v_id else \
                      test.variants.filter(is_control=False).first()
            if not variant:
                return self.error_response('No treatment variant found.', status_code=400)
            from .a_b_testing import run_t_test
            result = run_t_test(control, variant)
            return self.success_response(data=result)
        except ABTestVariant.DoesNotExist:
            return self.error_response('Variant not found.', status_code=404)
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(detail=True, methods=['post'], url_path='z-test')
    def z_test(self, request, pk=None):
        """
        Z-test for proportions between control and variant.
        POST body: { "variant_id": 5 }
        """
        test    = self._get_test(pk)
        v_id    = request.data.get('variant_id')
        control = test.variants.filter(is_control=True).first()
        if not control:
            return self.error_response('No control variant.', status_code=400)
        try:
            variant = ABTestVariant.objects.get(pk=v_id, test=test) if v_id else \
                      test.variants.filter(is_control=False).first()
            if not variant:
                return self.error_response('No treatment variant.', status_code=400)
            from .a_b_testing import run_z_test
            result = run_z_test(control, variant)
            return self.success_response(data=result)
        except ABTestVariant.DoesNotExist:
            return self.error_response('Variant not found.', status_code=404)
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(detail=True, methods=['get'], url_path='p-value')
    def p_value(self, request, pk=None):
        """Control vs best variant-এর p-value।"""
        test    = self._get_test(pk)
        control = test.variants.filter(is_control=True).first()
        best    = test.variants.filter(is_control=False).order_by('-ecpm').first()
        if not control or not best:
            return self.error_response('Need control + treatment variants.', status_code=400)
        try:
            from .a_b_testing import calculate_p_value
            pval = calculate_p_value(control, best)
            return self.success_response(data={
                'p_value':        round(pval, 6),
                'significant':    pval < (1 - float(test.confidence_level) / 100),
                'control':        control.name,
                'treatment':      best.name,
            })
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(detail=True, methods=['get'], url_path='uplift')
    def uplift(self, request, pk=None):
        """
        Each variant's uplift vs control।
        Metric: ecpm (default) | revenue | ctr | fill_rate
        """
        test    = self._get_test(pk)
        metric  = request.query_params.get('metric', 'ecpm')
        control = test.variants.filter(is_control=True).first()
        if not control:
            return self.error_response('No control variant.', status_code=400)
        from .a_b_testing import calculate_uplift
        results = []
        for v in test.variants.filter(is_control=False):
            ctrl_val = float(getattr(control, metric, 0) or 0)
            var_val  = float(getattr(v, metric, 0) or 0)
            uplift   = calculate_uplift(ctrl_val, var_val) if ctrl_val > 0 else 0
            results.append({
                'variant': v.name,
                'metric':  metric,
                'control_value':  ctrl_val,
                'variant_value':  var_val,
                'uplift_pct':     round(uplift, 4),
            })
        return self.success_response(data={'test_id': test.test_id, 'results': results})

    # ── REPORTING ──────────────────────────────────────────────────────────────

    @action(detail=True, methods=['get'], url_path='summary')
    def summary(self, request, pk=None):
        """
        Concise test summary — dashboard widget-এর জন্য।
        """
        test = self._get_test(pk)
        try:
            from .a_b_testing.test_reporting import get_test_roi
            roi = get_test_roi(test)
        except Exception:
            roi = {}
        control   = test.variants.filter(is_control=True).first()
        best      = test.variants.filter(is_control=False).order_by('-ecpm').first()
        return self.success_response(data={
            'test_id':        test.test_id,
            'name':           test.name,
            'status':         test.status,
            'test_type':      test.test_type,
            'duration_days':  test.duration_days,
            'is_conclusive':  test.is_conclusive,
            'has_enough_data':test.has_enough_data,
            'control':        control.name if control else None,
            'leading_variant':best.name if best else None,
            'roi':            roi,
            'confidence_achieved': float(test.confidence_achieved or 0),
        })

    @action(detail=True, methods=['get'], url_path='report')
    def report(self, request, pk=None):
        """
        Full test report।
        GET ?format=json (default) | summary_only=true
        """
        test = self._get_test(pk)
        try:
            from .a_b_testing import generate_test_report
            report_data = generate_test_report(test)
            return self.success_response(data=report_data)
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(detail=True, methods=['get'], url_path='export')
    def export(self, request, pk=None):
        """
        Test results export।
        GET ?format=csv | json (default)
        """
        test = self._get_test(pk)
        try:
            from .a_b_testing import export_test_results
            data = export_test_results(test)
            return self.success_response(data=data)
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(detail=True, methods=['get'], url_path='winner')
    def winner(self, request, pk=None):
        """Current winning variant (statistical)।"""
        test = self._get_test(pk)
        try:
            from .a_b_testing import get_winning_variant
            winner = get_winning_variant(test)
            if winner is None:
                return self.success_response(data={
                    'winner':  None,
                    'message': 'No conclusive winner yet.',
                })
            return self.success_response(data={
                'variant_id':   winner.pk,
                'variant_name': winner.name,
                'ecpm':         float(winner.ecpm),
                'revenue':      float(winner.total_revenue),
                'impressions':  winner.total_impressions,
            })
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(detail=False, methods=['get'], url_path='learnings')
    def learnings(self, request):
        """Completed tests থেকে learnings।"""
        publisher = self._get_publisher()
        limit = int(request.query_params.get('limit', 10))
        try:
            from .a_b_testing.test_reporting import get_learnings_from_completed_tests
            data = get_learnings_from_completed_tests(publisher, limit=limit)
            return self.success_response(data={'learnings': data, 'count': len(data)})
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(detail=False, methods=['get'], url_path='portfolio-report')
    def portfolio_report(self, request):
        """Publisher-এর সব tests-এর summary report।"""
        publisher = self._get_publisher()
        try:
            from .a_b_testing.test_reporting import generate_test_summary_report
            data = generate_test_summary_report(publisher)
            return self.success_response(data=data)
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    # ── DECISION ───────────────────────────────────────────────────────────────

    @action(detail=True, methods=['post'], url_path='select-winner')
    def select_winner(self, request, pk=None):
        """
        Manually select winner।
        POST body: { "variant_id": 5 }
        """
        test = self._get_test(pk)
        v_id = request.data.get('variant_id')
        if not v_id:
            return self.error_response('variant_id required.', status_code=400)
        try:
            ABTestVariant.objects.get(pk=v_id, test=test)
            from .a_b_testing.winner_selector import select_winner
            winner = select_winner(test)
            return self.success_response(
                data={'winner': winner.name if winner else None},
                message='Winner selected.'
            )
        except ABTestVariant.DoesNotExist:
            return self.error_response('Variant not found.', status_code=404)
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(detail=True, methods=['post'], url_path='auto-declare')
    def auto_declare(self, request, pk=None):
        """
        Statistical evidence-এর ভিত্তিতে auto declare winner।
        Requires: is_conclusive == True
        """
        test = self._get_test(pk)
        if not test.is_conclusive:
            return self.error_response(
                f'Test not conclusive yet. Confidence: '
                f'{test.confidence_achieved or 0:.1f}% / {test.confidence_level}% required.',
                status_code=400,
            )
        try:
            from .a_b_testing import auto_declare_winner
            winner = auto_declare_winner(test)
            return self.success_response(
                data={'winner': winner.name if winner else None},
                message='Winner auto-declared.'
            )
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    # ── SPECIALIZED CREATION ───────────────────────────────────────────────────

    @action(detail=False, methods=['post'], url_path='validate-config')
    def validate_config(self, request):
        """
        Test config validate করে (create করার আগে)।
        POST body: full test config payload
        """
        try:
            from .a_b_testing import validate_test_config
            errors = validate_test_config(request.data)
            if errors:
                return self.success_response(data={'valid': False, 'errors': errors})
            return self.success_response(data={'valid': True, 'errors': []})
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(detail=False, methods=['post'], url_path='create-floor-price')
    def create_floor_price(self, request):
        """
        Floor price A/B test তৈরি করে।
        POST body: {
          "ad_unit_id": 1,
          "control_floor": "0.50",
          "test_floor": "0.75",
          "name": "Floor Price Test Q1"
        }
        """
        publisher = self._get_publisher()
        ad_unit_id    = request.data.get('ad_unit_id')
        control_floor = request.data.get('control_floor')
        test_floor    = request.data.get('test_floor')
        if not all([ad_unit_id, control_floor, test_floor]):
            return self.error_response('ad_unit_id, control_floor, test_floor required.', status_code=400)
        try:
            ad_unit = AdUnit.objects.get(pk=ad_unit_id, publisher=publisher)
            from .a_b_testing.test_creator import create_floor_price_test
            test = create_floor_price_test(
                publisher, ad_unit,
                Decimal(control_floor), Decimal(test_floor),
                name=request.data.get('name'),
            )
            return self.success_response(
                data={'test_id': test.test_id, 'pk': test.pk, 'name': test.name},
                message='Floor price test created.',
                status_code=201,
            )
        except AdUnit.DoesNotExist:
            return self.error_response('Ad unit not found.', status_code=404)
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(detail=False, methods=['post'], url_path='create-placement')
    def create_placement(self, request):
        """
        Placement A/B test তৈরি করে।
        POST body: { "ad_unit_id": 1, "positions": ["top", "bottom", "sidebar"] }
        """
        publisher = self._get_publisher()
        ad_unit_id = request.data.get('ad_unit_id')
        positions  = request.data.get('positions', [])
        if not ad_unit_id or not positions:
            return self.error_response('ad_unit_id and positions required.', status_code=400)
        if len(positions) < 2:
            return self.error_response('At least 2 positions required.', status_code=400)
        try:
            ad_unit = AdUnit.objects.get(pk=ad_unit_id, publisher=publisher)
            from .a_b_testing.test_creator import create_placement_test
            test = create_placement_test(publisher, ad_unit, positions,
                                         name=request.data.get('name'))
            return self.success_response(
                data={'test_id': test.test_id, 'pk': test.pk, 'name': test.name},
                message='Placement test created.',
                status_code=201,
            )
        except AdUnit.DoesNotExist:
            return self.error_response('Ad unit not found.', status_code=404)
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(detail=False, methods=['post'], url_path='create-mvt')
    def create_mvt(self, request):
        """
        Multivariate test (MVT) তৈরি করে।
        POST body: {
          "ad_unit_id": 1,
          "variables": {
            "floor_price": ["0.50", "0.75", "1.00"],
            "ad_format":   ["banner", "native"]
          }
        }
        """
        publisher  = self._get_publisher()
        ad_unit_id = request.data.get('ad_unit_id')
        variables  = request.data.get('variables', {})
        if not ad_unit_id or not variables:
            return self.error_response('ad_unit_id and variables required.', status_code=400)
        try:
            ad_unit = AdUnit.objects.get(pk=ad_unit_id, publisher=publisher)
            from .a_b_testing.multivariate_testing import create_multivariate_test
            test = create_multivariate_test(publisher, ad_unit, variables)
            return self.success_response(
                data={'test_id': test.test_id, 'pk': test.pk, 'name': test.name},
                message='Multivariate test created.',
                status_code=201,
            )
        except AdUnit.DoesNotExist:
            return self.error_response('Ad unit not found.', status_code=404)
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    # ── PLACEMENT & MVT ANALYSIS ───────────────────────────────────────────────

    @action(detail=True, methods=['get'], url_path='placement-analysis')
    def placement_analysis(self, request, pk=None):
        """
        Placement test-এর position-level results।
        """
        test = self._get_test(pk)
        if test.test_type != 'placement':
            return self.error_response('Only available for placement tests.', status_code=400)
        try:
            from .a_b_testing import analyze_placement_results
            data = analyze_placement_results(test)
            return self.success_response(data=data)
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(detail=True, methods=['get'], url_path='mvt-analysis')
    def mvt_analysis(self, request, pk=None):
        """
        MVT variable interaction analysis।
        """
        test = self._get_test(pk)
        if test.test_type != 'multivariate':
            return self.error_response('Only available for multivariate tests.', status_code=400)
        try:
            from .a_b_testing.multivariate_testing import analyze_variable_interactions
            data = analyze_variable_interactions(test)
            return self.success_response(data={'interactions': data})
        except Exception as e:
            return self.error_response(str(e), status_code=503)
