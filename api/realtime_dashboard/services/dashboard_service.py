"""
Dashboard service for Real-time Dashboard Backend.

DRY FIX (v1.5.0 — 360-degree audit): create_dashboard() was defined but
UserDashboardViewSet.perform_create() called serializer.save(user_id=...)
directly instead (verified empirically — nothing in the codebase called
create_dashboard() outside its own tests). Tracing it also surfaced a
latent bug that would have fired the moment it WAS wired up: the old
`layout_id=data.get('layout')` line assumed `data['layout']` was a raw
primary key, but UserDashboardSerializer auto-generates `layout` as a
PrimaryKeyRelatedField, so validated_data['layout'] is actually a
DashboardLayout *instance* — assigning an instance to the `_id`-suffixed
kwarg is wrong. Rewritten to trust validated_data wholesale
(`UserDashboard.objects.create(**data)`), which is exactly what
`serializer.save()` already does under the hood, so there is no
instance-vs-id remapping left to get wrong.
"""
from typing import Optional, Dict, Any

from ..models.user_dashboard import UserDashboard


class DashboardService:
    """
    Service for dashboard operations.
    """

    def __init__(self) -> None:
        """Initialize the dashboard service."""
        pass

    def create_dashboard(self, data: Dict[str, Any]) -> UserDashboard:
        """
        Create a new dashboard from DRF-validated data (plus any extra
        keys the caller merges in, e.g. user_id from request.user).

        WIRED (v1.5.0): UserDashboardViewSet.perform_create() delegates
        here, passing {**serializer.validated_data, 'user_id': ...} —
        user_id is never taken from client input (see perform_create's
        docstring for the ownership rationale).

        Args:
            data: Dashboard data — validated_data plus injected user_id.

        Returns:
            UserDashboard instance
        """
        return UserDashboard.objects.create(**data)

    def get_dashboard(self, dashboard_id: int) -> Optional[UserDashboard]:
        """
        Get a dashboard by ID.

        NOTE: not currently called outside this service/its tests — DRF's
        default retrieve() correctly uses UserDashboardViewSet's own
        get_queryset() (which additionally scopes by owner unless staff;
        see that viewset). Left available for a future non-HTTP caller,
        same rationale as RealTimeMetricService.get_metric().

        Args:
            dashboard_id: Dashboard ID

        Returns:
            UserDashboard instance or None
        """
        try:
            return UserDashboard.objects.get(id=dashboard_id)
        except UserDashboard.DoesNotExist:
            return None

    def get_user_dashboards(self, user_id: str) -> list:
        """
        Get all active dashboards for a user.

        FIXED: was `UserDashboard.objects.filter(user_id=user_id,
        status='active')`. Now uses DashboardManager methods - DRY.

        Args:
            user_id: User ID

        Returns:
            List of active UserDashboard instances for the user
        """
        return list(UserDashboard.objects.by_user(user_id).active())
