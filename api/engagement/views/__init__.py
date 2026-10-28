# engagement/views/__init__.py
from .checkin_views import daily_checkin, checkins_list, checkins_stats
from .spin_views import spin_wheel, spins_list, spins_stats
from .leaderboard_views import (
    get_leaderboard, rebuild_leaderboard, distribute_leaderboard_rewards,
    leaderboard_rewards_list, leaderboard_reward_detail, leaderboard_seasons,
)
from .achievement_views import (
    achievements_list, my_achievements, claim_achievement_reward,
    achievements_admin, achievement_admin_detail,
)
from .xp_views import my_xp, xp_history, admin_grant_xp
from .quest_views import (
    my_quests, init_daily_quests, claim_quest_reward,
    quest_admin_list, quest_admin_detail,
)
from .challenge_views import (
    challenges_list, challenge_detail, join_challenge,
    my_challenges, challenge_admin_list,
)
from .shop_views import (
    shop_items, purchase_item, my_inventory,
    shop_admin_list, shop_admin_detail,
)
from .referral_views import (
    my_referrals, register_referral, referral_program_detail,
    referral_program_admin, referral_program_admin_detail, all_referrals_admin,
)
from .notification_views import (
    notifications_list, notifications_unread_count,
    mark_notification_read, mark_all_notifications_read,
    delete_notification, register_push_token, unregister_push_token,
    admin_send_notification,
)
from .stats_views import get_daily_stats, get_engagement_stats, platform_stats
from .battle_pass_views import battle_pass_current, claim_tier, unlock_premium, create_season
from .guild_views import (guilds_list, create_guild, guild_detail, join_guild,
                          leave_guild, my_guild, guild_leaderboard)
from .advanced_views import (
    social_feed, like_feed_item, comment_feed_item, delete_feed_item,
    send_friend_request, accept_friend_request, unfriend_user, follow_user, unfollow_user,
    # FIX: Added 16 missing exports that were wired in urls.py but not exported here
    friends_list,
    my_chests, open_chest, buy_chest,
    prestige_status, do_prestige, milestones_list,
    live_event, buy_event_item,
    combo_status,
    scratch_card, login_calendar, claim_calendar_day,
    auctions_list, place_bid, watch_auction,
    # end fix
    admin_campaign_create, admin_campaign_update, admin_campaign_detail, admin_campaign_list,
    feature_flag_check, ab_variant, ab_convert,
    analytics_dashboard, my_analytics,
    webhooks, webhook_delete,
    anti_cheat_flags, anti_cheat_resolve,
)
from .cpa_lead_views import cpa_lead_postback, earning_task_complete
