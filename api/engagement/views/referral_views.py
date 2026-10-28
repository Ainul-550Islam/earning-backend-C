# engagement/views/referral_views.py
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response

from ..services import ReferralService, GamificationEngine
from ..models.referral import Referral, ReferralProgram
from ..serializers import ReferralSerializer, ReferralProgramSerializer
from ..utils.decorators import engagement_endpoint


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def my_referrals(request):
    """
    GET /engagement/referrals/
    Returns all referrals made by the current user + their unique referral code.
    """
    referrals = (
        Referral.objects
        .filter(referrer=request.user)
        .select_related("referee", "program")
        .order_by("-created_at")
    )
    code = ReferralService.generate_code(request.user)
    return Response({
        "referral_code": code,
        "total_referrals": referrals.count(),
        "rewarded_referrals": referrals.filter(status="rewarded").count(),
        "results": ReferralSerializer(referrals, many=True).data,
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@engagement_endpoint
def register_referral(request):
    """
    POST /engagement/referrals/register/
    Body: { "code": "ABC123XYZ" }
    Called when a new user signs up with a referral code.
    """
    code = request.data.get("code")
    if not code:
        return Response({"error": "Referral code is required."}, status=400)

    # Find the referrer by code
    from django.contrib.auth import get_user_model
    User = get_user_model()

    # We store codes deterministically so we can reverse-lookup
    referrer = None
    for user in User.objects.all():
        if ReferralService.generate_code(user) == code.upper():
            referrer = user
            break

    if not referrer:
        return Response({"error": "Invalid referral code."}, status=404)

    tenant = getattr(request.user, "tenant", None)
    referral = ReferralService.register_referral(
        referrer=referrer,
        referee=request.user,
        code=code.upper(),
        tenant=tenant,
    )
    GamificationEngine.on_referral(referrer, referral, tenant=tenant)
    return Response({
        "success": True,
        "referral": ReferralSerializer(referral).data,
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def referral_program_detail(request):
    """
    GET /engagement/referrals/program/
    Returns the active referral program config (reward amounts etc.).
    """
    tenant  = getattr(request.user, "tenant", None)
    program = ReferralProgram.objects.filter(is_active=True, tenant=tenant).first()
    if not program:
        return Response({"detail": "No active referral program."}, status=404)
    return Response(ReferralProgramSerializer(program).data)


@api_view(["GET", "POST"])
@permission_classes([IsAdminUser])
def referral_program_admin(request):
    """
    Admin: GET all programs / POST create new program.
    GET /engagement/admin/referral-programs/
    """
    if request.method == "GET":
        programs = ReferralProgram.objects.all().order_by("-created_at")
        return Response(ReferralProgramSerializer(programs, many=True).data)

    serializer = ReferralProgramSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data, status=201)


@api_view(["GET", "PATCH", "DELETE"])
@permission_classes([IsAdminUser])
def referral_program_admin_detail(request, pk):
    """
    Admin: GET|PATCH|DELETE a referral program.
    GET|PATCH|DELETE /engagement/admin/referral-programs/<pk>/
    """
    try:
        program = ReferralProgram.objects.get(pk=pk)
    except ReferralProgram.DoesNotExist:
        return Response({"error": "Not found."}, status=404)

    if request.method == "GET":
        return Response(ReferralProgramSerializer(program).data)

    if request.method == "PATCH":
        serializer = ReferralProgramSerializer(program, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    program.delete()
    return Response(status=204)


@api_view(["GET"])
@permission_classes([IsAdminUser])
def all_referrals_admin(request):
    """
    Admin: GET all referrals across all users.
    GET /engagement/admin/referrals/
    """
    qs = Referral.objects.all().select_related("referrer", "referee", "program").order_by("-created_at")
    if status_filter := request.query_params.get("status"):
        qs = qs.filter(status=status_filter)
    return Response({
        "count": qs.count(),
        "results": ReferralSerializer(qs[:200], many=True).data,
    })
