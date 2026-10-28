# Copyright © 2026 Ainul Enterprise Engine. All Rights Reserved.
"""
Ainul Enterprise Engine — Webhook Dispatch System
permissions.py: Custom DRF permission classes.
"""

from rest_framework.permissions import BasePermission, IsAuthenticated


class IsEndpointOwner(BasePermission):
    """
    Ainul Enterprise Engine — Grants access only if the request user owns
    the WebhookEndpoint being accessed.  Used for nested subscription routes.
    """

    message = "You do not have permission to access this endpoint."

    def has_object_permission(self, request, view, obj):
        # obj may be a WebhookEndpoint or a WebhookSubscription
        endpoint = getattr(obj, "endpoint", obj)
        return endpoint.owner_id == request.user.pk


class IsSystemOrAdmin(BasePermission):
    """
    Ainul Enterprise Engine — Permits only staff users or service accounts
    to call internal emit/management APIs.
    """

    message = "This endpoint is restricted to staff and system accounts."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and (request.user.is_staff or request.user.is_superuser)
        )

class IsOwnerOrReadOnly(IsAuthenticated):
    """
    Ainul Enterprise Engine — Object-level permission.

    SAFE methods (GET, HEAD, OPTIONS) are allowed for any authenticated user.
    Write methods (POST, PUT, PATCH, DELETE) require the user to own the object.

    Used by: WebhookFilterViewSet, WebhookTemplateViewSet, WebhookBatchViewSet,
             WebhookSecretViewSet, WebhookHealthViewSet, WebhookReplayViewSet,
             InboundWebhookViewSet, InboundWebhookLogViewSet,
             WebhookAnalyticsViewSet, AdminWebhookViewSet.

    FIX: Was imported by 10 viewsets but never defined — caused ImportError at startup.
    """

    message = "You must be the owner to perform this action."

    def has_object_permission(self, request, view, obj):
        from rest_framework.permissions import SAFE_METHODS
        if request.method in SAFE_METHODS:
            return True
        owner = (
            getattr(obj, "owner", None)
            or getattr(obj, "created_by", None)
            or getattr(getattr(obj, "endpoint", None), "owner", None)
        )
        return owner is not None and owner == request.user


class IsSuperUser(IsAuthenticated):
    """
    Ainul Enterprise Engine — Permits only superusers.

    Used by AdminWebhookViewSet for destructive / privileged operations.

    FIX: Was imported by AdminWebhookViewSet but never defined.
    """

    message = "Only superusers can perform this action."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_superuser
        )
