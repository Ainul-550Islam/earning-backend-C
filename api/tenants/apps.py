"""
Tenant Management App Configuration

This module contains the Django app configuration for the tenant management
system, including signal registration and app initialization.
"""

from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class TenantsConfig(AppConfig):
    """
    Django app configuration for the tenant management system.
    
    This app provides comprehensive multi-tenant functionality including:
    - Tenant management and provisioning
    - Subscription plans and billing
    - Security and access control
    - Analytics and monitoring
    - Onboarding and user guidance
    - Branding and customization
    - Reseller management
    """
    
    name = "api.tenants"
    label = "tenants"
    verbose_name = _("Tenant Management")
    default_auto_field = 'django.db.models.BigAutoField'
    
    def ready(self):
        """
        Initialize the tenant management app.
        
        This method is called when the app is ready and performs:
        - Signal registration
        - Admin integration
        - Task registration
        """
        # Register signals
        self._register_signals()
        
        # Register admin classes
        self._register_admin()
        
        # Register tasks
        self._register_tasks()
        
        # Register management commands
        self._register_management_commands()
    
    def _register_signals(self):
        """Register all signal handlers."""
        try:
            # Import and register core signals
            from . import signals
            
            # Import signal handlers to ensure they're registered
            from .signals.core import (
                tenant_created_handler,
                tenant_updated_handler,
                tenant_deleted_handler,
                tenant_settings_updated_handler,
                tenant_invoice_created_handler,
            )
            
            # Import plan signals
            from .signals.plan import (
                plan_usage_recorded_handler,
                quota_exceeded_handler,
                plan_upgrade_created_handler,
                plan_updated_handler,
            )
            
            # Import security signals
            from .signals.security import (
                api_key_created_handler,
                api_key_used_handler,
                api_key_revoked_handler,
                webhook_triggered_handler,
                security_event_detected_handler,
            )
            
            # Import onboarding signals
            from .signals.onboarding import (
                onboarding_started_handler,
                onboarding_step_completed_handler,
                onboarding_completed_handler,
                trial_extension_requested_handler,
            )
            
            # Import analytics signals
            from .signals.analytics import (
                metric_recorded_handler,
                health_score_updated_handler,
                feature_flag_toggled_handler,
                notification_created_handler,
            )
            
            # Import branding signals
            from .signals.branding import (
                branding_updated_handler,
                domain_verified_handler,
                ssl_certificate_updated_handler,
            )
            
            # Import reseller signals
            from .signals.reseller import (
                reseller_created_handler,
                commission_calculated_handler,
                referral_activity_tracked_handler,
            )
            
        except Exception as e:
            # Log error but don't prevent app from loading
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to register signals: {e}")
    
    def _register_admin(self):
        """Register admin classes with Django admin."""
        try:
            from .admin import _force_register_tenants
            _force_register_tenants()
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to register admin classes: {e}")
    
    def _register_tasks(self):
        """Register Celery tasks."""
        try:
            # Import task modules to register them with Celery
            from . import tasks
            
            # Import billing tasks
            from .tasks.billing import (
                generate_monthly_invoices,
                process_dunning_workflow,
                send_payment_reminders,
                calculate_commission_payments,
                process_subscription_renewals,
                cleanup_old_invoices,
                generate_billing_reports,
            )
            
            # Import metrics tasks
            from .tasks.metrics import (
                collect_daily_metrics,
                collect_weekly_metrics,
                collect_monthly_metrics,
                calculate_health_scores,
                cleanup_old_metrics,
                generate_usage_analytics,
                track_api_usage,
                calculate_trends,
            )
            
            # Import notification tasks
            from .tasks.notifications import (
                send_onboarding_reminders,
                send_trial_expiry_notifications,
                send_quota_exceeded_notifications,
                send_security_alerts,
                process_email_queue,
                send_welcome_emails,
                cleanup_old_notifications,
            )
            
            # Import maintenance tasks
            from .tasks.maintenance import (
                cleanup_expired_api_keys,
                cleanup_expired_feature_flags,
                renew_ssl_certificates,
                backup_tenant_data,
                archive_audit_logs,
                cleanup_soft_deleted_tenants,
                optimize_database,
                update_system_statistics,
                check_data_integrity,
                cleanup_temp_files,
            )
            
            # Import monitoring tasks
            from .tasks.monitoring import (
                monitor_ssl_expiry,
                check_disk_usage,
                monitor_api_usage,
                generate_system_health_report,
                check_service_health,
                track_performance_metrics,
            )
            
            # Import onboarding tasks
            from .tasks.onboarding import (
                complete_onboarding_steps,
                send_welcome_emails,
                schedule_trial_extensions,
                send_progress_tips,
                cleanup_old_onboarding_data,
                generate_onboarding_analytics,
            )
            
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to register tasks: {e}")
    
    def _register_management_commands(self):
        """Register management commands."""
        try:
            # Import command modules to register them
            from . import management_commands
            
            # Import tenant commands
            from .management.commands.tenants import (
                CreateTenantCommand,
                ListTenantsCommand,
                SuspendTenantCommand,
                UnsuspendTenantCommand,
                DeleteTenantCommand,
                TenantInfoCommand,
            )
            
            # Import billing commands
            from .management.commands.billing import (
                GenerateInvoicesCommand,
                ProcessDunningCommand,
                SendPaymentRemindersCommand,
                CalculateCommissionsCommand,
                BillingReportCommand,
            )
            
            # Import metrics commands
            from .management.commands.metrics import (
                CollectMetricsCommand,
                CalculateHealthScoresCommand,
                CleanupOldMetricsCommand,
                GenerateUsageReportCommand,
                MetricSummaryCommand,
            )
            
            # Import maintenance commands
            from .management.commands.maintenance import (
                CleanupExpiredAPIKeysCommand,
                RenewSSLCertificatesCommand,
                BackupTenantDataCommand,
                ArchiveAuditLogsCommand,
                OptimizeDatabaseCommand,
                CheckSystemHealthCommand,
                CleanupTempFilesCommand,
            )
            
            # Import onboarding commands
            from .management.commands.onboarding import (
                CompleteOnboardingCommand,
                SendOnboardingRemindersCommand,
                ScheduleTrialExtensionsCommand,
                OnboardingAnalyticsCommand,
                OnboardingProgressCommand,
                CleanupOldOnboardingDataCommand,
            )
            
            # Import security commands
            from .management.commands.security import (
                RotateAPIKeysCommand,
                CheckSecurityEventsCommand,
                GenerateSecurityReportCommand,
                AuditLogExportCommand,
                SecurityScanCommand,
            )
            
            # Import analytics commands
            from .management.commands.analytics import (
                GenerateAnalyticsReportCommand,
                ExportTenantDataCommand,
                ImportTenantDataCommand,
                DataIntegrityCheckCommand,
                BackupAnalyticsCommand,
            )
            
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to register management commands: {e}")
    
    def get_models(self, include_auto_created=False, include_swapped=False):
        """
        Get all models for this app.
        
        Returns a dictionary of model classes keyed by model name.
        """
        models = super().get_models(include_auto_created, include_swapped)
        
        # Add any dynamically created models here if needed
        
        return models
    
    def get_model(self, model_name, require_ready=True):
        """
        Get a model by name.
        
        Args:
            model_name: The name of the model to get
            require_ready: Whether to require the app to be ready
            
        Returns:
            The model class or None if not found
        """
        return super().get_model(model_name, require_ready)
