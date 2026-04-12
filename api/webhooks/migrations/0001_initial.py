# Copyright © 2026 Ainul Enterprise Engine. All Rights Reserved.
# Generated migration for api.webhooks

import uuid
import api.webhooks.models
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("tenants", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="WebhookEndpoint",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Created At")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Updated At")),
                ("label", models.CharField(max_length=120, verbose_name="Label")),
                ("target_url", models.URLField(max_length=2048, verbose_name="Target URL")),
                ("http_method", models.CharField(choices=[("POST", "POST"), ("PUT", "PUT"), ("PATCH", "PATCH")], default="POST", max_length=8, verbose_name="HTTP Method")),
                ("secret_key", models.CharField(default=api.webhooks.models._generate_secret_key, editable=False, max_length=128, verbose_name="Signing Secret")),
                ("status", models.CharField(choices=[("active", "Active"), ("paused", "Paused"), ("disabled", "Disabled"), ("suspended", "Suspended (Auto — High Failure Rate)")], db_index=True, default="active", max_length=20, verbose_name="Status")),
                ("custom_headers", models.JSONField(blank=True, default=api.webhooks.models._empty_dict, verbose_name="Custom Headers")),
                ("description", models.TextField(blank=True, default="", verbose_name="Description")),
                ("version", models.PositiveSmallIntegerField(default=1, verbose_name="Schema Version")),
                ("max_retries", models.PositiveSmallIntegerField(default=5, verbose_name="Max Retries")),
                ("verify_ssl", models.BooleanField(default=True, verbose_name="Verify SSL")),
                ("total_deliveries", models.PositiveIntegerField(default=0)),
                ("success_deliveries", models.PositiveIntegerField(default=0)),
                ("failed_deliveries", models.PositiveIntegerField(default=0)),
                ("last_triggered_at", models.DateTimeField(blank=True, null=True)),
                ("tenant", models.ForeignKey(blank=True, db_index=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="webhook_endpoints", to="tenants.tenant", verbose_name="Tenant")),
                ("owner", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="webhook_endpoints", to=settings.AUTH_USER_MODEL, verbose_name="Owner")),
            ],
            options={"verbose_name": "Webhook Endpoint", "verbose_name_plural": "Webhook Endpoints", "ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="WebhookSubscription",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Created At")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Updated At")),
                ("event_type", models.CharField(choices=[("payout.success", "Payout Success"), ("payout.failed", "Payout Failed"), ("payout.pending", "Payout Pending"), ("payout.reversed", "Payout Reversed"), ("payout.scheduled", "Payout Scheduled"), ("wallet.credited", "Wallet Credited"), ("wallet.debited", "Wallet Debited"), ("wallet.frozen", "Wallet Frozen"), ("wallet.threshold_hit", "Wallet Threshold Hit"), ("user.registered", "User Registered"), ("user.verified", "User Verified (KYC)"), ("user.suspended", "User Suspended"), ("user.deleted", "User Deleted"), ("user.profile_updated", "User Profile Updated"), ("user.password_changed", "User Password Changed"), ("offer.completed", "Offer Completed"), ("offer.credited", "Offer Credited"), ("offer.reversed", "Offer Reversed"), ("offer.flagged", "Offer Flagged — Suspicious"), ("ad.impression", "Ad Impression"), ("ad.click", "Ad Click"), ("ad.reward_granted", "Ad Reward Granted"), ("ad.network_connected", "Ad Network Connected"), ("ad.network_disconnected", "Ad Network Disconnected"), ("referral.signup", "Referral Signup"), ("referral.commission", "Referral Commission Earned"), ("subscription.activated", "Subscription Activated"), ("subscription.cancelled", "Subscription Cancelled"), ("subscription.renewed", "Subscription Renewed"), ("subscription.expired", "Subscription Expired"), ("fraud.alert_raised", "Fraud Alert Raised"), ("fraud.account_blocked", "Fraud — Account Blocked"), ("fraud.ip_blacklisted", "Fraud — IP Blacklisted"), ("kyc.submitted", "KYC Submitted"), ("kyc.approved", "KYC Approved"), ("kyc.rejected", "KYC Rejected"), ("system.maintenance_start", "System Maintenance Started"), ("system.maintenance_end", "System Maintenance Ended"), ("system.alert", "System Alert"), ("webhook.test", "Webhook Test Ping")], db_index=True, max_length=80, verbose_name="Event Type")),
                ("is_active", models.BooleanField(db_index=True, default=True, verbose_name="Active")),
                ("filters", models.JSONField(blank=True, default=api.webhooks.models._empty_dict, verbose_name="Payload Filters")),
                ("endpoint", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="subscriptions", to="webhooks.webhookendpoint", verbose_name="Endpoint")),
            ],
            options={"verbose_name": "Webhook Subscription", "verbose_name_plural": "Webhook Subscriptions", "ordering": ["event_type"], "unique_together": {("endpoint", "event_type")}},
        ),
        migrations.CreateModel(
            name="WebhookDeliveryLog",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Created At")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Updated At")),
                ("event_type", models.CharField(db_index=True, max_length=80, verbose_name="Event Type")),
                ("delivery_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True, verbose_name="Delivery ID")),
                ("payload", models.JSONField(default=api.webhooks.models._empty_dict, verbose_name="Dispatched Payload")),
                ("request_headers", models.JSONField(blank=True, default=api.webhooks.models._empty_dict, verbose_name="Request Headers Sent")),
                ("signature", models.CharField(blank=True, default="", max_length=256, verbose_name="HMAC Signature")),
                ("http_status_code", models.PositiveSmallIntegerField(blank=True, null=True, verbose_name="HTTP Status Code")),
                ("response_body", models.TextField(blank=True, default="", verbose_name="Response Body")),
                ("response_time_ms", models.PositiveIntegerField(blank=True, null=True, verbose_name="Response Time (ms)")),
                ("error_message", models.TextField(blank=True, default="", verbose_name="Error Message")),
                ("status", models.CharField(choices=[("pending", "Pending"), ("dispatched", "Dispatched"), ("success", "Success"), ("failed", "Failed"), ("retrying", "Retrying"), ("exhausted", "Exhausted (Max Retries Reached)"), ("cancelled", "Cancelled")], db_index=True, default="pending", max_length=20, verbose_name="Delivery Status")),
                ("attempt_number", models.PositiveSmallIntegerField(default=1, verbose_name="Attempt Number")),
                ("max_attempts", models.PositiveSmallIntegerField(default=5, verbose_name="Max Attempts")),
                ("next_retry_at", models.DateTimeField(blank=True, db_index=True, null=True, verbose_name="Next Retry At")),
                ("dispatched_at", models.DateTimeField(blank=True, null=True, verbose_name="Dispatched At")),
                ("completed_at", models.DateTimeField(blank=True, null=True, verbose_name="Completed At")),
                ("endpoint", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="delivery_logs", to="webhooks.webhookendpoint", verbose_name="Endpoint")),
            ],
            options={"verbose_name": "Webhook Delivery Log", "verbose_name_plural": "Webhook Delivery Logs", "ordering": ["-created_at"]},
        ),
        migrations.AddIndex(
            model_name="webhookendpoint",
            index=models.Index(fields=["owner", "status"], name="webhook_end_owner_status_idx"),
        ),
        migrations.AddIndex(
            model_name="webhookendpoint",
            index=models.Index(fields=["tenant", "status"], name="webhook_end_tenant_status_idx"),
        ),
        migrations.AddIndex(
            model_name="webhooksubscription",
            index=models.Index(fields=["event_type", "is_active"], name="webhook_sub_event_active_idx"),
        ),
        migrations.AddIndex(
            model_name="webhookdeliverylog",
            index=models.Index(fields=["endpoint", "status"], name="webhook_log_endpoint_status_idx"),
        ),
        migrations.AddIndex(
            model_name="webhookdeliverylog",
            index=models.Index(fields=["event_type", "status"], name="webhook_log_event_status_idx"),
        ),
        migrations.AddIndex(
            model_name="webhookdeliverylog",
            index=models.Index(fields=["status", "next_retry_at"], name="webhook_log_status_retry_idx"),
        ),
        migrations.AddIndex(
            model_name="webhookdeliverylog",
            index=models.Index(fields=["delivery_id"], name="webhook_log_delivery_id_idx"),
        ),
    ]
