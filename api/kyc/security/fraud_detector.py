# kyc/security/fraud_detector.py  ── WORLD #1
"""Fraud detection engine for KYC submissions"""
import logging

logger = logging.getLogger(__name__)


class FraudDetector:
    """
    Multi-signal fraud detection.
    Call .check(kyc, request=request) → FraudResult
    """

    def __init__(self, kyc, request=None):
        self.kyc     = kyc
        self.request = request
        self.signals = {}
        self.risk_score = 0

    def check(self) -> 'FraudResult':
        self._check_blacklist()
        self._check_duplicate()
        self._check_age()
        self._check_name_match()
        self._check_ocr_confidence()
        self._check_ip()
        self._check_multiple_submissions()
        return self._build_result()

    def _check_blacklist(self):
        try:
            from ..models import KYCBlacklist
            flagged = False
            if self.kyc.phone_number   and KYCBlacklist.is_blacklisted('phone',    self.kyc.phone_number):   flagged = True
            if self.kyc.document_number and KYCBlacklist.is_blacklisted('document', self.kyc.document_number): flagged = True
            self.signals['blacklisted'] = flagged
            if flagged: self.risk_score += 60
        except Exception as e:
            logger.warning(f"_check_blacklist: {e}")

    def _check_duplicate(self):
        try:
            from ..models import KYC
            dup = False
            if self.kyc.document_number:
                dup = KYC.objects.filter(
                    document_number=self.kyc.document_number, status='verified'
                ).exclude(id=self.kyc.id).exists()
            if not dup and self.kyc.phone_number:
                dup = KYC.objects.filter(
                    phone_number=self.kyc.phone_number, status='verified'
                ).exclude(id=self.kyc.id).exists()
            self.signals['duplicate'] = dup
            if dup: self.risk_score += 40
        except Exception as e:
            logger.warning(f"_check_duplicate: {e}")

    def _check_age(self):
        try:
            from datetime import date
            if self.kyc.date_of_birth:
                age = (date.today() - self.kyc.date_of_birth).days / 365.25
                under18 = age < 18
                self.signals['age_under_18'] = under18
                if under18: self.risk_score += 50
        except Exception as e:
            logger.warning(f"_check_age: {e}")

    def _check_name_match(self):
        try:
            if self.kyc.extracted_name and self.kyc.full_name:
                from difflib import SequenceMatcher
                sim = SequenceMatcher(
                    None,
                    self.kyc.extracted_name.lower().strip(),
                    self.kyc.full_name.lower().strip()
                ).ratio()
                mismatch = sim < 0.75
                self.signals['name_mismatch'] = mismatch
                if mismatch: self.risk_score += 30
        except Exception as e:
            logger.warning(f"_check_name_match: {e}")

    def _check_ocr_confidence(self):
        try:
            low = self.kyc.ocr_confidence < 0.70
            self.signals['low_ocr'] = low
            if low: self.risk_score += 20
        except Exception as e:
            logger.warning(f"_check_ocr_confidence: {e}")

    def _check_ip(self):
        try:
            if self.request:
                from ..utils.audit_utils import get_client_ip
                ip = get_client_ip(self.request)
                if ip:
                    from ..models import KYCBlacklist
                    ip_blocked = KYCBlacklist.is_blacklisted('ip', ip)
                    self.signals['ip_blacklisted'] = ip_blocked
                    if ip_blocked: self.risk_score += 50
        except Exception as e:
            logger.warning(f"_check_ip: {e}")

    def _check_multiple_submissions(self):
        try:
            from ..models import KYC
            count = KYC.objects.filter(user=self.kyc.user).count()
            multi = count > 3
            self.signals['multiple_submissions'] = multi
            if multi: self.risk_score += 15
        except Exception as e:
            logger.warning(f"_check_multiple_submissions: {e}")

    def _build_result(self):
        score  = min(self.risk_score, 100)
        flags  = [k for k, v in self.signals.items() if v]
        if score <= 30:   level = 'low'
        elif score <= 60: level = 'medium'
        elif score <= 80: level = 'high'
        else:             level = 'critical'
        return FraudResult(score=score, level=level, flags=flags, signals=self.signals)


class FraudResult:
    def __init__(self, score: int, level: str, flags: list, signals: dict):
        self.score   = score
        self.level   = level
        self.flags   = flags
        self.signals = signals

    @property
    def is_high_risk(self) -> bool:
        return self.level in ('high', 'critical')

    @property
    def requires_manual_review(self) -> bool:
        return self.score > 60

    def to_dict(self) -> dict:
        return {
            'risk_score': self.score,
            'risk_level': self.level,
            'flags':      self.flags,
            'requires_manual_review': self.requires_manual_review,
        }
