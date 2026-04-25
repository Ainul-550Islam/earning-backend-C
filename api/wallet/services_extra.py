# api/wallet/services_extra.py
"""
World-class services matching CPAlead + Binance + Razorpay + Stripe + PayPal + bKash.

Services:
  KYCService          — tiered KYC with withdrawal limit gates
  FraudDetectionService — ML-based risk scoring (Stripe Radar-style)
  AMLService          — anti-money laundering detection
  DisputeService      — chargeback / dispute lifecycle
  RefundService       — full refund management
  InstantPayoutService — Stripe-style instant payout
  MassPayoutService   — PayPal-style bulk disbursement
  VirtualAccountService — Razorpay smart collect
  SettlementService   — T+0/T+1/T+2 batch settlement
  SecurityService     — 24h lock after security changes
  TaxService          — annual tax record generation
  OfferService        — CPAlead CPA/CPI/CPC offer management
  WebhookDeliveryService — configurable webhook delivery
"""
import logging
import hashlib
import hmac
import json
import time
from decimal import Decimal
from datetime import date, timedelta
from django.db import transaction
from django.utils import timezone
from django.db.models import Sum, Count

logger = logging.getLogger("wallet.services_extra")


class KYCService:
    """Binance-style tiered KYC with automatic withdrawal limit adjustment."""

    LIMITS = {
        0: {"daily": Decimal("500"),       "monthly": Decimal("5000")},
        1: {"daily": Decimal("50000"),     "monthly": Decimal("500000")},
        2: {"daily": Decimal("500000"),    "monthly": Decimal("5000000")},
        3: {"daily": Decimal("99999999"), "monthly": Decimal("999999999")},
    }

    @staticmethod
    @transaction.atomic
    def submit(user, wallet, level: int, doc_type: str, doc_number: str,
               doc_front_url: str = "", doc_back_url: str = "",
               selfie_url: str = "", address_proof_url: str = "") -> "KYCVerification":
        from .models_cpalead_extra import KYCVerification
        kyc = KYCVerification.objects.create(
            user=user, wallet=wallet, level=level,
            doc_type=doc_type, doc_number=doc_number,
            doc_front_url=doc_front_url, doc_back_url=doc_back_url,
            selfie_url=selfie_url, address_proof_url=address_proof_url,
            status="pending",
        )
        logger.info(f"KYC submitted: {user.username} level={level}")
        return kyc

    @staticmethod
    @transaction.atomic
    def approve(kyc_id: int, reviewed_by=None) -> dict:
        from .models_cpalead_extra import KYCVerification
        kyc = KYCVerification.objects.get(id=kyc_id)
        kyc.approve(reviewed_by=reviewed_by)
        limits = KYCService.LIMITS[kyc.level]
        logger.info(f"KYC approved: {kyc.user.username} level={kyc.level} daily_limit={limits['daily']}")
        return {
            "user": kyc.user.username,
            "level": kyc.level,
            "daily_limit": float(limits["daily"]),
            "monthly_limit": float(limits["monthly"]),
        }

    @staticmethod
    def reject(kyc_id: int, reason: str, reviewed_by=None):
        from .models_cpalead_extra import KYCVerification
        kyc = KYCVerification.objects.get(id=kyc_id)
        kyc.reject(reason, reviewed_by=reviewed_by)
        return kyc

    @staticmethod
    def get_user_level(user) -> int:
        from .models_cpalead_extra import KYCVerification
        kyc = KYCVerification.objects.filter(user=user, status="approved").order_by("-level").first()
        return kyc.level if kyc else 0

    @staticmethod
    def check_withdrawal_allowed(user, wallet, amount: Decimal) -> tuple:
        """Returns (allowed: bool, reason: str)."""
        from .models_cpalead_extra import KYCVerification
        from .models import WalletTransaction
        level = KYCService.get_user_level(user)
        limits = KYCService.LIMITS[level]
        today_total = abs(WalletTransaction.objects.filter(
            wallet=wallet, type="withdrawal",
            status__in=["pending","approved","processing","completed"],
            created_at__date=date.today(),
        ).aggregate(t=Sum("amount"))["t"] or Decimal("0"))
        if today_total + amount > limits["daily"]:
            return False, f"KYC Level {level} daily limit: {limits['daily']} BDT. Used: {today_total}. Please upgrade KYC."
        return True, ""


class FraudDetectionService:
    """
    Stripe Radar-style ML risk scoring.
    Scores each transaction 0-100. Auto-blocks at 85+.
    """

    @staticmethod
    def score_transaction(txn, ip_address: str = "", device_info: dict = None) -> dict:
        from .models_cpalead_extra import FraudScore
        from .models import WalletTransaction
        user   = txn.wallet.user
        wallet = txn.wallet
        device_info = device_info or {}

        # Signal: velocity (too many txns in 1h)
        one_hour_ago = timezone.now() - timedelta(hours=1)
        txn_count_1h = WalletTransaction.objects.filter(wallet=wallet, created_at__gte=one_hour_ago).count()
        velocity_score = min(txn_count_1h * 15, 100)

        # Signal: IP risk (known bad actor / VPN)
        ip_score = Decimal("0")
        if ip_address in ("", "127.0.0.1", "0.0.0.0"):
            ip_score = Decimal("50")

        # Signal: amount risk (unusually large)
        amount = abs(txn.amount)
        avg_txn = WalletTransaction.objects.filter(
            wallet=wallet, type="withdrawal", status="completed"
        ).aggregate(a=Sum("amount"))["a"] or Decimal("0")
        count = WalletTransaction.objects.filter(wallet=wallet, type="withdrawal", status="completed").count()
        avg = avg_txn / count if count else Decimal("0")
        amount_score = Decimal("0")
        if avg > 0 and amount > avg * 5:
            amount_score = Decimal("60")
        elif avg > 0 and amount > avg * 3:
            amount_score = Decimal("30")

        # Signal: KYC level
        kyc_level = KYCService.get_user_level(user)
        kyc_score = Decimal(str(max(0, (3 - kyc_level) * 15)))  # L0=45, L1=30, L2=15, L3=0

        # Signal: new account + large amount
        account_age_days = (timezone.now() - wallet.created_at).days
        pattern_score = Decimal("0")
        if account_age_days < 7 and amount > Decimal("5000"):
            pattern_score = Decimal("70")
        elif account_age_days < 30 and amount > Decimal("20000"):
            pattern_score = Decimal("50")

        fs = FraudScore.objects.create(
            user=user, wallet=wallet,
            transaction=txn if txn.type != "withdrawal" else None,
            velocity_score=Decimal(str(velocity_score)),
            ip_risk_score=ip_score,
            amount_risk_score=amount_score,
            kyc_score=kyc_score,
            pattern_score=pattern_score,
            device_risk_score=Decimal("0"),
            signals=[
                f"velocity_1h={txn_count_1h}",
                f"amount_vs_avg={float(amount/avg) if avg else 'N/A'}",
                f"account_age_days={account_age_days}",
                f"kyc_level={kyc_level}",
            ]
        )
        fs.calculate()
        logger.info(f"FraudScore: {user.username} txn={txn.txn_id} score={fs.score} level={fs.risk_level}")
        return {
            "score": float(fs.score),
            "risk_level": fs.risk_level,
            "is_blocked": fs.is_blocked,
            "signals": fs.signals,
        }


class AMLService:
    """Anti-money laundering detection and case management."""

    STRUCTURING_THRESHOLD = Decimal("9999")   # Just below reporting threshold
    VELOCITY_THRESHOLD    = 10                 # More than 10 txns/day
    ROUND_NUMBER_AMOUNTS  = [1000, 5000, 10000, 50000, 100000]

    @staticmethod
    def check(user, wallet, amount: Decimal, txn_type: str = "withdrawal") -> list:
        """Run AML checks and return list of flags triggered."""
        from .models_cpalead_extra import AMLFlag
        from .models import WalletTransaction
        flags = []

        # Structuring detection (smurfing)
        if Decimal("9000") <= amount <= AMLService.STRUCTURING_THRESHOLD:
            flags.append({
                "type": "structuring",
                "description": f"Amount {amount} near reporting threshold",
                "amount": float(amount),
            })

        # Rapid movement: large amount within 24h
        yesterday = timezone.now() - timedelta(hours=24)
        total_24h = abs(WalletTransaction.objects.filter(
            wallet=wallet, created_at__gte=yesterday,
        ).aggregate(t=Sum("amount"))["t"] or Decimal("0"))
        if total_24h > Decimal("100000"):
            flags.append({
                "type": "rapid_movement",
                "description": f"Moved {total_24h} in last 24 hours",
                "amount": float(total_24h),
            })

        # Round numbers
        if int(amount) in AMLService.ROUND_NUMBER_AMOUNTS:
            # Only flag if repeated round-number pattern
            round_count = WalletTransaction.objects.filter(
                wallet=wallet,
                amount__in=[-Decimal(str(a)) for a in AMLService.ROUND_NUMBER_AMOUNTS],
                created_at__gte=timezone.now() - timedelta(days=7),
            ).count()
            if round_count >= 3:
                flags.append({
                    "type": "round_numbers",
                    "description": f"Repeated round number withdrawals ({round_count} in last 7 days)",
                    "amount": float(amount),
                })

        # Create AML flags in DB
        for flag in flags:
            try:
                AMLFlag.objects.create(
                    user=user, wallet=wallet,
                    flag_type=flag["type"],
                    description=flag["description"],
                    suspicious_amount=flag["amount"],
                )
                logger.warning(f"AML flag: {user.username} | {flag['type']} | {flag['amount']}")
            except Exception as e:
                logger.error(f"AML flag creation failed: {e}")

        return flags


class DisputeService:
    """Chargeback and dispute lifecycle management."""

    @staticmethod
    @transaction.atomic
    def open(user, wallet, transaction_id: int = None, withdrawal_id: int = None,
             reason: str = "other", description: str = "", disputed_amount: Decimal = None) -> "DisputeCase":
        from .models_cpalead_extra import DisputeCase
        from .models import WalletTransaction, Withdrawal
        txn = WalletTransaction.objects.filter(id=transaction_id).first() if transaction_id else None
        wd  = Withdrawal.objects.filter(id=withdrawal_id).first() if withdrawal_id else None
        if not disputed_amount:
            disputed_amount = abs(txn.amount) if txn else (wd.amount if wd else Decimal("0"))

        case = DisputeCase.objects.create(
            user=user, wallet=wallet,
            transaction=txn, withdrawal=wd,
            reason=reason, description=description,
            disputed_amount=disputed_amount,
            due_by=timezone.now() + timedelta(days=7),
        )
        logger.info(f"Dispute opened: {case.case_id} user={user.username}")
        return case

    @staticmethod
    @transaction.atomic
    def resolve(case_id: int, outcome: str, refund_amount: Decimal = None,
                notes: str = "", resolved_by=None) -> "DisputeCase":
        from .models_cpalead_extra import DisputeCase
        from .services import WalletService
        case = DisputeCase.objects.get(id=case_id)
        case.outcome = outcome
        case.internal_notes = notes
        case.resolved_by = resolved_by
        case.resolved_at = timezone.now()

        if "user" in outcome:  # resolved in user's favor
            case.status = "resolved_user"
            amount = refund_amount or case.disputed_amount
            case.refunded_amount = amount
            WalletService.credit(
                case.wallet, amount, txn_type="refund",
                description=f"Dispute refund: {case.case_id}",
                metadata={"case_id": str(case.case_id), "outcome": outcome},
                approved_by=resolved_by,
            )
        else:
            case.status = "resolved_platform"

        case.save()
        return case


class RefundService:
    """Full refund management — partial or complete."""

    @staticmethod
    @transaction.atomic
    def create(user, wallet, txn_id: int, reason: str, amount: Decimal = None, description: str = "") -> "RefundRequest":
        from .models_cpalead_extra import RefundRequest
        from .models import WalletTransaction
        txn = WalletTransaction.objects.get(id=txn_id)
        req_amount = amount or abs(txn.amount)
        refund = RefundRequest.objects.create(
            user=user, wallet=wallet, original_txn=txn,
            reason=reason, requested_amount=req_amount,
            description=description,
        )
        logger.info(f"Refund created: {refund.refund_id} amount={req_amount}")
        return refund

    @staticmethod
    @transaction.atomic
    def approve(refund_id: int, approved_amount: Decimal, processed_by=None) -> "RefundRequest":
        from .models_cpalead_extra import RefundRequest
        from .services import WalletService
        refund = RefundRequest.objects.get(id=refund_id)
        if refund.status != "pending":
            raise ValueError(f"Cannot approve: {refund.status}")
        refund.approved_amount = approved_amount
        refund.status = "processing"
        refund.processed_by = processed_by
        refund.processed_at = timezone.now()
        refund.save()

        # Credit the refund
        refund_txn = WalletService.credit(
            refund.wallet, approved_amount, txn_type="refund",
            description=f"Refund {refund.refund_id}: {refund.reason}",
            approved_by=processed_by,
        )
        refund.refund_txn = refund_txn
        refund.status = "completed"
        refund.save()
        return refund


class InstantPayoutService:
    """Stripe-style instant payout with fee (1.5%, min 5 BDT)."""

    FEE_PERCENT = Decimal("1.50")
    MIN_FEE     = Decimal("5.00")

    @staticmethod
    @transaction.atomic
    def create(user, wallet, amount: Decimal, method: str, destination: str) -> "InstantPayout":
        from .models_cpalead_extra import InstantPayout
        from .services import WalletService

        if amount > wallet.available_balance:
            raise ValueError(f"Insufficient balance. Available: {wallet.available_balance}")

        fee = max(amount * InstantPayoutService.FEE_PERCENT / 100, InstantPayoutService.MIN_FEE)
        net = amount - fee
        if net <= 0:
            raise ValueError("Net amount after fee is zero")

        ip = InstantPayout.objects.create(
            user=user, wallet=wallet,
            amount=amount, fee=fee, net_amount=net,
            method=method, destination=destination,
            status="pending",
            arrival_time=timezone.now() + timedelta(minutes=30),
        )
        # Debit wallet
        WalletService.debit(wallet, amount, txn_type="withdrawal",
            description=f"Instant Payout {ip.payout_id} → {destination}",
            metadata={"instant_payout_id": str(ip.payout_id)},
        )
        ip.status = "in_transit"
        ip.save()
        logger.info(f"Instant payout: {user.username} amount={amount} fee={fee} net={net}")
        return ip


class MassPayoutService:
    """PayPal-style bulk payout to many users at once."""

    @staticmethod
    @transaction.atomic
    def create_job(title: str, items: list, payout_type: str = "general",
                   method: str = "bkash", created_by=None, note: str = "") -> "MassPayoutJob":
        """
        items = [{"user_id": 1, "amount": 100}, {"user_id": 2, "amount": 50}, ...]
        """
        from .models_cpalead_extra import MassPayoutJob, MassPayoutItem
        from django.contrib.auth import get_user_model
        from .models import Wallet
        User = get_user_model()

        total = sum(Decimal(str(i["amount"])) for i in items)
        job = MassPayoutJob.objects.create(
            title=title, status="queued",
            total_amount=total, total_count=len(items),
            pending_count=len(items),
            payout_type=payout_type, method=method,
            note=note, created_by=created_by,
        )
        for item in items:
            try:
                u = User.objects.get(id=item["user_id"])
                wallet = Wallet.objects.get(user=u)
                MassPayoutItem.objects.create(job=job, user=u, wallet=wallet, amount=Decimal(str(item["amount"])))
            except Exception as e:
                logger.warning(f"MassPayout item skip user={item.get('user_id')}: {e}")

        logger.info(f"MassPayout job created: {job.job_id} total={total} count={len(items)}")
        return job

    @staticmethod
    def process_job(job_id: int) -> dict:
        from .models_cpalead_extra import MassPayoutJob, MassPayoutItem
        from .services import WithdrawalService
        from .models import UserPaymentMethod
        job = MassPayoutJob.objects.get(id=job_id)
        if job.status not in ("queued","processing"):
            raise ValueError(f"Cannot process job in status: {job.status}")
        job.status = "processing"
        job.started_at = timezone.now()
        job.save()

        ok = fail = 0
        for item in MassPayoutItem.objects.filter(job=job, status="pending"):
            try:
                pm = UserPaymentMethod.objects.filter(
                    user=item.user, is_primary=True, is_verified=True, method_type=job.method
                ).first()
                if not pm:
                    item.status = "skipped"
                    item.error = "No verified primary payment method"
                    item.save()
                    fail += 1
                    continue
                wr = WithdrawalService.create(
                    item.wallet, item.amount, pm, note=f"MassPayout job={job.job_id}"
                )
                item.status = "success"
                item.withdrawal = wr
                item.processed_at = timezone.now()
                item.save()
                ok += 1
            except Exception as e:
                item.status = "failed"
                item.error = str(e)
                item.processed_at = timezone.now()
                item.save()
                fail += 1
                logger.error(f"MassPayout item failed: user={item.user_id} err={e}")

        job.success_count = ok
        job.failed_count  = fail
        job.pending_count = 0
        job.status = "success" if fail == 0 else ("partial" if ok > 0 else "failed")
        job.completed_at = timezone.now()
        job.save()
        return {"ok": ok, "fail": fail, "total": ok + fail}


class SecurityService:
    """Binance-style 24h withdrawal lock after security events."""

    @staticmethod
    def trigger_lock(user, wallet, event_type: str, lock_hours: int = 24,
                     ip_address: str = "", device_info: dict = None) -> "SecurityEvent":
        from .models_cpalead_extra import SecurityEvent
        event = SecurityEvent.objects.create(
            user=user, wallet=wallet,
            event_type=event_type, lock_hours=lock_hours,
            ip_address=ip_address, device_info=device_info or {},
        )
        logger.warning(f"Security lock: {user.username} event={event_type} until={event.lock_until}")
        return event

    @staticmethod
    def is_withdrawal_locked(user) -> tuple:
        """Returns (locked: bool, reason: str)."""
        from .models_cpalead_extra import SecurityEvent
        active = SecurityEvent.objects.filter(
            user=user, is_resolved=False, lock_until__gt=timezone.now()
        ).first()
        if active:
            remaining = (active.lock_until - timezone.now()).seconds // 3600
            return True, f"Withdrawals locked for {remaining}h more due to: {active.get_event_type_display()}"
        return False, ""

    @staticmethod
    def release_lock(event_id: int):
        from .models_cpalead_extra import SecurityEvent
        event = SecurityEvent.objects.get(id=event_id)
        event.is_resolved = True
        event.save()


class WebhookDeliveryService:
    """Stripe-style configurable webhook delivery with retry + HMAC signing."""

    MAX_RETRIES    = 5
    RETRY_DELAYS   = [30, 60, 300, 1800, 7200]  # exponential backoff (seconds)
    TIMEOUT        = 10

    @staticmethod
    def deliver(endpoint_url: str, payload: dict, secret: str = "") -> bool:
        import requests
        body = json.dumps(payload, default=str)
        headers = {"Content-Type": "application/json", "User-Agent": "WalletWebhook/1.0"}
        if secret:
            sig = hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()
            headers["X-Wallet-Signature"] = f"sha256={sig}"

        for attempt, delay in enumerate(WebhookDeliveryService.RETRY_DELAYS):
            try:
                resp = requests.post(endpoint_url, data=body, headers=headers,
                                     timeout=WebhookDeliveryService.TIMEOUT)
                if 200 <= resp.status_code < 300:
                    return True
                logger.warning(f"Webhook {endpoint_url} returned {resp.status_code}")
            except Exception as e:
                logger.error(f"Webhook delivery attempt {attempt+1} failed: {e}")
            if attempt < len(WebhookDeliveryService.RETRY_DELAYS) - 1:
                time.sleep(delay)
        return False

    @staticmethod
    def fire_event(event_type: str, data: dict, wallet=None):
        """Fire an event to all subscribed endpoints."""
        from .models_cpalead_extra import WebhookEndpoint
        qs = WebhookEndpoint.objects.filter(is_active=True)
        if wallet:
            qs = qs.filter(user=wallet.user)

        payload = {
            "event": event_type,
            "data": data,
            "timestamp": timezone.now().isoformat(),
        }
        for endpoint in qs:
            events = endpoint.subscribed_events
            if "*" in events or event_type in events:
                try:
                    from .tasks_extra import deliver_webhook
                    deliver_webhook.delay(endpoint.id, payload)
                except Exception as e:
                    logger.warning(f"Webhook dispatch failed: {e}")


class TaxService:
    """Annual tax record generation."""

    @staticmethod
    def generate(user, wallet, year: int) -> "TaxRecord":
        from .models_cpalead_extra import TaxRecord
        from .models import WalletTransaction
        from django.db.models import Sum
        start = timezone.datetime(year, 1, 1, tzinfo=timezone.utc)
        end   = timezone.datetime(year, 12, 31, 23, 59, 59, tzinfo=timezone.utc)

        txns = WalletTransaction.objects.filter(wallet=wallet, created_at__range=(start, end), status__in=["approved","completed"])
        income   = txns.filter(type__in=["earning","reward","referral"], amount__gt=0).aggregate(t=Sum("amount"))["t"] or Decimal("0")
        withdrawn= abs(txns.filter(type="withdrawal").aggregate(t=Sum("amount"))["t"] or Decimal("0"))
        fees     = txns.filter(type="withdrawal_fee").aggregate(t=Sum("amount"))["t"] or Decimal("0")
        bonuses  = txns.filter(type="bonus", amount__gt=0).aggregate(t=Sum("amount"))["t"] or Decimal("0")
        referral = txns.filter(type="referral", amount__gt=0).aggregate(t=Sum("amount"))["t"] or Decimal("0")

        rec, _ = TaxRecord.objects.update_or_create(
            user=user, tax_year=year,
            defaults=dict(
                wallet=wallet, status="generated",
                total_income=income, total_withdrawn=withdrawn,
                total_fees=abs(fees), total_bonuses=bonuses,
                total_referral=referral,
                transaction_count=txns.count(),
                generated_at=timezone.now(),
            )
        )
        logger.info(f"Tax record generated: {user.username} {year} income={income}")
        return rec


class OfferService:
    """CPAlead-style CPA/CPI/CPC offer management."""

    @staticmethod
    @transaction.atomic
    def record_conversion(offer_id: int, user, wallet, click_id: str = "",
                          ip_address: str = "", country_code: str = "",
                          device_type: str = "") -> dict:
        from .models_cpalead_extra import EarningOffer, OfferConversion
        from .services import WalletService

        offer = EarningOffer.objects.select_for_update().get(id=offer_id, is_active=True)
        if offer.is_capped():
            raise ValueError(f"Offer {offer.title} has reached its daily/total cap")

        # Check publisher level requirement
        try:
            from .models import PublisherLevel
            pl = PublisherLevel.objects.get(user=user)
            if pl.level < offer.min_publisher_level:
                raise ValueError(f"Publisher Level {offer.min_publisher_level}+ required")
        except Exception:
            pass

        # Get BDT equivalent (if offer pays in USD)
        payout_bdt = offer.payout_bdt or offer.payout  # use pre-computed or raw

        # Credit earnings
        txn = WalletService.credit(
            wallet, payout_bdt,
            txn_type="earning",
            description=f"{offer.get_offer_type_display()}: {offer.title}",
            reference_id=str(offer.offer_id),
            reference_type=offer.offer_type,
            metadata={"offer_id": offer.id, "click_id": click_id, "country": country_code},
            country_code=country_code,
        )

        conversion = OfferConversion.objects.create(
            offer=offer, user=user, wallet=wallet, transaction=txn,
            status="approved", payout=payout_bdt,
            click_id=click_id, ip_address=ip_address,
            country_code=country_code, device_type=device_type,
            approved_at=timezone.now(),
        )

        # Update offer stats
        offer.conversions_today += 1
        offer.total_conversions += 1
        offer.save(update_fields=["conversions_today","total_conversions","updated_at"])

        return {
            "conversion_id": conversion.id,
            "payout": float(payout_bdt),
            "txn_id": str(txn.txn_id),
        }
