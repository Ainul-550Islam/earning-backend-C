# api/djoyalty/migrations/0004_earn_redemption.py
"""
Migration: EarnRule, EarnRuleCondition, EarnRuleTierMultiplier,
EarnTransaction, BonusEvent, EarnRuleLog,
RedemptionRule, RedemptionRequest, RedemptionHistory,
Voucher, VoucherRedemption, GiftCard
"""
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('djoyalty', '0003_points_tiers'),
        ('tenants', '0001_initial'),
    ]

    operations = [
        # EarnRule
        migrations.CreateModel(
            name='EarnRule',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=128)),
                ('description', models.TextField(blank=True, null=True)),
                ('rule_type', models.CharField(choices=[('fixed', 'Fixed Points'), ('percentage', 'Percentage of Spend'), ('multiplier', 'Multiplier'), ('bonus', 'Bonus Points'), ('category', 'Category-Based')], db_index=True, max_length=32)),
                ('trigger', models.CharField(choices=[('purchase', 'Purchase'), ('signup', 'Sign Up'), ('birthday', 'Birthday'), ('referral', 'Referral'), ('review', 'Write a Review'), ('checkin', 'Check In'), ('custom', 'Custom Event')], db_index=True, max_length=32)),
                ('points_value', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('multiplier', models.DecimalField(decimal_places=2, default=1, max_digits=5)),
                ('min_spend', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('max_earn_per_txn', models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True)),
                ('max_earn_per_day', models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True)),
                ('applicable_tiers', models.JSONField(blank=True, null=True)),
                ('is_active', models.BooleanField(db_index=True, default=True)),
                ('valid_from', models.DateTimeField(blank=True, null=True)),
                ('valid_until', models.DateTimeField(blank=True, null=True)),
                ('priority', models.PositiveSmallIntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('tenant', models.ForeignKey(blank=True, db_index=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='djoyalty_earnrule_tenant', to='tenants.tenant')),
            ],
            options={'app_label': 'djoyalty', 'ordering': ['-priority', 'name']},
        ),

        # EarnRuleCondition
        migrations.CreateModel(
            name='EarnRuleCondition',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('field', models.CharField(max_length=64)),
                ('operator', models.CharField(choices=[('eq', '='), ('ne', '!='), ('gt', '>'), ('gte', '>='), ('lt', '<'), ('lte', '<='), ('in', 'IN'), ('not_in', 'NOT IN')], max_length=16)),
                ('value', models.CharField(max_length=256)),
                ('earn_rule', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='conditions', to='djoyalty.earnrule')),
            ],
            options={'app_label': 'djoyalty'},
        ),

        # EarnRuleTierMultiplier
        migrations.CreateModel(
            name='EarnRuleTierMultiplier',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('multiplier', models.DecimalField(decimal_places=2, default=1, max_digits=5)),
                ('earn_rule', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='tier_multipliers', to='djoyalty.earnrule')),
                ('tier', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='earn_multipliers', to='djoyalty.loyaltytier')),
            ],
            options={'app_label': 'djoyalty'},
        ),
        migrations.AlterUniqueTogether(name='earnruletiermultiplier', unique_together={('earn_rule', 'tier')}),

        # EarnTransaction
        migrations.CreateModel(
            name='EarnTransaction',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('points_earned', models.DecimalField(decimal_places=2, max_digits=12)),
                ('multiplier_applied', models.DecimalField(decimal_places=2, default=1, max_digits=5)),
                ('spend_amount', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('customer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='earn_transactions', to='djoyalty.customer')),
                ('earn_rule', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='earn_transactions', to='djoyalty.earnrule')),
                ('txn', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='earn_transactions', to='djoyalty.txn')),
                ('tenant', models.ForeignKey(blank=True, db_index=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='djoyalty_earntransaction_tenant', to='tenants.tenant')),
            ],
            options={'app_label': 'djoyalty', 'ordering': ['-created_at']},
        ),

        # BonusEvent
        migrations.CreateModel(
            name='BonusEvent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('points', models.DecimalField(decimal_places=2, max_digits=12)),
                ('reason', models.CharField(max_length=256)),
                ('triggered_by', models.CharField(blank=True, max_length=128, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('customer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='bonus_events', to='djoyalty.customer')),
                ('tenant', models.ForeignKey(blank=True, db_index=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='djoyalty_bonusevent_tenant', to='tenants.tenant')),
            ],
            options={'app_label': 'djoyalty', 'ordering': ['-created_at']},
        ),

        # EarnRuleLog
        migrations.CreateModel(
            name='EarnRuleLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('triggered', models.BooleanField(default=False)),
                ('points_result', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('reason', models.TextField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('customer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='earn_rule_logs', to='djoyalty.customer')),
                ('earn_rule', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='logs', to='djoyalty.earnrule')),
            ],
            options={'app_label': 'djoyalty', 'ordering': ['-created_at']},
        ),

        # RedemptionRule
        migrations.CreateModel(
            name='RedemptionRule',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=128)),
                ('description', models.TextField(blank=True, null=True)),
                ('redemption_type', models.CharField(choices=[('voucher', '🎫 Voucher'), ('cashback', '💵 Cashback'), ('product', '📦 Product'), ('giftcard', '🎁 Gift Card'), ('donation', '❤️ Donation')], max_length=32)),
                ('points_required', models.DecimalField(decimal_places=2, max_digits=12)),
                ('reward_value', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('is_active', models.BooleanField(db_index=True, default=True)),
                ('max_redemptions', models.PositiveIntegerField(blank=True, null=True)),
                ('max_per_customer', models.PositiveIntegerField(blank=True, null=True)),
                ('valid_from', models.DateTimeField(blank=True, null=True)),
                ('valid_until', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('min_tier', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='djoyalty.loyaltytier')),
                ('tenant', models.ForeignKey(blank=True, db_index=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='djoyalty_redemptionrule_tenant', to='tenants.tenant')),
            ],
            options={'app_label': 'djoyalty'},
        ),

        # RedemptionRequest
        migrations.CreateModel(
            name='RedemptionRequest',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('redemption_type', models.CharField(max_length=32)),
                ('points_used', models.DecimalField(decimal_places=2, max_digits=12)),
                ('reward_value', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('status', models.CharField(choices=[('pending', '⏳ Pending'), ('approved', '✅ Approved'), ('rejected', '❌ Rejected'), ('cancelled', '🚫 Cancelled'), ('completed', '🎉 Completed')], db_index=True, default='pending', max_length=16)),
                ('note', models.TextField(blank=True, null=True)),
                ('reviewed_by', models.CharField(blank=True, max_length=128, null=True)),
                ('reviewed_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('customer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='redemption_requests', to='djoyalty.customer')),
                ('rule', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='requests', to='djoyalty.redemptionrule')),
                ('tenant', models.ForeignKey(blank=True, db_index=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='djoyalty_redemptionrequest_tenant', to='tenants.tenant')),
            ],
            options={'app_label': 'djoyalty', 'ordering': ['-created_at']},
        ),

        # RedemptionHistory
        migrations.CreateModel(
            name='RedemptionHistory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('from_status', models.CharField(max_length=16)),
                ('to_status', models.CharField(max_length=16)),
                ('changed_by', models.CharField(blank=True, max_length=128, null=True)),
                ('note', models.TextField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('request', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='history', to='djoyalty.redemptionrequest')),
            ],
            options={'app_label': 'djoyalty', 'ordering': ['-created_at']},
        ),

        # Voucher
        migrations.CreateModel(
            name='Voucher',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(db_index=True, max_length=32, unique=True)),
                ('voucher_type', models.CharField(choices=[('percent', '% Percentage Discount'), ('fixed', '$ Fixed Discount'), ('free_shipping', '🚚 Free Shipping'), ('bogo', '🛒 Buy One Get One')], max_length=32)),
                ('discount_value', models.DecimalField(decimal_places=2, max_digits=10)),
                ('status', models.CharField(choices=[('active', '✅ Active'), ('used', '✔️ Used'), ('expired', '⌛ Expired'), ('cancelled', '🚫 Cancelled')], db_index=True, default='active', max_length=16)),
                ('min_order_value', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('max_discount', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
                ('expires_at', models.DateTimeField(blank=True, db_index=True, null=True)),
                ('used_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('customer', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='vouchers', to='djoyalty.customer')),
                ('redemption_request', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='vouchers', to='djoyalty.redemptionrequest')),
                ('tenant', models.ForeignKey(blank=True, db_index=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='djoyalty_voucher_tenant', to='tenants.tenant')),
            ],
            options={'app_label': 'djoyalty'},
        ),

        # VoucherRedemption
        migrations.CreateModel(
            name='VoucherRedemption',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('order_reference', models.CharField(blank=True, max_length=128, null=True)),
                ('discount_applied', models.DecimalField(decimal_places=2, max_digits=10)),
                ('used_at', models.DateTimeField(auto_now_add=True)),
                ('customer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='voucher_redemptions', to='djoyalty.customer')),
                ('voucher', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='redemptions', to='djoyalty.voucher')),
            ],
            options={'app_label': 'djoyalty'},
        ),

        # GiftCard
        migrations.CreateModel(
            name='GiftCard',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(db_index=True, max_length=32, unique=True)),
                ('initial_value', models.DecimalField(decimal_places=2, max_digits=10)),
                ('remaining_value', models.DecimalField(decimal_places=2, max_digits=10)),
                ('status', models.CharField(choices=[('active', '✅ Active'), ('used', '✔️ Used'), ('expired', '⌛ Expired'), ('cancelled', '🚫 Cancelled')], db_index=True, default='active', max_length=16)),
                ('expires_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('used_at', models.DateTimeField(blank=True, null=True)),
                ('issued_to', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='gift_cards', to='djoyalty.customer')),
                ('tenant', models.ForeignKey(blank=True, db_index=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='djoyalty_giftcard_tenant', to='tenants.tenant')),
            ],
            options={'app_label': 'djoyalty'},
        ),
    ]
