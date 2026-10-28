# wallet/urls_new_additions.py
"""
Add these URL patterns to wallet/urls.py
(inside the router block, after existing paths)
"""

# At top of urls.py, add these imports:
"""
from .views.postback_views import PostbackView, OfferwallListView, SmartwallUrlView
from .viewsets.AIInsightViewSet import AIInsightViewSet
"""

# Register AIInsight viewset with router:
"""
router.register(r"ai-insights", AIInsightViewSet, basename="ai-insight")
"""

# Add these URL patterns to urlpatterns list:
"""
# ── Offerwall Platform Postbacks (S2S) ──────────────────────────────────────
path("postback/<str:platform>/",    PostbackView.as_view(),      name="wallet-postback"),
path("offers/",                     OfferwallListView.as_view(),  name="wallet-offers"),
path("smartwall-urls/",             SmartwallUrlView.as_view(),   name="wallet-smartwall-urls"),
"""

# Full snippet to append after existing router.register() calls:
URLPATTERNS_ADDITION = """
from django.urls import path, include
from rest_framework.routers import DefaultRouter

# Existing router (already in urls.py) — ADD these lines:
router.register(r"ai-insights", AIInsightViewSet, basename="ai-insight")

# ADD to urlpatterns:
urlpatterns += [
    path("postback/<str:platform>/",  PostbackView.as_view(),     name="wallet-postback"),
    path("offers/",                   OfferwallListView.as_view(), name="wallet-offers"),
    path("smartwall-urls/",           SmartwallUrlView.as_view(),  name="wallet-smartwall-urls"),
]
"""
