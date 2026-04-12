from django.apps import AppConfig

class TenantsConfig(AppConfig):
    name = "api.tenants"
    label = "tenants"
    def ready(self):
        try:
            from api.tenants.admin import _force_register_tenants
            _force_register_tenants()
        except Exception as e:
            pass
