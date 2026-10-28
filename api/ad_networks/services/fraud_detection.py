"""
api/ad_networks/services/fraud_detection.py
Stub — extend as needed.
"""
import logging
logger = logging.getLogger(__name__)


class FraudDetectionService:
    """Ad network fraud detection service stub."""

    @classmethod
    def check(cls, *args, **kwargs):
        return {'is_fraud': False, 'score': 0}
