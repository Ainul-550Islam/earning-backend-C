# =============================================================================
# fraud_detection/views_tenant.py  — TENANT / ORGANISATION API VIEWS
# DRY: Uses tenant_permissions.py; no duplicate auth logic.
# =============================================================================
from __future__ import annotations
import logging, secrets
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework import status

logger = logging.getLogger(__name__)


def _ok(data, st=200):  return Response({"success": True,  "data": data},  status=st)
def _err(msg, st=400):  return Response({"success": False, "error": msg}, status=st)


class OrganisationListCreateAPIView(APIView):
    """GET /tenant/organisations/  — list user's orgs
       POST /tenant/organisations/  — create a new org"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            from api.fraud_detection.models_tenant import OrganisationMember
            memberships = OrganisationMember.objects.filter(
                user=request.user
            ).select_related("organisation").order_by("organisation__name")
            data = [
                {"id": str(m.organisation.pk), "name": m.organisation.name,
                 "slug": m.organisation.slug, "plan": m.organisation.plan,
                 "status": m.organisation.status, "role": m.role}
                for m in memberships
            ]
            return _ok({"organisations": data, "total": len(data)})
        except Exception as exc:
            logger.error("OrganisationListCreateAPIView.get: %s", exc)
            return _err(str(exc), 500)

    def post(self, request):
        try:
            from api.fraud_detection.models_tenant import Organisation, OrganisationMember
            from django.utils.text import slugify
            name = request.data.get("name", "").strip()
            if not name:
                return _err("name is required")
            slug    = slugify(name)
            api_key = secrets.token_urlsafe(32)
            org, created = Organisation.objects.get_or_create(
                slug=slug,
                defaults={"name": name, "api_key": api_key,
                          "plan": request.data.get("plan", "free")},
            )
            if not created:
                return _err(f"Organisation '{name}' already exists", 409)
            OrganisationMember.objects.create(
                organisation=org, user=request.user, role="owner"
            )
            return _ok({"id": str(org.pk), "name": org.name, "slug": org.slug,
                        "api_key": api_key, "plan": org.plan}, 201)
        except Exception as exc:
            logger.error("OrganisationListCreateAPIView.post: %s", exc)
            return _err(str(exc), 500)


class OrganisationDetailAPIView(APIView):
    """GET/PATCH /tenant/organisations/<pk>/"""
    permission_classes = [IsAuthenticated]

    def _get_org(self, request, pk):
        from api.fraud_detection.models_tenant import Organisation, OrganisationMember
        try:
            org = Organisation.objects.get(pk=pk)
            OrganisationMember.objects.get(organisation=org, user=request.user)
            return org, None
        except Organisation.DoesNotExist:
            return None, _err("Organisation not found", 404)
        except OrganisationMember.DoesNotExist:
            return None, _err("Access denied", 403)

    def get(self, request, pk):
        org, err = self._get_org(request, pk)
        if err: return err
        return _ok({"id": str(org.pk), "name": org.name, "slug": org.slug,
                    "plan": org.plan, "status": org.status,
                    "max_users": org.max_users, "metadata": org.metadata})

    def patch(self, request, pk):
        from api.fraud_detection.models_tenant import OrganisationMember
        org, err = self._get_org(request, pk)
        if err: return err
        member = OrganisationMember.objects.get(organisation=org, user=request.user)
        if not member.is_admin():
            return _err("Admin role required", 403)
        updatable = {k: v for k, v in request.data.items()
                     if k in ("name", "metadata", "max_users")}
        for field, value in updatable.items():
            setattr(org, field, value)
        org.save(update_fields=list(updatable.keys()) + ["updated_at"])
        return _ok({"id": str(org.pk), "updated_fields": list(updatable.keys())})


class OrganisationMembersAPIView(APIView):
    """GET /tenant/organisations/<pk>/members/"""
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        from api.fraud_detection.models_tenant import OrganisationMember
        qs = OrganisationMember.objects.filter(
            organisation_id=pk
        ).select_related("user").order_by("role", "joined_at")
        data = [{"user_id": m.user_id, "username": m.user.username,
                 "role": m.role, "joined_at": m.joined_at.isoformat()} for m in qs]
        return _ok({"members": data, "total": len(data)})

    def post(self, request, pk):
        """Invite a user to this organisation."""
        from api.fraud_detection.models_tenant import Organisation, OrganisationMember
        from django.contrib.auth import get_user_model
        User = get_user_model()
        try:
            org    = Organisation.objects.get(pk=pk)
            caller = OrganisationMember.objects.get(organisation=org, user=request.user)
            if not caller.is_admin():
                return _err("Admin role required", 403)
            user_id = request.data.get("user_id")
            role    = request.data.get("role", "viewer")
            user    = User.objects.get(pk=user_id)
            member, created = OrganisationMember.objects.get_or_create(
                organisation=org, user=user, defaults={"role": role}
            )
            if not created:
                return _err("User is already a member", 409)
            return _ok({"user_id": user_id, "role": role, "created": True}, 201)
        except Exception as exc:
            return _err(str(exc), 400)


class OrganisationRotateKeyAPIView(APIView):
    """POST /tenant/organisations/<pk>/rotate-key/  — rotate API key (admin only)"""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        from api.fraud_detection.models_tenant import Organisation, OrganisationMember
        try:
            org    = Organisation.objects.get(pk=pk)
            member = OrganisationMember.objects.get(organisation=org, user=request.user)
            if not member.is_admin():
                return _err("Admin role required", 403)
            org.api_key = secrets.token_urlsafe(32)
            org.save(update_fields=["api_key"])
            return _ok({"new_api_key": org.api_key,
                        "warning": "Previous key is now invalid. Update all integrations."})
        except Exception as exc:
            return _err(str(exc), 400)
