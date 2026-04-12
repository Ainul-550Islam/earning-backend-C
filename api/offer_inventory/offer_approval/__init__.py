# api/offer_inventory/offer_approval/__init__.py
"""
Offer Approval Workflow — Review and approve advertiser-submitted offers.
Checks: content policy, tracking URL validation, payout verification.
Supports: auto-approve (trusted advertisers), manual review queue.
"""
from .approval_engine import OfferApprovalEngine
from .review_queue    import OfferReviewQueue

__all__ = ['OfferApprovalEngine', 'OfferReviewQueue']
