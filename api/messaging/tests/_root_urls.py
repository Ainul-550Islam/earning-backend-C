"""
Minimal root URLConf used only for standalone testing of this module.

In the real host project (earning_backend), `messaging.urls` is mounted
under the `messaging/` prefix in the project's own root urls.py. This file
reproduces that exact mount point so the Django test client can resolve
real HTTP requests (e.g. self.client.post("/messaging/upload/")) when this
app is tested in isolation. It is never imported outside of test settings.
"""
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("messaging/", include("messaging.urls")),
]
