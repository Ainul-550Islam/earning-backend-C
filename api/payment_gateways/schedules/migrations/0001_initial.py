# schedules/migrations/0001_initial.py
import django.db.models.deletion
from decimal import Decimal
from django.conf import settings
from django.db import migrations, models

class Migration(migrations.Migration):
    initial = True
    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(name='PaymentSchedule', fields=[
            ('id', models.BigAutoField(primary_key=True)),
            ('created_at', models.DateTimeField(auto_now_add=True)),
            ('updated_at', models.DateTimeField(auto_now=True)),
            ('schedule_type', models.CharField(max_length=10, default='net30')),
            ('status', models.CharField(max_length=10, default='active')),
            ('payment_method', models.CharField(max_length=20, default='paypal')),
            ('payment_account', models.CharField(max_length=200)),
            ('payment_currency', models.CharField(max_length=5, default='USD')),
            ('minimum_payout', models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('1.00'))),
            ('next_payout_date', models.DateField(null=True, blank=True)),
            ('last_payout_date', models.DateField(null=True, blank=True)),
            ('last_payout_amount', models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0'))),
            ('notes', models.TextField(blank=True)),
            ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE,
                     related_name='payment_schedule', to=settings.AUTH_USER_MODEL)),
        ], options={'verbose_name': 'Payment Schedule'}),
        migrations.CreateModel(name='ScheduledPayout', fields=[
            ('id', models.BigAutoField(primary_key=True)),
            ('created_at', models.DateTimeField(auto_now_add=True)),
            ('updated_at', models.DateTimeField(auto_now=True)),
            ('amount', models.DecimalField(max_digits=10, decimal_places=2)),
            ('fee', models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0'))),
            ('net_amount', models.DecimalField(max_digits=10, decimal_places=2)),
            ('currency', models.CharField(max_length=5, default='USD')),
            ('payment_method', models.CharField(max_length=20)),
            ('payment_account', models.CharField(max_length=200)),
            ('status', models.CharField(max_length=15, default='pending')),
            ('period_start', models.DateField()),
            ('period_end', models.DateField()),
            ('scheduled_date', models.DateField()),
            ('processed_at', models.DateTimeField(null=True, blank=True)),
            ('gateway_reference', models.CharField(max_length=200, blank=True)),
            ('error_message', models.TextField(blank=True)),
            ('metadata', models.JSONField(default=dict, blank=True)),
            ('schedule', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                         related_name='payouts', to='payment_gateway_schedules.paymentschedule')),
            ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                     related_name='scheduled_payouts', to=settings.AUTH_USER_MODEL)),
        ], options={'verbose_name': 'Scheduled Payout', 'ordering': ['-scheduled_date']}),
        migrations.CreateModel(name='EarlyPaymentRequest', fields=[
            ('id', models.BigAutoField(primary_key=True)),
            ('created_at', models.DateTimeField(auto_now_add=True)),
            ('updated_at', models.DateTimeField(auto_now=True)),
            ('amount', models.DecimalField(max_digits=10, decimal_places=2)),
            ('early_fee', models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0'))),
            ('net_amount', models.DecimalField(max_digits=10, decimal_places=2)),
            ('payment_method', models.CharField(max_length=20)),
            ('payment_account', models.CharField(max_length=200)),
            ('status', models.CharField(max_length=15, default='pending')),
            ('reason', models.TextField(blank=True)),
            ('processed_at', models.DateTimeField(null=True, blank=True)),
            ('admin_notes', models.TextField(blank=True)),
            ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                     related_name='early_payment_requests', to=settings.AUTH_USER_MODEL)),
            ('approved_by', models.ForeignKey(null=True, blank=True,
                     on_delete=django.db.models.deletion.SET_NULL,
                     related_name='approved_early_payments', to=settings.AUTH_USER_MODEL)),
        ], options={'verbose_name': 'Early Payment Request', 'ordering': ['-created_at']}),
    ]
