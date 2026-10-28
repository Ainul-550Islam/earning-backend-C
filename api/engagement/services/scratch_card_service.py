# engagement/services/scratch_card_service.py
import random
import logging
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from .coin_service import CoinService
from .xp_service import XPService
from ..models.scratch_card import (ScratchCardTemplate, ScratchCardPrize, ScratchCardResult,
                                    LoginCalendar, LoginCalendarDay, UserLoginCalendarProgress)
from ..exceptions import ItemNotAvailableError

logger = logging.getLogger(__name__)


class ScratchCardService:

    @classmethod
    @transaction.atomic
    def scratch(cls, user, template_slug: str, tenant=None) -> dict:
        template = ScratchCardTemplate.objects.get(slug=template_slug, is_active=True)

        # Check daily limit
        from datetime import date
        used_today = ScratchCardResult.objects.filter(
            user=user, template=template,
            scratched_at__date=date.today(),
        ).count()
        if used_today >= template.max_per_day:
            raise ItemNotAvailableError(f"Daily scratch limit of {template.max_per_day} reached.")

        # Pay price if applicable
        if template.price_coins > 0:
            CoinService.deduct(user, template.price_coins, source="scratch_card")

        # Roll prize
        prizes = list(ScratchCardPrize.objects.filter(template=template))
        if not prizes:
            raise ItemNotAvailableError("No prizes configured.")

        total_weight = sum(p.weight for p in prizes)
        roll = random.randint(1, total_weight)
        cumulative = 0
        prize = prizes[-1]
        for p in prizes:
            cumulative += p.weight
            if roll <= cumulative:
                prize = p
                break

        # Grant reward
        coins_won = Decimal(str(prize.coins)) if prize.coins > 0 else Decimal("0")
        xp_won    = 0
        if coins_won > 0:
            CoinService.add(user, coins_won, source="scratch_card", ref_id=str(template.pk))
        if prize.xp > 0:
            XPService.grant(user, prize.xp, source="scratch_card")
            xp_won = prize.xp
        if prize.item_slug:
            from .shop_service import ShopService
            try:
                ShopService.purchase(user, prize.item_slug, tenant=tenant)
            except Exception:
                pass

        result = ScratchCardResult.objects.create(
            user=user, tenant=tenant or getattr(user, "tenant", None),
            template=template, prize=prize,
            coins_won=coins_won, xp_won=xp_won,
        )
        logger.info("ScratchCard: user=%s template=%s prize=%s", user.pk, template_slug, prize.label)
        return {
            "prize_label": prize.label,
            "coins_won":   float(coins_won),
            "xp_won":      xp_won,
            "item_slug":   prize.item_slug,
        }


class LoginCalendarService:

    @classmethod
    def get_current_calendar(cls, tenant=None) -> "LoginCalendar | None":
        from datetime import date
        today = date.today()
        return LoginCalendar.objects.filter(
            month=today.month, year=today.year, is_active=True,
            **({} if not tenant else {"tenant": tenant}),
        ).first()

    @classmethod
    @transaction.atomic
    def claim_today(cls, user, tenant=None) -> dict:
        from datetime import date
        today    = date.today()
        calendar = cls.get_current_calendar(tenant)
        if not calendar:
            return {"error": "No active calendar for this month."}

        try:
            day_reward = LoginCalendarDay.objects.get(calendar=calendar, day_number=today.day)
        except LoginCalendarDay.DoesNotExist:
            return {"error": "No reward configured for today."}

        prog, _ = UserLoginCalendarProgress.objects.get_or_create(
            user=user, calendar=calendar,
            defaults={"tenant": tenant or getattr(user, "tenant", None)},
        )

        if today.day in (prog.claimed_days or []):
            return {"error": "Already claimed today's calendar reward."}

        # Grant rewards
        result = {}
        if day_reward.coins > 0:
            CoinService.add(user, day_reward.coins, source="login_calendar")
            result["coins"] = float(day_reward.coins)
        if day_reward.xp > 0:
            XPService.grant(user, day_reward.xp, source="login_calendar")
            result["xp"] = day_reward.xp

        claimed = list(prog.claimed_days or [])
        claimed.append(today.day)
        prog.claimed_days     = claimed
        prog.last_claimed_day = today.day
        prog.last_claimed_at  = timezone.now()
        prog.save(update_fields=["claimed_days", "last_claimed_day", "last_claimed_at"])

        return {"success": True, "day": today.day, "is_milestone": day_reward.is_milestone, **result}
