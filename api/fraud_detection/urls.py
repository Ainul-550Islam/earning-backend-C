"""
Fraud Detection App URLs Configuration
"""

from django.urls import path, include
from rest_framework.routers import SimpleRouter as DefaultRouter
from . import views

router = DefaultRouter()

router.register(r'rules',         views.FraudRuleViewSet,       basename='fraud-rule')
router.register(r'attempts',      views.FraudAttemptViewSet,    basename='fraud-attempt')
router.register(r'risk-profiles', views.UserRiskProfileViewSet, basename='risk-profile')
router.register(r'alerts',        views.FraudAlertViewSet,      basename='fraud-alert')

urlpatterns = [
    # Custom actions MUST come before router.urls
    # (router catches alerts/{id}/ — custom paths must match first)

    # Fraud Detection
    path('detect/check-user/',        views.FraudDetectionAPIView.as_view(), name='fraud-detect-check-user'),
    path('detect/check-transaction/', views.FraudDetectionAPIView.as_view(), kwargs={'action': 'check_transaction'}, name='fraud-detect-check-transaction'),
    path('detect/check-offer/',       views.FraudDetectionAPIView.as_view(), kwargs={'action': 'check_offer'},       name='fraud-detect-check-offer'),
    path('detect/check-device/',      views.FraudDetectionAPIView.as_view(), kwargs={'action': 'check_device'},      name='fraud-detect-check-device'),

    # Auto-Ban
    path('auto-ban/process-attempt/', views.AutoBanAPIView.as_view(), kwargs={'action': 'process_attempt'}, name='auto-ban-process-attempt'),
    path('auto-ban/ban-user/',        views.AutoBanAPIView.as_view(), kwargs={'action': 'ban_user'},         name='auto-ban-user'),
    path('auto-ban/suspend-user/',    views.AutoBanAPIView.as_view(), kwargs={'action': 'suspend_user'},     name='auto-ban-suspend-user'),
    path('auto-ban/restrict-user/',   views.AutoBanAPIView.as_view(), kwargs={'action': 'restrict_user'},    name='auto-ban-restrict-user'),
    path('auto-ban/unban-users/',     views.AutoBanAPIView.as_view(), kwargs={'action': 'unban_users'},      name='auto-ban-unban-users'),

    # Review
    path('review/pending/',               views.ReviewAPIView.as_view(), kwargs={'action': 'pending'},  name='review-pending'),
    path('review/case/<uuid:attempt_id>/', views.ReviewAPIView.as_view(), kwargs={'action': 'case'},    name='review-case'),
    path('review/stats/',                 views.ReviewAPIView.as_view(), kwargs={'action': 'stats'},    name='review-stats'),
    path('review/decide/',                views.ReviewAPIView.as_view(), kwargs={'action': 'decide'},   name='review-decide'),
    path('review/escalate/',              views.ReviewAPIView.as_view(), kwargs={'action': 'escalate'}, name='review-escalate'),
    path('review/comment/',               views.ReviewAPIView.as_view(), kwargs={'action': 'comment'},  name='review-comment'),
    path('review/batch/',                 views.ReviewAPIView.as_view(), kwargs={'action': 'batch'},    name='review-batch'),

    # Dashboard & Stats
    path('dashboard/',          views.FraudDashboardAPIView.as_view(), name='fraud-dashboard'),
    path('statistics/',         views.fraud_statistics,                name='fraud-statistics'),
    path('quick-check/',        views.quick_fraud_check,               name='fraud-quick-check'),
    path('settings/block-vpn/', views.FraudSettingsAPIView.as_view(),  name='fraud-settings-block-vpn'),

    # Extra ViewSet Actions (before router to avoid {pk} conflict)
    path('rules/types/',                views.FraudRuleViewSet.as_view({'get': 'types'}),                    name='fraud-rule-types'),
    path('rules/stats/',                views.FraudRuleViewSet.as_view({'get': 'stats'}),                    name='fraud-rule-stats'),
    path('attempts/statistics/',        views.FraudAttemptViewSet.as_view({'get': 'statistics'}),            name='fraud-attempts-statistics'),
    path('attempts/bulk-update/',       views.FraudAttemptViewSet.as_view({'post': 'bulk_update'}),          name='fraud-attempts-bulk-update'),
    path('risk-profiles/high-risk/',    views.UserRiskProfileViewSet.as_view({'get': 'high_risk_users'}),    name='risk-profiles-high-risk'),
    path('risk-profiles/distribution/', views.UserRiskProfileViewSet.as_view({'get': 'risk_distribution'}), name='risk-profiles-distribution'),
    path('alerts/dashboard-stats/',     views.FraudAlertViewSet.as_view({'get': 'dashboard_stats'}),        name='alerts-dashboard-stats'),
    path('alerts/bulk-resolve/',        views.FraudAlertViewSet.as_view({'post': 'bulk_resolve'}),          name='alerts-bulk-resolve'),

    # Router URLs last (catches /{pk}/ patterns)
    path('', include(router.urls)),
]

app_name = 'fraud_detection'