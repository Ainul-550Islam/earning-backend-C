# publisher_tools/views_app_management.py
# Exposes app_management/ subfolder logic via DRF.
# Register: router.register(r'app-tools', AppManagementViewSet, basename='app-tool')

from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from .mixins import PublisherViewMixin, AdminScriptViewMixin, AdminOnlyMixin, ErrorHandlingMixin
from core.views import BaseViewSet
from .permissions import IsPublisher


class AppManagementViewSet(BaseViewSet):
    """
    App Management Tools API.
    app_management/ subfolder expose করা হয়েছে।

    Endpoints:
      GET /app-tools/performance/   — app performance summary
      GET /app-tools/by-format/     — revenue by ad format
      GET /app-tools/top-countries/ — top revenue countries
    """
    permission_classes = [IsAuthenticated, IsPublisher]

    def _get_publisher(self):
        try:
            return self.request.user.publisher_profile
        except Exception:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('No active publisher profile.')

    def _get_app(self, app_id, publisher):
        from .models import App
        return App.objects.filter(app_id=app_id, publisher=publisher).first()

    @action(detail=False, methods=['get'], url_path='performance')
    def performance(self, request):
        """
        App performance summary.
        GET /app-tools/performance/?app_id=APP123456&days=30
        """
        publisher = self._get_publisher()
        app_id    = request.query_params.get('app_id')
        days      = int(request.query_params.get('days', 30))

        if not app_id:
            return self.error_response('app_id is required.', status_code=400)

        app = self._get_app(app_id, publisher)
        if not app:
            return self.error_response('App not found.', status_code=404)

        try:
            from .app_management import get_app_performance_summary
            data = get_app_performance_summary(app, days=days)
        except (ImportError, Exception) as e:
            return self.error_response(str(e), status_code=503)

        return self.success_response(data=data)

    @action(detail=False, methods=['get'], url_path='by-format')
    def by_format(self, request):
        """
        Revenue by ad format for the app.
        GET /app-tools/by-format/?app_id=APP123456&days=30
        """
        publisher = self._get_publisher()
        app_id    = request.query_params.get('app_id')
        days      = int(request.query_params.get('days', 30))

        if not app_id:
            return self.error_response('app_id is required.', status_code=400)

        app = self._get_app(app_id, publisher)
        if not app:
            return self.error_response('App not found.', status_code=404)

        try:
            from .app_management import get_app_revenue_by_format
            data = get_app_revenue_by_format(app, days=days)
        except (ImportError, Exception) as e:
            return self.error_response(str(e), status_code=503)

        return self.success_response(data=data)

    @action(detail=False, methods=['get'], url_path='top-countries')
    def top_countries(self, request):
        """
        Top revenue countries for the app.
        GET /app-tools/top-countries/?app_id=APP123456&days=30&limit=10
        """
        publisher = self._get_publisher()
        app_id    = request.query_params.get('app_id')
        days      = int(request.query_params.get('days', 30))
        limit     = int(request.query_params.get('limit', 10))

        if not app_id:
            return self.error_response('app_id is required.', status_code=400)

        app = self._get_app(app_id, publisher)
        if not app:
            return self.error_response('App not found.', status_code=404)

        try:
            from .app_management import get_app_top_countries
            data = get_app_top_countries(app, days=days, limit=limit)
        except (ImportError, Exception) as e:
            return self.error_response(str(e), status_code=503)

        return self.success_response(data=data)
