# api/admin_panel/registry.py
"""
Admin Panel Central Registry — single source of truth for all registrations.
Viewsets, URLs, permissions, adapters all register here.
"""
from typing import Dict, List, Optional, Tuple, Type
import logging

logger = logging.getLogger(__name__)


class AdminPanelRegistry:
    """
    Central registry for admin_panel components.
    Every viewset, service, adapter registers here.
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._viewsets = {}
            cls._instance._services = {}
            cls._instance._middleware = []
            cls._instance._ready = False
        return cls._instance

    # ==================== VIEWSETS ====================

    def register_viewset(self, app: str, viewset_class, basename: str, url_prefix: str):
        self._viewsets[app] = {
            'class': viewset_class,
            'basename': basename,
            'url_prefix': url_prefix,
        }
        logger.debug(f"[Registry] ViewSet registered: {app} -> {url_prefix}")

    def get_viewset(self, app: str) -> Optional[Dict]:
        return self._viewsets.get(app)

    def list_viewsets(self) -> Dict:
        return {k: v['url_prefix'] for k, v in self._viewsets.items()}

    # ==================== SERVICES ====================

    def register_service(self, name: str, service_class):
        self._services[name] = service_class
        logger.debug(f"[Registry] Service registered: {name}")

    def get_service(self, name: str):
        svc = self._services.get(name)
        return svc() if svc else None

    # ==================== STATUS ====================

    def mark_ready(self):
        self._ready = True
        logger.info(f"[Registry] Admin panel registry ready: {len(self._viewsets)} viewsets, {len(self._services)} services")

    @property
    def is_ready(self) -> bool:
        return self._ready

    def get_stats(self) -> Dict:
        return {
            'viewsets': len(self._viewsets),
            'services': len(self._services),
            'ready': self._ready,
        }


# Global singleton
admin_registry = AdminPanelRegistry()


def register_all():
    """Auto-register all standard viewsets and services."""
    from api.admin_panel.viewsets import (
        DashboardViewSet, SystemConfigViewSet, FeatureFlagViewSet,
        MaintenanceWindowViewSet, ReportViewSet, AdminActivityViewSet,
        AdminSessionViewSet, DataExportViewSet, AdminSearchViewSet,
        AdminInsightViewSet, BulkActionViewSet,
    )
    viewset_map = [
        ('dashboard', DashboardViewSet, 'admin-dashboard', 'dashboard'),
        ('system-config', SystemConfigViewSet, 'system-config', 'config'),
        ('feature-flags', FeatureFlagViewSet, 'feature-flags', 'feature-flags'),
        ('maintenance', MaintenanceWindowViewSet, 'maintenance', 'maintenance'),
        ('reports', ReportViewSet, 'reports', 'reports'),
        ('activity', AdminActivityViewSet, 'admin-activity', 'activity'),
        ('sessions', AdminSessionViewSet, 'admin-sessions', 'sessions'),
        ('data-exports', DataExportViewSet, 'data-exports', 'data-exports'),
        ('search', AdminSearchViewSet, 'admin-search', 'search'),
        ('insights', AdminInsightViewSet, 'admin-insights', 'insights'),
        ('bulk-actions', BulkActionViewSet, 'bulk-actions', 'bulk-actions'),
    ]
    for app, cls, basename, prefix in viewset_map:
        admin_registry.register_viewset(app, cls, basename, prefix)
    admin_registry.mark_ready()