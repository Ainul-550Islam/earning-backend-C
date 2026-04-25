# api/payments/integ_config.py
"""
EXAMPLE — integ_config.py for the 'payments' module (bKash, Nagad, Rocket, Stripe).
"""
from api.notifications.integration_system.module_protocol import (
    ModuleConfig, SignalMap, EventMap, WebhookMap, HealthCheck
)


class PaymentsIntegConfig(ModuleConfig):
    module_name = 'payments'
    version = '1.0.0'
    description = 'Payment Gateway Integration (bKash, Nagad, Rocket, Stripe)'

    signal_maps = [
        SignalMap(
            model_path='payments.Transaction',
            field='status',
            value='success',
            event_type='payment.deposit_success',
            user_field='user_id',
            data_fields=['amount', 'currency', 'payment_method', 'transaction_id'],
        ),
        SignalMap(
            model_path='payments.Transaction',
            field='status',
            value='failed',
            event_type='payment.deposit_failed',
            user_field='user_id',
            data_fields=['amount', 'currency', 'payment_method', 'error_message'],
        ),
    ]

    event_maps = [
        EventMap(
            event_type='payment.deposit_success',
            notification_type='deposit_success',
            title_template='Deposit Successful! +{currency} {amount} 💰',
            message_template='Your {payment_method} payment of {currency} {amount} was successful.',
            channel='in_app',
            priority='high',
            send_push=True,
            send_email=True,
        ),
        EventMap(
            event_type='payment.deposit_failed',
            notification_type='deposit_failed',
            title_template='Payment Failed ❌',
            message_template='Your {payment_method} payment of {currency} {amount} failed. Please try again.',
            channel='in_app',
            priority='high',
        ),
    ]

    webhook_maps = [
        WebhookMap(provider='bkash', event_types=['payment_execute'], event_output='payment.deposit_success'),
        WebhookMap(provider='nagad', event_types=['complete'], event_output='payment.deposit_success'),
        WebhookMap(provider='stripe', event_types=['payment_intent.succeeded'], event_output='payment.deposit_success'),
        WebhookMap(provider='stripe', event_types=['payment_intent.payment_failed'], event_output='payment.deposit_failed'),
    ]

    health_checks = [HealthCheck(name='database', model_path='payments.Transaction')]
    allowed_targets = ['notifications', 'wallet', 'users']
