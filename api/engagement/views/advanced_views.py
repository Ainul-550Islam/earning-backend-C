# engagement/views/advanced_views.py
"""
All advanced system views in one file.
Each section clearly marked.
"""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from ..utils.decorators import engagement_endpoint


# ══════════════════════════════════════════════════════════════════════════════
# SOCIAL FEED
# ══════════════════════════════════════════════════════════════════════════════

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def social_feed(request):
    """GET /engagement/social/feed/?scope=global|friends|guild"""
    from ..services import SocialService
    scope = request.query_params.get("scope", "global")
    limit = int(request.query_params.get("limit", 20))
    items = SocialService.get_feed(request.user, scope=scope, limit=limit)
    data  = [{
        "id": i.pk, "type": i.type, "title": i.title, "body": i.body,
        "icon": i.icon, "username": i.user.username,
        "like_count": i.like_count, "comment_count": i.comment_count,
        "created_at": i.created_at,
    } for i in items]
    return Response({"results": data, "scope": scope})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@engagement_endpoint
def like_feed_item(request, pk):
    """POST /engagement/social/feed/<pk>/like/"""
    from ..services import SocialService
    reaction = request.data.get("reaction", "like")
    result   = SocialService.like(request.user, pk, reaction=reaction)
    return Response(result)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@engagement_endpoint
def comment_feed_item(request, pk):
    """POST /engagement/social/feed/<pk>/comment/"""
    from ..services import SocialService
    body    = request.data.get("body", "")
    comment = SocialService.comment(request.user, pk, body=body)
    return Response({"id": comment.pk, "body": comment.body, "created_at": comment.created_at})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@engagement_endpoint
def send_friend_request(request):
    """POST /engagement/social/friends/request/ — body: {user_id: N}"""
    from ..services import SocialService
    from django.contrib.auth import get_user_model
    User = get_user_model()
    try:
        receiver = User.objects.get(pk=request.data.get("user_id"))
    except User.DoesNotExist:
        return Response({"error": "User not found."}, status=404)
    fs = SocialService.send_friend_request(request.user, receiver)
    return Response({"status": fs.status, "id": fs.pk})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@engagement_endpoint
def accept_friend_request(request, pk):
    """POST /engagement/social/friends/<pk>/accept/"""
    from ..services import SocialService
    fs = SocialService.accept_friend_request(request.user, pk)
    return Response({"status": fs.status})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def friends_list(request):
    """GET /engagement/social/friends/"""
    from ..services import SocialService
    friends = SocialService.friends_list(request.user)
    return Response({"results": [{"id": u.pk, "username": u.username} for u in friends]})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@engagement_endpoint
def follow_user(request, user_id):
    """POST /engagement/social/follow/<user_id>/"""
    from ..services import SocialService
    from django.contrib.auth import get_user_model
    User = get_user_model()
    try:
        followee = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return Response(status=404)
    result = SocialService.follow(request.user, followee)
    return Response(result)


# ══════════════════════════════════════════════════════════════════════════════
# LOOT BOX / CHEST
# ══════════════════════════════════════════════════════════════════════════════

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def my_chests(request):
    """GET /engagement/chests/ — user's chest inventory."""
    from ..models.loot_box import UserChest
    from django.utils import timezone
    qs = UserChest.objects.filter(user=request.user, quantity__gt=0).select_related("chest_type")
    qs = qs.exclude(expires_at__lt=timezone.now())
    return Response([{
        "chest_slug": c.chest_type.slug, "name": c.chest_type.name,
        "icon": c.chest_type.icon, "rarity": c.chest_type.rarity,
        "quantity": c.quantity,
    } for c in qs])


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@engagement_endpoint
def open_chest(request):
    """POST /engagement/chests/open/ — body: {chest_slug: '...'}"""
    from ..services import LootBoxService
    slug   = request.data.get("chest_slug")
    if not slug:
        return Response({"error": "chest_slug required"}, status=400)
    tenant = getattr(request.user, "tenant", None)
    result = LootBoxService.open_chest(request.user, slug, tenant=tenant)
    return Response({"success": True, **result})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@engagement_endpoint
def buy_chest(request):
    """POST /engagement/chests/buy/ — body: {chest_slug: '...'}"""
    from ..services import LootBoxService
    slug   = request.data.get("chest_slug")
    tenant = getattr(request.user, "tenant", None)
    result = LootBoxService.buy_chest(request.user, slug, tenant=tenant)
    return Response(result)


# ══════════════════════════════════════════════════════════════════════════════
# PRESTIGE & MILESTONES
# ══════════════════════════════════════════════════════════════════════════════

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def prestige_status(request):
    """GET /engagement/prestige/ — current prestige level + multipliers."""
    from ..services import PrestigeService
    from ..models.prestige import PrestigeLevel, UserPrestige
    info   = PrestigeService.get_multipliers(request.user)
    next_p = PrestigeLevel.objects.filter(level=info["prestige_level"] + 1).first()
    return Response({
        **info,
        "next_required_level": next_p.required_level if next_p else None,
        "next_perks": {
            "coin_multiplier": float(next_p.coin_multiplier) if next_p else None,
            "xp_multiplier":   float(next_p.xp_multiplier) if next_p else None,
        } if next_p else None,
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@engagement_endpoint
def do_prestige(request):
    """POST /engagement/prestige/commit/"""
    from ..services import PrestigeService
    result = PrestigeService.attempt_prestige(request.user, getattr(request.user, "tenant", None))
    return Response(result)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def milestones_list(request):
    """GET /engagement/milestones/"""
    from ..services import MilestoneService
    from ..models.prestige import Milestone, UserMilestone
    unlocked_ids = set(UserMilestone.objects.filter(user=request.user).values_list("milestone_id", flat=True))
    milestones   = Milestone.objects.filter(is_active=True).order_by("metric", "order")
    return Response([{
        "id": m.pk, "slug": m.slug, "name": m.name,
        "metric": m.metric, "threshold": m.threshold,
        "coin_reward": float(m.coin_reward), "xp_reward": m.xp_reward,
        "is_unlocked": m.pk in unlocked_ids,
        "current_value": MilestoneService._get_metric(request.user, m.metric),
    } for m in milestones])


# ══════════════════════════════════════════════════════════════════════════════
# SEASONAL EVENTS
# ══════════════════════════════════════════════════════════════════════════════

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def live_event(request):
    """GET /engagement/events/live/"""
    from ..services import SeasonalEventService
    from ..models.seasonal_event import UserEventProgress, UserEventCurrency
    tenant = getattr(request.user, "tenant", None)
    event  = SeasonalEventService.get_live_event(tenant)
    if not event:
        return Response({"event": None})

    missions = list(event.missions.all().values(
        "id", "slug", "title", "description", "icon",
        "target", "action", "coin_reward", "xp_reward", "event_currency_reward",
    ))
    progress_map = {
        p.mission_id: {"progress": p.progress, "times_completed": p.times_completed}
        for p in UserEventProgress.objects.filter(user=request.user, event=event)
    }
    currency = UserEventCurrency.objects.filter(user=request.user, event=event).first()

    for m in missions:
        m.update(progress_map.get(m["id"], {"progress": 0, "times_completed": 0}))

    return Response({
        "id": event.pk, "name": event.name, "slug": event.slug,
        "ends_at": event.ends_at, "time_remaining": event.time_remaining_seconds,
        "theme_color": event.theme_color,
        "coin_multiplier": float(event.coin_multiplier),
        "xp_multiplier":  float(event.xp_multiplier),
        "currency_name":  event.event_currency_name,
        "currency_icon":  event.event_currency_icon,
        "currency_balance": currency.balance if currency else 0,
        "missions": missions,
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@engagement_endpoint
def buy_event_item(request):
    """POST /engagement/events/shop/buy/ — body: {item_id: N}"""
    from ..services import SeasonalEventService
    item_id = request.data.get("item_id")
    if not item_id:
        return Response({"error": "item_id required"}, status=400)
    result = SeasonalEventService.buy_event_item(
        request.user, int(item_id), getattr(request.user, "tenant", None)
    )
    return Response(result)


# ══════════════════════════════════════════════════════════════════════════════
# COMBO & ENERGY
# ══════════════════════════════════════════════════════════════════════════════

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def combo_status(request):
    """GET /engagement/combo/?action=spin"""
    from ..services import ComboService, EnergyService
    action = request.query_params.get("action", "spin")
    combo  = ComboService.get_combo(request.user, action)
    energy = EnergyService.get_energy(request.user)
    return Response({
        "combo": combo,
        "energy": {
            "current": energy.compute_current(),
            "max":     energy.max_energy,
        },
    })


# ══════════════════════════════════════════════════════════════════════════════
# SCRATCH CARD & LOGIN CALENDAR
# ══════════════════════════════════════════════════════════════════════════════

@api_view(["POST"])
@permission_classes([IsAuthenticated])
@engagement_endpoint
def scratch_card(request):
    """POST /engagement/scratch/ — body: {template_slug: '...'}"""
    from ..services import ScratchCardService
    slug   = request.data.get("template_slug")
    if not slug:
        return Response({"error": "template_slug required"}, status=400)
    result = ScratchCardService.scratch(request.user, slug, getattr(request.user, "tenant", None))
    return Response({"success": True, **result})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def login_calendar(request):
    """GET /engagement/calendar/ — current month calendar."""
    from ..services import LoginCalendarService
    from ..models.scratch_card import UserLoginCalendarProgress
    tenant   = getattr(request.user, "tenant", None)
    calendar = LoginCalendarService.get_current_calendar(tenant)
    if not calendar:
        return Response({"calendar": None})
    days  = list(calendar.days.all().values(
        "day_number", "coins", "xp", "item_slug", "is_milestone", "icon",
    ))
    prog  = UserLoginCalendarProgress.objects.filter(
        user=request.user, calendar=calendar
    ).first()
    return Response({
        "month": calendar.month, "year": calendar.year,
        "claimed_days": prog.claimed_days if prog else [],
        "days": days,
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@engagement_endpoint
def claim_calendar_day(request):
    """POST /engagement/calendar/claim/"""
    from ..services import LoginCalendarService
    result = LoginCalendarService.claim_today(request.user, getattr(request.user, "tenant", None))
    return Response(result)


# ══════════════════════════════════════════════════════════════════════════════
# AUCTION HOUSE
# ══════════════════════════════════════════════════════════════════════════════

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def auctions_list(request):
    """GET /engagement/auctions/"""
    from ..models.auction import Auction
    from django.utils import timezone
    now  = timezone.now()
    qs   = Auction.objects.filter(status="active", ends_at__gte=now).order_by("ends_at")
    return Response([{
        "id": a.pk, "title": a.title, "icon": a.icon,
        "current_bid": float(a.current_bid), "starting_bid": float(a.starting_bid),
        "total_bids": a.total_bids,
        "ends_at": a.ends_at, "time_remaining": a.time_remaining_seconds,
    } for a in qs[:50]])


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@engagement_endpoint
def place_bid(request, pk):
    """POST /engagement/auctions/<pk>/bid/ — body: {amount: 150}"""
    from ..services import AuctionService
    from decimal import Decimal
    amount = request.data.get("amount")
    if not amount:
        return Response({"error": "amount required"}, status=400)
    result = AuctionService.place_bid(
        request.user, pk, Decimal(str(amount)), getattr(request.user, "tenant", None)
    )
    return Response(result)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@engagement_endpoint
def watch_auction(request, pk):
    """POST /engagement/auctions/<pk>/watch/"""
    from ..services import AuctionService
    result = AuctionService.watch(request.user, pk, getattr(request.user, "tenant", None))
    return Response(result)


# ══════════════════════════════════════════════════════════════════════════════
# CAMPAIGN / AB TESTS / FEATURE FLAGS (admin)
# ══════════════════════════════════════════════════════════════════════════════

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def feature_flag_check(request, slug):
    """GET /engagement/flags/<slug>/ — is this flag enabled for me?"""
    from ..services import FeatureFlagService
    enabled = FeatureFlagService.is_enabled(request.user, slug)
    config  = FeatureFlagService.get_config(slug)
    return Response({"slug": slug, "enabled": enabled, "config": config})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def ab_variant(request, test_slug):
    """GET /engagement/ab/<test_slug>/ — which variant am I in?"""
    from ..services import ABTestService
    variant = ABTestService.get_variant(request.user, test_slug)
    if not variant:
        return Response({"variant": None})
    return Response({"slug": variant.slug, "name": variant.name, "config": variant.config})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def ab_convert(request, test_slug):
    """POST /engagement/ab/<test_slug>/convert/ — track conversion event."""
    from ..services import ABTestService
    ABTestService.track_conversion(request.user, test_slug)
    return Response({"tracked": True})


# ══════════════════════════════════════════════════════════════════════════════
# ANALYTICS DASHBOARD (admin)
# ══════════════════════════════════════════════════════════════════════════════

@api_view(["GET"])
@permission_classes([IsAdminUser])
def analytics_dashboard(request):
    """GET /engagement/admin/analytics/ — last 30 days KPIs."""
    from ..services import AnalyticsService
    days    = int(request.query_params.get("days", 30))
    tenant  = getattr(request.user, "tenant", None)
    metrics = AnalyticsService.last_n_days_metrics(days, tenant)
    return Response([{
        "date": str(m.date), "dau": m.dau,
        "checkins": m.checkins, "spins": m.spins,
        "quests_completed": m.quests_completed,
        "achievements_unlocked": m.achievements_unlocked,
        "shop_purchases": m.shop_purchases,
        "coins_distributed": float(m.coins_distributed),
        "new_users": m.new_users,
    } for m in metrics])


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def my_analytics(request):
    """GET /engagement/analytics/me/ — my engagement events summary."""
    from ..services import AnalyticsService
    days    = int(request.query_params.get("days", 7))
    summary = AnalyticsService.user_event_summary(request.user, days=days)
    return Response({"days": days, "events": summary})


# ══════════════════════════════════════════════════════════════════════════════
# WEBHOOK MANAGEMENT (admin)
# ══════════════════════════════════════════════════════════════════════════════

@api_view(["GET", "POST"])
@permission_classes([IsAdminUser])
def webhooks(request):
    """GET list / POST create webhook endpoint."""
    from ..models.webhook import WebhookEndpoint
    if request.method == "GET":
        eps = WebhookEndpoint.objects.filter(tenant=getattr(request.user, "tenant", None))
        return Response([{
            "id": e.pk, "name": e.name, "url": e.url,
            "events": e.events, "is_active": e.is_active,
            "success_count": e.success_count, "failure_count": e.failure_count,
        } for e in eps])
    ep = WebhookEndpoint.objects.create(
        name=request.data.get("name", ""),
        url=request.data.get("url", ""),
        secret=request.data.get("secret", ""),
        events=request.data.get("events", ["all"]),
        is_active=True,
        tenant=getattr(request.user, "tenant", None),
    )
    return Response({"id": ep.pk, "name": ep.name, "url": ep.url}, status=201)


@api_view(["DELETE"])
@permission_classes([IsAdminUser])
def webhook_delete(request, pk):
    """DELETE /engagement/admin/webhooks/<pk>/"""
    from ..models.webhook import WebhookEndpoint
    try:
        ep = WebhookEndpoint.objects.get(pk=pk)
        ep.delete()
        return Response(status=204)
    except WebhookEndpoint.DoesNotExist:
        return Response(status=404)


# ══════════════════════════════════════════════════════════════════════════════
# ANTI-CHEAT (admin)
# ══════════════════════════════════════════════════════════════════════════════

@api_view(["GET"])
@permission_classes([IsAdminUser])
def anti_cheat_flags(request):
    """GET /engagement/admin/anti-cheat/ — pending flags for review."""
    from ..models.anti_cheat import AntiCheatLog
    status_filter = request.query_params.get("status", "pending")
    qs = AntiCheatLog.objects.filter(status=status_filter).select_related("user", "rule").order_by("-created_at")[:100]
    return Response([{
        "id": l.pk, "username": l.user.username, "rule": l.rule.name,
        "severity": l.severity, "status": l.status,
        "details": l.details, "created_at": l.created_at,
    } for l in qs])


@api_view(["PATCH"])
@permission_classes([IsAdminUser])
def anti_cheat_resolve(request, pk):
    """PATCH /engagement/admin/anti-cheat/<pk>/ — resolve a flag."""
    from ..models.anti_cheat import AntiCheatLog
    from django.utils import timezone
    try:
        log = AntiCheatLog.objects.get(pk=pk)
    except AntiCheatLog.DoesNotExist:
        return Response(status=404)
    log.status      = request.data.get("status", "cleared")
    log.notes       = request.data.get("notes", "")
    log.reviewed_by = request.user
    log.reviewed_at = timezone.now()
    log.save(update_fields=["status", "notes", "reviewed_by", "reviewed_at"])
    return Response({"status": log.status})


# ── Missing stubs — referenced in views/__init__ ──────────────────────────────

@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def delete_feed_item(request, pk):
    """DELETE /engagement/social/feed/<pk>/"""
    from ..services import SocialService
    try:
        SocialService.delete_feed_item(request.user, pk)
        return Response({"success": True})
    except Exception as exc:
        return Response({"error": str(exc)}, status=400)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def unfriend_user(request, pk):
    """POST /engagement/social/friends/<pk>/unfriend/"""
    from ..services import SocialService
    try:
        SocialService.unfriend(request.user, pk)
        return Response({"success": True})
    except Exception as exc:
        return Response({"error": str(exc)}, status=400)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def unfollow_user(request, user_id):
    """POST /engagement/social/unfollow/<user_id>/"""
    from ..services import SocialService
    try:
        SocialService.unfollow(request.user, user_id)
        return Response({"success": True})
    except Exception as exc:
        return Response({"error": str(exc)}, status=400)


# Admin campaign stubs
@api_view(["GET"])
@permission_classes([IsAdminUser])
def admin_campaign_list(request):
    from ..services import CampaignService
    campaigns = CampaignService.list_campaigns(tenant=getattr(request.user, "tenant", None))
    return Response({"results": [{"id": c.pk, "name": c.name, "status": c.status} for c in campaigns]})


@api_view(["POST"])
@permission_classes([IsAdminUser])
def admin_campaign_create(request):
    from ..services import CampaignService
    campaign = CampaignService.create_campaign(request.data, tenant=getattr(request.user, "tenant", None))
    return Response({"success": True, "id": campaign.pk}, status=201)


@api_view(["GET", "PATCH", "DELETE"])
@permission_classes([IsAdminUser])
def admin_campaign_detail(request, pk):
    from ..services import CampaignService
    if request.method == "DELETE":
        CampaignService.delete_campaign(pk)
        return Response({"success": True})
    campaign = CampaignService.get_campaign(pk)
    if request.method == "PATCH":
        campaign = CampaignService.update_campaign(pk, request.data)
    return Response({"id": campaign.pk, "name": campaign.name})


@api_view(["PATCH"])
@permission_classes([IsAdminUser])
def admin_campaign_update(request, pk):
    from ..services import CampaignService
    campaign = CampaignService.update_campaign(pk, request.data)
    return Response({"success": True, "id": campaign.pk})
