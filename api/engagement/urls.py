# engagement/urls.py — COMPLETE WORLD #1 — All 80+ endpoints
from django.urls import path
from . import views
from .views import advanced_views, battle_pass_views, guild_views

app_name = "engagement"

urlpatterns = [
    # ── Dashboard / Stats ──────────────────────────────────────────────────────
    path("",                         views.get_daily_stats,        name="daily-stats"),
    path("daily-stats/",             views.get_daily_stats,        name="daily-stats-alt"),
    path("stats/",                   views.get_engagement_stats,   name="engagement-stats"),

    # ── Check-In ───────────────────────────────────────────────────────────────
    path("daily-checkin/",           views.daily_checkin,          name="daily-checkin"),
    path("checkins/stats/",          views.checkins_stats,         name="checkins-stats"),
    path("checkins/",                views.checkins_list,          name="checkins-list"),

    # ── Spin Wheel ─────────────────────────────────────────────────────────────
    path("spin-wheel/",              views.spin_wheel,             name="spin-wheel"),
    path("spins/stats/",             views.spins_stats,            name="spins-stats"),
    path("spins/",                   views.spins_list,             name="spins-list"),

    # ── Leaderboard ────────────────────────────────────────────────────────────
    path("leaderboard/",                     views.get_leaderboard,               name="leaderboard"),
    path("leaderboard/seasons/",             views.leaderboard_seasons,           name="leaderboard-seasons"),
    path("leaderboard/rebuild/",             views.rebuild_leaderboard,           name="leaderboard-rebuild"),
    path("leaderboard/distribute-rewards/",  views.distribute_leaderboard_rewards,name="leaderboard-distribute"),
    path("leaderboard-rewards/",             views.leaderboard_rewards_list,      name="leaderboard-rewards"),
    path("leaderboard-rewards/<int:rank>/",  views.leaderboard_reward_detail,     name="leaderboard-reward-detail"),

    # ── Achievements ───────────────────────────────────────────────────────────
    path("achievements/",                    views.achievements_list,             name="achievements-list"),
    path("achievements/mine/",               views.my_achievements,               name="my-achievements"),
    path("achievements/<int:achievement_id>/claim/",     views.claim_achievement_reward,      name="achievement-claim"),
    path("admin/achievements/",              views.achievements_admin,            name="achievements-admin"),
    path("admin/achievements/<int:pk>/",     views.achievement_admin_detail,      name="achievement-admin-detail"),

    # ── XP & Levels ────────────────────────────────────────────────────────────
    path("xp/",                      views.my_xp,                  name="my-xp"),
    path("xp/history/",              views.xp_history,             name="xp-history"),
    path("xp/grant/",                views.admin_grant_xp,         name="admin-grant-xp"),

    # ── Quests ─────────────────────────────────────────────────────────────────
    path("quests/",                  views.my_quests,              name="my-quests"),
    path("quests/init-daily/",       views.init_daily_quests,      name="init-daily-quests"),
    path("quests/<int:pk>/claim/",   views.claim_quest_reward,     name="quest-claim"),
    path("admin/quests/",            views.quest_admin_list,       name="quest-admin-list"),
    path("admin/quests/<int:pk>/",   views.quest_admin_detail,     name="quest-admin-detail"),

    # ── Challenges ─────────────────────────────────────────────────────────────
    path("challenges/",              views.challenges_list,        name="challenges-list"),
    path("challenges/mine/",         views.my_challenges,          name="my-challenges"),
    path("challenges/<int:pk>/",     views.challenge_detail,       name="challenge-detail"),
    path("challenges/<int:pk>/join/",views.join_challenge,         name="challenge-join"),
    path("admin/challenges/",        views.challenge_admin_list,   name="challenge-admin"),

    # ── Shop ───────────────────────────────────────────────────────────────────
    path("shop/",                    views.shop_items,             name="shop-items"),
    path("shop/purchase/",           views.purchase_item,          name="shop-purchase"),
    path("shop/inventory/",          views.my_inventory,           name="my-inventory"),
    path("admin/shop/",              views.shop_admin_list,        name="shop-admin-list"),
    path("admin/shop/<int:pk>/",     views.shop_admin_detail,      name="shop-admin-detail"),

    # ── Referrals ──────────────────────────────────────────────────────────────
    path("referrals/",               views.my_referrals,           name="my-referrals"),
    path("referrals/register/",      views.register_referral,      name="register-referral"),
    path("referrals/program/",       views.referral_program_detail,name="referral-program"),
    path("admin/referral-programs/",         views.referral_program_admin,        name="referral-program-admin"),
    path("admin/referral-programs/<int:pk>/",views.referral_program_admin_detail, name="referral-program-admin-detail"),
    path("admin/referrals/",                 views.all_referrals_admin,           name="all-referrals-admin"),

    # ── Notifications ──────────────────────────────────────────────────────────
    path("notifications/",                        views.notifications_list,            name="notifications-list"),
    path("notifications/unread-count/",           views.notifications_unread_count,    name="notifications-unread-count"),
    path("notifications/read-all/",               views.mark_all_notifications_read,   name="notifications-read-all"),
    path("notifications/push-token/",             views.register_push_token,           name="push-token-register"),
    path("notifications/push-token/unregister/",  views.unregister_push_token,         name="push-token-unregister"),
    path("notifications/<int:pk>/read/",          views.mark_notification_read,        name="notification-read"),
    path("notifications/<int:pk>/",               views.delete_notification,           name="notification-delete"),
    path("admin/notifications/send/",             views.admin_send_notification,       name="admin-send-notification"),

    # ── Battle Pass ────────────────────────────────────────────────────────────
    path("battle-pass/",                  battle_pass_views.battle_pass_current, name="battle-pass"),
    path("battle-pass/claim/",            battle_pass_views.claim_tier,          name="battle-pass-claim"),
    path("battle-pass/premium/",          battle_pass_views.unlock_premium,      name="battle-pass-premium"),
    path("admin/battle-pass/",            battle_pass_views.create_season,       name="battle-pass-admin"),

    # ── Guilds ─────────────────────────────────────────────────────────────────
    path("guilds/",                       guild_views.guilds_list,         name="guilds-list"),
    path("guilds/create/",                guild_views.create_guild,        name="guild-create"),
    path("guilds/mine/",                  guild_views.my_guild,            name="my-guild"),
    path("guilds/leaderboard/",           guild_views.guild_leaderboard,   name="guild-leaderboard"),
    path("guilds/<slug:slug>/",           guild_views.guild_detail,        name="guild-detail"),
    path("guilds/<slug:slug>/join/",      guild_views.join_guild,          name="guild-join"),
    path("guilds/<slug:slug>/leave/",     guild_views.leave_guild,         name="guild-leave"),

    # ── Social Feed ────────────────────────────────────────────────────────────
    path("social/feed/",                          advanced_views.social_feed,          name="social-feed"),
    path("social/feed/<int:pk>/like/",            advanced_views.like_feed_item,       name="feed-like"),
    path("social/feed/<int:pk>/comment/",         advanced_views.comment_feed_item,    name="feed-comment"),
    path("social/friends/",                       advanced_views.friends_list,         name="friends-list"),
    path("social/friends/request/",               advanced_views.send_friend_request,  name="friend-request"),
    path("social/friends/<int:pk>/accept/",       advanced_views.accept_friend_request,name="friend-accept"),
    path("social/follow/<int:user_id>/",          advanced_views.follow_user,          name="follow-user"),

    # ── Loot Box / Chests ──────────────────────────────────────────────────────
    path("chests/",                        advanced_views.my_chests,   name="my-chests"),
    path("chests/open/",                   advanced_views.open_chest,  name="chest-open"),
    path("chests/buy/",                    advanced_views.buy_chest,   name="chest-buy"),

    # ── Prestige ───────────────────────────────────────────────────────────────
    path("prestige/",                      advanced_views.prestige_status, name="prestige-status"),
    path("prestige/commit/",               advanced_views.do_prestige,     name="prestige-commit"),
    path("milestones/",                    advanced_views.milestones_list, name="milestones-list"),

    # ── Seasonal Events ────────────────────────────────────────────────────────
    path("events/live/",                   advanced_views.live_event,     name="live-event"),
    path("events/shop/buy/",               advanced_views.buy_event_item, name="event-shop-buy"),

    # ── Combo & Energy ─────────────────────────────────────────────────────────
    path("combo/",                         advanced_views.combo_status,   name="combo-status"),

    # ── Scratch Card & Login Calendar ──────────────────────────────────────────
    path("scratch/",                       advanced_views.scratch_card,       name="scratch-card"),
    path("calendar/",                      advanced_views.login_calendar,     name="login-calendar"),
    path("calendar/claim/",                advanced_views.claim_calendar_day, name="calendar-claim"),

    # ── Auction House ──────────────────────────────────────────────────────────
    path("auctions/",                      advanced_views.auctions_list,  name="auctions-list"),
    path("auctions/<int:pk>/bid/",         advanced_views.place_bid,      name="auction-bid"),
    path("auctions/<int:pk>/watch/",       advanced_views.watch_auction,  name="auction-watch"),

    # ── Feature Flags & A/B Tests ──────────────────────────────────────────────
    path("flags/<slug:slug>/",             advanced_views.feature_flag_check, name="feature-flag"),
    path("ab/<slug:test_slug>/",           advanced_views.ab_variant,         name="ab-variant"),
    path("ab/<slug:test_slug>/convert/",   advanced_views.ab_convert,         name="ab-convert"),

    # ── Analytics ──────────────────────────────────────────────────────────────
    path("analytics/me/",                  advanced_views.my_analytics,       name="my-analytics"),
    path("admin/analytics/",               advanced_views.analytics_dashboard, name="analytics-dashboard"),

    # ── Admin ─────────────────────────────────────────────────────────────────────
    path("admin/platform-stats/",       views.platform_stats,           name="platform-stats"),
    path("admin/webhooks/",             advanced_views.webhooks,         name="webhooks"),
    path("admin/webhooks/<int:pk>/",    advanced_views.webhook_delete,  name="webhook-delete"),
    path("admin/anti-cheat/",           advanced_views.anti_cheat_flags,name="anti-cheat-flags"),
    path("admin/anti-cheat/<int:pk>/",  advanced_views.anti_cheat_resolve, name="anti-cheat-resolve"),

    # ── CPAlead Integration ─────────────────────────────────────────────────────
    path("cpa-lead/postback/",          views.cpa_lead_postback,        name="cpa-lead-postback"),
    path("earning-task/complete/",      views.earning_task_complete,    name="earning-task-complete"),
]
