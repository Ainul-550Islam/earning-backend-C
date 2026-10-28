# api/support/api/v1/urls.py
"""API v1 URL routing — includes all support endpoints."""
from django.urls import path, include

# Simply re-use the main urls.py for now
# When breaking changes needed, create api/v2/urls.py
urlpatterns = [
    path('', include('api.support.urls')),
]