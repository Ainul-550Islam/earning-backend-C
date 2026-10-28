# engagement/serializers/guild_serializer.py
from rest_framework import serializers
from ..models.guild import Guild, GuildMember, GuildChallenge, GuildLeaderboard, GuildInvite


class GuildSerializer(serializers.ModelSerializer):
    member_count = serializers.IntegerField(read_only=True)
    owner_username = serializers.CharField(source="owner.username", read_only=True)

    class Meta:
        model  = Guild
        fields = [
            "id", "name", "slug", "description", "icon", "banner_color",
            "owner_username", "max_members", "member_count",
            "is_public", "min_level_required", "total_xp", "level", "is_active",
        ]
        read_only_fields = ["id", "total_xp", "level"]


class GuildMemberSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    guild_name = serializers.CharField(source="guild.name",  read_only=True)

    class Meta:
        model  = GuildMember
        fields = [
            "id", "username", "guild_name", "role", "status",
            "contribution_xp", "joined_at", "last_active_at",
        ]
        read_only_fields = ["id", "joined_at", "last_active_at"]


class GuildChallengeSerializer(serializers.ModelSerializer):
    pct = serializers.IntegerField(read_only=True)

    class Meta:
        model  = GuildChallenge
        fields = [
            "id", "title", "description", "metric", "target", "current", "pct",
            "starts_at", "ends_at",
            "coin_reward_per_member", "xp_reward_per_member", "is_completed",
        ]
        read_only_fields = ["id", "current", "pct", "is_completed"]


class GuildLeaderboardSerializer(serializers.ModelSerializer):
    guild_name = serializers.CharField(source="guild.name", read_only=True)
    guild_icon = serializers.CharField(source="guild.icon", read_only=True)

    class Meta:
        model  = GuildLeaderboard
        fields = ["id", "guild_name", "guild_icon", "week_start", "total_xp", "rank"]
        read_only_fields = fields
