# api/offer_inventory/ai_optimization/auto_pause_offers.py
"""
Auto-Pause Engine — Full Implementation.
Automatically pauses underperforming, high-fraud, or budget-exceeded offers.
Runs as a scheduled Celery task.

Rules:
  1. CVR < 0.5% after 200+ clicks → pause (low performance)
  2. Fraud rate > 20% after 50+ clicks → pause (fraud)
  3. Daily cap reached + pause_on_hit=True → pause (cap)
  4. Budget depleted (Campaign) → pause all campaign offers
  5. Offer expired (expires_at passed) → expire status
"""
import logging
from decimal import Decimal
from django.utils import timezone
from django.db.models import Count, Q

logger = logging.getLogger(__name__)

# Thresholds
MIN_CLICKS_FOR_EVAL  = 50      # Minimum clicks before evaluating
MIN_CLICKS_FOR_CVR   = 200     # More clicks needed for CVR eval
MIN_CVR_THRESHOLD    = Decimal('0.5')    # 0.5% minimum CVR
MAX_FRAUD_RATE       = Decimal('20.0')   # 20% max fraud rate
LOW_CVR_PAUSE_REASON = 'auto_pause:low_cvr'
HIGH_FRAUD_REASON    = 'auto_pause:high_fraud_rate'
CAP_REACHED_REASON   = 'auto_pause:cap_reached'
BUDGET_DEPLETED_REASON = 'auto_pause:campaign_budget_depleted'


class AutoPauseEngine:
    """
    Evaluates and pauses offers based on performance metrics.
    Each rule is independent — all are checked.
    """

    @classmethod
    def evaluate_and_pause(cls) -> dict:
        """
        Main entry point — evaluate ALL active offers.
        Returns summary of what was paused and why.
        """
        from api.offer_inventory.models import Offer

        results = {
            'evaluated' : 0,
            'paused'    : [],
            'expired'   : [],
            'skipped'   : [],
        }

        offers = Offer.objects.filter(status='active').prefetch_related('caps', 'clicks')

        for offer in offers:
            results['evaluated'] += 1

            # Rule 1: Expired
            if cls._is_expired(offer):
                cls._set_status(offer, 'expired', 'offer_expired')
                results['expired'].append({'id': str(offer.id), 'title': offer.title})
                continue

            # Rule 2: Fraud rate too high
            fraud_decision = cls._check_fraud_rate(offer)
            if fraud_decision['pause']:
                cls._pause(offer, fraud_decision['reason'])
                results['paused'].append({
                    'id'    : str(offer.id),
                    'title' : offer.title,
                    'reason': fraud_decision['reason'],
                })
                continue

            # Rule 3: CVR too low (need more data)
            cvr_decision = cls._check_cvr(offer)
            if cvr_decision['pause']:
                cls._pause(offer, cvr_decision['reason'])
                results['paused'].append({
                    'id'    : str(offer.id),
                    'title' : offer.title,
                    'reason': cvr_decision['reason'],
                })
                continue

            # Rule 4: Cap reached
            cap_decision = cls._check_caps(offer)
            if cap_decision['pause']:
                cls._pause(offer, cap_decision['reason'])
                results['paused'].append({
                    'id'    : str(offer.id),
                    'title' : offer.title,
                    'reason': cap_decision['reason'],
                })
                continue

            results['skipped'].append(str(offer.id))

        # Rule 5: Budget-depleted campaign offers
        budget_paused = cls._pause_budget_depleted()
        results['paused'].extend(budget_paused)

        logger.info(
            f'AutoPause: evaluated={results["evaluated"]} '
            f'paused={len(results["paused"])} '
            f'expired={len(results["expired"])}'
        )
        return results

    # ── Individual rule checkers ───────────────────────────────────

    @staticmethod
    def _is_expired(offer) -> bool:
        """Check if offer has passed its expiry date."""
        if offer.expires_at and timezone.now() > offer.expires_at:
            return True
        if offer.max_completions and offer.total_completions >= offer.max_completions:
            return True
        return False

    @staticmethod
    def _check_fraud_rate(offer) -> dict:
        """Check if fraud rate exceeds threshold."""
        total_clicks = offer.clicks.count()
        if total_clicks < MIN_CLICKS_FOR_EVAL:
            return {'pause': False, 'reason': 'insufficient_data'}

        fraud_clicks = offer.clicks.filter(is_fraud=True).count()
        if total_clicks == 0:
            return {'pause': False, 'reason': 'no_clicks'}

        fraud_rate = Decimal(str(fraud_clicks)) / Decimal(str(total_clicks)) * Decimal('100')

        if fraud_rate > MAX_FRAUD_RATE:
            return {
                'pause' : True,
                'reason': f'{HIGH_FRAUD_REASON}:{fraud_rate:.1f}%',
            }
        return {'pause': False, 'reason': 'ok'}

    @staticmethod
    def _check_cvr(offer) -> dict:
        """Check if CVR is below threshold."""
        total_clicks = offer.clicks.filter(is_fraud=False).count()
        if total_clicks < MIN_CLICKS_FOR_CVR:
            return {'pause': False, 'reason': 'insufficient_data_for_cvr'}

        cvr = Decimal(str(offer.conversion_rate or '0'))
        if cvr < MIN_CVR_THRESHOLD:
            return {
                'pause' : True,
                'reason': f'{LOW_CVR_PAUSE_REASON}:{cvr:.2f}%',
            }
        return {'pause': False, 'reason': 'ok'}

    @staticmethod
    def _check_caps(offer) -> dict:
        """Check if any binding cap is exhausted."""
        now = timezone.now()
        for cap in offer.caps.filter(pause_on_hit=True):
            # Reset expired cap window
            if cap.reset_at and now >= cap.reset_at:
                cap.current_count = 0
                cap.save(update_fields=['current_count'])
                continue
            if cap.current_count >= cap.cap_limit:
                return {
                    'pause' : True,
                    'reason': f'{CAP_REACHED_REASON}:{cap.cap_type}',
                }
        return {'pause': False, 'reason': 'ok'}

    @staticmethod
    def _pause_budget_depleted() -> list:
        """Pause offers linked to budget-depleted campaigns."""
        from api.offer_inventory.models import Campaign, Offer
        from django.db.models import F

        paused = []
        depleted_campaigns = Campaign.objects.filter(
            status='live', budget__gt=0
        ).filter(spent__gte=F('budget'))

        for campaign in depleted_campaigns:
            # Pause the campaign
            Campaign.objects.filter(id=campaign.id).update(status='paused')
            # Pause all associated offers (if tracked via network)
            if campaign.network:
                offers_to_pause = Offer.objects.filter(
                    network=campaign.network, status='active'
                )
                for offer in offers_to_pause:
                    AutoPauseEngine._pause(offer, BUDGET_DEPLETED_REASON)
                    paused.append({
                        'id'    : str(offer.id),
                        'title' : offer.title,
                        'reason': BUDGET_DEPLETED_REASON,
                    })

        return paused

    # ── Action helpers ─────────────────────────────────────────────

    @staticmethod
    def _pause(offer, reason: str):
        """Pause an offer and log the action."""
        from api.offer_inventory.models import Offer, OfferLog
        from django.core.cache import cache

        Offer.objects.filter(id=offer.id, status='active').update(status='paused')
        OfferLog.objects.create(
            offer     =offer,
            old_status='active',
            new_status='paused',
            note      =reason,
        )
        # Invalidate SmartLink cap cache
        cache.delete(f'offer_avail:{offer.id}')
        cache.delete(f'offer_epc:{offer.id}')

        logger.warning(f'Offer auto-paused: id={offer.id} title="{offer.title}" reason={reason}')

    @staticmethod
    def _set_status(offer, status: str, reason: str):
        """Set offer to a specific status."""
        from api.offer_inventory.models import Offer, OfferLog
        Offer.objects.filter(id=offer.id).update(status=status)
        OfferLog.objects.create(
            offer     =offer,
            old_status='active',
            new_status=status,
            note      =reason,
        )
        logger.info(f'Offer status set: id={offer.id} → {status} ({reason})')

    # ── Manual controls ────────────────────────────────────────────

    @staticmethod
    def resume_offer(offer_id: str, note: str = 'Manual resume') -> bool:
        """Manually resume a paused offer."""
        from api.offer_inventory.models import Offer, OfferLog

        updated = Offer.objects.filter(id=offer_id, status='paused').update(status='active')
        if updated:
            offer = Offer.objects.get(id=offer_id)
            OfferLog.objects.create(
                offer     =offer,
                old_status='paused',
                new_status='active',
                note      =note,
            )
            from django.core.cache import cache
            cache.delete(f'offer_avail:{offer_id}')
            logger.info(f'Offer manually resumed: {offer_id}')
        return updated > 0

    @staticmethod
    def get_pause_history(offer_id: str) -> list:
        """Get pause/resume history for an offer."""
        from api.offer_inventory.models import OfferLog
        return list(
            OfferLog.objects.filter(offer_id=offer_id)
            .order_by('-created_at')
            .values('old_status', 'new_status', 'note', 'created_at')[:20]
        )

    @staticmethod
    def get_paused_offers_summary() -> list:
        """List all paused offers with reason."""
        from api.offer_inventory.models import Offer, OfferLog
        from django.db.models import Subquery, OuterRef

        latest_log = OfferLog.objects.filter(
            offer=OuterRef('pk'), new_status='paused'
        ).order_by('-created_at')

        return list(
            Offer.objects.filter(status='paused')
            .annotate(
                pause_reason=Subquery(latest_log.values('note')[:1])
            )
            .values('id', 'title', 'pause_reason', 'updated_at')
            .order_by('-updated_at')[:100]
        )
