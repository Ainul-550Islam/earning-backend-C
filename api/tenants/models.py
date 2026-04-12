from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
import uuid


class Tenant(models.Model):
    PLAN_CHOICES = [
        ("basic", "Basic"),
        ("pro", "Pro"),
        ("enterprise", "Enterprise"),
    ]

    name = models.CharField(max_length=255, null=True, blank=True)
    slug = models.SlugField(unique=True, null=True, blank=True)
    domain = models.CharField(max_length=255, unique=True, null=True, blank=True)
    admin_email = models.EmailField(blank=True, null=True)
    api_key = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    logo = models.ImageField(upload_to="tenant_logos/", null=True, blank=True)
    primary_color = models.CharField(max_length=7, default="#007bff", null=True, blank=True)
    secondary_color = models.CharField(max_length=7, default="#6c757d", null=True, blank=True)
    plan = models.CharField(max_length=20, choices=PLAN_CHOICES, default="basic", null=True, blank=True)
    max_users = models.IntegerField(default=100)
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

    def get_active_user_count(self):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        return User.objects.filter(tenant=self, is_active=True).count()

    def is_user_limit_reached(self):
        return self.get_active_user_count() >= self.max_users


class TenantSettings(models.Model):
    tenant = models.OneToOneField(Tenant, on_delete=models.CASCADE, related_name='settings', null=True, blank=True)

    # App Branding
    app_name = models.CharField(max_length=100, default='EarningApp', null=True, blank=True)
    support_email = models.EmailField(blank=True)
    privacy_policy_url = models.URLField(null=True, blank=True)
    terms_url = models.URLField(null=True, blank=True)

    # Feature Flags
    enable_referral = models.BooleanField(default=True)
    enable_offerwall = models.BooleanField(default=True)
    enable_kyc = models.BooleanField(default=True)
    enable_leaderboard = models.BooleanField(default=True)
    enable_chat = models.BooleanField(default=False)
    enable_push_notifications = models.BooleanField(default=True)

    # Payout Rules
    min_withdrawal = models.DecimalField(max_digits=10, decimal_places=2, default=5.00, null=True, blank=True)
    withdrawal_fee_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0.00, null=True, blank=True)

    # React Native App Config
    android_package_name = models.CharField(max_length=255, null=True, blank=True)
    ios_bundle_id = models.CharField(max_length=255, null=True, blank=True)
    firebase_server_key = models.TextField(blank=True)

    class Meta:
        db_table = 'tenant_settings'

    def __str__(self):
        return f"{self.tenant.name} Settings"


class TenantBilling(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('expired', 'Expired'),
        ('cancelled', 'Cancelled'),
        ('trial', 'Trial'),
    ]

    tenant = models.OneToOneField(Tenant, on_delete=models.CASCADE, related_name='billing', null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='trial', null=True, blank=True)
    trial_ends_at = models.DateTimeField(null=True, blank=True)
    subscription_ends_at = models.DateTimeField(null=True, blank=True)
    monthly_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, null=True, blank=True)
    stripe_customer_id = models.CharField(max_length=255, null=True, blank=True)
    stripe_subscription_id = models.CharField(max_length=255, null=True, blank=True)
    last_payment_at = models.DateTimeField(null=True, blank=True)
    next_payment_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'tenant_billing'

    def __str__(self):
        return f"{self.tenant.name} - {self.status}"

    def is_active(self):
        from django.utils import timezone
        if self.status == 'trial':
            return self.trial_ends_at and self.trial_ends_at > timezone.now()
        if self.status == 'active':
            return self.subscription_ends_at and self.subscription_ends_at > timezone.now()
        return False


class TenantInvoice(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='invoices', null=True, blank=True)
    invoice_number = models.CharField(max_length=50, unique=True, null=True, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    status = models.CharField(max_length=20, default='unpaid', null=True, blank=True)
    due_date = models.DateTimeField()
    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'tenant_invoices'

    def save(self, *args, **kwargs):
        if not self.invoice_number:
            self.invoice_number = f"INV-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.invoice_number} - {self.tenant.name}"


@receiver(post_save, sender=Tenant)
def create_tenant_defaults(sender, instance, created, **kwargs):
    if created:
        TenantSettings.objects.get_or_create(tenant=instance)
        from django.utils import timezone
        TenantBilling.objects.get_or_create(
            tenant=instance,
            defaults={
                'status': 'trial',
                'trial_ends_at': timezone.now() + timezone.timedelta(days=14),
            }
        )
