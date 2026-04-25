# api/wallet/migrations/0006_wallet_last_activity_and_security.py
"""
Migration 0006:
  - Add last_activity_at to Wallet (for inactive wallet detection)
  - Add two_fa_enabled, withdrawal_pin to Wallet (Binance-style security)
  - Add auto_withdraw, auto_withdraw_threshold (CPAlead-style)
  - Fix decimal_places 2→8 on core financial fields
"""
import django.db.models.deletion
from decimal import Decimal
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("wallet", "0005_walletwebhooklog_and_cleanup"),
    ]

    operations = [
        # last_activity_at
        migrations.AddField(
            model_name="wallet",
            name="last_activity_at",
            field=models.DateTimeField(blank=True, null=True,
                help_text="Last transaction datetime — used for inactive wallet detection"),
        ),
        # two_fa_enabled
        migrations.AddField(
            model_name="wallet",
            name="two_fa_enabled",
            field=models.BooleanField(default=False,
                help_text="Require 2FA before withdrawal (Binance-style)"),
        ),
        # withdrawal_pin
        migrations.AddField(
            model_name="wallet",
            name="withdrawal_pin",
            field=models.CharField(blank=True, max_length=256,
                help_text="Hashed 6-digit PIN required before withdrawal"),
        ),
        # auto_withdraw
        migrations.AddField(
            model_name="wallet",
            name="auto_withdraw",
            field=models.BooleanField(default=False,
                help_text="Auto-withdraw when balance exceeds threshold (CPAlead-style)"),
        ),
        # auto_withdraw_threshold
        migrations.AddField(
            model_name="wallet",
            name="auto_withdraw_threshold",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=18, null=True,
                help_text="Auto-withdraw when balance exceeds this amount"),
        ),
        # daily_limit
        migrations.AddField(
            model_name="wallet",
            name="daily_limit",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=18, null=True,
                help_text="User-specific daily withdrawal limit (set by KYC level)"),
        ),
        # Fix decimal_places 2→8 on balance fields
        migrations.AlterField(
            model_name="wallet",
            name="current_balance",
            field=models.DecimalField(decimal_places=8, default=Decimal("0"), max_digits=20,
                help_text="Spendable / withdrawable balance"),
        ),
        migrations.AlterField(
            model_name="wallet",
            name="pending_balance",
            field=models.DecimalField(decimal_places=8, default=Decimal("0"), max_digits=20,
                help_text="Locked in pending withdrawals"),
        ),
        migrations.AlterField(
            model_name="wallet",
            name="frozen_balance",
            field=models.DecimalField(decimal_places=8, default=Decimal("0"), max_digits=20,
                help_text="Admin-frozen (fraud / dispute)"),
        ),
        migrations.AlterField(
            model_name="wallet",
            name="bonus_balance",
            field=models.DecimalField(decimal_places=8, default=Decimal("0"), max_digits=20,
                help_text="Promotional balance, may expire"),
        ),
        migrations.AlterField(
            model_name="wallet",
            name="total_earned",
            field=models.DecimalField(decimal_places=8, default=Decimal("0"), max_digits=20),
        ),
        migrations.AlterField(
            model_name="wallet",
            name="total_withdrawn",
            field=models.DecimalField(decimal_places=8, default=Decimal("0"), max_digits=20),
        ),
        # Add index on last_activity_at
        migrations.AddIndex(
            model_name="wallet",
            index=models.Index(fields=["last_activity_at"], name="wallet_last_activity_idx"),
        ),
    ]
