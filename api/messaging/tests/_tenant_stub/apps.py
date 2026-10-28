"""
Minimal stub so `messaging` is testable in isolation.

models.py defines `tenant = ForeignKey('tenants.Tenant', ...)` on every model,
because in the real host project (earning_backend) a `tenants` app already
exists. When this module is tested standalone (no host project present),
nothing provides that app — so we register this stub under the SAME
app_label ("tenants") purely so the FK string resolves. It is never
installed when a real `tenants` app is already on the INSTALLED_APPS list
(see conftest.py), so it can never collide with the real one.
"""
from django.apps import AppConfig


class TenantStubConfig(AppConfig):
    name = "messaging.tests._tenant_stub"
    label = "tenants"
    default_auto_field = "django.db.models.BigAutoField"
