# publisher_tools/views_app_management_full.py
"""
app_management subfolder — 10টি floating class → API।

Floating items wired (app_management/*.py):
  AppApprovalRecord   → approval history + checklist
  AppBlacklistEntry   → blacklist status + entry list
  AppCategory         → category list + lookup
  AppDownloadSnapshot → download trend data
  AppQualityScore     → quality score + breakdown
  AppRatingSnapshot   → store rating history
  AppSDKConfig        → SDK config management
  AppStoreMetadata    → store metadata sync
  AppVerification     → verification flow
  AppWhitelistEntry   → whitelist management

Register in urls.py:
  router.register(r'app-management', AppManagementFullViewSet, basename='app-mgmt-full')
"""
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from core.views import BaseViewSet
from .permissions import IsPublisher, IsAdminOrPublisher


class AppManagementFullViewSet(BaseViewSet):
    """
    App Management Full API।
    app_management/ subfolder-এর সব 10টি floating class expose করে।

    Endpoints:
      GET  /app-management/approval-history/           — AppApprovalRecord
      GET  /app-management/approval-checklist/         — AppApprovalRecord checklist
      GET  /app-management/blacklist-status/           — AppBlacklistEntry
      GET  /app-management/blacklist-entries/          — AppBlacklistEntry list (admin)
      GET  /app-management/categories/                 — AppCategory list
      GET  /app-management/category-lookup/            — AppCategory search
      GET  /app-management/download-trend/             — AppDownloadSnapshot
      GET  /app-management/quality-score/              — AppQualityScore
      GET  /app-management/quality-breakdown/          — AppQualityScore breakdown
      GET  /app-management/rating-history/             — AppRatingSnapshot
      GET  /app-management/sdk-config/                 — AppSDKConfig
      POST /app-management/sdk-config/update/          — AppSDKConfig update
      GET  /app-management/store-metadata/             — AppStoreMetadata
      POST /app-management/store-metadata/sync/        — AppStoreMetadata sync
      GET  /app-management/verification-status/        — AppVerification
      POST /app-management/verification-start/         — AppVerification start
      GET  /app-management/whitelist-status/           — AppWhitelistEntry
      GET  /app-management/whitelist-entries/          — AppWhitelistEntry list (admin)
    """
    permission_classes = [IsAuthenticated, IsPublisher]

    def _get_publisher(self):
        try:
            return self.request.user.publisher_profile
        except AttributeError:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('No publisher profile.')

    def _get_app(self, app_id=None):
        """Query param থেকে app বের করে।"""
        publisher = self._get_publisher()
        try:
            from .models import App
            qs = App.objects.filter(publisher=publisher)
            if app_id:
                qs = qs.filter(app_id=app_id)
            return qs.first()
        except Exception:
            return None

    # ══════════════════════════════════════════════════════════════════════════
    # AppApprovalRecord
    # ══════════════════════════════════════════════════════════════════════════

    @action(detail=False, methods=['get'], url_path='approval-history')
    def approval_history(self, request):
        """
        App approval/rejection history।
        GET /app-management/approval-history/?app_id=APP001
        """
        publisher = self._get_publisher()
        app_id    = request.query_params.get('app_id')
        try:
            from .app_management.app_approval import AppApprovalRecord
            qs = AppApprovalRecord.objects.filter(
                app__publisher=publisher
            ).order_by('-created_at')
            if app_id:
                qs = qs.filter(app__app_id=app_id)
            records = [
                {
                    'pk':         r.pk,
                    'app_id':     getattr(r.app, 'app_id', '') if hasattr(r, 'app') else '',
                    'action':     getattr(r, 'action', ''),
                    'reason':     getattr(r, 'reason', ''),
                    'decided_by': getattr(r, 'decided_by', ''),
                    'created_at': str(r.created_at),
                }
                for r in qs[:50]
            ]
        except (ImportError, Exception) as e:
            return self.error_response(str(e), status_code=503)
        return self.success_response(data={'records': records, 'count': len(records)})

    @action(detail=False, methods=['get'], url_path='approval-checklist')
    def approval_checklist(self, request):
        """
        App approval checklist items।
        GET /app-management/approval-checklist/?app_id=APP001
        """
        app_id = request.query_params.get('app_id')
        try:
            from .app_management.app_approval import AppApprovalRecord
            app = self._get_app(app_id)
            if not app:
                return self.success_response(data={'checklist': [], 'app': None})
            checklist = []
            if hasattr(AppApprovalRecord, 'get_checklist'):
                checklist = AppApprovalRecord.get_checklist(app)
            else:
                checklist = [
                    {'item': 'store_url_valid',     'passed': bool(getattr(app, 'play_store_url', '') or getattr(app, 'app_store_url', ''))},
                    {'item': 'package_name_set',    'passed': bool(getattr(app, 'package_name', ''))},
                    {'item': 'category_set',        'passed': bool(getattr(app, 'category', ''))},
                    {'item': 'icon_uploaded',       'passed': bool(getattr(app, 'icon_url', ''))},
                    {'item': 'content_rating_set',  'passed': bool(getattr(app, 'content_rating', ''))},
                ]
            passed = sum(1 for c in checklist if c.get('passed'))
            return self.success_response(data={
                'checklist':       checklist,
                'passed':          passed,
                'total':           len(checklist),
                'ready_to_submit': passed == len(checklist),
            })
        except (ImportError, Exception) as e:
            return self.error_response(str(e), status_code=503)

    # ══════════════════════════════════════════════════════════════════════════
    # AppBlacklistEntry
    # ══════════════════════════════════════════════════════════════════════════

    @action(detail=False, methods=['get'], url_path='blacklist-status')
    def blacklist_status(self, request):
        """
        App blacklist status।
        GET /app-management/blacklist-status/?app_id=APP001
        """
        publisher = self._get_publisher()
        app_id    = request.query_params.get('app_id')
        try:
            from .app_management.app_blacklist import AppBlacklistEntry
            qs = AppBlacklistEntry.objects.filter(
                app__publisher=publisher, is_active=True
            )
            if app_id:
                qs = qs.filter(app__app_id=app_id)
            entry = qs.first()
            return self.success_response(data={
                'is_blacklisted': entry is not None,
                'reason':         getattr(entry, 'reason', '') if entry else '',
                'blacklisted_at': str(entry.created_at) if entry else '',
                'expires_at':     str(getattr(entry, 'expires_at', '')) if entry else '',
            })
        except (ImportError, Exception) as e:
            return self.error_response(str(e), status_code=503)

    @action(detail=False, methods=['get'], url_path='blacklist-entries',
            permission_classes=[IsAuthenticated, IsAdminUser])
    def blacklist_entries(self, request):
        """
        All active blacklist entries (admin only)।
        GET /app-management/blacklist-entries/
        """
        try:
            from .app_management.app_blacklist import AppBlacklistEntry
            entries = AppBlacklistEntry.objects.filter(is_active=True).order_by('-created_at')[:100]
            return self.success_response(data={
                'entries': [
                    {
                        'pk':           e.pk,
                        'app_id':       getattr(e.app, 'app_id', '') if hasattr(e, 'app') else '',
                        'reason':       getattr(e, 'reason', ''),
                        'is_permanent': getattr(e, 'is_permanent', False),
                        'expires_at':   str(getattr(e, 'expires_at', '')),
                        'added_by':     getattr(e, 'added_by', ''),
                        'created_at':   str(e.created_at),
                    }
                    for e in entries
                ],
                'count': entries.count(),
            })
        except (ImportError, Exception) as e:
            return self.error_response(str(e), status_code=503)

    # ══════════════════════════════════════════════════════════════════════════
    # AppCategory
    # ══════════════════════════════════════════════════════════════════════════

    @action(detail=False, methods=['get'], url_path='categories')
    def categories(self, request):
        """
        All app categories।
        GET /app-management/categories/?platform=android
        """
        platform = request.query_params.get('platform', '')
        try:
            from .app_management.app_category import AppCategory
            qs = AppCategory.objects.filter(is_active=True)
            if platform:
                qs = qs.filter(platform=platform)
            cats = [
                {
                    'pk':           c.pk,
                    'name':         getattr(c, 'name', ''),
                    'slug':         getattr(c, 'slug', ''),
                    'platform':     getattr(c, 'platform', ''),
                    'parent':       getattr(c, 'parent_id', None),
                    'description':  getattr(c, 'description', ''),
                }
                for c in qs.order_by('name')[:200]
            ]
        except (ImportError, Exception) as e:
            return self.error_response(str(e), status_code=503)
        return self.success_response(data={'categories': cats, 'count': len(cats)})

    @action(detail=False, methods=['get'], url_path='category-lookup')
    def category_lookup(self, request):
        """
        Category search।
        GET /app-management/category-lookup/?q=game&platform=android
        """
        query    = request.query_params.get('q', '').strip()
        platform = request.query_params.get('platform', '')
        if not query:
            return self.error_response('q parameter required.', status_code=400)
        try:
            from .app_management.app_category import AppCategory
            qs = AppCategory.objects.filter(name__icontains=query, is_active=True)
            if platform:
                qs = qs.filter(platform=platform)
            cats = [
                {'pk': c.pk, 'name': getattr(c, 'name', ''), 'platform': getattr(c, 'platform', '')}
                for c in qs[:20]
            ]
        except (ImportError, Exception) as e:
            return self.error_response(str(e), status_code=503)
        return self.success_response(data={'results': cats, 'count': len(cats)})

    # ══════════════════════════════════════════════════════════════════════════
    # AppDownloadSnapshot
    # ══════════════════════════════════════════════════════════════════════════

    @action(detail=False, methods=['get'], url_path='download-trend')
    def download_trend(self, request):
        """
        App download trend (snapshots)।
        GET /app-management/download-trend/?app_id=APP001&days=30
        """
        publisher = self._get_publisher()
        app_id    = request.query_params.get('app_id')
        days      = int(request.query_params.get('days', 30))
        try:
            from .app_management.app_download import AppDownloadSnapshot
            from django.utils import timezone
            from datetime import timedelta
            since = timezone.now().date() - timedelta(days=days)
            qs = AppDownloadSnapshot.objects.filter(
                app__publisher=publisher, snapshot_date__gte=since
            ).order_by('snapshot_date')
            if app_id:
                qs = qs.filter(app__app_id=app_id)
            snapshots = [
                {
                    'date':               str(getattr(s, 'snapshot_date', '')),
                    'total_downloads':    getattr(s, 'total_downloads', 0),
                    'new_downloads':      getattr(s, 'new_downloads', 0),
                    'daily_active_users': getattr(s, 'daily_active_users', 0),
                }
                for s in qs[:90]
            ]
        except (ImportError, Exception) as e:
            return self.error_response(str(e), status_code=503)
        return self.success_response(data={'snapshots': snapshots, 'days': days, 'count': len(snapshots)})

    # ══════════════════════════════════════════════════════════════════════════
    # AppQualityScore
    # ══════════════════════════════════════════════════════════════════════════

    @action(detail=False, methods=['get'], url_path='quality-score')
    def quality_score(self, request):
        """
        Latest app quality score।
        GET /app-management/quality-score/?app_id=APP001
        """
        publisher = self._get_publisher()
        app_id    = request.query_params.get('app_id')
        try:
            from .app_management.app_quality import AppQualityScore
            qs = AppQualityScore.objects.filter(
                app__publisher=publisher
            ).order_by('-created_at')
            if app_id:
                qs = qs.filter(app__app_id=app_id)
            score = qs.first()
            if not score:
                return self.success_response(data={'score': None, 'message': 'No quality score yet.'})
            return self.success_response(data={
                'pk':              score.pk,
                'overall_score':   getattr(score, 'overall_score', 0),
                'content_score':   getattr(score, 'content_score', 0),
                'technical_score': getattr(score, 'technical_score', 0),
                'policy_score':    getattr(score, 'policy_score', 0),
                'scored_at':       str(score.created_at),
            })
        except (ImportError, Exception) as e:
            return self.error_response(str(e), status_code=503)

    @action(detail=False, methods=['get'], url_path='quality-breakdown')
    def quality_breakdown(self, request):
        """
        Quality score breakdown with individual checks।
        GET /app-management/quality-breakdown/?app_id=APP001
        """
        publisher = self._get_publisher()
        app_id    = request.query_params.get('app_id')
        try:
            from .app_management.app_quality import AppQualityScore
            qs = AppQualityScore.objects.filter(app__publisher=publisher).order_by('-created_at')
            if app_id:
                qs = qs.filter(app__app_id=app_id)
            score = qs.first()
            if not score:
                return self.success_response(data={'breakdown': [], 'message': 'No score yet.'})
            breakdown = score.breakdown() if hasattr(score, 'breakdown') else {
                'content':   {'score': getattr(score, 'content_score', 0),   'weight': 0.4},
                'technical': {'score': getattr(score, 'technical_score', 0), 'weight': 0.35},
                'policy':    {'score': getattr(score, 'policy_score', 0),    'weight': 0.25},
            }
            return self.success_response(data={'breakdown': breakdown})
        except (ImportError, Exception) as e:
            return self.error_response(str(e), status_code=503)

    # ══════════════════════════════════════════════════════════════════════════
    # AppRatingSnapshot
    # ══════════════════════════════════════════════════════════════════════════

    @action(detail=False, methods=['get'], url_path='rating-history')
    def rating_history(self, request):
        """
        App store rating history (snapshots)।
        GET /app-management/rating-history/?app_id=APP001&days=90
        """
        publisher = self._get_publisher()
        app_id    = request.query_params.get('app_id')
        days      = int(request.query_params.get('days', 90))
        try:
            from .app_management.app_rating import AppRatingSnapshot
            from django.utils import timezone
            from datetime import timedelta
            since = timezone.now().date() - timedelta(days=days)
            qs = AppRatingSnapshot.objects.filter(
                app__publisher=publisher, snapshot_date__gte=since
            ).order_by('snapshot_date')
            if app_id:
                qs = qs.filter(app__app_id=app_id)
            snapshots = [
                {
                    'date':           str(getattr(s, 'snapshot_date', '')),
                    'rating':         float(getattr(s, 'rating', 0)),
                    'rating_count':   getattr(s, 'rating_count', 0),
                    'reviews_count':  getattr(s, 'reviews_count', 0),
                }
                for s in qs[:120]
            ]
        except (ImportError, Exception) as e:
            return self.error_response(str(e), status_code=503)
        return self.success_response(data={'snapshots': snapshots, 'count': len(snapshots)})

    # ══════════════════════════════════════════════════════════════════════════
    # AppSDKConfig
    # ══════════════════════════════════════════════════════════════════════════

    @action(detail=False, methods=['get'], url_path='sdk-config')
    def sdk_config(self, request):
        """
        App SDK configuration।
        GET /app-management/sdk-config/?app_id=APP001
        """
        publisher = self._get_publisher()
        app_id    = request.query_params.get('app_id')
        try:
            from .app_management.app_sdk import AppSDKConfig
            app = self._get_app(app_id)
            if not app:
                return self.error_response('App not found.', status_code=404)
            config = AppSDKConfig.objects.filter(app=app).first()
            if not config:
                return self.success_response(data={'config': None, 'message': 'No SDK config.'})
            return self.success_response(data={
                'pk':              config.pk,
                'sdk_version':     getattr(config, 'sdk_version', ''),
                'init_options':    getattr(config, 'init_options', {}),
                'mediation_order': getattr(config, 'mediation_order', []),
                'test_mode':       getattr(config, 'test_mode', False),
                'updated_at':      str(config.updated_at),
            })
        except (ImportError, Exception) as e:
            return self.error_response(str(e), status_code=503)

    @action(detail=False, methods=['post'], url_path='sdk-config/update')
    def sdk_config_update(self, request):
        """
        Update app SDK configuration।
        POST /app-management/sdk-config/update/
        Body: { "app_id": "APP001", "sdk_version": "10.0.0", "test_mode": false, ... }
        """
        app_id = request.data.get('app_id', '')
        if not app_id:
            return self.error_response('app_id required.', status_code=400)
        try:
            from .app_management.app_sdk import AppSDKConfig
            app = self._get_app(app_id)
            if not app:
                return self.error_response('App not found.', status_code=404)
            config, created = AppSDKConfig.objects.get_or_create(app=app)
            for field in ['sdk_version', 'init_options', 'mediation_order', 'test_mode']:
                if request.data.get(field) is not None:
                    setattr(config, field, request.data[field])
            config.save()
            return self.success_response(
                data={'pk': config.pk, 'created': created},
                message='SDK config updated.',
            )
        except (ImportError, Exception) as e:
            return self.error_response(str(e), status_code=503)

    # ══════════════════════════════════════════════════════════════════════════
    # AppStoreMetadata
    # ══════════════════════════════════════════════════════════════════════════

    @action(detail=False, methods=['get'], url_path='store-metadata')
    def store_metadata(self, request):
        """
        App store metadata (title, description, screenshots etc.)।
        GET /app-management/store-metadata/?app_id=APP001
        """
        publisher = self._get_publisher()
        app_id    = request.query_params.get('app_id')
        try:
            from .app_management.app_store import AppStoreMetadata
            app = self._get_app(app_id)
            if not app:
                return self.error_response('App not found.', status_code=404)
            meta = AppStoreMetadata.objects.filter(app=app).first()
            if not meta:
                return self.success_response(data={'metadata': None, 'message': 'No store metadata.'})
            return self.success_response(data={
                'pk':              meta.pk,
                'store_title':     getattr(meta, 'store_title', ''),
                'store_desc':      getattr(meta, 'store_description', ''),
                'screenshots':     getattr(meta, 'screenshot_urls', []),
                'promo_video_url': getattr(meta, 'promo_video_url', ''),
                'last_synced_at':  str(getattr(meta, 'last_synced_at', '')),
            })
        except (ImportError, Exception) as e:
            return self.error_response(str(e), status_code=503)

    @action(detail=False, methods=['post'], url_path='store-metadata/sync')
    def store_metadata_sync(self, request):
        """
        Sync app metadata from Play Store / App Store।
        POST /app-management/store-metadata/sync/
        Body: { "app_id": "APP001" }
        """
        app_id = request.data.get('app_id', '')
        if not app_id:
            return self.error_response('app_id required.', status_code=400)
        try:
            from .app_management.app_store import AppStoreMetadata
            app = self._get_app(app_id)
            if not app:
                return self.error_response('App not found.', status_code=404)
            meta, created = AppStoreMetadata.objects.get_or_create(app=app)
            if hasattr(meta, 'sync_from_store'):
                result = meta.sync_from_store()
            else:
                from django.utils import timezone
                meta.last_synced_at = timezone.now()
                meta.save(update_fields=['last_synced_at'])
                result = {'synced': True, 'last_synced_at': str(meta.last_synced_at)}
            return self.success_response(data=result, message='Store metadata synced.')
        except (ImportError, Exception) as e:
            return self.error_response(str(e), status_code=503)

    # ══════════════════════════════════════════════════════════════════════════
    # AppVerification
    # ══════════════════════════════════════════════════════════════════════════

    @action(detail=False, methods=['get'], url_path='verification-status')
    def verification_status(self, request):
        """
        App verification status।
        GET /app-management/verification-status/?app_id=APP001
        """
        publisher = self._get_publisher()
        app_id    = request.query_params.get('app_id')
        try:
            from .app_management.app_verification import AppVerification
            qs = AppVerification.objects.filter(app__publisher=publisher)
            if app_id:
                qs = qs.filter(app__app_id=app_id)
            verifications = [
                {
                    'pk':                v.pk,
                    'verification_type': getattr(v, 'verification_type', ''),
                    'status':            getattr(v, 'status', ''),
                    'method':            getattr(v, 'method', ''),
                    'verified_at':       str(getattr(v, 'verified_at', '')),
                    'expires_at':        str(getattr(v, 'expires_at', '')),
                    'is_expired':        v.is_expired() if hasattr(v, 'is_expired') else False,
                }
                for v in qs
            ]
            return self.success_response(data={
                'verifications':  verifications,
                'count':          len(verifications),
                'all_verified':   all(
                    v['status'] == 'verified' for v in verifications
                ) if verifications else False,
            })
        except (ImportError, Exception) as e:
            return self.error_response(str(e), status_code=503)

    @action(detail=False, methods=['post'], url_path='verification-start')
    def verification_start(self, request):
        """
        Start app verification flow।
        POST /app-management/verification-start/
        Body: { "app_id": "APP001", "method": "sdk_token" | "store_listing" }
        """
        app_id = request.data.get('app_id', '')
        method = request.data.get('method', 'sdk_token')
        if not app_id:
            return self.error_response('app_id required.', status_code=400)
        try:
            from .app_management.app_verification import AppVerification
            app = self._get_app(app_id)
            if not app:
                return self.error_response('App not found.', status_code=404)
            verification = AppVerification(app=app, method=method, status='pending')
            if hasattr(verification, 'generate_token'):
                token = verification.generate_token()
            else:
                import secrets
                token = secrets.token_urlsafe(32)
            verification.save()
            return self.success_response(
                data={
                    'pk':     verification.pk,
                    'method': method,
                    'token':  token,
                    'status': 'pending',
                },
                message='Verification started.',
            )
        except (ImportError, Exception) as e:
            return self.error_response(str(e), status_code=503)

    # ══════════════════════════════════════════════════════════════════════════
    # AppWhitelistEntry
    # ══════════════════════════════════════════════════════════════════════════

    @action(detail=False, methods=['get'], url_path='whitelist-status')
    def whitelist_status(self, request):
        """
        Is publisher's app on any whitelist?
        GET /app-management/whitelist-status/?app_id=APP001
        """
        publisher = self._get_publisher()
        app_id    = request.query_params.get('app_id')
        try:
            from .app_management.app_whitelist import AppWhitelistEntry
            qs = AppWhitelistEntry.objects.filter(app__publisher=publisher, is_active=True)
            if app_id:
                qs = qs.filter(app__app_id=app_id)
            entry = qs.first()
            return self.success_response(data={
                'is_whitelisted': entry is not None,
                'whitelist_type': getattr(entry, 'whitelist_type', '') if entry else '',
                'added_at':       str(entry.created_at) if entry else '',
                'notes':          getattr(entry, 'notes', '') if entry else '',
            })
        except (ImportError, Exception) as e:
            return self.error_response(str(e), status_code=503)

    @action(detail=False, methods=['get'], url_path='whitelist-entries',
            permission_classes=[IsAuthenticated, IsAdminUser])
    def whitelist_entries(self, request):
        """
        All whitelist entries (admin only)।
        GET /app-management/whitelist-entries/?type=premium
        """
        wl_type = request.query_params.get('type', '')
        try:
            from .app_management.app_whitelist import AppWhitelistEntry
            qs = AppWhitelistEntry.objects.filter(is_active=True).order_by('-created_at')
            if wl_type:
                qs = qs.filter(whitelist_type=wl_type)
            entries = [
                {
                    'pk':             e.pk,
                    'app_id':         getattr(e.app, 'app_id', '') if hasattr(e, 'app') else '',
                    'whitelist_type': getattr(e, 'whitelist_type', ''),
                    'added_by':       getattr(e, 'added_by', ''),
                    'notes':          getattr(e, 'notes', ''),
                    'created_at':     str(e.created_at),
                }
                for e in qs[:100]
            ]
            return self.success_response(data={'entries': entries, 'count': len(entries)})
        except (ImportError, Exception) as e:
            return self.error_response(str(e), status_code=503)
