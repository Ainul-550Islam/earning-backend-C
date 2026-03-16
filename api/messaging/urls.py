"""
Messaging URLs — DRF Router registration.
"""
from django.urls import path, include
from .views import MessageAttachmentUploadView
from rest_framework.routers import DefaultRouter
from .viewsets import (
    InternalChatViewSet,
    AdminBroadcastViewSet,
    SupportThreadViewSet,
    UserInboxViewSet,
)

router = DefaultRouter()
router.register(r"chats", InternalChatViewSet, basename="internalchat")
router.register(r"broadcasts", AdminBroadcastViewSet, basename="adminbroadcast")
router.register(r"support", SupportThreadViewSet, basename="supportthread")
router.register(r"inbox", UserInboxViewSet, basename="userinbox")

urlpatterns = [
    path("upload/", MessageAttachmentUploadView.as_view(), name="messaging-upload"),
    path("", include(router.urls)),
]
