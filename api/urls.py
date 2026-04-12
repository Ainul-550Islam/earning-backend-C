from django.urls import path, include
from . import views
from api.views import signup, login, refresh_token, get_profile
from api.admin_panel.views import admin_dashboard
from rest_framework.routers import SimpleRouter as DefaultRouter
from api.notifications.views import NotificationViewSet
from .views import (
    UserViewSet, WalletViewSet, TransactionViewSet,
    OfferViewSet, UserOfferViewSet, ReferralViewSet,
    WithdrawalViewSet,
    register_user, dashboard_stats, earnings_chart
)

router = DefaultRouter()
#router.register(r'users', UserViewSet, basename='user')
router.register(r'wallets', WalletViewSet, basename='wallet')
router.register(r'GatewayTransactions', TransactionViewSet, basename='Transaction')
# router.register(r'offers', OfferViewSet, basename='offer')  # moved to offerwall urls
# router.register(r'user-offers', UserOfferViewSet, basename='user-offer')  # moved to offerwall urls
# router.register(r'referrals', ReferralViewSet, basename='referral')  # moved to referral app
router.register(r'withdrawals', WithdrawalViewSet, basename='withdrawal')
# router.register(r'notifications', NotificationViewSet, basename='notification')  # moved to notifications app

urlpatterns = [
    # Auth endpoints
    path('auth/register/', register_user, name='register'),
    
    # Dashboard endpoints
    path('dashboard/stats/', dashboard_stats, name='dashboard-stats'),
    path('dashboard/earnings-chart/', earnings_chart, name='earnings-chart'),
    
    # Router URLs
    path('', include(router.urls)),
        path('admin-dashboard/', admin_dashboard, name='admin_dashboard'),
    
   
    path('search/', lambda r: None, name='search'),
    
    # --- Auth (লগইন ও সাইনআপ) ---
    path('auth/signup/', views.signup),
    path('auth/login/', views.login),          
    path('auth/refresh/', views.refresh_token),
    path('auth/password/reset/', views.forgot_password),
    path('auth/password/reset/confirm/', views.reset_password_confirm),
    
    # --- Profile (ইউজার প্রোফাইল) ---
    path('profile/', views.get_profile),
    path('profile/update/', views.update_profile),
    path('profile/avatar/', views.upload_avatar),
    path('profile/change-phone/', views.request_phone_change),
    path('profile/verify-phone/', views.verify_phone_change),
    path('profile/login-history/', views.get_login_history),
    
    # --- Earning & General Features ---
    path('register/', views.register),
    path('login/', views.login), # আগের login যদি আলাদা থাকে
    path('user/', views.get_user_info),
    path('notices/', views.get_notices),
    path('complete-ad/', views.complete_ad_watch),
    path('mylead-postback/', views.mylead_postback),
    path('payment-request/', views.create_payment_request),
    path('my-payment-requests/', views.get_payment_requests),
    path('payment-history/', views.get_payment_history),
    # path('notifications/', include('api.notifications.urls')),  # moved to config/urls.py
    path('fraud_detection/', include('api.fraud_detection.urls')),
    path('tasks/', include('api.tasks.urls')),
    # path('referral/', include('api.referral.urls')),  # moved to config/urls.py
    path('kyc/', include('api.kyc.urls')),
    path('support/', include('api.support.urls')),
    path('alerts/', include('api.alerts.urls')),
    path('backup/', include('api.backup.urls')),
    path('loyalty/', include('api.djoyalty.urls')),
    path('promotions/', include('api.promotions.urls')),
    path('analytics/', include('api.analytics.urls')),
    path('engagement/', include('api.engagement.urls')),
    # path('subscriptions/', include('api.subscription.urls')),
    path('webhooks/', include('api.webhooks.urls', namespace='webhooks')),
    
]    
