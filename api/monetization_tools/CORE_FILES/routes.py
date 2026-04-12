"""CORE_FILES/routes.py — Centralised URL routing helper."""
from django.urls import path, include
from rest_framework.routers import DefaultRouter


def build_monetization_router():
    """Build and return the full DefaultRouter for monetization_tools."""
    from ..urls import router
    return router


def get_urlpatterns():
    """Return urlpatterns list for inclusion in main urls.py."""
    return [path("monetization/", include("api.monetization_tools.urls"))]


class MonetizationRouter(DefaultRouter):
    """Extended router with custom trailing-slash and format-suffix config."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.trailing_slash = "/"
