# engagement/models/auction.py
"""
Auction House System
Rare items available via coin-based bidding.
Auto-closes at deadline and distributes item to highest bidder.
"""
from django.db import models
from django.utils import timezone
from django.conf import settings
from .base import TenantModel, UserEngagementModel


class Auction(TenantModel):
    """An active or completed auction listing."""
    STATUS_CHOICES = [
        ("upcoming",  "Upcoming"),
        ("active",    "Active"),
        ("ended",     "Ended"),
        ("cancelled", "Cancelled"),
    ]
    title         = models.CharField(max_length=200)
    description   = models.TextField(blank=True)
    icon          = models.CharField(max_length=200, blank=True)
    item_slug     = models.CharField(max_length=100, blank=True)   # ShopItem slug being auctioned
    item_quantity = models.IntegerField(default=1)
    starting_bid  = models.DecimalField(max_digits=12, decimal_places=2, default=10)
    bid_increment = models.DecimalField(max_digits=10, decimal_places=2, default=5)
    current_bid   = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status        = models.CharField(max_length=10, choices=STATUS_CHOICES, default="upcoming")
    starts_at     = models.DateTimeField()
    ends_at       = models.DateTimeField()
    winner        = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="won_auctions",
    )
    total_bids    = models.IntegerField(default=0)

    class Meta:
        ordering = ["-ends_at"]

    def __str__(self):
        return f"[Auction] {self.title} ({self.status})"

    @property
    def is_live(self):
        now = timezone.now()
        return self.status == "active" and self.starts_at <= now <= self.ends_at

    @property
    def time_remaining_seconds(self):
        if not self.is_live:
            return 0
        return int((self.ends_at - timezone.now()).total_seconds())


class AuctionBid(UserEngagementModel):
    """A single bid placed on an auction."""
    auction      = models.ForeignKey(Auction, on_delete=models.CASCADE, related_name="bids")
    amount       = models.DecimalField(max_digits=12, decimal_places=2)
    is_winning   = models.BooleanField(default=False)    # is this currently the top bid?
    coins_held   = models.DecimalField(max_digits=12, decimal_places=2, default=0)  # escrowed
    coins_returned = models.BooleanField(default=False)  # was escrow returned after outbid?

    class Meta:
        ordering = ["-amount", "-created_at"]

    def __str__(self):
        return f"{self.user} bid {self.amount} on {self.auction.title}"


class AuctionWatchlist(UserEngagementModel):
    """Auctions a user is watching (for notifications)."""
    auction     = models.ForeignKey(Auction, on_delete=models.CASCADE, related_name="watchers")
    notify_outbid = models.BooleanField(default=True)
    notify_ending = models.BooleanField(default=True)

    class Meta:
        unique_together = ["user", "auction"]
