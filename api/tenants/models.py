from django.db import models
import uuid

class Tenant(models.Model):
    PLAN_CHOICES = [
        ("basic", "Basic"),
        ("pro", "Pro"),
        ("enterprise", "Enterprise"),
    ]

    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    domain = models.CharField(max_length=255, unique=True)
    api_key = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    logo = models.ImageField(upload_to="tenant_logos/", null=True, blank=True)
    primary_color = models.CharField(max_length=7, default="#007bff")
    secondary_color = models.CharField(max_length=7, default="#6c757d")
    plan = models.CharField(max_length=20, choices=PLAN_CHOICES, default="basic")
    max_users = models.IntegerField(default=10)
    admin_email = models.EmailField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "tenants"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            from django.utils.text import slugify
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class TenantSettings(models.Model):
    tenant = models.OneToOneField(Tenant, on_delete=models.CASCADE, related_name='settings')

    # App Branding
    app_name = models.CharField(max_length=100, default='EarningApp')
    support_email = models.EmailField(blank=True)
    privacy_policy_url = models.URLField(blank=True)
    terms_url = models.URLField(blank=True)

    # Feature Flags (on/off per tenant)
    enable_referral = models.BooleanField(default=True)
    enable_offerwall = models.BooleanField(default=True)
    enable_kyc = models.BooleanField(default=True)
    enable_leaderboard = models.BooleanField(default=True)
    enable_chat = models.BooleanField(default=False)
    enable_push_notifications = models.BooleanField(default=True)

    # Payout Rules
    min_withdrawal = models.DecimalField(max_digits=10, decimal_places=2, default=5.00)
    withdrawal_fee_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)

    # React Native App Config
    android_package_name = models.CharField(max_length=255, blank=True)
    ios_bundle_id = models.CharField(max_length=255, blank=True)
    firebase_server_key = models.TextField(blank=True)

    class Meta:
        db_table = 'tenant_settings'

    def __str__(self):
        return f"{self.tenant.name} Settings"


from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=Tenant)
def create_tenant_settings(sender, instance, created, **kwargs):
    if created:
        TenantSettings.objects.get_or_create(tenant=instance)
