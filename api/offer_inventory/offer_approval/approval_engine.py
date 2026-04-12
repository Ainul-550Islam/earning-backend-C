# api/offer_inventory/offer_approval/approval_engine.py
"""
Offer Approval Engine — Auto and manual offer review pipeline.
Ensures only quality, policy-compliant offers go live.
"""
import logging
from django.utils import timezone

logger = logging.getLogger(__name__)

AUTO_APPROVE_TRUSTED_NETWORKS = True
TRUSTED_NETWORK_MIN_CONVERSIONS = 100


class OfferApprovalEngine:
    """
    Two-track approval:
    1. Auto-approve: trusted networks with good history → instant live
    2. Manual review: new networks, high payout, flagged content → queue
    """

    @classmethod
    def submit_for_review(cls, offer, submitted_by=None) -> dict:
        """Submit offer for review. Returns approval decision."""
        # Run all checks
        results = cls._run_checks(offer)
        passed  = all(r['passed'] for r in results)
        critical = [r for r in results if not r['passed'] and r['severity'] == 'critical']

        # Critical failures = instant reject
        if critical:
            cls._reject(offer, reasons=[r['message'] for r in critical])
            return {
                'decision'  : 'rejected',
                'reasons'   : [r['message'] for r in critical],
                'checks'    : results,
            }

        # Auto-approve check
        if passed and cls._is_auto_approvable(offer):
            cls._approve(offer, auto=True)
            return {'decision': 'auto_approved', 'checks': results}

        # Queue for manual review
        cls._queue_for_review(offer, results)
        return {
            'decision': 'pending_review',
            'checks'  : results,
            'message' : 'Offer is in the review queue. Expected: 24h.',
        }

    @staticmethod
    def _run_checks(offer) -> list:
        """Run all offer validation checks."""
        from api.offer_inventory.compliance_legal.ad_content_filter import AdContentFilter

        results = []

        # 1. Content policy
        content = AdContentFilter.validate_offer(offer)
        results.append({
            'check'   : 'content_policy',
            'passed'  : content['approved'],
            'severity': 'critical',
            'message' : f"Content violations: {content['violations']}" if not content['approved'] else 'OK',
        })

        # 2. Tracking URL
        has_url = bool(offer.offer_url and offer.offer_url.startswith('http'))
        results.append({
            'check'   : 'tracking_url',
            'passed'  : has_url,
            'severity': 'critical',
            'message' : 'Missing or invalid offer URL' if not has_url else 'OK',
        })

        # 3. Payout sanity
        payout_ok = float(offer.payout_amount or 0) > 0
        results.append({
            'check'   : 'payout_positive',
            'passed'  : payout_ok,
            'severity': 'critical',
            'message' : 'Payout must be > 0' if not payout_ok else 'OK',
        })

        # 4. Description length
        desc_ok = len(offer.description or '') >= 20
        results.append({
            'check'   : 'description_length',
            'passed'  : desc_ok,
            'severity': 'warning',
            'message' : 'Description too short (<20 chars)' if not desc_ok else 'OK',
        })

        # 5. Network configured
        net_ok = offer.network_id is not None
        results.append({
            'check'   : 'network_assigned',
            'passed'  : net_ok,
            'severity': 'warning',
            'message' : 'No network assigned' if not net_ok else 'OK',
        })

        return results

    @staticmethod
    def _is_auto_approvable(offer) -> bool:
        """Check if offer qualifies for auto-approval."""
        if not AUTO_APPROVE_TRUSTED_NETWORKS:
            return False
        if not offer.network_id:
            return False
        from api.offer_inventory.models import Conversion
        network_convs = Conversion.objects.filter(
            offer__network=offer.network,
            status__name='approved',
        ).count()
        return network_convs >= TRUSTED_NETWORK_MIN_CONVERSIONS

    @staticmethod
    def _approve(offer, auto: bool = False, reviewer=None):
        from api.offer_inventory.models import Offer
        Offer.objects.filter(id=offer.id).update(
            status='active',
            approved_at=timezone.now(),
        )
        logger.info(f'Offer approved: {offer.id} auto={auto}')

    @staticmethod
    def _reject(offer, reasons: list):
        from api.offer_inventory.models import Offer
        Offer.objects.filter(id=offer.id).update(
            status     ='rejected',
            rejected_at=timezone.now(),
            reject_reason='; '.join(reasons[:3]),
        )
        logger.info(f'Offer rejected: {offer.id} reasons={reasons}')

    @staticmethod
    def _queue_for_review(offer, check_results: list):
        from api.offer_inventory.models import Offer
        Offer.objects.filter(id=offer.id).update(status='pending_review')
        logger.info(f'Offer queued for review: {offer.id}')

    @staticmethod
    def approve(offer_id: str, reviewer) -> bool:
        """Manual approval by admin."""
        from api.offer_inventory.models import Offer
        updated = Offer.objects.filter(id=offer_id).update(
            status='active', approved_at=timezone.now()
        )
        logger.info(f'Offer manually approved: {offer_id} by {reviewer.username}')
        return updated > 0

    @staticmethod
    def reject(offer_id: str, reviewer, reason: str) -> bool:
        """Manual rejection by admin."""
        from api.offer_inventory.models import Offer
        updated = Offer.objects.filter(id=offer_id).update(
            status='rejected',
            rejected_at=timezone.now(),
            reject_reason=reason,
        )
        logger.info(f'Offer rejected: {offer_id} by {reviewer.username}')
        return updated > 0


# ─────────────────────────────────────────────────────
# offer_approval/review_queue.py
# ─────────────────────────────────────────────────────

class OfferReviewQueue:
    """Manage the offer manual review queue."""

    @staticmethod
    def get_pending(limit: int = 50) -> list:
        """Get all offers pending review."""
        from api.offer_inventory.models import Offer
        return list(
            Offer.objects.filter(status__in=['pending_review', 'draft'])
            .select_related('network', 'category')
            .order_by('-created_at')
            .values(
                'id', 'title', 'payout_amount', 'reward_amount',
                'network__name', 'category__name', 'created_at',
            )
            [:limit]
        )

    @staticmethod
    def get_stats() -> dict:
        """Review queue statistics."""
        from api.offer_inventory.models import Offer
        from django.db.models import Count
        return dict(
            Offer.objects.values_list('status')
            .annotate(count=Count('id'))
        )

    @staticmethod
    def bulk_approve(offer_ids: list, reviewer) -> dict:
        """Bulk approve multiple offers."""
        approved = 0
        for oid in offer_ids:
            if OfferApprovalEngine.approve(oid, reviewer):
                approved += 1
        return {'approved': approved, 'total': len(offer_ids)}

    @staticmethod
    def get_review_age_report() -> list:
        """Offers waiting longest in review queue."""
        from api.offer_inventory.models import Offer
        from django.utils import timezone
        return list(
            Offer.objects.filter(status='pending_review')
            .order_by('created_at')
            .values('id', 'title', 'created_at')
            .annotate()
            [:20]
        )
