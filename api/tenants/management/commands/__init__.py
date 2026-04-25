"""
Tenant Management Commands

This module contains Django management commands for the tenant management system,
including utilities for maintenance, data migration, reporting, and system administration.
"""

from .tenants import (
    CreateTenantCommand,
    ListTenantsCommand,
    SuspendTenantCommand,
    UnsuspendTenantCommand,
    DeleteTenantCommand,
)

from .billing import (
    GenerateInvoicesCommand,
    ProcessDunningCommand,
    SendPaymentRemindersCommand,
    CalculateCommissionsCommand,
)

from .metrics import (
    CollectMetricsCommand,
    CalculateHealthScoresCommand,
    CleanupOldMetricsCommand,
    GenerateUsageReportCommand,
)

from .maintenance import (
    CleanupExpiredAPIKeysCommand,
    RenewSSLCertificatesCommand,
    BackupTenantDataCommand,
    ArchiveAuditLogsCommand,
    OptimizeDatabaseCommand,
)

from .onboarding import (
    CompleteOnboardingCommand,
    SendOnboardingRemindersCommand,
    ScheduleTrialExtensionsCommand,
)

from .security import (
    RotateAPIKeysCommand,
    CheckSecurityEventsCommand,
    GenerateSecurityReportCommand,
)

from .analytics import (
    GenerateAnalyticsReportCommand,
    ExportTenantDataCommand,
    ImportTenantDataCommand,
)

__all__ = [
    # Tenant management commands
    'CreateTenantCommand',
    'ListTenantsCommand',
    'SuspendTenantCommand',
    'UnsuspendTenantCommand',
    'DeleteTenantCommand',
    
    # Billing commands
    'GenerateInvoicesCommand',
    'ProcessDunningCommand',
    'SendPaymentRemindersCommand',
    'CalculateCommissionsCommand',
    
    # Metrics commands
    'CollectMetricsCommand',
    'CalculateHealthScoresCommand',
    'CleanupOldMetricsCommand',
    'GenerateUsageReportCommand',
    
    # Maintenance commands
    'CleanupExpiredAPIKeysCommand',
    'RenewSSLCertificatesCommand',
    'BackupTenantDataCommand',
    'ArchiveAuditLogsCommand',
    'OptimizeDatabaseCommand',
    
    # Onboarding commands
    'CompleteOnboardingCommand',
    'SendOnboardingRemindersCommand',
    'ScheduleTrialExtensionsCommand',
    
    # Security commands
    'RotateAPIKeysCommand',
    'CheckSecurityEventsCommand',
    'GenerateSecurityReportCommand',
    
    # Analytics commands
    'GenerateAnalyticsReportCommand',
    'ExportTenantDataCommand',
    'ImportTenantDataCommand',
]