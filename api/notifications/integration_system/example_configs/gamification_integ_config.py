# api/gamification/integ_config.py
"""
Gamification Module — Integration Configuration
"এক কাজের জন্য একটাই মালিক"
"""
from api.notifications.integration_system.module_protocol import (
    ModuleConfig, SignalMap, EventMap, HealthCheck
)

class GamificationIntegConfig(ModuleConfig):
    module_name = 'gamification'
    version = '1.0.0'
    description = 'Gamification — Achievements, Leaderboard, Streaks, Contests'

    signal_maps = [
        SignalMap(
            model_path='gamification.UserAchievement',
            field='is_completed',
            value=True,
            event_type='achievement.unlocked',
            user_field='user_id',
            data_fields=['achievement_name', 'achievement_type', 'points', 'badge_icon'],
            on_created=False,
            on_update=True,
        ),
        SignalMap(
            model_path='gamification.LeaderboardSnapshot',
            field='is_final',
            value=True,
            event_type='achievement.leaderboard_changed',
            user_field=None,  # Broadcast — sent to top 10 users
            data_fields=['period', 'top_users'],
        ),
        SignalMap(
            model_path='gamification.ContestReward',
            field='status',
            value='distributed',
            event_type='achievement.contest_reward',
            user_field='user_id',
            data_fields=['contest_name', 'rank', 'reward_amount', 'reward_type'],
        ),
    ]

    event_maps = [
        EventMap(
            event_type='achievement.unlocked',
            notification_type='achievement_unlocked',
            title_template='🏆 Achievement Unlocked!',
            message_template='"{achievement_name}" badge অর্জন করেছেন! +{points} points',
            channel='in_app',
            priority='high',
            send_push=True,
        ),
        EventMap(
            event_type='achievement.contest_reward',
            notification_type='milestone_reached',
            title_template='Contest Reward! Rank #{rank} 🥇',
            message_template='{contest_name} এ #{rank} হয়েছেন! ৳{reward_amount} পুরস্কার পেয়েছেন।',
            channel='in_app',
            priority='high',
            send_push=True,
        ),
    ]

    health_checks = [HealthCheck(name='gamification_db', model_path='gamification.UserAchievement')]
    allowed_targets = ['notifications', 'users', 'wallet', 'analytics']
