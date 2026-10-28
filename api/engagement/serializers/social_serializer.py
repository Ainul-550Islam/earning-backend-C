# engagement/serializers/social_serializer.py
from rest_framework import serializers
from ..models.social import FeedItem, FeedLike, FeedComment, Friendship, UserFollow


class FeedItemSerializer(serializers.ModelSerializer):
    username       = serializers.CharField(source="user.username", read_only=True)
    is_liked_by_me = serializers.SerializerMethodField()

    class Meta:
        model  = FeedItem
        fields = [
            "id", "username", "type", "title", "body", "icon", "data",
            "is_public", "like_count", "comment_count", "is_liked_by_me", "created_at",
        ]
        read_only_fields = ["id", "like_count", "comment_count", "created_at"]

    def get_is_liked_by_me(self, obj):
        req = self.context.get("request")
        if req and req.user.is_authenticated:
            return obj.likes.filter(user=req.user).exists()
        return False


class FeedCommentSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model  = FeedComment
        fields = ["id", "username", "body", "is_deleted", "created_at"]
        read_only_fields = ["id", "created_at"]


class FriendshipSerializer(serializers.ModelSerializer):
    requester_username = serializers.CharField(source="requester.username", read_only=True)
    receiver_username  = serializers.CharField(source="receiver.username",  read_only=True)

    class Meta:
        model  = Friendship
        fields = [
            "id", "requester_username", "receiver_username",
            "status", "accepted_at", "created_at",
        ]
        read_only_fields = fields


class UserFollowSerializer(serializers.ModelSerializer):
    follower_username = serializers.CharField(source="follower.username", read_only=True)
    followee_username = serializers.CharField(source="followee.username", read_only=True)

    class Meta:
        model  = UserFollow
        fields = ["id", "follower_username", "followee_username", "created_at"]
        read_only_fields = fields
