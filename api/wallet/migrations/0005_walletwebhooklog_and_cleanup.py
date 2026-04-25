# api/wallet/migrations/0005_walletwebhooklog_and_cleanup.py
"""
Migration 0005:
  - Ensure WalletWebhookLog table is properly created from models_webhook.py
  - Add retry_count, is_verified, signature, transaction_ref, ip_address fields
  - Fix db_table name consistency
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("wallet", "0004_world_class_features"),
        ("tenants", "0001_initial"),
    ]

    operations = [
        # Add missing fields to WalletWebhookLog
        migrations.AddField(
            model_name="walletwebhooklog",
            name="signature",
            field=models.CharField(blank=True, max_length=500),
        ),
        migrations.AddField(
            model_name="walletwebhooklog",
            name="is_verified",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="walletwebhooklog",
            name="transaction_ref",
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AddField(
            model_name="walletwebhooklog",
            name="ip_address",
            field=models.GenericIPAddressField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="walletwebhooklog",
            name="retry_count",
            field=models.PositiveIntegerField(default=0),
        ),
        # Add nowpayments to webhook type choices
        migrations.AlterField(
            model_name="walletwebhooklog",
            name="webhook_type",
            field=models.CharField(
                choices=[
                    ("bkash","bKash"),("nagad","Nagad"),("rocket","Rocket"),
                    ("stripe","Stripe"),("paypal","PayPal"),("sslcommerz","SSLCommerz"),
                    ("nowpayments","NowPayments (USDT)"),("unknown","Unknown"),
                ],
                db_index=True,
                max_length=20,
            ),
        ),
        # Add indexes
        migrations.AddIndex(
            model_name="walletwebhooklog",
            index=models.Index(fields=["webhook_type","is_processed"], name="wallet_hook_type_proc_idx"),
        ),
        migrations.AddIndex(
            model_name="walletwebhooklog",
            index=models.Index(fields=["reference_id"], name="wallet_hook_ref_idx"),
        ),
    ]
