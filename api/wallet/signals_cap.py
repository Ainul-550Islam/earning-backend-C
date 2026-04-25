# api/wallet/signals_cap.py
"""
CPAlead-specific signals (CAP = CPAlead Publisher).
"""
import logging
from decimal import Decimal
from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger("wallet.signals_cap")


def connect_cpalead_signals():
    """Connect all CPAlead signals. Called from apps.py ready()."""

    # 1. When EarningRecord created → update PointsLedger
    try:
        from .models.earning import EarningRecord
        from .models_cpalead_extra import PointsLedger

        @receiver(post_save, sender=EarningRecord, dispatch_uid="cap_update_points")
        def on_earning_update_points(sender, instance, created, **kwargs):
            if not created: return
            try:
                pl, _ = PointsLedger.objects.get_or_create(
                    user=instance.wallet.user, wallet=instance.wallet
                )
                pl.award(instance.amount)
            except Exception as e:
                logger.debug(f"cap_update_points skip: {e}")

    except ImportError:
        pass

    # 2. When OfferConversion created → increment offer stats
    try:
        from .models_cpalead_extra import OfferConversion

        @receiver(post_save, sender=OfferConversion, dispatch_uid="cap_offer_stats")
        def on_offer_conversion_stats(sender, instance, created, **kwargs):
            if not created: return
            try:
                instance.offer.total_conversions = (
                    OfferConversion.objects.filter(offer=instance.offer, status="approved").count()
                )
                instance.offer.save(update_fields=["total_conversions","updated_at"])
            except Exception as e:
                logger.debug(f"cap_offer_stats skip: {e}")

    except ImportError:
        pass

    # 3. When PublisherLevel upgraded → update payout schedule
    try:
        from .models_cpalead_extra import PublisherLevel, PayoutSchedule

        @receiver(post_save, sender=PublisherLevel, dispatch_uid="cap_payout_schedule")
        def on_publisher_level_change_payout(sender, instance, **kwargs):
            try:
                sched, _ = PayoutSchedule.objects.get_or_create(
                    user=instance.user, wallet=instance.wallet
                )
                sched.frequency = instance.payout_freq
                sched.save(update_fields=["frequency","updated_at"])
            except Exception as e:
                logger.debug(f"cap_payout_schedule skip: {e}")

    except ImportError:
        pass

    logger.debug("CPAlead signals connected")
