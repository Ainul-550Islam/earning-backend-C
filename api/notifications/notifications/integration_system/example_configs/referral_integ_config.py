# api/referral/integ_config.py
"""
Referral Module — Integration Configuration
"এক কাজের জন্য একটাই মালিক"
"""
from api.notifications.integration_system.module_protocol import (
    ModuleConfig, SignalMap, EventMap, HealthCheck
)

class ReferralIntegConfig(ModuleConfig):
    module_name = 'referral'
    version = '1.0.0'
    description = 'Referral & Multi-level Earning System'

    signal_maps = [
        SignalMap(
            model_path='referral.Referral',
            field='status',
            value='completed',
            event_type='referral.completed',
            user_field='referrer_id',
            data_fields=['referral_id', 'referred_username', 'bonus_amount', 'currency'],
        ),
        SignalMap(
            model_path='referral.ReferralEarning',
            field='status',
            value='credited',
            event_type='referral.reward_issued',
            user_field='user_id',
            data_fields=['amount', 'currency', 'referral_level', 'source_username'],
            on_created=True,
            on_update=False,
        ),
        SignalMap(
            model_path='referral.ReferralChain',
            field='level',
            value=2,
            event_type='referral.team_bonus',
            user_field='root_user_id',
            data_fields=['chain_depth', 'total_bonus'],
        ),
    ]

    event_maps = [
        EventMap(
            event_type='referral.completed',
            notification_type='referral_completed',
            title_template='Referral Successful! 🎁',
            message_template='{referred_username} joined via your link! Bonus: ৳{bonus_amount}',
            channel='in_app',
            priority='high',
            send_push=True,
        ),
        EventMap(
            event_type='referral.reward_issued',
            notification_type='referral_reward',
            title_template='Referral Bonus +৳{amount} 💰',
            message_template='Level {referral_level} referral bonus from {source_username}. ৳{amount} credited.',
            channel='in_app',
            priority='high',
        ),
    ]

    health_checks = [HealthCheck(name='referral_db', model_path='referral.Referral')]
    allowed_targets = ['notifications', 'wallet', 'users', 'analytics']
