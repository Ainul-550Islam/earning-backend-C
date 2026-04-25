# api/payment_gateways/migrations/0005_add_completed_at.py
# Adds completed_at to GatewayTransaction and new fields to PayoutRequest

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('payment_gateways', '0004_add_new_gateways'),
    ]

    operations = [
        # completed_at on GatewayTransaction (was missing — CRITICAL BUG fixed)
        migrations.AddField(
            model_name='gatewaytransaction',
            name='completed_at',
            field=models.DateTimeField(null=True, blank=True),
        ),
        # Additional new fields for world-class system
        migrations.AddField(
            model_name='gatewaytransaction',
            name='ip_address',
            field=models.GenericIPAddressField(null=True, blank=True),
        ),
        migrations.AddField(
            model_name='gatewaytransaction',
            name='device_type',
            field=models.CharField(max_length=20, blank=True),
        ),
        # PayoutRequest enhancements
        migrations.AddField(
            model_name='payoutrequest',
            name='processed_at',
            field=models.DateTimeField(null=True, blank=True),
        ),
        migrations.AddField(
            model_name='payoutrequest',
            name='metadata',
            field=models.JSONField(default=dict, blank=True),
        ),
        # Indexes for performance
        migrations.AddIndex(
            model_name='gatewaytransaction',
            index=models.Index(fields=['gateway', 'created_at'], name='txn_gateway_date_idx'),
        ),
        migrations.AddIndex(
            model_name='gatewaytransaction',
            index=models.Index(fields=['transaction_type', 'status'], name='txn_type_status_idx'),
        ),
        migrations.AddIndex(
            model_name='payoutrequest',
            index=models.Index(fields=['status'], name='payout_status_idx'),
        ),
    ]
