# api/djoyalty/migrations/0003_points_tiers.py
"""
Migration: LoyaltyPoints, PointsLedger, PointsExpiry, PointsTransfer,
PointsConversion, PointsReservation, PointsRate, PointsAdjustment,
LoyaltyTier, UserTier, TierBenefit, TierHistory, TierConfig
"""
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('djoyalty', '0002_customer_tenant_event_tenant_txn_tenant_and_more'),
        ('tenants', '0001_initial'),
    ]

    operations = [
        # LoyaltyPoints
        migrations.CreateModel(
            name='LoyaltyPoints',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('balance', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('lifetime_earned', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('lifetime_redeemed', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('lifetime_expired', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('customer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='loyalty_points', to='djoyalty.customer')),
                ('tenant', models.ForeignKey(blank=True, db_index=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='djoyalty_loyaltypoints_tenant', to='tenants.tenant')),
            ],
            options={'app_label': 'djoyalty'},
        ),
        migrations.AlterUniqueTogether(name='loyaltypoints', unique_together={('tenant', 'customer')}),

        # PointsLedger
        migrations.CreateModel(
            name='PointsLedger',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('txn_type', models.CharField(choices=[('credit', 'Credit'), ('debit', 'Debit')], db_index=True, max_length=16)),
                ('source', models.CharField(db_index=True, max_length=32)),
                ('points', models.DecimalField(decimal_places=2, max_digits=12)),
                ('remaining_points', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('balance_after', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('description', models.TextField(blank=True, null=True)),
                ('reference_id', models.CharField(blank=True, db_index=True, max_length=128, null=True)),
                ('expires_at', models.DateTimeField(blank=True, db_index=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('metadata', models.JSONField(blank=True, default=dict, null=True)),
                ('customer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='points_ledger', to='djoyalty.customer')),
                ('tenant', models.ForeignKey(blank=True, db_index=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='djoyalty_pointsledger_tenant', to='tenants.tenant')),
            ],
            options={'app_label': 'djoyalty', 'ordering': ['-created_at']},
        ),

        # PointsExpiry
        migrations.CreateModel(
            name='PointsExpiry',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('points', models.DecimalField(decimal_places=2, max_digits=12)),
                ('expires_at', models.DateTimeField(db_index=True)),
                ('is_processed', models.BooleanField(db_index=True, default=False)),
                ('processed_at', models.DateTimeField(blank=True, null=True)),
                ('warning_sent', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('customer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='points_expiries', to='djoyalty.customer')),
                ('ledger_entry', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='expiry_records', to='djoyalty.pointsledger')),
                ('tenant', models.ForeignKey(blank=True, db_index=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='djoyalty_pointsexpiry_tenant', to='tenants.tenant')),
            ],
            options={'app_label': 'djoyalty'},
        ),

        # PointsRate
        migrations.CreateModel(
            name='PointsRate',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('earn_rate', models.DecimalField(decimal_places=4, default=1, max_digits=8)),
                ('point_value', models.DecimalField(decimal_places=6, default=0.01, max_digits=8)),
                ('min_spend_to_earn', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('rounding', models.CharField(choices=[('floor', 'Floor'), ('ceil', 'Ceil'), ('round', 'Round')], default='floor', max_length=16)),
                ('is_active', models.BooleanField(default=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('tenant', models.ForeignKey(blank=True, db_index=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='djoyalty_pointsrate_tenant', to='tenants.tenant')),
            ],
            options={'app_label': 'djoyalty'},
        ),

        # PointsAdjustment
        migrations.CreateModel(
            name='PointsAdjustment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('points', models.DecimalField(decimal_places=2, max_digits=12)),
                ('reason', models.TextField()),
                ('adjusted_by', models.CharField(blank=True, max_length=128, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('customer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='points_adjustments', to='djoyalty.customer')),
                ('tenant', models.ForeignKey(blank=True, db_index=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='djoyalty_pointsadjustment_tenant', to='tenants.tenant')),
            ],
            options={'app_label': 'djoyalty'},
        ),

        # PointsTransfer
        migrations.CreateModel(
            name='PointsTransfer',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('points', models.DecimalField(decimal_places=2, max_digits=12)),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('completed', 'Completed'), ('failed', 'Failed'), ('cancelled', 'Cancelled')], db_index=True, default='pending', max_length=16)),
                ('note', models.TextField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('from_customer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='points_transfers_sent', to='djoyalty.customer')),
                ('to_customer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='points_transfers_received', to='djoyalty.customer')),
                ('tenant', models.ForeignKey(blank=True, db_index=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='djoyalty_pointstransfer_tenant', to='tenants.tenant')),
            ],
            options={'app_label': 'djoyalty'},
        ),

        # PointsConversion
        migrations.CreateModel(
            name='PointsConversion',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('points_used', models.DecimalField(decimal_places=2, max_digits=12)),
                ('currency_value', models.DecimalField(decimal_places=2, max_digits=10)),
                ('conversion_rate', models.DecimalField(decimal_places=4, max_digits=8)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('reference', models.CharField(blank=True, max_length=128, null=True)),
                ('customer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='points_conversions', to='djoyalty.customer')),
                ('tenant', models.ForeignKey(blank=True, db_index=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='djoyalty_pointsconversion_tenant', to='tenants.tenant')),
            ],
            options={'app_label': 'djoyalty'},
        ),

        # PointsReservation
        migrations.CreateModel(
            name='PointsReservation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('points', models.DecimalField(decimal_places=2, max_digits=12)),
                ('reference', models.CharField(db_index=True, max_length=128)),
                ('is_released', models.BooleanField(db_index=True, default=False)),
                ('is_confirmed', models.BooleanField(default=False)),
                ('expires_at', models.DateTimeField(db_index=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('released_at', models.DateTimeField(blank=True, null=True)),
                ('customer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='points_reservations', to='djoyalty.customer')),
                ('tenant', models.ForeignKey(blank=True, db_index=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='djoyalty_pointsreservation_tenant', to='tenants.tenant')),
            ],
            options={'app_label': 'djoyalty'},
        ),

        # LoyaltyTier
        migrations.CreateModel(
            name='LoyaltyTier',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(choices=[('bronze', '🥉 Bronze'), ('silver', '🥈 Silver'), ('gold', '🥇 Gold'), ('platinum', '💎 Platinum'), ('diamond', '💠 Diamond')], db_index=True, max_length=32)),
                ('label', models.CharField(default='', max_length=64)),
                ('min_points', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('max_points', models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True)),
                ('earn_multiplier', models.DecimalField(decimal_places=2, default=1, max_digits=5)),
                ('color', models.CharField(default='#888888', max_length=7)),
                ('icon', models.CharField(default='⭐', max_length=8)),
                ('description', models.TextField(blank=True, null=True)),
                ('is_active', models.BooleanField(default=True)),
                ('rank', models.PositiveSmallIntegerField(default=1)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('tenant', models.ForeignKey(blank=True, db_index=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='djoyalty_loyaltytier_tenant', to='tenants.tenant')),
            ],
            options={'app_label': 'djoyalty', 'ordering': ['rank']},
        ),
        migrations.AlterUniqueTogether(name='loyaltytier', unique_together={('tenant', 'name')}),

        # TierBenefit
        migrations.CreateModel(
            name='TierBenefit',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=128)),
                ('description', models.TextField(blank=True, null=True)),
                ('benefit_type', models.CharField(default='perk', max_length=64)),
                ('value', models.CharField(blank=True, max_length=64, null=True)),
                ('is_active', models.BooleanField(default=True)),
                ('tier', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='benefits', to='djoyalty.loyaltytier')),
            ],
            options={'app_label': 'djoyalty'},
        ),

        # UserTier
        migrations.CreateModel(
            name='UserTier',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('is_current', models.BooleanField(db_index=True, default=True)),
                ('assigned_at', models.DateTimeField(auto_now_add=True)),
                ('valid_until', models.DateTimeField(blank=True, null=True)),
                ('points_at_assignment', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('customer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='user_tiers', to='djoyalty.customer')),
                ('tier', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='user_tiers', to='djoyalty.loyaltytier')),
                ('tenant', models.ForeignKey(blank=True, db_index=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='djoyalty_usertier_tenant', to='tenants.tenant')),
            ],
            options={'app_label': 'djoyalty'},
        ),

        # TierHistory
        migrations.CreateModel(
            name='TierHistory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('change_type', models.CharField(choices=[('upgrade', 'Upgrade'), ('downgrade', 'Downgrade'), ('initial', 'Initial')], max_length=16)),
                ('reason', models.TextField(blank=True, null=True)),
                ('points_at_change', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('customer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='tier_history', to='djoyalty.customer')),
                ('from_tier', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='djoyalty.loyaltytier')),
                ('to_tier', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='+', to='djoyalty.loyaltytier')),
            ],
            options={'app_label': 'djoyalty', 'ordering': ['-created_at']},
        ),

        # TierConfig
        migrations.CreateModel(
            name='TierConfig',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('evaluation_period_months', models.PositiveSmallIntegerField(default=12)),
                ('downgrade_protection_months', models.PositiveSmallIntegerField(default=3)),
                ('auto_downgrade', models.BooleanField(default=True)),
                ('notify_on_upgrade', models.BooleanField(default=True)),
                ('notify_on_downgrade', models.BooleanField(default=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('tenant', models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='djoyalty_tier_config', to='tenants.tenant')),
            ],
            options={'app_label': 'djoyalty'},
        ),
    ]
