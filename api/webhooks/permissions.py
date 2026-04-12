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
