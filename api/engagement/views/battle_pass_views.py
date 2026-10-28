# engagement/views/battle_pass_views.py
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from ..services import BattlePassService
from ..models.battle_pass import BattlePass, UserBattlePass, BattlePassTier
from ..utils.decorators import engagement_endpoint


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def battle_pass_current(request):
    """GET /engagement/battle-pass/ — current season info + user progress."""
    tenant = getattr(request.user, "tenant", None)
    bp = BattlePass.objects.filter(is_active=True, tenant=tenant).first()
    if not bp:
        return Response({"detail": "No active battle pass."}, status=404)
    ubp = BattlePassService.get_or_enroll(request.user, bp, tenant)
    tiers = list(BattlePassTier.objects.filter(battle_pass=bp).values(
        "tier_number", "xp_required", "free_coins", "free_xp", "free_item_slug",
        "free_badge_slug", "premium_coins", "premium_xp", "premium_item_slug",
        "premium_badge_slug", "is_milestone",
    ))
    return Response({
        "season_num":   bp.season_num,
        "name":         bp.name,
        "starts_at":    bp.starts_at,
        "ends_at":      bp.ends_at,
        "is_premium":   ubp.is_premium,
        "current_xp":   ubp.current_xp,
        "current_tier": ubp.current_tier,
        "last_claimed": ubp.last_claimed_tier,
        "premium_price": float(bp.premium_price_coins),
        "total_tiers":  bp.total_tiers,
        "unclaimed_tiers": ubp.unclaimed_tiers,
        "tiers":        tiers,
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@engagement_endpoint
def claim_tier(request):
    """POST /engagement/battle-pass/claim/ — body: {tier_number: N}"""
    tier_number = request.data.get("tier_number")
    if tier_number is None:
        return Response({"error": "tier_number required"}, status=400)
    tenant = getattr(request.user, "tenant", None)
    result = BattlePassService.claim_tier_rewards(request.user, int(tier_number), tenant)
    return Response({"success": True, **result})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@engagement_endpoint
def unlock_premium(request):
    """POST /engagement/battle-pass/premium/ — unlock premium track."""
    tenant = getattr(request.user, "tenant", None)
    result = BattlePassService.unlock_premium(request.user, tenant)
    return Response(result)


@api_view(["POST"])
@permission_classes([IsAdminUser])
def create_season(request):
    """POST /engagement/admin/battle-pass/ — create new season."""
    from ..models.battle_pass import BattlePass
    data   = request.data
    tenant = getattr(request.user, "tenant", None)
    bp = BattlePass.objects.create(
        name=data.get("name", "New Season"),
        season_num=data.get("season_num", 1),
        starts_at=data.get("starts_at"),
        ends_at=data.get("ends_at"),
        premium_price_coins=data.get("premium_price_coins", 500),
        total_tiers=data.get("total_tiers", 50),
        is_active=data.get("is_active", True),
        tenant=tenant,
    )
    return Response({"id": bp.pk, "name": bp.name, "season_num": bp.season_num}, status=201)
