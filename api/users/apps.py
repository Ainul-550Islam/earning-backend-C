# api/users/apps.py
from django.apps import AppConfig

class UsersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api.users'
    label = 'users'
    verbose_name = 'User Management'
    
    def ready(self):
        # Import signals - this should happen after Django is ready
        try:
            import api.users.signals
            print("[OK] Users app ready - signals imported")
        except ImportError as e:
            print("[ERROR] Failed to import signals: {}".format(e))
        try:
            from api.users.admin import _force_register_users
            _force_register_users()
        except Exception as e:
            pass
