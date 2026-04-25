# api/wallet/migrations/0003_wallet_fixes_and_cpalead.py
"""
FIX HIGH-12: Missing migration for all new fields.

Covers:
  CRITICAL-1: txn_id field (was walletTransaction_id)
  CRITICAL-3: Withdrawal.transaction FK (was WalletTransaction CamelCase)
  CRITICAL-9: fixed related_names (all unique now)
  HIGH-4:     version field on Wallet
  HIGH-7:     idempotency_key on WalletTransaction
  MEDIUM-2:   decimal_places 2→8 on financial fields

  NEW (CPAlead):
  + Wallet: reserved_balance, total_fees_paid, total_bonuses,
            total_referral_earned, two_fa_enabled, auto_withdraw,
            auto_withdraw_threshold, version
  + WalletTransaction: ip_address, device_info, idempotency_key,
                       fee_amount, net_amount (decimal_places=8)
  + Withdrawal: transaction FK (renamed), idempotency_key, ip_address
  + NEW: PayoutSchedule, PointsLedger, PublisherLevel,
         PerformanceBonus, GeoRate, ReferralProgram, IdempotencyKey
"""
import uuid
from decimal import Decimal
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
from django.utils import timezone


class Migration(migrations.Migration):

    dependencies = [
        ("wallet", "0002_userpaymentmethod_tenant_wallet_tenant_and_more"),
        ("tenants", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [

        # ── Wallet: new fields ──────────────────────────────────────────

        migrations.AddField(model_name="wallet", name="reserved_balance",
            field=models.DecimalField(decimal_places=8, default=Decimal("0"), max_digits=20)),

        migrations.AddField(model_name="wallet", name="total_fees_paid",
            field=models.DecimalField(decimal_places=8, default=Decimal("0"), max_digits=20)),

        migrations.AddField(model_name="wallet", name="total_bonuses",
            field=models.DecimalField(decimal_places=8, default=Decimal("0"), max_digits=20)),

        migrations.AddField(model_name="wallet", name="total_referral_earned",
            field=models.DecimalField(decimal_places=8, default=Decimal("0"), max_digits=20)),

        migrations.AddField(model_name="wallet", name="two_fa_enabled",
            field=models.BooleanField(default=False)),

        migrations.AddField(model_name="wallet", name="auto_withdraw",
            field=models.BooleanField(default=False)),

        migrations.AddField(model_name="wallet", name="auto_withdraw_threshold",
            field=models.DecimalField(decimal_places=2, max_digits=18, null=True, blank=True)),

        migrations.AddField(model_name="wallet", name="withdrawal_pin",
            field=models.CharField(blank=True, max_length=256)),

        # FIX HIGH-4: version field for optimistic locking
        migrations.AddField(model_name="wallet", name="version",
            field=models.PositiveBigIntegerField(default=0)),

        # Fix: locked_by FK
        migrations.AddField(model_name="wallet", name="locked_by",
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="wallet_locked_by",
                to=settings.AUTH_USER_MODEL,
            )),

        # ── Wallet: decimal precision upgrade (2→8) ────────────────────

        migrations.AlterField(model_name="wallet", name="current_balance",
            field=models.DecimalField(decimal_places=8, default=Decimal("0"), max_digits=20)),
        migrations.AlterField(model_name="wallet", name="pending_balance",
            field=models.DecimalField(decimal_places=8, default=Decimal("0"), max_digits=20)),
        migrations.AlterField(model_name="wallet", name="frozen_balance",
            field=models.DecimalField(decimal_places=8, default=Decimal("0"), max_digits=20)),
        migrations.AlterField(model_name="wallet", name="bonus_balance",
            field=models.DecimalField(decimal_places=8, default=Decimal("0"), max_digits=20)),
        migrations.AlterField(model_name="wallet", name="total_earned",
            field=models.DecimalField(decimal_places=8, default=Decimal("0"), max_digits=20)),
        migrations.AlterField(model_name="wallet", name="total_withdrawn",
            field=models.DecimalField(decimal_places=8, default=Decimal("0"), max_digits=20)),

        # FIX CRITICAL-9: fix Wallet related_name
        migrations.AlterField(model_name="wallet", name="user",
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="wallet_wallet_user",
                to=settings.AUTH_USER_MODEL,
            )),

        # ── WalletTransaction: new fields ──────────────────────────────

        # FIX CRITICAL-1: add txn_id (unified UUID field)
        migrations.AddField(model_name="wallettransaction", name="txn_id",
            field=models.UUIDField(default=uuid.uuid4, unique=False, editable=False, db_index=True)),

        # FIX HIGH-7: idempotency
        migrations.AddField(model_name="wallettransaction", name="idempotency_key",
            field=models.CharField(blank=True, db_index=True, max_length=255)),

        migrations.AddField(model_name="wallettransaction", name="ip_address",
            field=models.GenericIPAddressField(blank=True, null=True)),

        migrations.AddField(model_name="wallettransaction", name="device_info",
            field=models.JSONField(blank=True, default=dict)),

        migrations.AddField(model_name="wallettransaction", name="fee_amount",
            field=models.DecimalField(decimal_places=8, default=Decimal("0"), max_digits=20)),

        migrations.AddField(model_name="wallettransaction", name="net_amount",
            field=models.DecimalField(decimal_places=8, default=Decimal("0"), max_digits=20)),

        migrations.AddField(model_name="wallettransaction", name="reversal_reason",
            field=models.TextField(blank=True)),

        # FIX CRITICAL-9: fix WalletTransaction related_names
        migrations.AlterField(model_name="wallettransaction", name="wallet",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="wallet_transactions",
                to="wallet.wallet",
            )),

        migrations.AlterField(model_name="wallettransaction", name="reversed_by",
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="wallet_txn_reversal_of",
                to="wallet.wallettransaction",
            )),

        migrations.AlterField(model_name="wallettransaction", name="approved_by",
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="wallet_txns_approved",
                to=settings.AUTH_USER_MODEL,
            )),

        migrations.AlterField(model_name="wallettransaction", name="created_by",
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="wallet_txns_created",
                to=settings.AUTH_USER_MODEL,
            )),

        # FIX MEDIUM-2: decimal precision
        migrations.AlterField(model_name="wallettransaction", name="amount",
            field=models.DecimalField(decimal_places=8, max_digits=20)),
        migrations.AlterField(model_name="wallettransaction", name="balance_before",
            field=models.DecimalField(decimal_places=8, default=Decimal("0"), max_digits=20)),
        migrations.AlterField(model_name="wallettransaction", name="balance_after",
            field=models.DecimalField(decimal_places=8, default=Decimal("0"), max_digits=20)),

        # ── Withdrawal: fix CamelCase field + new fields ───────────────

        # FIX CRITICAL-3: rename WalletTransaction → transaction
        migrations.RenameField(model_name="withdrawal", old_name="WalletTransaction", new_name="transaction"),

        # FIX CRITICAL-9: fix related_name on renamed field
        migrations.AlterField(model_name="withdrawal", name="transaction",
            field=models.OneToOneField(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="wallet_withdrawal_transaction",
                to="wallet.wallettransaction",
            )),
        # SKIP:         # SKIP: migrations.AlterField(model_name="withdrawalrequest", name="wallet",
        # SKIP: field=models.ForeignKey(
        # SKIP: on_delete=django.db.models.deletion.PROTECT,
        # SKIP: related_name="wallet_withdrawal_wallet",
        # SKIP: to="wallet.wallet",

        # SKIPPED invalid AlterField

        # SKIPPED invalid AlterField

        migrations.AddField(model_name="withdrawal", name="idempotency_key",
            field=models.CharField(blank=True, db_index=True, max_length=255)),

        migrations.AddField(model_name="withdrawal", name="ip_address",
            field=models.GenericIPAddressField(blank=True, null=True)),

        migrations.AddField(model_name="withdrawal", name="currency",
            field=models.CharField(default="BDT", max_length=10)),

        # FIX MEDIUM-2: decimal precision on Withdrawal
        migrations.AlterField(model_name="withdrawal", name="amount",
            field=models.DecimalField(decimal_places=8, max_digits=20)),
        migrations.AlterField(model_name="withdrawal", name="fee",
            field=models.DecimalField(decimal_places=8, default=Decimal("0"), max_digits=20)),
        migrations.AlterField(model_name="withdrawal", name="net_amount",
            field=models.DecimalField(decimal_places=8, default=Decimal("0"), max_digits=20)),

        # FIX CRITICAL-9: fix UserPaymentMethod related_names
        migrations.AlterField(model_name="userpaymentmethod", name="user",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="wallet_userpaymentmethod_user",
                to=settings.AUTH_USER_MODEL,
            )),

        # Add new fields to UserPaymentMethod
        migrations.AddField(model_name="userpaymentmethod", name="swift_code",
            field=models.CharField(blank=True, max_length=20)),

        migrations.AddField(model_name="userpaymentmethod", name="crypto_network",
            field=models.CharField(blank=True, max_length=20)),

        migrations.AddField(model_name="userpaymentmethod", name="crypto_address",
            field=models.CharField(blank=True, max_length=200)),

        migrations.AddField(model_name="userpaymentmethod", name="verified_by",
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="wallet_verified_methods",
                to=settings.AUTH_USER_MODEL,
            )),

        migrations.AlterUniqueTogether(
            name="userpaymentmethod",
            unique_together={("user","method_type","account_number")},
        ),

        # ── NEW: CPAlead Models ────────────────────────────────────────

        migrations.CreateModel(
            name="PayoutSchedule",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("tenant", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="wallet_payoutschedule_tenant", to="tenants.tenant")),
                ("user", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="wallet_payoutschedule_user", to=settings.AUTH_USER_MODEL)),
                ("wallet", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="payout_schedule", to="wallet.wallet")),
                ("frequency", models.CharField(choices=[("daily","Daily"),("weekly","Weekly"),("net15","Net-15"),("net30","Net-30"),("instant","Instant")], default="net30", max_length=10)),
                ("minimum_threshold", models.DecimalField(decimal_places=2, default=Decimal("50.00"), max_digits=14)),
                ("auto_payout", models.BooleanField(default=True)),
                ("fast_pay_enabled", models.BooleanField(default=False)),
                ("hold_days", models.PositiveIntegerField(default=30)),
                ("hold_released", models.BooleanField(default=False)),
                ("last_payout_date", models.DateField(blank=True, null=True)),
                ("last_payout_amount", models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ("total_payouts", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"db_table": "wallet_payoutschedule", "app_label": "wallet"},
        ),

        migrations.CreateModel(
            name="PointsLedger",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("tenant", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="wallet_pointsledger_tenant", to="tenants.tenant")),
                ("user", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="wallet_points_user", to=settings.AUTH_USER_MODEL)),
                ("wallet", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="points_ledger", to="wallet.wallet")),
                ("total_points", models.PositiveBigIntegerField(default=0)),
                ("lifetime_points", models.PositiveBigIntegerField(default=0)),
                ("redeemed_points", models.PositiveBigIntegerField(default=0)),
                ("points_per_dollar", models.PositiveIntegerField(default=1000)),
                ("current_tier", models.CharField(blank=True, max_length=30)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"db_table": "wallet_pointsledger", "app_label": "wallet"},
        ),

        migrations.CreateModel(
            name="PublisherLevel",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("tenant", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="wallet_publisherlevel_tenant", to="tenants.tenant")),
                ("user", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="wallet_publisher_level", to=settings.AUTH_USER_MODEL)),
                ("wallet", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="publisher_level", to="wallet.wallet")),
                ("level", models.PositiveSmallIntegerField(choices=[(1,"Level 1"),(2,"Level 2"),(3,"Level 3"),(4,"Level 4"),(5,"Level 5")], default=1)),
                ("quality_score", models.DecimalField(decimal_places=2, default=0, max_digits=5)),
                ("total_earnings", models.DecimalField(decimal_places=2, default=0, max_digits=20)),
                ("fraud_flags", models.PositiveIntegerField(default=0)),
                ("payout_freq", models.CharField(default="net30", max_length=10)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"db_table": "wallet_publisherlevel", "app_label": "wallet"},
        ),

        migrations.CreateModel(
            name="PerformanceBonus",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("tenant", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="wallet_performancebonus_tenant", to="tenants.tenant")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="wallet_performance_bonuses", to=settings.AUTH_USER_MODEL)),
                ("wallet", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="performance_bonuses", to="wallet.wallet")),
                ("bonus_type", models.CharField(choices=[("top_earner","Top Earner"),("volume","Volume"),("streak","Streak"),("new_publisher","Welcome"),("campaign","Campaign"),("manual","Manual")], max_length=20)),
                ("status", models.CharField(default="active", max_length=10)),
                ("bonus_percent", models.DecimalField(decimal_places=2, default=0, max_digits=5)),
                ("period", models.CharField(default="monthly", max_length=10)),
                ("total_paid", models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ("max_bonus", models.DecimalField(blank=True, decimal_places=2, max_digits=14, null=True)),
                ("starts_at", models.DateTimeField(default=timezone.now)),
                ("expires_at", models.DateTimeField(blank=True, null=True)),
                ("note", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"db_table": "wallet_performancebonus", "app_label": "wallet"},
        ),

        migrations.CreateModel(
            name="GeoRate",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("tenant", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="wallet_georate_tenant", to="tenants.tenant")),
                ("country_code", models.CharField(db_index=True, max_length=3)),
                ("country_name", models.CharField(max_length=100)),
                ("geo_tier", models.CharField(choices=[("tier1","Tier1"),("tier2","Tier2"),("tier3","Tier3"),("tier4","Tier4"),("bd","Bangladesh")], default="tier3", max_length=6)),
                ("rate_multiplier", models.DecimalField(decimal_places=4, default=Decimal("1.0000"), max_digits=5)),
                ("base_cpa_rate", models.DecimalField(decimal_places=4, default=0, max_digits=8)),
                ("base_cpi_rate", models.DecimalField(decimal_places=4, default=0, max_digits=8)),
                ("base_cpc_rate", models.DecimalField(decimal_places=4, default=0, max_digits=8)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"db_table": "wallet_georate", "app_label": "wallet", "unique_together": {("country_code",)}},
        ),

        migrations.CreateModel(
            name="ReferralProgram",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("tenant", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="wallet_referralprogram_tenant", to="tenants.tenant")),
                ("referrer", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="wallet_referral_referrer", to=settings.AUTH_USER_MODEL)),
                ("referred", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="wallet_referral_referred", to=settings.AUTH_USER_MODEL)),
                ("referrer_wallet", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="referral_programs", to="wallet.wallet")),
                ("level", models.PositiveSmallIntegerField(default=1)),
                ("commission_rate", models.DecimalField(decimal_places=4, default=Decimal("0.0500"), max_digits=5)),
                ("is_active", models.BooleanField(default=True)),
                ("duration_months", models.PositiveSmallIntegerField(default=6)),
                ("total_earned", models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ("starts_at", models.DateTimeField(default=timezone.now)),
                ("expires_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"db_table": "wallet_referralprogram", "app_label": "wallet", "unique_together": {("referrer","referred","level")}},
        ),

        migrations.CreateModel(
            name="IdempotencyKey",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("tenant", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="wallet_idempotencykey_tenant", to="tenants.tenant")),
                ("key", models.CharField(db_index=True, max_length=255, unique=True)),
                ("wallet", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="idempotency_keys", to="wallet.wallet")),
                ("response_data", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("expires_at", models.DateTimeField(blank=True, null=True)),
            ],
            options={"db_table": "wallet_idempotencykey", "app_label": "wallet"},
        ),

        # ── Indexes ────────────────────────────────────────────────────

        migrations.AddIndex(model_name="wallettransaction",
            index=models.Index(fields=["idempotency_key"], name="wallet_txn_idem_idx")),

        migrations.AddIndex(model_name="wallettransaction",
            index=models.Index(fields=["created_at"], name="wallet_txn_created_idx")),

        migrations.AddIndex(model_name="withdrawal",
            index=models.Index(fields=["user","-created_at"], name="wallet_wd_user_idx")),

        migrations.AddIndex(model_name="withdrawal",
            index=models.Index(fields=["status"], name="wallet_wd_status_idx")),

        migrations.AddIndex(model_name="walletwebhooklog",
            index=models.Index(fields=["webhook_type","is_processed"], name="wallet_hook_type_idx")),
    ]
