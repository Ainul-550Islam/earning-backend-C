# fraud_detection/views_mfa.py — MFA API Views
# DRY: All logic in mfa_validator.py; views are thin HTTP adapters.
from __future__ import annotations
import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework import status

logger = logging.getLogger(__name__)

def _ok(d, st=200):  return Response({"success": True,  "data": d},    status=st)
def _err(m, st=400): return Response({"success": False, "error": str(m)}, status=st)


class MFAEnrollInitAPIView(APIView):
    """POST /mfa/enroll/init/ — generate TOTP secret + provisioning URI."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        from api.fraud_detection.mfa_validator import get_mfa_service
        svc    = get_mfa_service()
        secret = svc.generate_secret(request.user.pk)
        uri    = svc.get_provisioning_uri(request.user.pk, request.user.username)
        return _ok({"secret": secret, "provisioning_uri": uri,
                    "instructions": "Scan the QR code in your authenticator app, then confirm with /mfa/enroll/confirm/"}, 201)


class MFAEnrollConfirmAPIView(APIView):
    """POST /mfa/enroll/confirm/ — confirm enrollment with first TOTP code."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        code = request.data.get("code", "")
        if not code:
            return _err("code is required")
        from api.fraud_detection.mfa_validator import get_mfa_service
        svc   = get_mfa_service()
        valid = svc.confirm_enrollment(request.user.pk, code)
        if not valid:
            return _err("Invalid code — please check your authenticator and retry", 400)
        return _ok({"enrolled": True, "message": "MFA successfully enabled"})


class MFAValidateAPIView(APIView):
    """POST /mfa/validate/ — validate TOTP code for current session."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        code = request.data.get("code", "")
        if not code:
            return _err("code is required")
        from api.fraud_detection.mfa_validator import get_mfa_service
        svc   = get_mfa_service()
        valid = svc.validate_code(request.user.pk, code)
        if not valid:
            return _err("Invalid or expired code", 401)
        svc.mark_session_verified(request.user.pk)
        return _ok({"verified": True, "session_ttl_seconds": 3600})


class MFAValidateActionAPIView(APIView):
    """POST /mfa/validate-action/ — MFA check before high-risk action."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        code   = request.data.get("code", "")
        action = request.data.get("action", "generic")
        if not code:
            return _err("code is required")
        from api.fraud_detection.mfa_validator import get_mfa_service
        valid = get_mfa_service().validate_for_action(request.user.pk, code, action)
        if not valid:
            return _err(f"MFA failed for action '{action}'", 403)
        return _ok({"verified": True, "action": action})


class MFAStatusAPIView(APIView):
    """GET /mfa/status/ — current MFA enrollment and session status."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from api.fraud_detection.mfa_validator import get_mfa_service
        svc = get_mfa_service()
        return _ok({
            "enrolled":         svc.is_enrolled(request.user.pk),
            "session_verified": svc.is_session_verified(request.user.pk),
        })


class MFARevokeSessionAPIView(APIView):
    """POST /mfa/revoke-session/ — revoke MFA session (force re-verify)."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        from api.fraud_detection.mfa_validator import get_mfa_service
        get_mfa_service().revoke_session(request.user.pk)
        return _ok({"revoked": True})


class MFAAdminStatusAPIView(APIView):
    """GET /mfa/admin/users/<user_id>/status/ — admin: check user MFA status."""
    permission_classes = [IsAdminUser]

    def get(self, request, user_id: int):
        from api.fraud_detection.mfa_validator import get_mfa_service
        svc = get_mfa_service()
        return _ok({"user_id": user_id,
                    "enrolled": svc.is_enrolled(user_id),
                    "session_verified": svc.is_session_verified(user_id)})
