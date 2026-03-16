# api/audit_logs/apps.py
from django.apps import AppConfig

class AuditLogsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api.audit_logs'
    label = 'audit_logs'
    verbose_name = '📋 Audit Logs Management'
    
    def ready(self):
        """Initialize audit_logs app"""
        try:
            import api.audit_logs.signals
            print("[OK] Audit Logs signals loaded")
        except ImportError:
            pass
        
        # Force admin registration
        try:
            from django.contrib import admin
            from .models import (
                AuditLog, AuditLogAction, AuditLogLevel, AuditLogConfig,
                AuditLogArchive, AuditAlertRule, AuditDashboard
            )
            
            print("[LOADING] Checking audit_logs admin registration...")
            
            try:
                from .admin import (
                    AuditLogAdmin,
                    AuditLogConfigAdmin, AuditLogArchiveAdmin,
                    AuditAlertRuleAdmin, AuditDashboardAdmin
                )
                
                models_to_register = [
                    (AuditLog, AuditLogAdmin),
                    (AuditLogConfig, AuditLogConfigAdmin),
                    (AuditLogArchive, AuditLogArchiveAdmin),
                    (AuditAlertRule, AuditAlertRuleAdmin),
                    (AuditDashboard, AuditDashboardAdmin),
                ]
                
                registered = 0
                for model, admin_class in models_to_register:
                    if not admin.site.is_registered(model):
                        admin.site.register(model, admin_class)
                        registered += 1
                        print(f"[OK] Registered: {model.__name__} from apps.py")
                
                if registered > 0:
                    print(f"[OK][OK][OK] {registered} audit_logs models registered from apps.py")
                else:
                    print("[OK] All audit_logs models already registered")
                    
            except ImportError as e:
                print(f"[WARN] Could not import admin classes: {e}")
                
        except Exception as e:
            print(f"[WARN] Audit Logs admin registration error: {e}")