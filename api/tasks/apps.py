# api/tasks/apps.py
from django.apps import AppConfig

class TasksConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api.tasks'
    
    def ready(self):
        """Connect signals when app is ready"""
        # Import signals
        import api.tasks.signals
    
        try:
            print("[OK] Tasks signals loaded")
        except ImportError as e:
            print(f"[WARN] Tasks signals not loaded: {e}")
        
        # 2. তারপর admin registration force করুন (নতুন যোগ করবেন)
        try:
            from django.contrib import admin
            from .models import MasterTask, UserTaskCompletion, AdminLedger
            from .admin import MasterTaskAdmin, UserTaskCompletionAdmin, AdminLedgerAdmin
            
            print("[LOADING] Loading tasks admin...")
            registered = 0
            
            # MasterTask register
            if not admin.site.is_registered(MasterTask):
                admin.site.register(MasterTask, MasterTaskAdmin)
                registered += 1
                print("[OK] Registered: MasterTask")
            
            # UserTaskCompletion register
            if not admin.site.is_registered(UserTaskCompletion):
                admin.site.register(UserTaskCompletion, UserTaskCompletionAdmin)
                registered += 1
                print("[OK] Registered: UserTaskCompletion")
            
            # AdminLedger register
            if not admin.site.is_registered(AdminLedger):
                admin.site.register(AdminLedger, AdminLedgerAdmin)
                registered += 1
                print("[OK] Registered: AdminLedger")
            
            if registered > 0:
                print(f"[OK][OK][OK] {registered} tasks models registered from apps.py")
            else:
                print("[OK] All tasks models already registered")
                
        except Exception as e:
            print(f"[WARN] Tasks admin registration error: {e}")