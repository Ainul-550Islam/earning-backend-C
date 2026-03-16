from django.urls import path
from .views import AdMobWebhookView, UnityAdsWebhookView, IronSourceWebhookView

urlpatterns = [
    path('admob/', AdMobWebhookView.as_view(), name='admob-webhook'),
    path('unity/', UnityAdsWebhookView.as_view(), name='unity-webhook'),
    path('ironsource/', IronSourceWebhookView.as_view(), name='ironsource-webhook'),
]