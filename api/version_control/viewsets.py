# =============================================================================
# version_control/viewsets.py
# =============================================================================
"""
DRF ViewSets for the version_control application.

Endpoints summary:
  GET  /version-check/          → public version-check (no auth required)
  --- AppUpdatePolicy ---
  GET    /policies/             → list (staff)
  POST   /policies/             → create draft (staff)
  GET    /policies/{id}/        → retrieve (staff)
  PATCH  /policies/{id}/        → update (staff)
  POST   /policies/{id}/activate/   → activate draft
  POST   /policies/{id}/deactivate/ → deactivate
  --- MaintenanceSchedule ---
  GET    /maintenance/          → list (staff)
  POST   /maintenance/          → schedule new window (staff)
  GET    /maintenance/{id}/     → retrieve (staff)
  POST   /maintenance/{id}/start/   → start now
  POST   /maintenance/{id}/end/     → end active window
  POST   /maintenance/{id}/cancel/  → cancel scheduled window
  GET    /maintenance/status/       → public maintenance status (any client)
  --- PlatformRedirect ---
  GET    /redirects/            → list (auth)
  POST   /redirects/            → create (staff)
  GET    /redirects/{id}/       → retrieve (auth)
  PATCH  /redirects/{id}/       → update (staff)
  DELETE /redirects/{id}/       → delete (staff)
"""

from __future__ import annotations

import logging

from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response

from .exceptions import (
    InvalidPlatformError,
    InvalidVersionStringError,
    MaintenanceAlreadyActiveError,
    MaintenanceNotFoundError,
    PolicyAlreadyExistsError,
)
from .filters import AppUpdatePolicyFilter, MaintenanceScheduleFilter, PlatformRedirectFilter
from .models import AppUpdatePolicy, MaintenanceSchedule, PlatformRedirect
from .permissions import AllowAny, IsStaffOnly, IsStaffOrReadOnly
from .serializers import (
    AppUpdatePolicyCreateSerializer,
    AppUpdatePolicySerializer,
    MaintenanceScheduleCreateSerializer,
    MaintenanceScheduleSerializer,
    MaintenanceStatusSerializer,
    PlatformRedirectSerializer,
    VersionCheckResultSerializer,
)
from .services import (
    MaintenanceService,
    RedirectService,
    UpdatePolicyService,
    VersionCheckService,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Version Check (public)
# =============================================================================

class VersionCheckViewSet(viewsets.ViewSet):
    """
    Single-action public endpoint.
    GET /version-check/?platform=ios&version=1.0.0
    """
    permission_classes = [AllowAny]

    def list(self, request: Request) -> Response:
        platform       = request.query_params.get("platform", "").strip().lower()
        client_version = request.query_params.get("version",  "").strip()

        if not platform:
            return Response(
                {"detail": "Query param 'platform' is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not client_version:
            return Response(
                {"detail": "Query param 'version' is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            result = VersionCheckService.check(
                platform=platform, client_version=client_version
            )
        except (InvalidVersionStringError, InvalidPlatformError) as exc:
            return Response({"detail": str(exc.detail)}, status=exc.status_code)

        serializer = VersionCheckResultSerializer(result)
        return Response(serializer.data)


# =============================================================================
# AppUpdatePolicy
# =============================================================================

class AppUpdatePolicyViewSet(
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [IsStaffOnly]
    filterset_class    = AppUpdatePolicyFilter
    ordering_fields    = ["created_at", "platform", "update_type", "status"]
    ordering           = ["-created_at"]

    def get_queryset(self):
        return AppUpdatePolicy.objects.select_related("created_by").all()

    def get_serializer_class(self):
        if self.action == "create":
            return AppUpdatePolicyCreateSerializer
        return AppUpdatePolicySerializer

    def perform_create(self, serializer) -> None:
        vd = serializer.validated_data
        UpdatePolicyService.create_policy(
            platform=vd["platform"],
            min_version=vd["min_version"],
            max_version=vd.get("max_version", ""),
            target_version=vd["target_version"],
            update_type=vd.get("update_type", "optional"),
            release_notes=vd.get("release_notes", ""),
            release_notes_url=vd.get("release_notes_url", ""),
            force_update_after=vd.get("force_update_after"),
            created_by=self.request.user,
            metadata=vd.get("metadata") or {},
        )

    def create(self, request: Request, *args, **kwargs) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            self.perform_create(serializer)
        except PolicyAlreadyExistsError as exc:
            return Response({"detail": str(exc.detail)}, status=exc.status_code)
        return Response(
            {"detail": "Policy created in DRAFT status."},
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"], url_path="activate")
    def activate(self, request: Request, pk=None) -> Response:
        policy = self.get_object()
        policy = UpdatePolicyService.activate_policy(policy)
        return Response(AppUpdatePolicySerializer(policy).data)

    @action(detail=True, methods=["post"], url_path="deactivate")
    def deactivate(self, request: Request, pk=None) -> Response:
        policy = self.get_object()
        policy = UpdatePolicyService.deactivate_policy(policy)
        return Response(AppUpdatePolicySerializer(policy).data)


# =============================================================================
# MaintenanceSchedule
# =============================================================================

class MaintenanceScheduleViewSet(
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [IsStaffOnly]
    filterset_class    = MaintenanceScheduleFilter
    ordering_fields    = ["scheduled_start", "status", "created_at"]
    ordering           = ["-scheduled_start"]

    def get_queryset(self):
        return MaintenanceSchedule.objects.all()

    def get_serializer_class(self):
        if self.action == "create":
            return MaintenanceScheduleCreateSerializer
        return MaintenanceScheduleSerializer

    def create(self, request: Request, *args, **kwargs) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        vd = serializer.validated_data
        schedule = MaintenanceService.create_schedule(
            title=vd["title"],
            scheduled_start=vd["scheduled_start"],
            scheduled_end=vd["scheduled_end"],
            description=vd.get("description", ""),
            platforms=vd.get("platforms") or [],
            notify_users=vd.get("notify_users", True),
            bypass_token=vd.get("bypass_token", ""),
        )
        return Response(
            MaintenanceScheduleSerializer(schedule).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"], url_path="start")
    def start(self, request: Request, pk=None) -> Response:
        schedule = self.get_object()
        try:
            schedule = MaintenanceService.start_maintenance(schedule)
        except MaintenanceAlreadyActiveError as exc:
            return Response({"detail": str(exc.detail)}, status=exc.status_code)
        return Response(MaintenanceScheduleSerializer(schedule).data)

    @action(detail=True, methods=["post"], url_path="end")
    def end(self, request: Request, pk=None) -> Response:
        schedule = self.get_object()
        try:
            schedule = MaintenanceService.end_maintenance(schedule)
        except MaintenanceNotFoundError as exc:
            return Response({"detail": str(exc.detail)}, status=exc.status_code)
        return Response(MaintenanceScheduleSerializer(schedule).data)

    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel(self, request: Request, pk=None) -> Response:
        schedule = self.get_object()
        schedule = MaintenanceService.cancel_maintenance(schedule)
        return Response(MaintenanceScheduleSerializer(schedule).data)

    @action(detail=False, methods=["get"], url_path="status",
            permission_classes=[AllowAny])
    def maintenance_status(self, request: Request) -> Response:
        """
        Public endpoint — returns current maintenance status for a platform.
        Query param: ?platform=ios  (default: web)
        """
        platform = request.query_params.get("platform", "web").strip().lower()
        schedule = (
            MaintenanceSchedule.objects.currently_active()
            .order_by("scheduled_end")
            .first()
        )
        is_active = schedule is not None and schedule.affects_platform(platform)
        data = {
            "is_active":     is_active,
            "platform":      platform,
            "title":         schedule.title        if is_active else None,
            "description":   schedule.description  if is_active else None,
            "scheduled_end": schedule.scheduled_end if is_active else None,
        }
        return Response(MaintenanceStatusSerializer(data).data)


# =============================================================================
# PlatformRedirect
# =============================================================================

class PlatformRedirectViewSet(
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class   = PlatformRedirectSerializer
    permission_classes = [IsStaffOrReadOnly]
    filterset_class    = PlatformRedirectFilter
    ordering_fields    = ["platform", "created_at"]
    ordering           = ["platform"]

    def get_queryset(self):
        return PlatformRedirect.objects.all()

    @action(detail=False, methods=["get"], url_path="resolve",
            permission_classes=[AllowAny])
    def resolve(self, request: Request) -> Response:
        """
        Public endpoint — resolve the redirect URL for a platform.
        GET /redirects/resolve/?platform=ios
        """
        platform = request.query_params.get("platform", "").strip().lower()
        if not platform:
            return Response(
                {"detail": "Query param 'platform' is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        url = RedirectService.get_redirect_url(platform)
        if url is None:
            return Response(
                {"detail": f"No redirect configured for platform '{platform}'."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response({"platform": platform, "url": url})
