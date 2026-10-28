# api/admin_panel/models/__init__.py
"""
Admin panel models package.
Imports all models from sub-modules for easy access.

Usage:
    from api.admin_panel.models import (
        AdminAction, SystemSettings, SiteNotification, SiteContent,
        AdminProfile, AdminPermissionGroup,
        DashboardWidget, DashboardLayout, DashboardMetric, DashboardAlert, QuickAction,
        AdminActivity, AdminSession, AdminNote, AdminBookmark, AdminSearch,
        SystemConfig, FeatureFlag, MaintenanceWindow, APIRateConfig, EmailTemplate,
        ReportDefinition, ReportSchedule, ReportExport, AdminInsight, DataExport,
    )
"""

# ==================== Core Models ====================
from .core import (
    AdminAction,
    Report,
    SystemSettings,
    SiteNotification,
    SiteContent,
    AdminProfile,
    AdminPermissionGroup,
)

# ==================== Dashboard Models ====================
from .dashboard import (
    DashboardWidget,
    DashboardLayout,
    DashboardMetric,
    DashboardAlert,
    QuickAction,
)

# ==================== Activity Models ====================
from .activity import (
    AdminActivity,
    AdminSession,
    AdminNote,
    AdminBookmark,
    AdminSearch,
)

# ==================== Config Models ====================
from .config import (
    SystemConfig,
    FeatureFlag,
    MaintenanceWindow,
    APIRateConfig,
    EmailTemplate,
)

# ==================== Reports Models ====================
from .reports import (
    ReportDefinition,
    ReportSchedule,
    ReportExport,
    AdminInsight,
    DataExport,
)

# Keep EndpointToggle accessible via admin_panel.models too
from ..endpoint_toggle import EndpointToggle

__all__ = [
    # Core
    'AdminAction',
    'Report',
    'SystemSettings',
    'SiteNotification',
    'SiteContent',
    'AdminProfile',
    'AdminPermissionGroup',
    # Dashboard
    'DashboardWidget',
    'DashboardLayout',
    'DashboardMetric',
    'DashboardAlert',
    'QuickAction',
    # Activity
    'AdminActivity',
    'AdminSession',
    'AdminNote',
    'AdminBookmark',
    'AdminSearch',
    # Config
    'SystemConfig',
    'FeatureFlag',
    'MaintenanceWindow',
    'APIRateConfig',
    'EmailTemplate',
    # Reports
    'ReportDefinition',
    'ReportSchedule',
    'ReportExport',
    'AdminInsight',
    'DataExport',
    # EndpointToggle
    'EndpointToggle',
]