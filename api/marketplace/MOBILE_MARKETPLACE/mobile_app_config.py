"""
MOBILE_MARKETPLACE/mobile_app_config.py — Remote App Configuration
====================================================================
Allows updating app behaviour without a new release.
Fetched on app launch → cached locally.
"""
from django.db import models
from django.core.cache import cache
import json


class MobileAppConfig(models.Model):
    tenant      = models.ForeignKey("tenants.Tenant", on_delete=models.SET_NULL, null=True,
                                     related_name="mobile_configs_tenant")
    key         = models.CharField(max_length=100)
    value       = models.TextField()
    value_type  = models.CharField(max_length=10, default="string",
                                    choices=[("string","String"),("number","Number"),
                                             ("boolean","Boolean"),("json","JSON")])
    platform    = models.CharField(max_length=10, default="all",
                                    choices=[("all","All"),("android","Android"),("ios","iOS")])
    min_version = models.CharField(max_length=10, blank=True)
    description = models.CharField(max_length=255, blank=True)
    is_active   = models.BooleanField(default=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "marketplace"
        db_table  = "marketplace_mobile_app_config"
        unique_together = [("tenant","key","platform")]

    def parsed_value(self):
        if self.value_type == "number":
            return float(self.value)
        if self.value_type == "boolean":
            return self.value.lower() in ("true","1","yes")
        if self.value_type == "json":
            try:
                return json.loads(self.value)
            except Exception:
                return {}
        return self.value


def get_app_config(tenant, platform: str = "all") -> dict:
    cache_key = f"mobile_config:{tenant.pk}:{platform}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    configs = MobileAppConfig.objects.filter(
        tenant=tenant, is_active=True, platform__in=[platform, "all"]
    )
    result = {}
    for cfg in configs:
        result[cfg.key] = cfg.parsed_value()

    # Defaults
    result.setdefault("maintenance_mode", False)
    result.setdefault("min_app_version", "1.0.0")
    result.setdefault("force_update", False)
    result.setdefault("features", {
        "loyalty_program": True,
        "referral_program": True,
        "flash_sale": True,
        "ar_try_on": False,
        "voice_search": False,
    })
    result.setdefault("contact_support_url", "https://support.example.com")
    result.setdefault("banner_ads_enabled", False)

    cache.set(cache_key, result, 300)  # 5 min cache
    return result


def set_config(tenant, key: str, value, value_type: str = "string", platform: str = "all"):
    MobileAppConfig.objects.update_or_create(
        tenant=tenant, key=key, platform=platform,
        defaults={"value": str(value), "value_type": value_type, "is_active": True}
    )
    cache.delete(f"mobile_config:{tenant.pk}:{platform}")
    cache.delete(f"mobile_config:{tenant.pk}:all")
