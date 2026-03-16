# api/engagement/urls.py  —  COMPLETE CRUD
from django.urls import path
from . import views

app_name = 'engagement'

urlpatterns = [
    # ── Daily Stats ────────────────────────────────────────────────
    path('',              views.get_daily_stats,         name='daily-stats'),
    path('daily-stats/',  views.get_daily_stats,         name='daily-stats-alt'),

    # ── Engagement Score ───────────────────────────────────────────
    # ✅ NEW: GET /engagement/stats/ — overall engagement score (89% card)
    path('stats/',        views.get_engagement_stats,    name='engagement-stats'),

    # ── Daily Check-In ─────────────────────────────────────────────
    path('daily-checkin/', views.daily_checkin,          name='daily-checkin'),
    # ✅ NEW: checkins stats MUST come before checkins list
    path('checkins/stats/', views.checkins_stats,        name='checkins-stats'),
    # ✅ NEW: GET /engagement/checkins/
    path('checkins/',      views.checkins_list,          name='checkins-list'),

    # ── Spin Wheel ─────────────────────────────────────────────────
    path('spin-wheel/',    views.spin_wheel,             name='spin-wheel'),
    # ✅ NEW: spins stats MUST come before spins list
    path('spins/stats/',   views.spins_stats,            name='spins-stats'),
    # ✅ NEW: GET /engagement/spins/
    path('spins/',         views.spins_list,             name='spins-list'),

    # ── Leaderboard ────────────────────────────────────────────────
    path('leaderboard/',   views.get_leaderboard,        name='leaderboard'),

    # ── Leaderboard Rewards ────────────────────────────────────────
    # ✅ NEW: GET/PATCH leaderboard rewards
    path('leaderboard-rewards/',        views.leaderboard_rewards_list,   name='leaderboard-rewards'),
    path('leaderboard-rewards/<int:rank>/', views.leaderboard_reward_update, name='leaderboard-reward-update'),
]