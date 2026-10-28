# publisher_tools/views_site_advanced.py
"""
FILE 7 of 10 — Site Management Advanced API
============================================
site_management/ remaining 6 floating functions exposed.
Previously floating: checklist_score, make_decision,
  mobile_pct, desktop_pct, return_visitor_pct, is_effective (blacklist)

Register in urls.py:
  router.register(r'site-advanced', SiteAdvancedViewSet, basename='site-adv')
"""
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from .mixins import PublisherViewMixin, AdminScriptViewMixin, AdminOnlyMixin, ErrorHandlingMixin
from core.views import BaseViewSet
from .permissions import IsPublisher, IsAdminOrPublisher
from .models import Site


class SiteAdvancedViewSet(BaseViewSet):
    """
    Site Management Advanced API.

    Approval:
      GET  /site-advanced/approval-checklist/  — checklist with scores
      POST /site-advanced/make-decision/       — approve/reject (admin)

    Analytics breakdown:
      GET  /site-advanced/device-split/        — mobile vs desktop split
      GET  /site-advanced/return-visitor-rate/ — return visitor %

    Blacklist:
      GET  /site-advanced/blacklist-status/    — site blacklist check
    """
    permission_classes = [IsAuthenticated, IsPublisher]

    def _get_site(self, site_id, publisher):
        try:
            return Site.objects.get(pk=site_id, publisher=publisher)
        except Site.DoesNotExist:
            from rest_framework.exceptions import NotFound
            raise NotFound('Site not found.')

    @action(detail=False, methods=['get'], url_path='approval-checklist')
    def approval_checklist(self, request):
        """Site approval checklist with score। GET ?site_id=5"""
        publisher = self._get_publisher()
        site_id   = request.query_params.get('site_id')
        if not site_id:
            return self.error_response('site_id required.', status_code=400)
        site = self._get_site(site_id, publisher)
        try:
            from .site_management.site_approval import SiteApprovalChecklist
            chk = SiteApprovalChecklist.objects.filter(site=site).first()
            if not chk:
                return self.success_response(data={
                    'site_id': site_id,
                    'checklist': None,
                    'message': 'No approval checklist found.',
                })
            return self.success_response(data={
                'site_id':        site_id,
                'checklist_score': chk.checklist_score() if hasattr(chk, 'checklist_score') else 0,
                'status':          getattr(chk, 'status', ''),
                'items':           getattr(chk, 'items', {}),
            })
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(
        detail=False, methods=['post'], url_path='make-decision',
        permission_classes=[IsAuthenticated, IsAdminUser],
    )
    def make_decision(self, request):
        """[Admin] Approve or reject a site. POST body: {site_id, decision, reason}"""
        site_id  = request.data.get('site_id')
        decision = request.data.get('decision', '')
        reason   = request.data.get('reason', '')
        if not site_id or not decision:
            return self.error_response('site_id and decision required.', status_code=400)
        if decision not in ('approve', 'reject'):
            return self.error_response('decision must be approve or reject.', status_code=400)
        try:
            site = Site.objects.get(pk=site_id)
            from .site_management.site_approval import SiteApprovalChecklist
            chk  = SiteApprovalChecklist.objects.filter(site=site).first()
            if chk and hasattr(chk, 'make_decision'):
                chk.make_decision(decision, reason=reason, reviewer=request.user)
            else:
                site.status = 'active' if decision == 'approve' else 'rejected'
                site.save(update_fields=['status', 'updated_at'])
            return self.success_response(data={
                'site_id':  site_id,
                'decision': decision,
                'new_status': site.status,
            })
        except Site.DoesNotExist:
            return self.error_response('Site not found.', status_code=404)
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(detail=False, methods=['get'], url_path='device-split')
    def device_split(self, request):
        """Mobile vs desktop visitor split। GET ?site_id=5&days=30"""
        publisher = self._get_publisher()
        site_id   = request.query_params.get('site_id')
        days      = int(request.query_params.get('days', 30))
        if not site_id:
            return self.error_response('site_id required.', status_code=400)
        site = self._get_site(site_id, publisher)
        try:
            from .site_management.site_analytics import SiteAnalyticsSnapshot
            snap = SiteAnalyticsSnapshot.objects.filter(site=site).order_by('-created_at').first()
            if not snap:
                return self.success_response(data={
                    'site_id': site_id, 'mobile_pct': None, 'desktop_pct': None
                })
            return self.success_response(data={
                'site_id':     site_id,
                'mobile_pct':  snap.mobile_pct()  if hasattr(snap, 'mobile_pct')  else None,
                'desktop_pct': snap.desktop_pct() if hasattr(snap, 'desktop_pct') else None,
                'days':        days,
            })
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(detail=False, methods=['get'], url_path='return-visitor-rate')
    def return_visitor_rate(self, request):
        """Return visitor %। GET ?site_id=5"""
        publisher = self._get_publisher()
        site_id   = request.query_params.get('site_id')
        if not site_id:
            return self.error_response('site_id required.', status_code=400)
        site = self._get_site(site_id, publisher)
        try:
            from .site_management.site_analytics import SiteAnalyticsSnapshot
            snap = SiteAnalyticsSnapshot.objects.filter(site=site).order_by('-created_at').first()
            rate = snap.return_visitor_pct() if snap and hasattr(snap, 'return_visitor_pct') else None
            return self.success_response(data={'site_id': site_id, 'return_visitor_pct': rate})
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(detail=False, methods=['get'], url_path='blacklist-status')
    def blacklist_status(self, request):
        """Check if site is blacklisted। GET ?site_id=5"""
        publisher = self._get_publisher()
        site_id   = request.query_params.get('site_id')
        if not site_id:
            return self.error_response('site_id required.', status_code=400)
        site = self._get_site(site_id, publisher)
        try:
            from .site_management.site_blacklist import SiteBlacklist
            bl   = SiteBlacklist.objects.filter(site=site).first()
            is_bl = (bl.is_effective() if bl and hasattr(bl, 'is_effective') else False)
            return self.success_response(data={
                'site_id':       site_id,
                'is_blacklisted': is_bl,
                'reason':        getattr(bl, 'reason', '') if bl else '',
            })
        except Exception as e:
            return self.error_response(str(e), status_code=503)
