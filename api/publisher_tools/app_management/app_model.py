# api/publisher_tools/app_management/app_model.py
"""App Model extensions — App store info, SDK config."""
from django.db import models
from django.utils.translation import gettext_lazy as _
from core.models import TimeStampedModel


class AppSDKConfig(TimeStampedModel):
    """App SDK integration configuration."""
    tenant = models.ForeignKey("tenants.Tenant", on_delete=models.SET_NULL, null=True, blank=True, related_name="publisher_tools_appsdkconfig_tenant", db_index=True)
    app              = models.OneToOneField("publisher_tools.App", on_delete=models.CASCADE, related_name="sdk_config")
    sdk_version      = models.CharField(max_length=20, default="1.0.0")
    sdk_platform     = models.CharField(max_length=20, choices=[("android","Android"),("ios","iOS"),("flutter","Flutter"),("react_native","React Native"),("unity","Unity")], default="android")
    app_key          = models.CharField(max_length=100, blank=True)
    app_secret       = models.CharField(max_length=200, blank=True)
    test_mode        = models.BooleanField(default=False)
    auto_init        = models.BooleanField(default=True)
    gdpr_consent_required = models.BooleanField(default=False)
    coppa_compliant  = models.BooleanField(default=False)
    min_sdk_version  = models.CharField(max_length=10, blank=True)
    sdk_init_code    = models.TextField(blank=True, help_text="Integration code snippet")
    is_integrated    = models.BooleanField(default=False)
    first_integrated_at = models.DateTimeField(null=True, blank=True)
    last_ping_at     = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "publisher_tools_app_sdk_configs"
        verbose_name = _("App SDK Config")

    def __str__(self):
        return f"SDK: {self.app.name} — {self.sdk_platform}"

    def generate_init_code(self):
        if self.sdk_platform == "android":
            return f"""// Android SDK Init\nPublisherTools.initialize(this, "{self.app_key}");"""
        elif self.sdk_platform == "ios":
            return f"""// iOS SDK Init\nPublisherTools.initialize(publisherId: "{self.app_key}")"""
        return ""
