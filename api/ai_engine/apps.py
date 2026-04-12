from django.apps import AppConfig
class AiEngineConfig(AppConfig):
    default_auto_field  = "django.db.models.BigAutoField"
    name                = "api.ai_engine"
    verbose_name        = "AI Engine"
    def ready(self):
        try:
            import api.ai_engine.signals
        except Exception:
            pass
        try:
            from api.ai_engine.admin import _force_register_ai_engine
            _force_register_ai_engine()
        except Exception as e:
            print(f"[WARN] AI Engine admin: {e}")
