# engagement/serializers/auction_serializer.py
from rest_framework import serializers
from ..models.auction import Auction, AuctionBid, AuctionWatchlist


class AuctionSerializer(serializers.ModelSerializer):
    is_live          = serializers.BooleanField(read_only=True)
    time_remaining   = serializers.IntegerField(source="time_remaining_seconds", read_only=True)
    winner_username  = serializers.SerializerMethodField()

    class Meta:
        model  = Auction
        fields = [
            "id", "title", "description", "icon", "item_slug", "item_quantity",
            "starting_bid", "bid_increment", "current_bid", "status",
            "starts_at", "ends_at", "is_live", "time_remaining",
            "total_bids", "winner_username",
        ]
        read_only_fields = ["id", "current_bid", "total_bids"]

    def get_winner_username(self, obj):
        return obj.winner.username if obj.winner else None


class AuctionBidSerializer(serializers.ModelSerializer):
    username     = serializers.CharField(source="user.username",    read_only=True)
    auction_title = serializers.CharField(source="auction.title",   read_only=True)

    class Meta:
        model  = AuctionBid
        fields = [
            "id", "username", "auction_title", "amount",
            "is_winning", "coins_held", "coins_returned", "created_at",
        ]
        read_only_fields = fields


class AuctionWatchlistSerializer(serializers.ModelSerializer):
    auction = AuctionSerializer(read_only=True)

    class Meta:
        model  = AuctionWatchlist
        fields = ["id", "auction", "notify_outbid", "notify_ending"]
