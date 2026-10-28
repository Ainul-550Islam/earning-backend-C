# engagement/models/guild.py
"""
Guild / Clan System
Users form guilds, earn collective XP, compete in guild leaderboards,
and tackle guild-specific challenges together.
"""
from django.db import models
from django.conf import settings
from .base import TenantModel, UserEngagementModel


class Guild(TenantModel):
    """A guild (clan / team)."""
    name         = models.CharField(max_length=100, unique=True)
    slug         = models.SlugField(max_length=100, unique=True)
    description  = models.TextField(blank=True)
    icon         = models.CharField(max_length=200, blank=True)   # emoji or URL
    banner_color = models.CharField(max_length=20, default="#7F77DD")
    owner        = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, related_name="owned_guilds",
    )
    max_members  = models.IntegerField(default=50)
    is_public    = models.BooleanField(default=True)   # open join vs invite-only
    min_level_required = models.IntegerField(default=1)
    total_xp     = models.BigIntegerField(default=0)
    level        = models.IntegerField(default=1)
    is_active    = models.BooleanField(default=True)

    class Meta:
        ordering = ["-total_xp"]

    def __str__(self):
        return f"[Guild] {self.name}"

    @property
    def member_count(self):
        return self.members.filter(status="active").count()


class GuildMember(UserEngagementModel):
    """A user's membership in a guild."""
    ROLE_CHOICES = [
        ("owner",  "Owner"),
        ("admin",  "Admin"),
        ("elder",  "Elder"),
        ("member", "Member"),
    ]
    STATUS_CHOICES = [
        ("active",   "Active"),
        ("kicked",   "Kicked"),
        ("left",     "Left"),
        ("pending",  "Pending (invite)"),
    ]
    guild          = models.ForeignKey(Guild, on_delete=models.CASCADE, related_name="members")
    role           = models.CharField(max_length=10, choices=ROLE_CHOICES, default="member")
    status         = models.CharField(max_length=10, choices=STATUS_CHOICES, default="active")
    contribution_xp = models.BigIntegerField(default=0)   # XP contributed to guild
    joined_at      = models.DateTimeField(auto_now_add=True)
    last_active_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ["user", "guild"]
        ordering        = ["-contribution_xp"]

    def __str__(self):
        return f"{self.user} in {self.guild.name} [{self.role}]"


class GuildChallenge(TenantModel):
    """A challenge specifically for guilds — collective goal."""
    guild        = models.ForeignKey(Guild, on_delete=models.CASCADE, related_name="challenges")
    title        = models.CharField(max_length=200)
    description  = models.TextField(blank=True)
    metric       = models.CharField(max_length=50)   # "total_checkins", "total_spins"
    target       = models.IntegerField(default=100)
    current      = models.IntegerField(default=0)
    starts_at    = models.DateTimeField()
    ends_at      = models.DateTimeField()
    coin_reward_per_member = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    xp_reward_per_member   = models.IntegerField(default=0)
    is_completed = models.BooleanField(default=False)
    reward_distributed = models.BooleanField(default=False)

    class Meta:
        ordering = ["-starts_at"]

    @property
    def pct(self):
        return min(100, int(self.current / self.target * 100)) if self.target else 100


class GuildLeaderboard(TenantModel):
    """Weekly guild ranking snapshot."""
    guild      = models.ForeignKey(Guild, on_delete=models.CASCADE, related_name="leaderboard_entries")
    week_start = models.DateField(db_index=True)
    total_xp   = models.BigIntegerField(default=0)
    rank       = models.IntegerField(default=0)
    reward_distributed = models.BooleanField(default=False)

    class Meta:
        unique_together = ["guild", "week_start"]
        ordering        = ["rank"]


class GuildInvite(TenantModel):
    """An invite from a guild to a specific user."""
    guild      = models.ForeignKey(Guild, on_delete=models.CASCADE, related_name="invites")
    invited_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                   related_name="guild_invites_sent")
    invited_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                     related_name="guild_invites_received")
    status     = models.CharField(max_length=10,
                                  choices=[("pending","Pending"),("accepted","Accepted"),("declined","Declined")],
                                  default="pending")
    expires_at = models.DateTimeField()

    class Meta:
        unique_together = ["guild", "invited_user"]
