"""
apps.py
"""
from django.apps import AppConfig
class PostbackEngineConfig(AppConfig):
    name = "api.postback_engine"
    label = "postback_engine"
    verbose_name = "Postback Engine"
    default_auto_field = "django.db.models.BigAutoField"
    def ready(self):
        try:
            import api.postback_engine.receivers
        except ImportError:
            pass
        try:
            from api.postback_engine.admin import _force_register_postback_engine
            _force_register_postback_engine()
        except Exception as e:
            print(f"[WARN] Postback Engine admin: {e}")
