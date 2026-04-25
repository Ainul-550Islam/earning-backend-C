# api/fraud_detection/integ_config.py
"""
Fraud Detection Module — Integration Configuration
"এক কাজের জন্য একটাই মালিক"
"""
from api.notifications.integration_system.module_protocol import (
    ModuleConfig, SignalMap, EventMap, HealthCheck
)

class FraudDetectionIntegConfig(ModuleConfig):
    module_name = 'fraud_detection'
    version = '1.0.0'
    description = 'Fraud Detection & Risk Management'

    signal_maps = [
        SignalMap(
            model_path='fraud_detection.FraudAlert',
            field='priority',
            value='high',
            event_type='fraud.detected',
            user_field='user_id',
            data_fields=['alert_type', 'fraud_score', 'description', 'attempt_type'],
            notify_admin=True,
            on_created=True,
        ),
        SignalMap(
            model_path='fraud_detection.FraudAttempt',
            field='action_taken',
            value='banned',
            event_type='fraud.account_suspended',
            user_field='user_id',
            data_fields=['reason', 'fraud_score', 'attempt_type'],
        ),
        SignalMap(
            model_path='fraud_detection.UserRiskProfile',
            field='risk_level',
            value='critical',
            event_type='fraud.critical_risk',
            user_field='user_id',
            data_fields=['risk_score', 'risk_factors'],
            notify_admin=True,
        ),
    ]

    event_maps = [
        EventMap(
            event_type='fraud.account_suspended',
            notification_type='account_suspended',
            title_template='Account Suspended ⛔',
            message_template='আপনার account সাময়িকভাবে suspend করা হয়েছে। কারণ: {reason}. Support এ যোগাযোগ করুন।',
            channel='in_app',
            priority='critical',
            send_email=True,
        ),
        EventMap(
            event_type='fraud.detected',
            notification_type='fraud_detected',
            title_template='Security Alert 🚨',
            message_template='আপনার account এ সন্দেহজনক activity ধরা পড়েছে। Admin review করছে।',
            channel='in_app',
            priority='urgent',
        ),
    ]

    health_checks = [HealthCheck(name='fraud_db', model_path='fraud_detection.FraudAttempt')]
    allowed_targets = ['notifications', 'users', 'wallet', 'kyc', 'analytics']
