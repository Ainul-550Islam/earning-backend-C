# =============================================================================
# fraud_detection/security/urls_security.py
# =============================================================================
"""
URL patterns for all security protection endpoints.

Include in urls_final_complete.py:
    from .security.urls_security import security_urlpatterns
    urlpatterns += security_urlpatterns

Routes added:
  GET  security/brute-force/status/<identifier>/
  POST security/brute-force/reset/<identifier>/
  POST security/brute-force/check/
  GET  security/brute-force/stats/
  POST security/lockout/check/
  POST security/lockout/unlock/
  POST security/credential-stuffing/check-ip/
  POST security/credential-stuffing/check-password/
  POST security/credential-stuffing/report/
  GET  security/attack-log/
  GET  security/attack-log/stats/
  POST security/attack-log/clear/
"""
from django.urls import path

from .security_views import (
    AttackLogAPIView,
    AttackLogClearAPIView,
    AttackLogStatsAPIView,
    BruteForceCheckAPIView,
    BruteForceResetAPIView,
    BruteForceStatusAPIView,
    BruteForceStatsAPIView,
    CredentialStuffingCheckIPAPIView,
    CredentialStuffingCheckPasswordAPIView,
    CredentialStuffingReportAPIView,
    LockoutCheckAPIView,
    LockoutUnlockAPIView,
)

security_urlpatterns = [
    # ── Brute-Force ──────────────────────────────────────────────────────────
    path('security/brute-force/check/',
         BruteForceCheckAPIView.as_view(),  name='security-bf-check'),
    path('security/brute-force/stats/',
         BruteForceStatsAPIView.as_view(),  name='security-bf-stats'),
    path('security/brute-force/status/<str:identifier>/',
         BruteForceStatusAPIView.as_view(), name='security-bf-status'),
    path('security/brute-force/reset/<str:identifier>/',
         BruteForceResetAPIView.as_view(),  name='security-bf-reset'),

    # ── Lockout ───────────────────────────────────────────────────────────────
    path('security/lockout/check/',
         LockoutCheckAPIView.as_view(),  name='security-lockout-check'),
    path('security/lockout/unlock/',
         LockoutUnlockAPIView.as_view(), name='security-lockout-unlock'),

    # ── Credential Stuffing ────────────────────────────────────────────────
    path('security/credential-stuffing/check-ip/',
         CredentialStuffingCheckIPAPIView.as_view(),       name='security-cs-check-ip'),
    path('security/credential-stuffing/check-password/',
         CredentialStuffingCheckPasswordAPIView.as_view(), name='security-cs-check-password'),
    path('security/credential-stuffing/report/',
         CredentialStuffingReportAPIView.as_view(),        name='security-cs-report'),

    # ── Attack Log ────────────────────────────────────────────────────────
    path('security/attack-log/',
         AttackLogAPIView.as_view(),      name='security-attack-log'),
    path('security/attack-log/stats/',
         AttackLogStatsAPIView.as_view(), name='security-attack-log-stats'),
    path('security/attack-log/clear/',
         AttackLogClearAPIView.as_view(), name='security-attack-log-clear'),
]

urlpatterns = security_urlpatterns
