from django.urls import path, include
from rest_framework.routers import SimpleRouter as DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'configs', views.RateLimitConfigViewSet, basename='ratelimit-config')
router.register(r'logs', views.RateLimitLogViewSet, basename='ratelimit-log')
router.register(r'user-profiles', views.UserRateLimitProfileViewSet, basename='user-ratelimit-profile')

urlpatterns = [
    path('', include(router.urls)),
    
    # Health check
    path('health/', views.RateLimitHealthView.as_view(), name='rate-limit-health'),
    
    # Test endpoint
    path('test/', views.RateLimitTestView.as_view(), name='rate-limit-test'),
    
    # Dashboard
    path('dashboard/', views.RateLimitDashboardView.as_view(), name='rate-limit-dashboard'),
    
    # User-specific endpoints
    path('user/info/', views.RateLimitTestView.as_view(), name='user-rate-limit-info'),
    
    # Earning app specific endpoints
    path('earning/task-limit/', views.RateLimitTestView.as_view(), name='task-rate-limit-check'),
    path('earning/offer-limit/', views.RateLimitTestView.as_view(), name='offer-rate-limit-check'),
    path('earning/referral-limit/', views.RateLimitTestView.as_view(), name='referral-rate-limit-check'),
]