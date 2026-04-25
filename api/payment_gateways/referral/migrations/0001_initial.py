# referral/migrations/0001_initial.py
import django.db.models.deletion
from decimal import Decimal
from django.conf import settings
from django.db import migrations, models

class Migration(migrations.Migration):
    initial = True
    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(name='ReferralProgram', fields=[
            ('id', models.BigAutoField(primary_key=True)),
            ('created_at', models.DateTimeField(auto_now_add=True)),
            ('updated_at', models.DateTimeField(auto_now=True)),
            ('is_active', models.BooleanField(default=True)),
            ('commission_percent', models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('10'))),
            ('commission_months', models.IntegerField(default=6)),
            ('minimum_payout', models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('10'))),
            ('cookie_duration_days', models.IntegerField(default=30)),
            ('description', models.TextField(blank=True)),
        ], options={'verbose_name': 'Referral Program'}),
        migrations.CreateModel(name='ReferralLink', fields=[
            ('id', models.BigAutoField(primary_key=True)),
            ('created_at', models.DateTimeField(auto_now_add=True)),
            ('updated_at', models.DateTimeField(auto_now=True)),
            ('code', models.CharField(max_length=20, unique=True, default='')),
            ('total_clicks', models.IntegerField(default=0)),
            ('total_signups', models.IntegerField(default=0)),
            ('total_earned', models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))),
            ('is_active', models.BooleanField(default=True)),
            ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE,
                     related_name='referral_link', to=settings.AUTH_USER_MODEL)),
        ], options={'verbose_name': 'Referral Link'}),
        migrations.CreateModel(name='Referral', fields=[
            ('id', models.BigAutoField(primary_key=True)),
            ('created_at', models.DateTimeField(auto_now_add=True)),
            ('updated_at', models.DateTimeField(auto_now=True)),
            ('is_active', models.BooleanField(default=True)),
            ('commission_start', models.DateField(auto_now_add=True)),
            ('commission_end', models.DateField(null=True, blank=True)),
            ('total_commission_paid', models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))),
            ('referrer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                         related_name='referrals_made', to=settings.AUTH_USER_MODEL)),
            ('referred_user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE,
                              related_name='referred_by', to=settings.AUTH_USER_MODEL)),
            ('referral_link', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL,
                              to='payment_gateway_referral.referrallink')),
        ], options={'verbose_name': 'Referral'}),
        migrations.CreateModel(name='ReferralCommission', fields=[
            ('id', models.BigAutoField(primary_key=True)),
            ('created_at', models.DateTimeField(auto_now_add=True)),
            ('updated_at', models.DateTimeField(auto_now=True)),
            ('original_amount', models.DecimalField(max_digits=10, decimal_places=2)),
            ('commission_amount', models.DecimalField(max_digits=10, decimal_places=2)),
            ('commission_percent', models.DecimalField(max_digits=5, decimal_places=2)),
            ('status', models.CharField(max_length=15, default='pending')),
            ('paid_at', models.DateTimeField(null=True, blank=True)),
            ('transaction_ref', models.CharField(max_length=100, blank=True)),
            ('referral', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                         related_name='commissions', to='payment_gateway_referral.referral')),
            ('referrer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                         related_name='referral_commissions', to=settings.AUTH_USER_MODEL)),
            ('referred_user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                              related_name='generated_commissions', to=settings.AUTH_USER_MODEL)),
        ], options={'verbose_name': 'Referral Commission', 'ordering': ['-created_at']}),
    ]
