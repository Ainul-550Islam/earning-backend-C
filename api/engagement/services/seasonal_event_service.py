# engagement/services/seasonal_event_service.py
import logging
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from .coin_service import CoinService
from .xp_service import XPService
from ..models.seasonal_event import (SeasonalEvent, EventMission, UserEventProgress,
                                      UserEventCurrency, EventShopItem)

logger = logging.getLogger(__name__)


class SeasonalEventService:

    @staticmethod
    def get_live_event(tenant=None) -> "SeasonalEvent | None":
        now = timezone.now()
        return SeasonalEvent.objects.filter(
            is_active=True, starts_at__lte=now, ends_at__gte=now,
            **({} if not tenant else {"tenant": tenant}),
        ).first()

    @classmethod
    @transaction.atomic
    def record_action(cls, user, action: str, increment: int = 1, tenant=None) -> list:
        """Advance progress on live event missions matching action. Returns completed missions."""
        event = cls.get_live_event(tenant)
        if not event:
            return []

        missions = EventMission.objects.filter(event=event, action=action, is_active=True if hasattr(EventMission, 'is_active') else True)
        completed = []
        for mission in missions:
            prog, _ = UserEventProgress.objects.select_for_update().get_or_create(
                user=user, event=event, mission=mission,
                defaults={"tenant": tenant or getattr(user, "tenant", None)},
            )
            if prog.reward_claimed and not mission.repeatable:
                continue
            prog.progress = min(prog.progress + increment, mission.target)
            if prog.progress >= mission.target:
                prog.times_completed += 1
                prog.last_completed_at = timezone.now()
                cls._grant_reward(user, event, mission, prog, tenant)
                completed.append(mission)
                if not mission.repeatable:
                    prog.progress = mission.target
                else:
                    prog.progress = 0   # reset for next repeat
            prog.save(update_fields=["progress", "times_completed", "last_completed_at", "reward_claimed"])

        return completed

    @classmethod
    def _grant_reward(cls, user, event, mission, prog, tenant=None):
        if mission.coin_reward > 0:
            multiplied = mission.coin_reward * event.coin_multiplier
            CoinService.add(user, multiplied, source="event_mission", ref_id=str(mission.pk))
        if mission.xp_reward > 0:
            multiplied_xp = int(mission.xp_reward * event.xp_multiplier)
            XPService.grant(user, multiplied_xp, source="event_mission", ref_id=str(mission.pk))
        if mission.event_currency_reward > 0:
            currency, _ = UserEventCurrency.objects.get_or_create(
                user=user, event=event,
                defaults={"tenant": tenant or getattr(user, "tenant", None)},
            )
            currency.balance += mission.event_currency_reward
            currency.save(update_fields=["balance"])
        prog.reward_claimed = True

    @classmethod
    @transaction.atomic
    def buy_event_item(cls, user, item_id: int, tenant=None) -> dict:
        """Purchase an item from the event shop using event currency."""
        event = cls.get_live_event(tenant)
        if not event:
            return {"error": "No live event."}

        item = EventShopItem.objects.get(pk=item_id, event=event, is_active=True)
        currency = UserEventCurrency.objects.select_for_update().filter(
            user=user, event=event
        ).first()
        if not currency or currency.balance < item.price_event_currency:
            return {"error": "Insufficient event currency."}

        currency.balance -= item.price_event_currency
        currency.save(update_fields=["balance"])

        if item.reward_coins > 0:
            CoinService.add(user, item.reward_coins, source="event_shop")
        if item.reward_xp > 0:
            XPService.grant(user, item.reward_xp, source="event_shop")
        if item.reward_item_slug:
            from .shop_service import ShopService
            try:
                ShopService.purchase(user, item.reward_item_slug, tenant=tenant)
            except Exception:
                pass
        if item.stock != -1:
            EventShopItem.objects.filter(pk=item.pk).update(
                stock=__import__("django.db.models", fromlist=["F"]).F("stock") - 1
            )

        return {"success": True, "currency_spent": item.price_event_currency, "item": item.name}
