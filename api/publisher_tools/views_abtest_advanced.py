# publisher_tools/views_abtest_advanced.py
"""
FILE 8 of 10 — A/B Testing Advanced API
========================================
a_b_testing/ remaining 6 floating functions exposed.
Previously floating: create_format_test, create_position_ab_test,
  get_best_position_by_revenue, two_proportion_z_test, welch_t_test

Register in urls.py:
  router.register(r'ab-tests-adv', ABTestAdvancedViewSet, basename='abtest-adv')
"""
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from .mixins import PublisherViewMixin, AdminScriptViewMixin, AdminOnlyMixin, ErrorHandlingMixin
from core.views import BaseViewSet
from .permissions import IsPublisher
from .models import AdUnit, Site


class ABTestAdvancedViewSet(BaseViewSet):
    """
    A/B Testing Advanced API.

    GET  /ab-tests-adv/best-position/         — best ad position by revenue
    POST /ab-tests-adv/create-format/         — create ad format test
    POST /ab-tests-adv/create-position/       — create position A/B test
    POST /ab-tests-adv/two-proportion-z/      — two-proportion Z-test
    POST /ab-tests-adv/welch-t-test/          — Welch's t-test
    GET  /ab-tests-adv/format-comparison/     — compare ad formats
    """
    permission_classes = [IsAuthenticated, IsPublisher]

    @action(detail=False, methods=['get'], url_path='best-position')
    def best_position(self, request):
        """Best ad position by historical revenue। GET ?site_id=5&days=30"""
        publisher = self._get_publisher()
        site_id   = request.query_params.get('site_id')
        days      = int(request.query_params.get('days', 30))
        if not site_id:
            return self.error_response('site_id required.', status_code=400)
        try:
            site = Site.objects.get(pk=site_id, publisher=publisher)
            from .a_b_testing.placement_testing import get_best_position_by_revenue
            result = get_best_position_by_revenue(site, days=days)
            return self.success_response(data=result if isinstance(result, dict)
                                          else {'best_position': result})
        except Site.DoesNotExist:
            return self.error_response('Site not found.', status_code=404)
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(detail=False, methods=['post'], url_path='create-format')
    def create_format(self, request):
        """
        Create ad format A/B test (banner vs native vs interstitial etc).
        POST body: { "ad_unit_id": 5, "formats": ["banner", "native", "interstitial"] }
        """
        publisher  = self._get_publisher()
        ad_unit_id = request.data.get('ad_unit_id')
        formats    = request.data.get('formats', [])
        if not ad_unit_id or len(formats) < 2:
            return self.error_response('ad_unit_id and at least 2 formats required.', status_code=400)
        try:
            ad_unit = AdUnit.objects.get(pk=ad_unit_id, publisher=publisher)
            from .a_b_testing.test_creator import create_format_test
            test = create_format_test(publisher, ad_unit, formats)
            return self.success_response(
                data={'test_id': test.test_id, 'pk': test.pk, 'name': test.name},
                status_code=201,
            )
        except AdUnit.DoesNotExist:
            return self.error_response('Ad unit not found.', status_code=404)
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(detail=False, methods=['post'], url_path='create-position')
    def create_position(self, request):
        """
        Create position A/B test.
        POST body: { "site_id": 5, "positions": ["top_of_page", "sidebar", "in_article"] }
        """
        publisher = self._get_publisher()
        site_id   = request.data.get('site_id')
        positions = request.data.get('positions', [])
        if not site_id or len(positions) < 2:
            return self.error_response('site_id and at least 2 positions required.', status_code=400)
        try:
            site = Site.objects.get(pk=site_id, publisher=publisher)
            from .a_b_testing.placement_testing import create_position_ab_test
            test = create_position_ab_test(publisher, site, positions)
            return self.success_response(
                data={'test_id': getattr(test, 'test_id', None), 'pk': test.pk},
                status_code=201,
            )
        except Site.DoesNotExist:
            return self.error_response('Site not found.', status_code=404)
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(detail=False, methods=['post'], url_path='two-proportion-z')
    def two_proportion_z(self, request):
        """
        Two-proportion Z-test for CTR comparison.
        POST body: { "n1": 1000, "x1": 50, "n2": 1000, "x2": 65 }
        """
        try:
            n1 = int(request.data.get('n1', 0))
            x1 = int(request.data.get('x1', 0))
            n2 = int(request.data.get('n2', 0))
            x2 = int(request.data.get('x2', 0))
        except (TypeError, ValueError):
            return self.error_response('n1, x1, n2, x2 must be integers.', status_code=400)
        if n1 <= 0 or n2 <= 0:
            return self.error_response('n1 and n2 must be > 0.', status_code=400)
        try:
            from .a_b_testing.hypothesis_tester import two_proportion_z_test
            result = two_proportion_z_test(n1, x1, n2, x2)
            return self.success_response(data=result if isinstance(result, dict) else {
                'z_score': result, 'n1': n1, 'x1': x1, 'n2': n2, 'x2': x2
            })
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(detail=False, methods=['post'], url_path='welch-t-test')
    def welch_t_test(self, request):
        """
        Welch's t-test for unequal variance samples.
        POST body: { "mean1": 2.5, "var1": 0.4, "n1": 500,
                     "mean2": 2.8, "var2": 0.3, "n2": 480 }
        """
        try:
            mean1 = float(request.data.get('mean1', 0))
            var1  = float(request.data.get('var1', 1))
            n1    = int(request.data.get('n1', 0))
            mean2 = float(request.data.get('mean2', 0))
            var2  = float(request.data.get('var2', 1))
            n2    = int(request.data.get('n2', 0))
        except (TypeError, ValueError):
            return self.error_response('Invalid numeric parameters.', status_code=400)
        if n1 <= 0 or n2 <= 0:
            return self.error_response('n1 and n2 must be > 0.', status_code=400)
        try:
            from .a_b_testing.hypothesis_tester import welch_t_test
            result = welch_t_test(mean1, var1, n1, mean2, var2, n2)
            return self.success_response(data=result if isinstance(result, dict) else {
                't_statistic': result
            })
        except Exception as e:
            return self.error_response(str(e), status_code=503)
