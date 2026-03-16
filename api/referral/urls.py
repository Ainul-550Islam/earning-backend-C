from django.urls import path
from . import views

urlpatterns = [
    path("", views.get_referral_stats, name="referral-stats"),
    path("stats/", views.get_referral_stats, name="referral-stats-alt"),
    path("referrals/", views.admin_referrals_list, name="referral-list"),
    path("referrals/<int:referral_id>/", views.admin_delete_referral, name="referral-detail"),
    path("settings/", views.admin_referral_settings, name="referral-settings"),
    path("earnings/", views.admin_recent_earnings, name="referral-earnings"),
    path("admin/overview/", views.admin_referral_overview, name="referral-admin-overview"),
    path("admin/stats-by-date/", views.admin_stats_by_date, name="referral-stats-date"),
    path("admin/list/", views.admin_referrals_list, name="referral-admin-list"),
    path("admin/create/", views.admin_create_referral, name="referral-admin-create"),
    path("admin/delete/<int:referral_id>/", views.admin_delete_referral, name="referral-admin-delete"),
    path("admin/give-bonus/<int:referral_id>/", views.admin_give_bonus, name="referral-give-bonus"),
    path("admin/adjust-commission/<int:referral_id>/", views.admin_adjust_commission, name="referral-adjust-commission"),
    path("admin/earnings/", views.admin_recent_earnings, name="referral-admin-earnings"),
    path("admin/earnings/delete/<int:earning_id>/", views.admin_delete_earning, name="referral-earning-delete"),
    path("admin/settings/", views.admin_referral_settings, name="referral-admin-settings"),
    path("admin/toggle-program/", views.admin_toggle_program, name="referral-toggle-program"),
    path("admin/search-users/", views.admin_search_users, name="referral-search-users"),
]
