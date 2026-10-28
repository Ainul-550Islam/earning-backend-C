# engagement/views/guild_views.py
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from ..services import GuildService
from ..models.guild import Guild, GuildMember, GuildChallenge
from ..utils.decorators import engagement_endpoint


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def guilds_list(request):
    """GET /engagement/guilds/ — list public guilds."""
    guilds = Guild.objects.filter(is_public=True, is_active=True).order_by("-total_xp")[:50]
    data = [{
        "id": g.pk, "name": g.name, "slug": g.slug, "icon": g.icon,
        "total_xp": g.total_xp, "level": g.level,
        "member_count": g.member_count, "max_members": g.max_members,
        "min_level_required": g.min_level_required,
    } for g in guilds]
    return Response({"results": data, "count": len(data)})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@engagement_endpoint
def create_guild(request):
    """POST /engagement/guilds/create/"""
    tenant = getattr(request.user, "tenant", None)
    guild  = GuildService.create(
        owner=request.user,
        name=request.data.get("name", ""),
        slug=request.data.get("slug", ""),
        description=request.data.get("description", ""),
        is_public=request.data.get("is_public", True),
        tenant=tenant,
    )
    return Response({"id": guild.pk, "name": guild.name, "slug": guild.slug}, status=201)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def guild_detail(request, slug):
    """GET /engagement/guilds/<slug>/"""
    try:
        guild = Guild.objects.get(slug=slug, is_active=True)
    except Guild.DoesNotExist:
        return Response(status=404)
    members = GuildMember.objects.filter(guild=guild, status="active").select_related("user").order_by("-contribution_xp")[:20]
    return Response({
        "id": guild.pk, "name": guild.name, "description": guild.description,
        "icon": guild.icon, "total_xp": guild.total_xp, "level": guild.level,
        "member_count": guild.member_count, "max_members": guild.max_members,
        "is_public": guild.is_public,
        "members": [{"username": m.user.username, "role": m.role, "xp": m.contribution_xp} for m in members],
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@engagement_endpoint
def join_guild(request, slug):
    """POST /engagement/guilds/<slug>/join/"""
    try:
        guild = Guild.objects.get(slug=slug, is_active=True)
    except Guild.DoesNotExist:
        return Response(status=404)
    tenant = getattr(request.user, "tenant", None)
    member = GuildService.join(request.user, guild, tenant)
    return Response({"joined": True, "guild": guild.name, "role": member.role})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@engagement_endpoint
def leave_guild(request, slug):
    """POST /engagement/guilds/<slug>/leave/"""
    try:
        guild = Guild.objects.get(slug=slug)
    except Guild.DoesNotExist:
        return Response(status=404)
    GuildService.leave(request.user, guild)
    return Response({"left": True})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def my_guild(request):
    """GET /engagement/guilds/mine/ — user's current guild."""
    member = GuildMember.objects.filter(user=request.user, status="active").select_related("guild").first()
    if not member:
        return Response({"guild": None})
    g = member.guild
    return Response({
        "id": g.pk, "name": g.name, "slug": g.slug, "icon": g.icon,
        "role": member.role, "contribution_xp": member.contribution_xp,
        "total_xp": g.total_xp, "level": g.level,
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def guild_leaderboard(request):
    """GET /engagement/guilds/leaderboard/"""
    from datetime import date, timedelta
    monday = date.today() - timedelta(days=date.today().weekday())
    tenant = getattr(request.user, "tenant", None)
    entries = GuildService.leaderboard(monday, tenant)
    data = [{
        "rank": e.rank, "guild": e.guild.name, "icon": e.guild.icon,
        "total_xp": e.total_xp,
    } for e in entries]
    return Response({"results": data, "week_start": str(monday)})
