# engagement/services/social_service.py
import logging
from django.db import transaction
from django.utils import timezone
from ..models.social import FeedItem, FeedLike, FeedComment, Friendship, UserFollow

logger = logging.getLogger(__name__)


class SocialService:

    # ── Feed ─────────────────────────────────────────────────────────────────

    @classmethod
    def post_feed_item(cls, user, feed_type: str, title: str, body: str = "",
                       icon: str = "", data: dict = None, tenant=None) -> FeedItem:
        item = FeedItem.objects.create(
            user=user,
            tenant=tenant or getattr(user, "tenant", None),
            type=feed_type,
            title=title,
            body=body,
            icon=icon,
            data=data or {},
            is_public=True,
        )
        return item

    @classmethod
    def get_feed(cls, user, scope: str = "global", limit: int = 20) -> list:
        """scope: 'global' | 'friends' | 'guild'"""
        qs = FeedItem.objects.filter(is_public=True).select_related("user").order_by("-created_at")
        if scope == "friends":
            friend_ids = cls._friend_ids(user)
            qs = qs.filter(user_id__in=friend_ids)
        elif scope == "guild":
            from ..models.guild import GuildMember
            guild_member_ids = GuildMember.objects.filter(
                user=user, status="active"
            ).values_list("guild__members__user_id", flat=True)
            qs = qs.filter(user_id__in=guild_member_ids)
        return list(qs[:limit])

    @classmethod
    @transaction.atomic
    def like(cls, user, feed_item_id: int, reaction: str = "like", tenant=None) -> dict:
        item = FeedItem.objects.select_for_update().get(pk=feed_item_id)
        like, created = FeedLike.objects.get_or_create(
            feed_item=item, user=user,
            defaults={"reaction": reaction, "tenant": tenant or getattr(user, "tenant", None)},
        )
        if not created:
            # Toggle off
            like.delete()
            item.like_count = max(0, item.like_count - 1)
            item.save(update_fields=["like_count"])
            return {"liked": False, "like_count": item.like_count}
        item.like_count += 1
        item.save(update_fields=["like_count"])
        return {"liked": True, "like_count": item.like_count, "reaction": reaction}

    @classmethod
    @transaction.atomic
    def comment(cls, user, feed_item_id: int, body: str, tenant=None) -> FeedComment:
        item    = FeedItem.objects.select_for_update().get(pk=feed_item_id)
        comment = FeedComment.objects.create(
            user=user,
            tenant=tenant or getattr(user, "tenant", None),
            feed_item=item,
            body=body[:500],
        )
        item.comment_count += 1
        item.save(update_fields=["comment_count"])
        return comment

    # ── Friendships ───────────────────────────────────────────────────────────

    @classmethod
    @transaction.atomic
    def send_friend_request(cls, requester, receiver, tenant=None) -> Friendship:
        if requester.pk == receiver.pk:
            raise ValueError("Cannot friend yourself.")
        fs, created = Friendship.objects.get_or_create(
            requester=requester, receiver=receiver,
            defaults={"tenant": tenant or getattr(requester, "tenant", None)},
        )
        if not created and fs.status == "accepted":
            raise ValueError("Already friends.")
        return fs

    @classmethod
    @transaction.atomic
    def accept_friend_request(cls, receiver, friendship_id: int) -> Friendship:
        fs = Friendship.objects.select_for_update().get(pk=friendship_id, receiver=receiver, status="pending")
        fs.status      = "accepted"
        fs.accepted_at = timezone.now()
        fs.save(update_fields=["status", "accepted_at"])
        return fs

    @classmethod
    def friends_list(cls, user, limit: int = 50) -> list:
        ids = cls._friend_ids(user)
        from django.contrib.auth import get_user_model
        return list(get_user_model().objects.filter(pk__in=ids)[:limit])

    # ── Follow ────────────────────────────────────────────────────────────────

    @classmethod
    @transaction.atomic
    def follow(cls, follower, followee, tenant=None):
        if follower.pk == followee.pk:
            raise ValueError("Cannot follow yourself.")
        obj, created = UserFollow.objects.get_or_create(
            follower=follower, followee=followee,
            defaults={"tenant": tenant or getattr(follower, "tenant", None)},
        )
        if not created:
            obj.delete()
            return {"following": False}
        return {"following": True}

    # ── Private ───────────────────────────────────────────────────────────────

    @staticmethod
    def _friend_ids(user) -> list:
        sent = list(Friendship.objects.filter(
            requester=user, status="accepted"
        ).values_list("receiver_id", flat=True))
        received = list(Friendship.objects.filter(
            receiver=user, status="accepted"
        ).values_list("requester_id", flat=True))
        return list(set(sent + received))

    @classmethod
    def delete_feed_item(cls, user, feed_item_id: int) -> None:
        """Delete a feed item if owned by user."""
        from ..models.social import FeedItem
        try:
            item = FeedItem.objects.get(pk=feed_item_id, user=user)
            item.delete()
        except FeedItem.DoesNotExist:
            raise ValueError("Feed item not found or not owned by user")

    @classmethod
    def unfriend(cls, user, friendship_id: int) -> None:
        """Remove a friendship."""
        from ..models.social import Friendship
        try:
            f = Friendship.objects.get(
                pk=friendship_id,
                status="accepted"
            )
            if f.sender != user and f.receiver != user:
                raise ValueError("Not part of this friendship")
            f.delete()
        except Friendship.DoesNotExist:
            raise ValueError("Friendship not found")

    @classmethod
    def unfollow(cls, follower, followee_id: int) -> None:
        """Unfollow a user."""
        from ..models.social import UserFollow
        UserFollow.objects.filter(follower=follower, followee_id=followee_id).delete()
