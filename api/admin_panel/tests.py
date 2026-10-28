# api/admin_panel/tests.py
"""
Admin Panel Test Suite.
Full tests are in tests/ package (factories, test_models, test_views, etc.)
This file provides the main test runner entry point.
"""
from django.test import TestCase


class AdminPanelSmokeTest(TestCase):
    """Basic smoke tests to verify imports work."""

    def test_models_importable(self):
        from api.admin_panel.models import (
            AdminAction, Report, SystemSettings,
            SiteNotification, SiteContent, EndpointToggle,
        )
        self.assertTrue(True)

    def test_new_models_importable(self):
        from api.admin_panel.models import (
            AdminProfile, AdminPermissionGroup,
            DashboardWidget, DashboardMetric,
            AdminActivity, AdminSession,
            SystemConfig, FeatureFlag, MaintenanceWindow,
            ReportDefinition, DataExport, AdminInsight,
        )
        self.assertTrue(True)

    def test_services_importable(self):
        from api.admin_panel.services.SystemConfigService import SystemConfigService
        from api.admin_panel.services.FeatureFlagService import FeatureFlagService
        from api.admin_panel.services.MaintenanceModeService import MaintenanceModeService
        self.assertTrue(True)

    def test_utils_importable(self):
        from api.admin_panel.utils import (
            get_client_ip, format_currency, get_date_range,
            compute_model_diff, slugify_key,
        )
        self.assertTrue(True)