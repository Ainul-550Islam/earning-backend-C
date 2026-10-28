# engagement/serializers/seasonal_serializer.py
from rest_framework import serializers
from ..models.seasonal_event import (SeasonalEvent, EventMission, UserEventProgress,
                                      UserEventCurrency, EventShopItem)
from ..models.scratch_card import (ScratchCardTemplate, ScratchCardPrize, ScratchCardResult,
                                    LoginCalendar, LoginCalendarDay, UserLoginCalendarProgress)


class EventMissionSerializer(serializers.ModelSerializer):
    class Meta:
        model  = EventMission
        fields = [
            "id", "slug", "title", "description", "icon",
            "target", "action", "coin_reward", "xp_reward",
            "event_currency_reward", "chest_reward_slug", "order", "repeatable",
        ]


class SeasonalEventSerializer(serializers.ModelSerializer):
    is_live          = serializers.BooleanField(read_only=True)
    time_remaining   = serializers.IntegerField(source="time_remaining_seconds", read_only=True)
    missions         = EventMissionSerializer(many=True, read_only=True)

    class Meta:
        model  = SeasonalEvent
        fields = [
            "id", "slug", "name", "description", "theme_color", "banner_image", "icon",
            "starts_at", "ends_at", "is_active", "is_live", "time_remaining",
            "event_currency_name", "event_currency_icon",
            "coin_multiplier", "xp_multiplier", "missions",
        ]


class UserEventProgressSerializer(serializers.ModelSerializer):
    mission_title = serializers.CharField(source="mission.title", read_only=True)
    pct           = serializers.IntegerField(read_only=True)

    class Meta:
        model  = UserEventProgress
        fields = [
            "id", "mission_title", "progress", "pct",
            "times_completed", "reward_claimed", "last_completed_at",
        ]
        read_only_fields = fields


class UserEventCurrencySerializer(serializers.ModelSerializer):
    event_name           = serializers.CharField(source="event.name",                 read_only=True)
    currency_name        = serializers.CharField(source="event.event_currency_name",  read_only=True)
    currency_icon        = serializers.CharField(source="event.event_currency_icon",  read_only=True)

    class Meta:
        model  = UserEventCurrency
        fields = ["id", "event_name", "currency_name", "currency_icon", "balance"]
        read_only_fields = fields


class EventShopItemSerializer(serializers.ModelSerializer):
    class Meta:
        model  = EventShopItem
        fields = [
            "id", "name", "description", "icon", "price_event_currency",
            "stock", "reward_coins", "reward_xp", "reward_item_slug",
            "reward_chest_slug", "order", "is_active",
        ]


# ── Scratch Card ──────────────────────────────────────────────────────────────

class ScratchCardPrizeSerializer(serializers.ModelSerializer):
    """FIX: ScratchCardPrize was imported but had no serializer class."""
    class Meta:
        model  = ScratchCardPrize
        fields = ["id", "label", "probability", "coins", "xp", "item_slug", "chest_slug"]


class ScratchCardTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model  = ScratchCardTemplate
        fields = ["id", "slug", "name", "icon", "max_per_day", "price_coins", "is_active"]


class ScratchCardResultSerializer(serializers.ModelSerializer):
    template_name = serializers.CharField(source="template.name", read_only=True)
    prize_label   = serializers.CharField(source="prize.label",   read_only=True)

    class Meta:
        model  = ScratchCardResult
        fields = ["id", "template_name", "prize_label", "coins_won", "xp_won", "scratched_at"]
        read_only_fields = fields


# ── Login Calendar ────────────────────────────────────────────────────────────

class LoginCalendarDaySerializer(serializers.ModelSerializer):
    class Meta:
        model  = LoginCalendarDay
        fields = ["day_number", "coins", "xp", "item_slug", "chest_slug", "is_milestone", "icon"]


class LoginCalendarSerializer(serializers.ModelSerializer):
    days = LoginCalendarDaySerializer(many=True, read_only=True)

    class Meta:
        model  = LoginCalendar
        fields = ["id", "month", "year", "is_active", "days"]


class UserLoginCalendarProgressSerializer(serializers.ModelSerializer):
    class Meta:
        model  = UserLoginCalendarProgress
        fields = ["id", "claimed_days", "last_claimed_day", "last_claimed_at"]
        read_only_fields = fields
