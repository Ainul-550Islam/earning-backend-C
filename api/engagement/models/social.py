# engagement/models/social.py
"""
Social Engagement Layer
- Activity Feed (what users did publicly)
- Friendships
- Likes / Reactions on feed items
- Comments
- User Follow system
"""
from django.db import models
from django.conf import settings
from .base import TenantModel, UserEngagementModel


class FeedItem(UserEngagementModel):
    """A public activity entry in the social feed."""
    TYPE_CHOICES = [
        ("checkin",          "Daily Check-In"),
        ("streak_milestone", "Streak Milestone"),
        ("achievement",      "Achievement Unlocked"),
        ("level_up",         "Level Up"),
        ("quest_complete",   "Quest Completed"),
        ("challenge_win",    "Challenge Won"),
        ("guild_join",       "Joined Guild"),
        ("leaderboard_top",  "Leaderboard Top 3"),
        ("battle_pass_tier", "Battle Pass Tier"),
        ("prestige",         "Prestige Reached"),
    ]
    type         = models.CharField(max_length=30, choices=TYPE_CHOICES, db_index=True)
    title        = models.CharField(max_length=200)
    body         = models.TextField(blank=True)
    icon         = models.CharField(max_length=200, blank=True)
    data         = models.JSONField(default=dict, blank=True)
    is_public    = models.BooleanField(default=True)
    like_count   = models.IntegerField(default=0)
    comment_count = models.IntegerField(default=0)

    class Meta:
        ordering = ["-created_at"]
        indexes  = [
            models.Index(fields=["user", "is_public", "created_at"]),
            models.Index(fields=["tenant", "is_public", "created_at"]),
        ]

    def __str__(self):
        return f"{self.user.username}: {self.title}"


class FeedLike(TenantModel):
    """A reaction/like on a feed item."""
    REACTION_CHOICES = [
        ("like",  "Like"),
        ("fire",  "Fire"),
        ("clap",  "Clap"),
        ("wow",   "Wow"),
    ]
    feed_item = models.ForeignKey(FeedItem, on_delete=models.CASCADE, related_name="likes")
    user      = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                  related_name="feed_likes")
    reaction  = models.CharField(max_length=10, choices=REACTION_CHOICES, default="like")

    class Meta:
        unique_together = ["feed_item", "user"]


class FeedComment(UserEngagementModel):
    """A comment on a feed item."""
    feed_item = models.ForeignKey(FeedItem, on_delete=models.CASCADE, related_name="comments")
    body      = models.TextField(max_length=500)
    is_deleted = models.BooleanField(default=False)

    class Meta:
        ordering = ["created_at"]


class Friendship(TenantModel):
    """A friendship between two users."""
    STATUS_CHOICES = [
        ("pending",  "Pending"),
        ("accepted", "Friends"),
        ("blocked",  "Blocked"),
    ]
    requester = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                  related_name="friend_requests_sent")
    receiver  = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                  related_name="friend_requests_received")
    status    = models.CharField(max_length=10, choices=STATUS_CHOICES, default="pending")
    accepted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ["requester", "receiver"]
        ordering        = ["-created_at"]

    def __str__(self):
        return f"{self.requester} ↔ {self.receiver} [{self.status}]"


class UserFollow(TenantModel):
    """Asymmetric follow (Twitter-style): follower follows followee."""
    follower = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                 related_name="following")
    followee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                 related_name="followers")

    class Meta:
        unique_together = ["follower", "followee"]

    def __str__(self):
        return f"{self.follower} → {self.followee}"
