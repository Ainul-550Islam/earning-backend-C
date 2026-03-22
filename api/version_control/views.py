# =============================================================================
# version_control/views.py
# =============================================================================
"""
Non-ViewSet views for version_control.

Covers:
  - Public version-check endpoint (no auth required — used by mobile clients)
  - Public maintenance status banner endpoint
  - Staff-only policy activation shortcut
  - Deployment webhook: auto-activate a policy when a new build deploys
"""

from __future__ import annotations

import hashlib
import hmac
import logging

from django.conf import settings
from django.utils import timezone
from api.tenants.mixins import TenantMixin
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .exceptions import (
    InvalidPlatformError,
    InvalidVersionStringError,
    MaintenanceAlreadyActiveError,
    UpdatePolicyNotFoundError,
)
from .models import AppUpdatePolicy, MaintenanceSchedule
from .permissions import AllowAny, IsStaffOnly
from .serializers import (
    AppUpdatePolicySerializer,
    MaintenanceStatusSerializer,
    VersionCheckResultSerializer,
)
from .services import MaintenanceService, UpdatePolicyService, VersionCheckService

logger = logging.getLogger(__name__)


# =============================================================================
# Public: Version check
# =============================================================================

class PublicVersionCheckView(APIView):
    """
    GET /version/check/?platform=ios&version=1.2.3

    Completely public — no authentication required.
    Used by mobile and desktop clients on startup to check for updates.

    Response:
        200 { update_required, update_type, target_version, ... }
        400 on bad input
    """

    permission_classes = [AllowAny]

    def get(self, request: Request) -> Response:
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
                platform=platform,
                client_version=client_version,
            )
        except InvalidVersionStringError as exc:
            return Response({"detail": str(exc.detail)}, status=status.HTTP_400_BAD_REQUEST)
        except InvalidPlatformError as exc:
            return Response({"detail": str(exc.detail)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            logger.exception(
                "public_version_check.unexpected platform=%s version=%s",
                platform, client_version,
            )
            return Response(
                {"detail": "Version check temporarily unavailable."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        return Response(VersionCheckResultSerializer(result).data)


# =============================================================================
# Public: Maintenance status banner
# =============================================================================

class PublicMaintenanceStatusView(APIView):
    """
    GET /version/maintenance-status/?platform=ios

    Returns the current maintenance status for a platform.
    Used by apps to show a maintenance banner without hitting the full API.

    Always returns 200 — the `is_active` field communicates the state.
    """

    permission_classes = [AllowAny]

    def get(self, request: Request) -> Response:
        platform = request.query_params.get("platform", "web").strip().lower()

        schedule = (
            MaintenanceSchedule.objects.currently_active()
            .order_by("scheduled_end")
            .first()
        )
        is_active = (
            schedule is not None
            and schedule.affects_platform(platform)
        )

        data = {
            "is_active":     is_active,
            "platform":      platform,
            "title":         schedule.title        if is_active else None,
            "description":   schedule.description  if is_active else None,
            "scheduled_end": schedule.scheduled_end if is_active else None,
        }
        return Response(MaintenanceStatusSerializer(data).data)


# =============================================================================
# Staff: Quickly activate a draft policy by ID
# =============================================================================

class ActivatePolicyView(APIView):
    """
    POST /version/policies/<pk>/activate/

    Activate a DRAFT AppUpdatePolicy.
    Convenience view for operators who don't want to use the ViewSet.

    Staff only.
    """

    permission_classes = [IsStaffOnly]

    def post(self, request: Request, pk: str) -> Response:
        try:
            policy = AppUpdatePolicy.objects.get(pk=pk)
        except AppUpdatePolicy.DoesNotExist:
            raise UpdatePolicyNotFoundError()

        policy = UpdatePolicyService.activate_policy(policy)
        logger.info(
            "policy.activated_via_view pk=%s by user=%s",
            pk, request.user.pk,
        )
        return Response(AppUpdatePolicySerializer(policy).data)


# =============================================================================
# Staff: Immediately start a maintenance window
# =============================================================================

class StartMaintenanceView(APIView):
    """
    POST /version/maintenance/<pk>/start/

    Start a scheduled MaintenanceSchedule immediately.
    Staff only.
    """

    permission_classes = [IsStaffOnly]

    def post(self, request: Request, pk: str) -> Response:
        try:
            schedule = MaintenanceSchedule.objects.get(pk=pk)
        except MaintenanceSchedule.DoesNotExist:
            return Response(
                {"detail": "Maintenance schedule not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            schedule = MaintenanceService.start_maintenance(schedule)
        except MaintenanceAlreadyActiveError as exc:
            return Response({"detail": str(exc.detail)}, status=exc.status_code)

        return Response({"detail": "Maintenance started.", "id": str(schedule.pk)})


# =============================================================================
# Webhook: CI/CD deploy hook — auto-activate policy on new build
# =============================================================================

class DeployWebhookView(APIView):
    """
    POST /version/webhook/deploy/

    Called by CI/CD pipelines after a successful deployment.
    Automatically activates any DRAFT policies matching the deployed version.

    Security: payload must be signed with HMAC-SHA256 using
    settings.VERSION_CONTROL_WEBHOOK_SECRET.

    Headers:
        X-Deploy-Signature: sha256=<hex_digest>

    Body:
        {
            "platform":   "ios",
            "version":    "2.0.0",
            "build_meta": { ... }   (optional)
        }
    """

    permission_classes = [AllowAny]  # auth done via HMAC signature

    _SECRET_SETTING = "VERSION_CONTROL_WEBHOOK_SECRET"

    def post(self, request: Request) -> Response:
        # ----------------------------------------------------------------
        # 1. Verify HMAC signature
        # ----------------------------------------------------------------
        if not self._verify_signature(request):
            logger.warning(
                "deploy_webhook.invalid_signature ip=%s",
                request.META.get("REMOTE_ADDR"),
            )
            return Response(
                {"detail": "Invalid signature."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # ----------------------------------------------------------------
        # 2. Parse body
        # ----------------------------------------------------------------
        platform = request.data.get("platform", "").strip().lower()
        version  = request.data.get("version",  "").strip()

        if not platform or not version:
            return Response(
                {"detail": "Both 'platform' and 'version' are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ----------------------------------------------------------------
        # 3. Find and activate matching DRAFT policies
        # ----------------------------------------------------------------
        from .choices import PolicyStatus

        policies = AppUpdatePolicy.objects.filter(
            platform=platform,
            target_version=version,
            status=PolicyStatus.DRAFT,
        )

        activated = []
        for policy in policies:
            try:
                UpdatePolicyService.activate_policy(policy)
                activated.append(str(policy.pk))
                logger.info(
                    "deploy_webhook.policy_activated pk=%s platform=%s version=%s",
                    policy.pk, platform, version,
                )
            except Exception:
                logger.exception(
                    "deploy_webhook.activation_failed pk=%s", policy.pk
                )

        return Response(
            {
                "platform":   platform,
                "version":    version,
                "activated":  activated,
                "count":      len(activated),
                "timestamp":  timezone.now().isoformat(),
            },
            status=status.HTTP_200_OK,
        )

    def _verify_signature(self, request: Request) -> bool:
        secret = getattr(settings, self._SECRET_SETTING, "")
        if not secret:
            # No secret configured → skip signature check (dev mode)
            logger.warning(
                "deploy_webhook.no_secret_configured — accepting all requests"
            )
            return True

        header_sig = request.META.get("HTTP_X_DEPLOY_SIGNATURE", "")
        if not header_sig.startswith("sha256="):
            return False

        expected = hmac.new(
            secret.encode(),
            request.body,
            hashlib.sha256,
        ).hexdigest()

        return hmac.compare_digest(
            header_sig[7:],  # strip "sha256="
            expected,
        )
