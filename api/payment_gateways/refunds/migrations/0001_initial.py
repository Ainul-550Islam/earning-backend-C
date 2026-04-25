# api/payment_gateways/refunds/migrations/0001_initial.py
# FILE 65 of 257

import django.db.models.deletion
import django.core.validators
from decimal import Decimal
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('payment_gateways', '0004_add_new_gateways'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    ALL_GATEWAY_CHOICES = [
        ('bkash', 'bKash'), ('nagad', 'Nagad'), ('sslcommerz', 'SSLCommerz'),
        ('amarpay', 'AmarPay'), ('upay', 'Upay'), ('shurjopay', 'ShurjoPay'),
        ('stripe', 'Stripe'), ('paypal', 'PayPal'),
    ]

    operations = [
        migrations.CreateModel(
            name='RefundRequest',
            fields=[
                ('id',               models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('created_at',       models.DateTimeField(auto_now_add=True)),
                ('updated_at',       models.DateTimeField(auto_now=True)),
                ('gateway',          models.CharField(choices=ALL_GATEWAY_CHOICES, max_length=20)),
                ('amount',           models.DecimalField(decimal_places=2, max_digits=10, validators=[django.core.validators.MinValueValidator(Decimal('1.00'))])),
                ('status',           models.CharField(choices=[('pending','Pending'),('processing','Processing'),('completed','Completed'),('failed','Failed'),('cancelled','Cancelled')], default='pending', max_length=20)),
                ('reason',           models.CharField(choices=[('duplicate','Duplicate payment'),('fraudulent','Fraudulent transaction'),('customer_request','Customer requested refund'),('order_cancelled','Order cancelled'),('service_not_provided','Service not provided'),('partial_refund','Partial refund'),('other','Other')], default='customer_request', max_length=50)),
                ('reference_id',     models.CharField(max_length=100, unique=True)),
                ('gateway_refund_id', models.CharField(blank=True, max_length=200, null=True)),
                ('completed_at',     models.DateTimeField(blank=True, null=True)),
                ('failed_at',        models.DateTimeField(blank=True, null=True)),
                ('metadata',         models.JSONField(blank=True, default=dict)),
                ('notes',            models.TextField(blank=True, null=True)),
                ('user',             models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='refund_requests', to=settings.AUTH_USER_MODEL)),
                ('initiated_by',     models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='initiated_refunds', to=settings.AUTH_USER_MODEL)),
                ('original_transaction', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='refund_requests', to='payment_gateways.gatewaytransaction')),
            ],
            options={'verbose_name': 'Refund Request', 'verbose_name_plural': 'Refund Requests', 'ordering': ['-created_at']},
        ),
        migrations.CreateModel(
            name='RefundPolicy',
            fields=[
                ('id',                  models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('created_at',          models.DateTimeField(auto_now_add=True)),
                ('updated_at',          models.DateTimeField(auto_now=True)),
                ('gateway',             models.CharField(choices=ALL_GATEWAY_CHOICES, max_length=20, unique=True)),
                ('auto_approve',        models.BooleanField(default=False)),
                ('max_refund_days',     models.IntegerField(default=30)),
                ('max_refund_amount',   models.DecimalField(decimal_places=2, default=Decimal('50000.00'), max_digits=10)),
                ('allow_partial_refund', models.BooleanField(default=True)),
                ('fee_refundable',      models.BooleanField(default=False)),
                ('is_active',           models.BooleanField(default=True)),
                ('notes',               models.TextField(blank=True, null=True)),
            ],
            options={'verbose_name': 'Refund Policy', 'verbose_name_plural': 'Refund Policies'},
        ),
        migrations.CreateModel(
            name='RefundAuditLog',
            fields=[
                ('id',              models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('created_at',      models.DateTimeField(auto_now_add=True)),
                ('updated_at',      models.DateTimeField(auto_now=True)),
                ('previous_status', models.CharField(blank=True, choices=[('pending','Pending'),('processing','Processing'),('completed','Completed'),('failed','Failed'),('cancelled','Cancelled')], max_length=20)),
                ('new_status',      models.CharField(choices=[('pending','Pending'),('processing','Processing'),('completed','Completed'),('failed','Failed'),('cancelled','Cancelled')], max_length=20)),
                ('note',            models.TextField(blank=True)),
                ('metadata',        models.JSONField(blank=True, default=dict)),
                ('changed_by',      models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='refund_audit_actions', to=settings.AUTH_USER_MODEL)),
                ('refund_request',  models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='audit_logs', to='payment_gateway_refunds.refundrequest')),
            ],
            options={'verbose_name': 'Refund Audit Log', 'verbose_name_plural': 'Refund Audit Logs', 'ordering': ['created_at']},
        ),
        migrations.AddIndex(model_name='refundrequest', index=models.Index(fields=['status'], name='refund_status_idx')),
        migrations.AddIndex(model_name='refundrequest', index=models.Index(fields=['gateway'], name='refund_gateway_idx')),
        migrations.AddIndex(model_name='refundrequest', index=models.Index(fields=['user', 'status'], name='refund_user_status_idx')),
        migrations.AddIndex(model_name='refundrequest', index=models.Index(fields=['reference_id'], name='refund_ref_idx')),
    ]
