"""
URL configuration for the Disaster Recovery app.

The DR system runs as a standalone SQLAlchemy/FastAPI service.
These Django URLs are placeholder stubs so the app can be included
in INSTALLED_APPS without breaking URL resolution.
"""
from django.urls import path

app_name = 'disaster_recovery'

urlpatterns = [
    # DR system is served by its own FastAPI process.
    # Add proxy/status endpoints here if needed.
]
