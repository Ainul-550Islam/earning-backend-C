# api/admin_panel/models.py
"""
Backward-compatibility shim.
Real models live in admin_panel/models/ package.
Django gives the package (__init__.py) priority over this file.
This shim ensures: from api.admin_panel.models import X  always works.
"""
from .models import (
    AdminAction, Report, SystemSettings, SiteNotification, SiteContent,
    AdminProfile, AdminPermissionGroup,
    DashboardWidget, DashboardLayout, DashboardMetric, DashboardAlert, QuickAction,
    AdminActivity, AdminSession, AdminNote, AdminBookmark, AdminSearch,
    SystemConfig, FeatureFlag, MaintenanceWindow, APIRateConfig, EmailTemplate,
    ReportDefinition, ReportSchedule, ReportExport, AdminInsight, DataExport,
    EndpointToggle,
)