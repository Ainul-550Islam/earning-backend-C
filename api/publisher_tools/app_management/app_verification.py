# api/publisher_tools/app_management/app_verification.py
"""App verification — Play Store / App Store ownership verification."""
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from core.models import TimeStampedModel


class AppVerification(TimeStampedModel):
    """App ownership verification record."""
    tenant = models.ForeignKey("tenants.Tenant", on_delete=models.SET_NULL, null=True, blank=True, related_name="publisher_tools_appverif_tenant", db_index=True)
    METHODS = [("store_listing","Store Listing Check"),("api_key","API Key Verification"),("sdk_ping","SDK First Ping"),("manual","Manual Review")]
    STATUS  = [("pending","Pending"),("verified","Verified"),("failed","Failed"),("expired","Expired")]

    app              = models.ForeignKey("publisher_tools.App", on_delete=models.CASCADE, related_name="app_verifications")
    method           = models.CharField(max_length=20, choices=METHODS, default="store_listing")
    status           = models.CharField(max_length=20, choices=STATUS, default="pending", db_index=True)
    verification_code= models.CharField(max_length=50, blank=True)
    store_url_verified = models.BooleanField(default=False)
    package_name_verified = models.BooleanField(default=False)
    developer_email_verified = models.BooleanField(default=False)
    attempt_count    = models.IntegerField(default=0)
    verified_at      = models.DateTimeField(null=True, blank=True)
    expires_at       = models.DateTimeField(null=True, blank=True)
    failure_reason   = models.TextField(blank=True)
    last_checked_at  = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "publisher_tools_app_verifications"
        verbose_name = _("App Verification")
        ordering = ["-created_at"]

    def __str__(self):
        return f"Verify: {self.app.name} [{self.method}] — {self.status}"

    def verify(self):
        self.attempt_count += 1
        self.last_checked_at = timezone.now()
        # Simplified: production-এ store API call করো
        if self.app.play_store_url or self.app.app_store_url:
            self.store_url_verified = True
            self.package_name_verified = True
            self.status = "verified"
            self.verified_at = timezone.now()
            self.app.status = "active"
            self.app.approved_at = timezone.now()
            self.app.save(update_fields=["status", "approved_at", "updated_at"])
        else:
            self.status = "failed"
            self.failure_reason = "Store URL not provided."
        self.save()
        return self.status == "verified"
