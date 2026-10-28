# api/wallet/compliance.py
"""
Regulatory compliance layer — GDPR, BFIU (Bangladesh), PCI-DSS, AML/CFT.
Ensures wallet system meets regulatory requirements.

Regulations:
  - GDPR: Data minimization, right to erasure, data portability
  - BFIU (Bangladesh Financial Intelligence Unit): AML reporting
  - PCI-DSS: No full PAN storage, encryption at rest
  - FATF: KYC tiers, beneficial owner verification
"""
import logging
from decimal import Decimal
from django.utils import timezone

logger = logging.getLogger("wallet.compliance")

# Thresholds (BDT)
BFIU_CASH_THRESHOLD    = Decimal("100000")   # BFIU: report > 1 lakh BDT
BFIU_STR_THRESHOLD     = Decimal("500000")   # Suspicious Transaction Report threshold
STRUCTURING_THRESHOLD  = Decimal("9999")     # Just below reporting threshold


class ComplianceChecker:
    """Run compliance checks for wallet operations."""

    @staticmethod
    def check_withdrawal_compliance(user, wallet, amount: Decimal) -> dict:
        """Full compliance check before processing a withdrawal."""
        results = {"compliant": True, "warnings": [], "blocks": []}

        # 1. KYC check
        kyc_result = ComplianceChecker._check_kyc(user, amount)
        if not kyc_result["passed"]:
            results["compliant"] = False
            results["blocks"].append(f"KYC: {kyc_result['reason']}")

        # 2. AML structuring check
        aml_result = ComplianceChecker._check_structuring(wallet, amount)
        if aml_result["flagged"]:
            results["warnings"].append(f"AML: {aml_result['reason']}")
            ComplianceChecker._file_aml_report(user, wallet, amount, aml_result)

        # 3. BFIU reporting threshold
        if amount >= BFIU_CASH_THRESHOLD:
            results["warnings"].append(f"BFIU: Amount {amount} BDT exceeds reporting threshold")
            ComplianceChecker._file_bfiu_report(user, wallet, amount)

        # 4. Sanctions check
        try:
            from .sanctions import SanctionsChecker
            sanctions = SanctionsChecker.check_user(user)
            if sanctions["is_sanctioned"]:
                results["compliant"] = False
                results["blocks"].append(f"Sanctions: {sanctions.get('sanction_reason','Match found')}")
        except Exception: pass

        return results

    @staticmethod
    def _check_kyc(user, amount: Decimal) -> dict:
        """Check KYC level is sufficient for the amount."""
        try:
            from .models_cpalead_extra import KYCVerification
            from .constants import KYC_LIMITS
            kyc   = KYCVerification.objects.filter(user=user, status="approved").order_by("-level").first()
            level = kyc.level if kyc else 0
            limits = KYC_LIMITS.get(level, {})
            daily_limit = limits.get("daily", Decimal("500"))
            if amount > daily_limit:
                return {"passed": False, "reason": f"KYC L{level} daily limit: {daily_limit} BDT"}
        except Exception: pass
        return {"passed": True}

    @staticmethod
    def _check_structuring(wallet, amount: Decimal) -> dict:
        """Detect structuring (amounts just below reporting threshold)."""
        from datetime import timedelta
        from .models.core import WalletTransaction
        if not (STRUCTURING_THRESHOLD - 500 <= amount <= STRUCTURING_THRESHOLD + 100):
            return {"flagged": False}
        week_ago = timezone.now() - timedelta(days=7)
        count = WalletTransaction.objects.filter(
            wallet=wallet, type="withdrawal",
            amount__gte=-(STRUCTURING_THRESHOLD + 200),
            amount__lte=-(STRUCTURING_THRESHOLD - 500),
            created_at__gte=week_ago,
        ).count()
        if count >= 2:
            return {"flagged": True, "reason": f"Structuring pattern: {count+1}x near-threshold in 7 days"}
        return {"flagged": False}

    @staticmethod
    def _file_aml_report(user, wallet, amount: Decimal, aml_info: dict):
        """File AML suspicious transaction report."""
        try:
            from .models_cpalead_extra import AMLFlag
            AMLFlag.objects.get_or_create(
                user=user, flag_type="structuring", is_resolved=False,
                defaults={"wallet": wallet, "suspicious_amount": amount,
                          "details": aml_info.get("reason",""), "risk_score": 75}
            )
            logger.warning(f"AML STR filed: user={user.id} amount={amount}")
        except Exception as e:
            logger.error(f"AML report error: {e}")

    @staticmethod
    def _file_bfiu_report(user, wallet, amount: Decimal):
        """Log BFIU cash transaction report."""
        logger.info(f"BFIU CTR: user={user.id} amount={amount} BDT at {timezone.now()}")


class GDPRCompliance:
    """GDPR compliance utilities."""

    @staticmethod
    def export_user_data(user) -> dict:
        """GDPR Article 20 — data portability export."""
        from .data_export import UserDataExporter
        return UserDataExporter.export_user_data(user)

    @staticmethod
    def delete_user_data(user) -> dict:
        """GDPR Article 17 — right to erasure (soft delete / anonymize)."""
        deleted = {}
        try:
            from .models.notification import WalletNotification
            count = WalletNotification.objects.filter(user=user).delete()[0]
            deleted["notifications"] = count
        except Exception: pass
        try:
            from .models.withdrawal import WithdrawalMethod
            for pm in WithdrawalMethod.objects.filter(user=user):
                pm.account_number = "****DELETED****"
                pm.account_name   = "DELETED"
                pm.save(update_fields=["account_number","account_name","updated_at"])
            deleted["payment_methods_anonymized"] = True
        except Exception: pass
        logger.info(f"GDPR erasure: user={user.id} deleted={deleted}")
        return deleted

    @staticmethod
    def check_data_minimization() -> list:
        """
        Check that no unnecessary PAN data is stored in plaintext.
        Returns list of compliance issues.
        """
        issues = []
        try:
            from .models.withdrawal import WithdrawalMethod
            pms = WithdrawalMethod.objects.all()
            for pm in pms:
                if pm.account_number and len(pm.account_number) > 20:
                    if not pm.account_number.startswith("****"):
                        issues.append(f"PM {pm.id}: Full account number stored unmasked")
        except Exception: pass
        return issues
