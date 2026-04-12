from django.apps import AppConfig
class AdminPanelConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "api.admin_panel"
    verbose_name = "Admin Panel"
    def ready(self):
        try:
            import api.admin_panel.signals
        except ImportError:
            pass
        try:
            from django.db import connection
            connection.ensure_connection()
        except Exception:
            pass

def _post_migrate_sync(sender, **kwargs):
    try:
        from api.admin_panel.admin import admin_site, _sync_all_apps_to_modern_site
        _sync_all_apps_to_modern_site()
    except Exception as e:
        print(f"[WARN] sync failed: {e}")

from django.db.models.signals import post_migrate
post_migrate.connect(_post_migrate_sync)
