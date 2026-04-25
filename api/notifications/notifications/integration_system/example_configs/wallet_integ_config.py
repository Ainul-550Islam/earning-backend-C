# api/wallet/integ_config.py
"""
Wallet Module — Integration Configuration
"এক কাজের জন্য একটাই মালিক"

Wallet module owns:
  - Wallet, WalletTransaction, UserPaymentMethod, Withdrawal, WithdrawalRequest

Wallet PUBLISHES these events → Notification module SUBSCRIBES and sends notifications.
No other module touches Wallet's tables. No direct Notification.objects.create() here.

REMOVES the anti-pattern from wallet/signals.py:
  ❌ OLD: from api.notifications.models import Notification
          Notification.objects.create(...)   ← VIOLATION
  ✅ NEW: event_bus.publish(Events.WITHDRAWAL_COMPLETED, {...})  ← CLEAN
"""

from api.notifications.integration_system.module_protocol import (
    ModuleConfig, SignalMap, EventMap, WebhookMap, HealthCheck
)


class WalletIntegConfig(ModuleConfig):
    module_name = 'wallet'
    version = '1.0.0'
    description = 'Wallet, Transactions & Withdrawals — Earning Site'

    # ------------------------------------------------------------------
    # STEP 1: Model events → EventBus
    # Wallet module publishes events. Notification module subscribes.
    # ------------------------------------------------------------------
    signal_maps = [
        # Withdrawal status changes
        SignalMap(
            model_path='wallet.Withdrawal',
            field='status',
            value='completed',
            event_type='withdrawal.completed',
            user_field='user_id',
            data_fields=['amount', 'currency', 'payment_method', 'transaction_id'],
        ),
        SignalMap(
            model_path='wallet.Withdrawal',
            field='status',
            value='approved',
            event_type='withdrawal.approved',
            user_field='user_id',
            data_fields=['amount', 'currency', 'payment_method'],
        ),
        SignalMap(
            model_path='wallet.Withdrawal',
            field='status',
            value='rejected',
            event_type='withdrawal.rejected',
            user_field='user_id',
            data_fields=['amount', 'currency', 'rejection_reason'],
        ),
        SignalMap(
            model_path='wallet.Withdrawal',
            field='status',
            value='failed',
            event_type='withdrawal.failed',
            user_field='user_id',
            data_fields=['amount', 'currency', 'error_message'],
            on_created=False,
            on_update=True,
        ),
        # Wallet transaction — credit events
        SignalMap(
            model_path='wallet.WalletTransaction',
            field='transaction_type',
            value='credit',
            event_type='wallet.credited',
            user_field='user_id',
            data_fields=['amount', 'currency', 'description', 'balance_after'],
            on_created=True,
            on_update=False,
        ),
        # Low balance warning (debit that drops below threshold)
        SignalMap(
            model_path='wallet.WalletTransaction',
            field='transaction_type',
            value='debit',
            event_type='wallet.debited',
            user_field='user_id',
            data_fields=['amount', 'currency', 'description', 'balance_after'],
            on_created=True,
            on_update=False,
        ),
        # Withdrawal request created
        SignalMap(
            model_path='wallet.WithdrawalRequest',
            field='status',
            value='pending',
            event_type='withdrawal.requested',
            user_field='user_id',
            data_fields=['amount', 'currency', 'payment_method'],
            on_created=True,
            on_update=False,
        ),
    ]

    # ------------------------------------------------------------------
    # STEP 2: Events → Notifications
    # Notification module handles the actual sending.
    # ------------------------------------------------------------------
    event_maps = [
        EventMap(
            event_type='withdrawal.completed',
            notification_type='withdrawal_success',
            title_template='Withdrawal Successful! 💰',
            message_template='৳{amount} has been sent to your {payment_method} account successfully.',
            channel='in_app',
            priority='high',
            send_push=True,
            send_email=True,
        ),
        EventMap(
            event_type='withdrawal.approved',
            notification_type='withdrawal_approved',
            title_template='Withdrawal Approved ✅',
            message_template='Your withdrawal of ৳{amount} has been approved and is being processed.',
            channel='in_app',
            priority='high',
            send_push=True,
        ),
        EventMap(
            event_type='withdrawal.rejected',
            notification_type='withdrawal_rejected',
            title_template='Withdrawal Rejected ❌',
            message_template='Your withdrawal of ৳{amount} was rejected. Please contact support.',
            channel='in_app',
            priority='high',
            send_push=True,
        ),
        EventMap(
            event_type='withdrawal.failed',
            notification_type='withdrawal_failed',
            title_template='Withdrawal Failed',
            message_template='Your withdrawal of ৳{amount} failed. Please try again.',
            channel='in_app',
            priority='high',
        ),
        EventMap(
            event_type='withdrawal.requested',
            notification_type='withdrawal_pending',
            title_template='Withdrawal Request Submitted',
            message_template='Your withdrawal request of ৳{amount} has been received and is under review.',
            channel='in_app',
            priority='medium',
        ),
        EventMap(
            event_type='wallet.credited',
            notification_type='wallet_credited',
            title_template='Wallet Credited +৳{amount} 💵',
            message_template='৳{amount} has been added to your wallet. Balance: ৳{balance_after}',
            channel='in_app',
            priority='medium',
        ),
    ]

    # ------------------------------------------------------------------
    # STEP 3: Inbound webhooks (bKash, Nagad, Rocket, Stripe)
    # ------------------------------------------------------------------
    webhook_maps = [
        WebhookMap(
            provider='bkash',
            event_types=['payment_execute', 'payment_confirm'],
            event_output='wallet.credited',
        ),
        WebhookMap(
            provider='nagad',
            event_types=['complete', 'verify'],
            event_output='wallet.credited',
        ),
        WebhookMap(
            provider='rocket',
            event_types=['payment_success'],
            event_output='wallet.credited',
        ),
        WebhookMap(
            provider='stripe',
            event_types=['payment_intent.succeeded'],
            event_output='wallet.credited',
        ),
        WebhookMap(
            provider='stripe',
            event_types=['payment_intent.payment_failed'],
            event_output='wallet.payment_failed',
        ),
    ]

    health_checks = [
        HealthCheck(name='wallet_db', model_path='wallet.Wallet'),
        HealthCheck(name='withdrawal_db', model_path='wallet.Withdrawal'),
    ]

    # Wallet can access notifications and users — nothing else touches wallet
    allowed_targets = ['notifications', 'users', 'analytics']
