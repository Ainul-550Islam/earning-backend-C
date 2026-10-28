# publisher_tools/views_adunit_advanced.py
"""
FILE 9 of 10 — Ad Unit Management Advanced API
===============================================
ad_unit_management/ remaining 5 floating functions exposed.
Previously floating: is_capped, expected_ecpm_multiplier,
  is_scheduled, is_effective (targeting), pct_diff

Register in urls.py:
  router.register(r'ad-unit-adv', AdUnitAdvancedViewSet, basename='adunit-adv')
"""
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from .mixins import PublisherViewMixin, AdminScriptViewMixin, AdminOnlyMixin, ErrorHandlingMixin
from core.views import BaseViewSet
from .permissions import IsPublisher
from .models import AdUnit


class AdUnitAdvancedViewSet(BaseViewSet):
    """
    Ad Unit Advanced API.

    GET  /ad-unit-adv/frequency-cap-status/  — is unit frequency-capped
    GET  /ad-unit-adv/position-multiplier/   — expected eCPM multiplier
    GET  /ad-unit-adv/targeting-schedule/    — is targeting currently active
    GET  /ad-unit-adv/performance-diff/      — % diff between two periods
    GET  /ad-unit-adv/targeting-effective/   — is targeting rule effective
    """
    permission_classes = [IsAuthenticated, IsPublisher]

    def _get_unit(self, unit_id, publisher):
        try:
            return AdUnit.objects.get(pk=unit_id, publisher=publisher)
        except AdUnit.DoesNotExist:
            from rest_framework.exceptions import NotFound
            raise NotFound('Ad unit not found.')

    @action(detail=False, methods=['get'], url_path='frequency-cap-status')
    def frequency_cap_status(self, request):
        """
        Is ad unit frequency-capped for a user session।
        GET ?unit_id=5&session_id=sess_abc
        """
        publisher  = self._get_publisher()
        unit_id    = request.query_params.get('unit_id')
        session_id = request.query_params.get('session_id', '')
        if not unit_id:
            return self.error_response('unit_id required.', status_code=400)
        unit = self._get_unit(unit_id, publisher)
        try:
            from .ad_unit_management.ad_unit_frequency import AdUnitFrequencyCap
            cap = AdUnitFrequencyCap.objects.filter(ad_unit=unit).first()
            if not cap:
                return self.success_response(data={
                    'unit_id': unit_id, 'is_capped': False, 'reason': 'No cap configured'
                })
            is_capped = cap.is_capped(session_id) if hasattr(cap, 'is_capped') else False
            return self.success_response(data={
                'unit_id':    unit_id,
                'session_id': session_id,
                'is_capped':  is_capped,
                'cap_limit':  getattr(cap, 'max_impressions', 0),
                'cap_window': getattr(cap, 'window_hours', 24),
            })
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(detail=False, methods=['get'], url_path='position-multiplier')
    def position_multiplier(self, request):
        """
        Expected eCPM multiplier for a placement position.
        GET ?position=top_of_page | sidebar | in_article | ...
        Multiple: GET ?position=top_of_page,sidebar
        """
        pos_param = request.query_params.get('position', 'top_of_page')
        positions = [p.strip() for p in pos_param.split(',')]
        try:
            from .ad_unit_management.ad_unit_position import expected_ecpm_multiplier
            result = {p: expected_ecpm_multiplier(p) for p in positions}
            return self.success_response(data={'multipliers': result})
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(detail=False, methods=['get'], url_path='targeting-schedule')
    def targeting_schedule(self, request):
        """
        Is ad unit targeting scheduled to be active right now.
        GET ?unit_id=5
        """
        publisher = self._get_publisher()
        unit_id   = request.query_params.get('unit_id')
        if not unit_id:
            return self.error_response('unit_id required.', status_code=400)
        unit = self._get_unit(unit_id, publisher)
        try:
            from .ad_unit_management.ad_unit_targeting import AdUnitTargeting
            targeting = AdUnitTargeting.objects.filter(ad_unit=unit).first()
            if not targeting:
                return self.success_response(data={
                    'unit_id': unit_id, 'is_scheduled': True, 'reason': 'No schedule configured'
                })
            is_sched = targeting.is_scheduled() if hasattr(targeting, 'is_scheduled') else True
            return self.success_response(data={
                'unit_id':      unit_id,
                'is_scheduled': is_sched,
                'schedule':     getattr(targeting, 'schedule', {}),
            })
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(detail=False, methods=['get'], url_path='targeting-effective')
    def targeting_effective(self, request):
        """
        Is targeting rule currently effective.
        GET ?unit_id=5
        """
        publisher = self._get_publisher()
        unit_id   = request.query_params.get('unit_id')
        if not unit_id:
            return self.error_response('unit_id required.', status_code=400)
        unit = self._get_unit(unit_id, publisher)
        try:
            from .ad_unit_management.ad_unit_targeting import AdUnitTargeting
            targeting  = AdUnitTargeting.objects.filter(ad_unit=unit).first()
            is_eff = targeting.is_effective() if targeting and hasattr(targeting, 'is_effective') else True
            return self.success_response(data={'unit_id': unit_id, 'is_effective': is_eff})
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(detail=False, methods=['get'], url_path='performance-diff')
    def performance_diff(self, request):
        """
        % diff in performance between two periods.
        GET ?unit_id=5&days_a=30&days_b=60
        """
        publisher = self._get_publisher()
        unit_id   = request.query_params.get('unit_id')
        days_a    = int(request.query_params.get('days_a', 7))
        days_b    = int(request.query_params.get('days_b', 30))
        if not unit_id:
            return self.error_response('unit_id required.', status_code=400)
        unit = self._get_unit(unit_id, publisher)
        try:
            from .ad_unit_management.ad_unit_performance import pct_diff
            result = pct_diff(unit, days_a=days_a, days_b=days_b)
            return self.success_response(data=result if isinstance(result, dict) else {
                'pct_diff': result, 'days_a': days_a, 'days_b': days_b
            })
        except Exception as e:
            return self.error_response(str(e), status_code=503)
