# api/admin_panel/exceptions.py
"""
Custom exceptions for admin_panel app.
"""
from rest_framework.exceptions import APIException
from rest_framework import status


# ==================== Base Admin Exception ====================

class AdminPanelException(APIException):
    """Base exception for all admin panel errors."""
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'An admin panel error occurred.'
    default_code = 'admin_panel_error'


# ==================== Settings & Config Exceptions ====================

class SystemSettingsError(AdminPanelException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'System settings operation failed.'
    default_code = 'system_settings_error'


class SystemConfigNotFound(AdminPanelException):
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = 'System config key not found.'
    default_code = 'config_not_found'


class SystemConfigValidationError(AdminPanelException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'System config value is invalid.'
    default_code = 'config_validation_error'


class SingletonViolation(AdminPanelException):
    """Raised when trying to create a second singleton instance."""
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'Only one instance of this object is allowed.'
    default_code = 'singleton_violation'


# ==================== Feature Flag Exceptions ====================

class FeatureFlagNotFound(AdminPanelException):
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = 'Feature flag not found.'
    default_code = 'feature_flag_not_found'


class FeatureFlagDisabled(AdminPanelException):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = 'This feature is currently disabled.'
    default_code = 'feature_flag_disabled'


class InvalidRolloutPercentage(AdminPanelException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'Rollout percentage must be between 0 and 100.'
    default_code = 'invalid_rollout_percentage'


# ==================== Dashboard Exceptions ====================

class DashboardWidgetError(AdminPanelException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'Dashboard widget operation failed.'
    default_code = 'dashboard_widget_error'


class MaxWidgetsExceeded(AdminPanelException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'Maximum number of dashboard widgets exceeded.'
    default_code = 'max_widgets_exceeded'


class MetricNotFound(AdminPanelException):
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = 'Dashboard metric not found.'
    default_code = 'metric_not_found'


# ==================== Report Exceptions ====================

class ReportGenerationError(AdminPanelException):
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_detail = 'Report generation failed.'
    default_code = 'report_generation_error'


class ReportNotFound(AdminPanelException):
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = 'Report not found.'
    default_code = 'report_not_found'


class ReportFileNotFound(AdminPanelException):
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = 'Report file not found on disk.'
    default_code = 'report_file_not_found'


class InvalidReportFormat(AdminPanelException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'Invalid report format. Allowed: csv, xlsx, pdf, json.'
    default_code = 'invalid_report_format'


class MaxScheduledReportsExceeded(AdminPanelException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'Maximum number of scheduled reports per user exceeded.'
    default_code = 'max_scheduled_reports_exceeded'


# ==================== Data Export Exceptions ====================

class DataExportError(AdminPanelException):
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_detail = 'Data export operation failed.'
    default_code = 'data_export_error'


class ExportNotReady(AdminPanelException):
    status_code = status.HTTP_202_ACCEPTED
    default_detail = 'Export is still processing. Please try again later.'
    default_code = 'export_not_ready'


class ExportExpired(AdminPanelException):
    status_code = status.HTTP_410_GONE
    default_detail = 'This export has expired. Please generate a new one.'
    default_code = 'export_expired'


# ==================== Activity Exceptions ====================

class ActivityLogError(AdminPanelException):
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_detail = 'Failed to log admin activity.'
    default_code = 'activity_log_error'


class SessionNotFound(AdminPanelException):
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = 'Admin session not found.'
    default_code = 'session_not_found'


class SessionAlreadyExpired(AdminPanelException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'Session is already expired or logged out.'
    default_code = 'session_already_expired'


# ==================== Search Exceptions ====================

class SearchQueryTooShort(AdminPanelException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'Search query is too short. Minimum 2 characters required.'
    default_code = 'search_query_too_short'


class SearchModelNotFound(AdminPanelException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'Invalid search model specified.'
    default_code = 'search_model_not_found'


# ==================== Bulk Action Exceptions ====================

class BulkActionError(AdminPanelException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'Bulk action operation failed.'
    default_code = 'bulk_action_error'


class BulkActionLimitExceeded(AdminPanelException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'Too many records selected for bulk action. Max 500 allowed.'
    default_code = 'bulk_action_limit_exceeded'


class InvalidBulkActionType(AdminPanelException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'Invalid bulk action type.'
    default_code = 'invalid_bulk_action_type'


# ==================== Maintenance Exceptions ====================

class MaintenanceModeActive(AdminPanelException):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = 'System is currently under maintenance. Please try again later.'
    default_code = 'maintenance_mode_active'


class MaintenanceWindowOverlap(AdminPanelException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'A maintenance window already overlaps with the requested period.'
    default_code = 'maintenance_window_overlap'


class MaintenanceWindowNotFound(AdminPanelException):
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = 'Maintenance window not found.'
    default_code = 'maintenance_window_not_found'


# ==================== Insight Exceptions ====================

class InsightGenerationError(AdminPanelException):
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_detail = 'Failed to generate admin insights.'
    default_code = 'insight_generation_error'


# ==================== Permission Exceptions ====================

class InsufficientAdminPermission(AdminPanelException):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = 'You do not have sufficient admin permissions for this action.'
    default_code = 'insufficient_admin_permission'


class AdminProfileNotFound(AdminPanelException):
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = 'Admin profile not found.'
    default_code = 'admin_profile_not_found'