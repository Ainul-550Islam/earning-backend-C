# api/cache/urls.py  —  COMPLETE CRUD URLs
from django.urls import path
from . import views

urlpatterns = [
    # ── READ ──────────────────────────────────────────────────────────
    path('',                         views.cache_stats_view,       name='cache-stats'),
    path('stats/',                   views.cached_system_stats,    name='cache-system-stats'),
    path('user/<int:user_id>/profile/', views.cached_user_profile, name='cache-user-profile'),
    path('task/<int:task_id>/',      views.CachedTaskView.as_view(),name='cache-task-detail'),

    # ── NEW: Health check ─────────────────────────────────────────────
    path('health/',                  views.cache_health_view,      name='cache-health'),

    # ── NEW: Keys CRUD (admin only) ───────────────────────────────────
    path('keys/',                    views.cache_keys_list,        name='cache-keys-list'),   # GET
    path('key/',                     views.cache_key_delete,       name='cache-key-delete'),  # DELETE
    path('set/',                     views.cache_key_set,          name='cache-key-set'),     # POST (CREATE)

    # ── CLEAR (bulk delete) ───────────────────────────────────────────
    path('clear/',                   views.cache_clear_view,       name='cache-clear'),       # POST
]