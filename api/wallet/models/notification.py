# api/wallet/models/notification.py
from django.db import models
from django.conf import settings
from django.utils import timezone


class WalletNotification(models.Model):
    """In-app notification for wallet events."""
    TYPES = [
        ("wallet_credited","Wallet Credited"),
        ("withdrawal_requested","Withdrawal Pending"),
        ("withdrawal_completed","Withdrawal Completed"),
        ("withdrawal_failed","Withdrawal Failed"),
        ("kyc_approved","KYC Approved"),
        ("kyc_rejected","KYC Rejected"),
        ("streak_milestone","Streak Milestone"),
        ("publisher_level_upgraded","Level Upgraded"),
        ("bonus_expiring","Bonus Expiring"),
        ("fraud_detected","Security Alert"),
        ("system","System"),
    ]
    tenant     = models.ForeignKey("tenants.Tenant",on_delete=models.SET_NULL,null=True,blank=True,related_name="wallet_notification_tenant",db_index=True)
    user       = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE,related_name="wallet_notifications")
    event_type = models.CharField(max_length=50,choices=TYPES,db_index=True)
    title      = models.CharField(max_length=200)
    message    = models.TextField()
    data       = models.JSONField(default=dict,blank=True)
    is_read    = models.BooleanField(default=False,db_index=True)
    read_at    = models.DateTimeField(null=True,blank=True)
    created_at = models.DateTimeField(auto_now_add=True,db_index=True)

    class Meta:
        app_label="wallet"; db_table="wallet_notification"; ordering=["-created_at"]
        indexes=[models.Index(fields=["user","is_read"]),models.Index(fields=["user","created_at"])]

    def __str__(self): return f"{self.user_id}|{self.event_type}|{self.title[:30]}"

    def mark_read(self):
        self.is_read=True; self.read_at=timezone.now()
        self.save(update_fields=["is_read","read_at"])


class NotificationPreference(models.Model):
    """User notification preferences."""
    tenant        = models.ForeignKey("tenants.Tenant",on_delete=models.SET_NULL,null=True,blank=True,related_name="wallet_notifpref_tenant",db_index=True)
    user          = models.OneToOneField(settings.AUTH_USER_MODEL,on_delete=models.CASCADE,related_name="wallet_notification_preference")
    push_enabled  = models.BooleanField(default=True)
    email_enabled = models.BooleanField(default=True)
    sms_enabled   = models.BooleanField(default=False)
    events        = models.JSONField(default=dict,blank=True,help_text="Per-event channel config")
    updated_at    = models.DateTimeField(auto_now=True)

    class Meta:
        app_label="wallet"; db_table="wallet_notification_preference"

    def __str__(self): return f"{self.user_id}|push={self.push_enabled}|email={self.email_enabled}"
