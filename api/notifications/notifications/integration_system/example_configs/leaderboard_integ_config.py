# api/leaderboard/integ_config.py
"""EXAMPLE — integ_config.py for the 'leaderboard' module."""
from api.notifications.integration_system.module_protocol import (
    ModuleConfig, SignalMap, EventMap, HealthCheck
)


class LeaderboardIntegConfig(ModuleConfig):
    module_name = 'leaderboard'
    version = '1.0.0'
    description = 'Leaderboard & Rankings System'

    signal_maps = [
        SignalMap(
            model_path='leaderboard.LeaderboardEntry',
            field='rank_changed',
            value=True,
            event_type='achievement.leaderboard_changed',
            user_field='user_id',
            data_fields=['rank', 'previous_rank', 'score', 'period'],
        ),
    ]

    event_maps = [
        EventMap(
            event_type='achievement.leaderboard_changed',
            notification_type='leaderboard_update',
            title_template='Leaderboard Update 🏆',
            message_template='You moved to rank #{rank} (was #{previous_rank}). Score: {score}',
            channel='in_app',
            priority='medium',
        ),
    ]

    health_checks = [HealthCheck(name='database', model_path='leaderboard.LeaderboardEntry')]
    allowed_targets = ['notifications', 'users', 'analytics']
