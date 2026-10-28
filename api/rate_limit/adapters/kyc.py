# api/rate_limit/adapters/kyc.py
"""
KYC System ↔ Rate Limit Adapter
==================================
Covers: KYC submit, document upload, status check, re-verification.

Usage in api/kyc/:
    from api.rate_limit.adapters.kyc import KYCRateLimitAdapter

    class KYCMixin:
        def check_rate_limit(self, action, limit, window):
            # Replace internal KYCRateLimiter with this adapter
            return KYCRateLimitAdapter.check_action(
                action, self.request
            ).allowed

Usage — replaces api/kyc/mixins.py → KYCRateLimitMixin.check_rate_limit()
"""

import logging
from api.rate_limit.integration_service import RateLimitIntegrationService, RateLimitResult

logger = logging.getLogger('rate_limit.adapters.kyc')


class KYCRateLimitAdapter:
    """Adapter for api/kyc system."""

    @staticmethod
    def check_submit(request, user=None) -> RateLimitResult:
        """
        Check before KYC form submission.
        Where to call: api/kyc/views.py → KYCSubmitView
        """
        user = user or getattr(request, 'user', None)
        return RateLimitIntegrationService.check('kyc_submit', request=request, user=user)

    @staticmethod
    def check_document_upload(request, user=None) -> RateLimitResult:
        """
        Check before document upload.
        Where to call: api/kyc/ → document upload endpoint
        """
        user = user or getattr(request, 'user', None)
        return RateLimitIntegrationService.check('kyc_document_upload', request=request, user=user)

    @staticmethod
    def check_status(request, user=None) -> RateLimitResult:
        """
        Check before KYC status polling.
        Where to call: api/kyc/ → status endpoint
        """
        user = user or getattr(request, 'user', None)
        return RateLimitIntegrationService.check('kyc_status_check', request=request, user=user)

    @staticmethod
    def check_reverification(request, user=None) -> RateLimitResult:
        """
        Check before re-verification request.
        Where to call: api/kyc/ → re-verify endpoint
        """
        user = user or getattr(request, 'user', None)
        return RateLimitIntegrationService.check('kyc_reverification', request=request, user=user)

    @staticmethod
    def check_action(action: str, request=None, user=None) -> RateLimitResult:
        """
        Generic check. Drop-in for KYCRateLimitMixin.check_rate_limit().
        Replaces: limiter.allow(action, limit=limit, window=window)
        """
        kyc_map = {
            'submit': 'kyc_submit',
            'document_upload': 'kyc_document_upload',
            'status': 'kyc_status_check',
            'reverification': 'kyc_reverification',
        }
        mapped = kyc_map.get(action, 'kyc_submit')
        user = user or (getattr(request, 'user', None) if request else None)
        return RateLimitIntegrationService.check(mapped, request=request, user=user)

    @staticmethod
    def notify_kyc_verified(user) -> bool:
        """
        Call when KYC is approved. Reduces suspicion score + raises limits.
        Where to call: api/kyc/ → KYC approval webhook/admin action
        """
        return RateLimitIntegrationService.sync_kyc_status(user, kyc_verified=True)

    @staticmethod
    def notify_kyc_rejected(user) -> bool:
        """
        Call when KYC is rejected/flagged.
        Where to call: api/kyc/ → KYC rejection
        """
        return RateLimitIntegrationService.sync_kyc_status(user, kyc_verified=False)
