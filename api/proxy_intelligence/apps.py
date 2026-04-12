from django.apps import AppConfig


class ProxyIntelligenceConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api.proxy_intelligence'
    verbose_name = 'Proxy Intelligence'

    def ready(self):
        import api.proxy_intelligence.signals  # noqa
        try:
            from api.proxy_intelligence.admin import _force_register_proxy_intelligence
            _force_register_proxy_intelligence()
        except Exception as e:
            pass
