# api/backup/apps.py
from django.apps import AppConfig

class BackupConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api.backup'
    label = 'backup'
    verbose_name = '💾 Backup Management'
    
    def ready(self):
        """Initialize backup app"""
        # Import signals
        try:
            import api.backup.signals
            print("[OK] Backup signals loaded")
        except ImportError:
            pass
        
        # Force admin registration
        try:
            from django.contrib import admin
            from .models import (
                Backup, BackupSchedule, BackupLog, BackupRestoration,
                BackupStorageLocation, RetentionPolicy, 
                BackupNotificationConfig, DeltaBackupTracker
            )
            
            print("[LOADING] Checking backup admin registration...")
            
            # Try to import admin classes
            try:
                from .admin import (
                    BackupAdmin, BackupScheduleAdmin, BackupLogAdmin,
                    BackupRestorationAdmin, BackupStorageLocationAdmin,
                    RetentionPolicyAdmin, BackupNotificationConfigAdmin,
                    DeltaBackupTrackerAdmin
                )
                
                models_to_register = [
                    (Backup, BackupAdmin),
                    (BackupSchedule, BackupScheduleAdmin),
                    (BackupLog, BackupLogAdmin),
                    (BackupRestoration, BackupRestorationAdmin),
                    (BackupStorageLocation, BackupStorageLocationAdmin),
                    (RetentionPolicy, RetentionPolicyAdmin),
                    (BackupNotificationConfig, BackupNotificationConfigAdmin),
                    (DeltaBackupTracker, DeltaBackupTrackerAdmin),
                ]
                
                registered = 0
                for model, admin_class in models_to_register:
                    if not admin.site.is_registered(model):
                        try:
                            admin.site.register(model, admin_class)
                            registered += 1
                            print(f"[OK] Registered: {model.__name__} from apps.py")
                        except Exception as e:
                            print(f"[WARN] Could not register {model.__name__}: {e}")
                
                if registered > 0:
                    print(f"[OK][OK][OK] {registered} backup models registered from apps.py")
                else:
                    print("[OK] All backup models already registered")
                    
            except ImportError as e:
                print(f"[WARN] Could not import admin classes: {e}")
                # Fallback: register without custom admin
                for model in [Backup, BackupSchedule, BackupLog, BackupRestoration,
                            BackupStorageLocation, RetentionPolicy, 
                            BackupNotificationConfig, DeltaBackupTracker]:
                    if not admin.site.is_registered(model):
                        try:
                            admin.site.register(model)
                            print(f"[OK] Registered: {model.__name__} (default)")
                        except Exception as e:
                            print(f"[WARN] Could not register {model.__name__}: {e}")
                
                # Also register with custom admin site if exists
                try:
                    from .admin import backup_admin_site
                    print("📋 Registering with custom backup admin site...")
                    for model in [Backup, BackupSchedule, BackupLog, BackupRestoration,
                                BackupStorageLocation, RetentionPolicy, 
                                BackupNotificationConfig, DeltaBackupTracker]:
                        if not backup_admin_site.is_registered(model):
                            try:
                                backup_admin_site.register(model)
                                print(f"[OK] Registered in backup admin: {model.__name__}")
                            except Exception as e:
                                print(f"[WARN] Could not register in backup admin: {e}")
                except ImportError:
                    pass
                
        except Exception as e:
            print(f"[WARN] Backup admin registration error: {e}")
        try:
            from api.backup.admin import _force_register_backup
            _force_register_backup()
        except Exception as e:
            pass
