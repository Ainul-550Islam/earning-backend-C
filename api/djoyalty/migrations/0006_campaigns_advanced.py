# api/djoyalty/migrations/0006_campaigns_advanced.py
"""
Migration: LoyaltyCampaign, CampaignSegment, CampaignParticipant,
ReferralPointsRule, PartnerMerchant,
LoyaltyNotification, PointsAlert, LoyaltySubscription,
LoyaltyFraudRule, PointsAbuseLog, LoyaltyInsight, CoalitionEarn
"""
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('djoyalty', '0005_engagement'),
        ('tenants', '0001_initial'),
    ]

    operations = [
        # LoyaltyCampaign
        migrations.CreateModel(
            name='LoyaltyCampaign',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=128)),
                ('description', models.TextField(blank=True, null=True)),
                ('campaign_type', models.CharField(choices=[('points_multiplier', '✖️ Points Multiplier'), ('bonus_points', '➕ Bonus Points'), ('double_points', '✌️ Double Points'), ('flash_earn', '⚡ Flash Earn'), ('referral_boost', '👥 Referral Boost')], db_index=True, max_length=32)),
                ('status', models.CharField(choices=[('draft', '📝 Draft'), ('active', '🟢 Active'), ('paused', '⏸️ Paused'), ('ended', '🏁 Ended'), ('cancelled', '🚫 Cancelled')], db_index=True, default='draft', max_length=16)),
                ('multiplier', models.DecimalField(decimal_places=2, default=1, max_digits=5)),
                ('bonus_points', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('min_spend', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('max_participants', models.PositiveIntegerField(blank=True, null=True)),
                ('applicable_tiers', models.JSONField(blank=True, null=True)),
                ('start_date', models.DateTimeField()),
                ('end_date', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('tenant', models.ForeignKey(blank=True, db_index=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='djoyalty_loyaltycampaign_tenant', to='tenants.tenant')),
            ],
            options={'app_label': 'djoyalty', 'ordering': ['-start_date']},
        ),

        # CampaignSegment
        migrations.CreateModel(
            name='CampaignSegment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=128)),
                ('filter_criteria', models.JSONField(default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('campaign', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='segments', to='djoyalty.loyaltycampaign')),
            ],
            options={'app_label': 'djoyalty'},
        ),

        # CampaignParticipant
        migrations.CreateModel(
            name='CampaignParticipant',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('joined_at', models.DateTimeField(auto_now_add=True)),
                ('points_earned', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('is_active', models.BooleanField(default=True)),
                ('campaign', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='campaign_participants', to='djoyalty.loyaltycampaign')),
                ('customer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='campaign_participations', to='djoyalty.customer')),
            ],
            options={'app_label': 'djoyalty'},
        ),
        migrations.AlterUniqueTogether(name='campaignparticipant', unique_together={('campaign', 'customer')}),

        # ReferralPointsRule
        migrations.CreateModel(
            name='ReferralPointsRule',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('referrer_points', models.DecimalField(decimal_places=2, default=150, max_digits=12)),
                ('referee_points', models.DecimalField(decimal_places=2, default=50, max_digits=12)),
                ('min_referee_spend', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('max_referrals_per_customer', models.PositiveIntegerField(blank=True, null=True)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('tenant', models.ForeignKey(blank=True, db_index=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='djoyalty_referralpointsrule_tenant', to='tenants.tenant')),
            ],
            options={'app_label': 'djoyalty'},
        ),

        # PartnerMerchant
        migrations.CreateModel(
            name='PartnerMerchant',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=128)),
                ('api_key', models.CharField(db_index=True, max_length=64, unique=True)),
                ('webhook_url', models.URLField(blank=True, null=True)),
                ('earn_rate', models.DecimalField(decimal_places=4, default=1, max_digits=8)),
                ('burn_rate', models.DecimalField(decimal_places=4, default=1, max_digits=8)),
                ('is_active', models.BooleanField(db_index=True, default=True)),
                ('sync_interval_minutes', models.PositiveIntegerField(default=60)),
                ('last_sync_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('tenant', models.ForeignKey(blank=True, db_index=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='djoyalty_partnermerchant_tenant', to='tenants.tenant')),
            ],
            options={'app_label': 'djoyalty'},
        ),

        # LoyaltyNotification
        migrations.CreateModel(
            name='LoyaltyNotification',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('notification_type', models.CharField(db_index=True, max_length=32)),
                ('channel', models.CharField(default='email', max_length=16)),
                ('title', models.CharField(max_length=256)),
                ('body', models.TextField()),
                ('is_read', models.BooleanField(db_index=True, default=False)),
                ('is_sent', models.BooleanField(db_index=True, default=False)),
                ('sent_at', models.DateTimeField(blank=True, null=True)),
                ('read_at', models.DateTimeField(blank=True, null=True)),
                ('metadata', models.JSONField(blank=True, default=dict, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('customer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='loyalty_notifications', to='djoyalty.customer')),
                ('tenant', models.ForeignKey(blank=True, db_index=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='djoyalty_loyaltynotification_tenant', to='tenants.tenant')),
            ],
            options={'app_label': 'djoyalty', 'ordering': ['-created_at']},
        ),

        # PointsAlert
        migrations.CreateModel(
            name='PointsAlert',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('points_expiring', models.DecimalField(decimal_places=2, max_digits=12)),
                ('expires_at', models.DateTimeField()),
                ('alert_sent_at', models.DateTimeField(auto_now_add=True)),
                ('channel', models.CharField(default='email', max_length=16)),
                ('customer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='points_alerts', to='djoyalty.customer')),
            ],
            options={'app_label': 'djoyalty', 'ordering': ['-alert_sent_at']},
        ),

        # LoyaltySubscription
        migrations.CreateModel(
            name='LoyaltySubscription',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('plan_name', models.CharField(max_length=128)),
                ('monthly_fee', models.DecimalField(decimal_places=2, default=0, max_digits=8)),
                ('bonus_points_monthly', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('earn_multiplier_bonus', models.DecimalField(decimal_places=2, default=0, max_digits=5)),
                ('is_active', models.BooleanField(db_index=True, default=True)),
                ('started_at', models.DateTimeField(auto_now_add=True)),
                ('next_renewal_at', models.DateTimeField(blank=True, null=True)),
                ('cancelled_at', models.DateTimeField(blank=True, null=True)),
                ('customer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='loyalty_subscriptions', to='djoyalty.customer')),
                ('tenant', models.ForeignKey(blank=True, db_index=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='djoyalty_loyaltysubscription_tenant', to='tenants.tenant')),
            ],
            options={'app_label': 'djoyalty'},
        ),

        # LoyaltyFraudRule
        migrations.CreateModel(
            name='LoyaltyFraudRule',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=128)),
                ('description', models.TextField(blank=True, null=True)),
                ('rule_type', models.CharField(max_length=64)),
                ('threshold_value', models.DecimalField(decimal_places=2, max_digits=12)),
                ('window_minutes', models.PositiveIntegerField(default=60)),
                ('risk_level', models.CharField(choices=[('low', '🟢 Low'), ('medium', '🟡 Medium'), ('high', '🟠 High'), ('critical', '🔴 Critical')], default='medium', max_length=16)),
                ('action', models.CharField(choices=[('flag', '⚑ Flag'), ('suspend', '⏸️ Suspend'), ('block', '🚫 Block'), ('notify', '🔔 Notify Admin')], default='flag', max_length=16)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('tenant', models.ForeignKey(blank=True, db_index=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='djoyalty_loyaltyfraudrule_tenant', to='tenants.tenant')),
            ],
            options={'app_label': 'djoyalty'},
        ),

        # PointsAbuseLog
        migrations.CreateModel(
            name='PointsAbuseLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('risk_level', models.CharField(db_index=True, max_length=16)),
                ('action_taken', models.CharField(max_length=16)),
                ('description', models.TextField()),
                ('is_resolved', models.BooleanField(db_index=True, default=False)),
                ('resolved_by', models.CharField(blank=True, max_length=128, null=True)),
                ('resolved_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('metadata', models.JSONField(blank=True, default=dict, null=True)),
                ('customer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='abuse_logs', to='djoyalty.customer')),
                ('fraud_rule', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='abuse_logs', to='djoyalty.loyaltyfraudrule')),
                ('tenant', models.ForeignKey(blank=True, db_index=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='djoyalty_pointsabuselog_tenant', to='tenants.tenant')),
            ],
            options={'app_label': 'djoyalty', 'ordering': ['-created_at']},
        ),

        # LoyaltyInsight
        migrations.CreateModel(
            name='LoyaltyInsight',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('report_date', models.DateField(db_index=True)),
                ('period', models.CharField(choices=[('daily', 'Daily'), ('weekly', 'Weekly'), ('monthly', 'Monthly')], default='daily', max_length=8)),
                ('total_customers', models.PositiveIntegerField(default=0)),
                ('active_customers', models.PositiveIntegerField(default=0)),
                ('new_customers', models.PositiveIntegerField(default=0)),
                ('total_points_issued', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('total_points_redeemed', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('total_points_expired', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('total_transactions', models.PositiveIntegerField(default=0)),
                ('total_revenue', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('tier_distribution', models.JSONField(default=dict)),
                ('top_earners', models.JSONField(default=list)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('tenant', models.ForeignKey(blank=True, db_index=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='djoyalty_loyaltyinsight_tenant', to='tenants.tenant')),
            ],
            options={'app_label': 'djoyalty', 'ordering': ['-report_date']},
        ),
        migrations.AlterUniqueTogether(name='loyaltyinsight', unique_together={('tenant', 'report_date', 'period')}),

        # CoalitionEarn
        migrations.CreateModel(
            name='CoalitionEarn',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('spend_amount', models.DecimalField(decimal_places=2, max_digits=10)),
                ('points_earned', models.DecimalField(decimal_places=2, max_digits=12)),
                ('reference', models.CharField(blank=True, db_index=True, max_length=128, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('customer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='coalition_earns', to='djoyalty.customer')),
                ('partner', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='coalition_earns', to='djoyalty.partnermerchant')),
                ('tenant', models.ForeignKey(blank=True, db_index=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='djoyalty_coalitionearn_tenant', to='tenants.tenant')),
            ],
            options={'app_label': 'djoyalty', 'ordering': ['-created_at']},
        ),
    ]
