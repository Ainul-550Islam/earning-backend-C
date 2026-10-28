# publisher_tools/views_site_management.py
# Exposes site_management/ subfolder logic via DRF.
# Register: router.register(r'site-tools', SiteManagementViewSet, basename='site-tool')

from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from .mixins import PublisherViewMixin, AdminScriptViewMixin, AdminOnlyMixin, ErrorHandlingMixin
from core.views import BaseViewSet
from .permissions import IsPublisher


class SiteManagementViewSet(BaseViewSet):
    """
    Site Management Tools API.
    site_management/ subfolder expose করা হয়েছে।

    Publisher endpoints:
      POST /site-tools/verify-ads-txt/     — ads.txt verification
      POST /site-tools/verify-meta-tag/    — meta tag verification
      POST /site-tools/verify-dns/         — DNS verification
      POST /site-tools/verify-html/        — HTML file verification
      GET  /site-tools/domain-check/       — domain validity check
      GET  /site-tools/performance/        — site performance summary
      GET  /site-tools/quality-score/      — composite quality score

    Admin endpoints:
      POST /site-tools/full-verify/        — run full verification flow
    """
    permission_classes = [IsAuthenticated, IsPublisher]

    def _get_publisher(self):
        try:
            return self.request.user.publisher_profile
        except Exception:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('No active publisher profile.')

    def _get_site(self, site_id, publisher):
        from .models import Site
        site = Site.objects.filter(site_id=site_id, publisher=publisher).first()
        if not site:
            return None
        return site

    # ── Verify Ads.txt ────────────────────────────────────────────────────────

    @action(detail=False, methods=['post'], url_path='verify-ads-txt')
    def verify_ads_txt(self, request):
        """
        ads.txt verification।
        POST /site-tools/verify-ads-txt/
        Body: {"site_id": "SITE123456"}
        """
        publisher = self._get_publisher()
        site_id   = request.data.get('site_id')
        if not site_id:
            return self.error_response('site_id is required.', status_code=400)

        site = self._get_site(site_id, publisher)
        if not site:
            return self.error_response('Site not found.', status_code=404)

        try:
            from .site_management import verify_ads_txt
            verified, message = verify_ads_txt(site.domain, publisher.publisher_id)
        except (ImportError, Exception) as e:
            return self.error_response(str(e), status_code=503)

        if verified:
            site.is_ads_txt_verified = True
            site.save(update_fields=['is_ads_txt_verified', 'updated_at'])

        return self.success_response(data={
            'site_id':  site_id,
            'domain':   site.domain,
            'verified': verified,
            'message':  message,
            'ads_txt_url': f'https://{site.domain}/ads.txt',
        })

    # ── Verify Meta Tag ───────────────────────────────────────────────────────

    @action(detail=False, methods=['post'], url_path='verify-meta-tag')
    def verify_meta_tag(self, request):
        """
        Meta tag verification।
        POST /site-tools/verify-meta-tag/
        Body: {"site_id": "SITE123456", "token": "abc123"}
        """
        publisher = self._get_publisher()
        site_id   = request.data.get('site_id')
        token     = request.data.get('token', '')

        if not site_id:
            return self.error_response('site_id is required.', status_code=400)

        site = self._get_site(site_id, publisher)
        if not site:
            return self.error_response('Site not found.', status_code=404)

        try:
            from .site_management import verify_meta_tag
            verified, message = verify_meta_tag(site.url, token)
        except (ImportError, Exception) as e:
            return self.error_response(str(e), status_code=503)

        return self.success_response(data={
            'site_id':  site_id,
            'verified': verified,
            'message':  message,
        })

    # ── Verify DNS ────────────────────────────────────────────────────────────

    @action(detail=False, methods=['post'], url_path='verify-dns')
    def verify_dns(self, request):
        """
        DNS TXT record verification।
        POST /site-tools/verify-dns/
        Body: {"site_id": "SITE123456", "token": "abc123"}
        """
        publisher = self._get_publisher()
        site_id   = request.data.get('site_id')
        token     = request.data.get('token', '')

        if not site_id:
            return self.error_response('site_id is required.', status_code=400)

        site = self._get_site(site_id, publisher)
        if not site:
            return self.error_response('Site not found.', status_code=404)

        try:
            from .site_management import verify_dns_record
            verified, message = verify_dns_record(site.domain, token)
        except (ImportError, Exception) as e:
            return self.error_response(str(e), status_code=503)

        return self.success_response(data={'site_id': site_id, 'verified': verified, 'message': message})

    # ── Verify HTML File ──────────────────────────────────────────────────────

    @action(detail=False, methods=['post'], url_path='verify-html')
    def verify_html(self, request):
        """
        HTML file verification।
        POST /site-tools/verify-html/
        Body: {"site_id": "SITE123456", "token": "abc123"}
        """
        publisher = self._get_publisher()
        site_id   = request.data.get('site_id')
        token     = request.data.get('token', '')

        if not site_id:
            return self.error_response('site_id is required.', status_code=400)

        site = self._get_site(site_id, publisher)
        if not site:
            return self.error_response('Site not found.', status_code=404)

        try:
            from .site_management import verify_html_file
            verified, message = verify_html_file(site.url, token)
        except (ImportError, Exception) as e:
            return self.error_response(str(e), status_code=503)

        return self.success_response(data={'site_id': site_id, 'verified': verified, 'message': message})

    # ── Domain Check ─────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='domain-check')
    def domain_check(self, request):
        """
        Domain validity check + clean domain।
        GET /site-tools/domain-check/?domain=example.com
        """
        raw_domain = request.query_params.get('domain', '')
        if not raw_domain:
            return self.error_response('domain is required.', status_code=400)

        try:
            from .site_management import clean_domain, is_valid_domain, get_root_domain
            cleaned     = clean_domain(raw_domain)
            is_valid    = is_valid_domain(cleaned)
            root_domain = get_root_domain(cleaned)
        except (ImportError, Exception) as e:
            return self.error_response(str(e), status_code=503)

        return self.success_response(data={
            'raw':        raw_domain,
            'cleaned':    cleaned,
            'is_valid':   is_valid,
            'root_domain': root_domain,
        })

    # ── Performance Summary ───────────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='performance')
    def performance(self, request):
        """
        Site performance summary।
        GET /site-tools/performance/?site_id=SITE123456&days=30
        """
        publisher = self._get_publisher()
        site_id   = request.query_params.get('site_id')
        days      = int(request.query_params.get('days', 30))

        if not site_id:
            return self.error_response('site_id is required.', status_code=400)

        site = self._get_site(site_id, publisher)
        if not site:
            return self.error_response('Site not found.', status_code=404)

        try:
            from .site_management import get_site_performance_summary
            data = get_site_performance_summary(site, days=days)
        except (ImportError, Exception) as e:
            return self.error_response(str(e), status_code=503)

        return self.success_response(data=data)

    # ── Quality Score ─────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='quality-score')
    def quality_score(self, request):
        """
        Composite quality score calculation।
        GET /site-tools/quality-score/?site_id=SITE123456
        """
        publisher = self._get_publisher()
        site_id   = request.query_params.get('site_id')

        if not site_id:
            return self.error_response('site_id is required.', status_code=400)

        site = self._get_site(site_id, publisher)
        if not site:
            return self.error_response('Site not found.', status_code=404)

        try:
            from .site_management import calculate_composite_score
            scores = {
                'content':     site.quality_score,
                'ads_txt':     100 if site.is_ads_txt_verified else 0,
                'ivt':         max(0, 100 - int(float(site.ivt_rate or 0) * 500)),
                'bounce_rate': max(0, 100 - int(float(site.bounce_rate or 0.5) * 100)),
            }
            composite = calculate_composite_score(scores)
        except (ImportError, Exception):
            composite = site.quality_score

        return self.success_response(data={
            'site_id':         site_id,
            'domain':          site.domain,
            'composite_score': composite,
            'ads_txt_verified': site.is_ads_txt_verified,
            'current_db_score': site.quality_score,
        })

    # ── ADMIN: Full Verify ────────────────────────────────────────────────────

    @action(
        detail=False, methods=['post'], url_path='full-verify',
        permission_classes=[IsAuthenticated, IsAdminUser],
    )
    def full_verify(self, request):
        """
        Full site verification flow (admin only)。
        POST /site-tools/full-verify/
        Body: {"site_id": "SITE123456"}
        """
        site_id = request.data.get('site_id')
        if not site_id:
            return self.error_response('site_id is required.', status_code=400)

        from .models import Site, InventoryVerification
        site = Site.objects.filter(site_id=site_id).first()
        if not site:
            return self.error_response('Site not found.', status_code=404)

        try:
            from .site_management import perform_verification
            from .models import InventoryVerification
            verification = InventoryVerification.objects.filter(site=site).order_by('-created_at').first()
            if not verification:
                from .utils import generate_verification_token
                verification = InventoryVerification.objects.create(
                    publisher=site.publisher,
                    site=site,
                    method='ads_txt',
                    verification_token=generate_verification_token(),
                )
            result = perform_verification(site, verification)
        except (ImportError, Exception) as e:
            return self.error_response(str(e), status_code=503)

        return self.success_response(data=result)
