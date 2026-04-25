# api/wallet/models_webhook.py
"""
WalletWebhookLog — payment gateway webhook log.
Kept separate to avoid circular imports with models_cpalead_extra.py.
"""
from django.db import models
from django.utils import timezone


class WalletWebhookLog(models.Model):
    """
    Log every incoming payment gateway webhook callback.
    Webhooks are processed asynchronously by process_webhook Celery task.
    """
    WEBHOOK_TYPES = [
        ("bkash",       "bKash"),
        ("nagad",       "Nagad"),
        ("rocket",      "Rocket"),
        ("stripe",      "Stripe"),
        ("paypal",      "PayPal"),
        ("sslcommerz",  "SSLCommerz"),
        ("nowpayments", "NowPayments (USDT)"),
        ("unknown",     "Unknown"),
    ]

    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="wallet_webhooklog_tenant",
        db_index=True,
    )
    webhook_type       = models.CharField(max_length=20, choices=WEBHOOK_TYPES, db_index=True)
    event_type         = models.CharField(max_length=100, blank=True)
    payload            = models.JSONField(default=dict, blank=True)
    headers            = models.JSONField(default=dict, blank=True)
    signature          = models.CharField(max_length=500, blank=True)
    is_processed       = models.BooleanField(default=False, db_index=True)
    is_verified        = models.BooleanField(default=False)
    processing_error   = models.TextField(blank=True)
    reference_id       = models.CharField(max_length=200, blank=True, db_index=True)
    transaction_ref    = models.CharField(max_length=200, blank=True)
    ip_address         = models.GenericIPAddressField(null=True, blank=True)
    received_at        = models.DateTimeField(auto_now_add=True, db_index=True)
    processed_at       = models.DateTimeField(null=True, blank=True)
    retry_count        = models.PositiveIntegerField(default=0)

    class Meta:
        app_label = "wallet"
        db_table  = "wallet_webhooklog"
        ordering  = ["-received_at"]
        indexes   = [
            models.Index(fields=["webhook_type", "is_processed"]),
            models.Index(fields=["reference_id"]),
        ]

    def __str__(self):
        return f"{self.webhook_type} | {self.event_type} | {self.received_at}"

    def mark_processed(self, error: str = ""):
        self.is_processed    = True
        self.processed_at    = timezone.now()
        self.processing_error = error
        self.save(update_fields=["is_processed", "processed_at", "processing_error"])

    def increment_retry(self):
        self.retry_count += 1
        self.save(update_fields=["retry_count"])
