# api/payout_queue/integ_config.py
"""
Payout Queue Module — Integration Configuration
"এক কাজের জন্য একটাই মালিক"
"""
from api.notifications.integration_system.module_protocol import (
    ModuleConfig, SignalMap, EventMap, HealthCheck
)

class PayoutQueueIntegConfig(ModuleConfig):
    module_name = 'payout_queue'
    version = '1.0.0'
    description = 'Publisher Payout Queue & Batch Payment Processing'

    signal_maps = [
        SignalMap(
            model_path='payout_queue.PayoutBatch',
            field='status',
            value='completed',
            event_type='payout.batch_completed',
            user_field=None,
            data_fields=['batch_id', 'total_amount', 'user_count', 'currency'],
            notify_admin=True,
        ),
        SignalMap(
            model_path='payout_queue.PayoutEntry',
            field='status',
            value='paid',
            event_type='payout.publisher_paid',
            user_field='publisher_id',
            data_fields=['amount', 'currency', 'payment_method', 'transaction_id'],
        ),
        SignalMap(
            model_path='payout_queue.PayoutEntry',
            field='status',
            value='failed',
            event_type='payout.payment_failed',
            user_field='publisher_id',
            data_fields=['amount', 'currency', 'error_reason'],
        ),
    ]

    event_maps = [
        EventMap(
            event_type='payout.publisher_paid',
            notification_type='publisher_payout',
            title_template='Payout Sent! 💰 {currency} {amount}',
            message_template='{currency} {amount} has been sent to your {payment_method}. TX: {transaction_id}',
            channel='in_app',
            priority='high',
            send_push=True,
            send_email=True,
        ),
        EventMap(
            event_type='payout.payment_failed',
            notification_type='withdrawal_failed',
            title_template='Payout Failed ❌',
            message_template='Your payout of {currency} {amount} failed. Reason: {error_reason}',
            channel='in_app',
            priority='high',
            send_email=True,
        ),
    ]

    health_checks = [HealthCheck(name='payout_db', model_path='payout_queue.PayoutBatch')]
    allowed_targets = ['notifications', 'wallet', 'analytics']
