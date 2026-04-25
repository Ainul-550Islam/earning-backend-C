# api/wallet/views_extra.py
"""
World-class wallet viewsets for CPAlead + Binance + Stripe features.
"""
import logging
from decimal import Decimal
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from django.utils import timezone

logger = logging.getLogger("wallet.views_extra")


# ── KYC ────────────────────────────────────────────────────

class KYCVerificationViewSet(viewsets.ModelViewSet):
    """Binance-style tiered KYC verification."""
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        from .models_cpalead_extra import KYCVerification
        u = self.request.user
        if u.is_staff: return KYCVerification.objects.all()
        return KYCVerification.objects.filter(user=u)

    def get_serializer_class(self):
        from rest_framework import serializers
        from .models_cpalead_extra import KYCVerification
        class S(serializers.ModelSerializer):
            class Meta:
                model = KYCVerification
                fields = ["id","user","wallet","level","status","doc_type","doc_number",
                          "doc_front_url","doc_back_url","selfie_url","address_proof_url",
                          "daily_wd_limit","monthly_wd_limit","reviewed_at","rejection_reason",
                          "risk_score","created_at","updated_at"]
                read_only_fields = ["daily_wd_limit","monthly_wd_limit","reviewed_at","risk_score"]
        return S

    def create(self, request, *args, **kwargs):
        """Submit KYC documents."""
        try:
            from .services_extra import KYCService
            from .models import Wallet
            wallet = Wallet.objects.get(user=request.user)
            kyc = KYCService.submit(
                user=request.user, wallet=wallet,
                level=int(request.data.get("level",1)),
                doc_type=request.data.get("doc_type","nid"),
                doc_number=request.data.get("doc_number",""),
                doc_front_url=request.data.get("doc_front_url",""),
                doc_back_url=request.data.get("doc_back_url",""),
                selfie_url=request.data.get("selfie_url",""),
                address_proof_url=request.data.get("address_proof_url",""),
            )
            return Response({"success":True,"kyc_id":kyc.id,"status":kyc.status,"level":kyc.level}, status=201)
        except Exception as e:
            return Response({"success":False,"error":str(e)}, status=400)

    @action(detail=True, methods=["post"], permission_classes=[IsAdminUser])
    def approve(self, request, pk=None):
        try:
            from .services_extra import KYCService
            result = KYCService.approve(int(pk), reviewed_by=request.user)
            return Response({"success":True,"data":result})
        except Exception as e:
            return Response({"success":False,"error":str(e)}, status=400)

    @action(detail=True, methods=["post"], permission_classes=[IsAdminUser])
    def reject(self, request, pk=None):
        try:
            from .services_extra import KYCService
            KYCService.reject(int(pk), reason=request.data.get("reason",""), reviewed_by=request.user)
            return Response({"success":True})
        except Exception as e:
            return Response({"success":False,"error":str(e)}, status=400)

    @action(detail=False, methods=["get"])
    def my_level(self, request):
        from .services_extra import KYCService
        level = KYCService.get_user_level(request.user)
        limits = KYCService.LIMITS.get(level, KYCService.LIMITS[0])
        return Response({"level":level,"daily_limit":float(limits["daily"]),"monthly_limit":float(limits["monthly"])})


# ── Payout Schedule ─────────────────────────────────────────

class PayoutScheduleViewSet(viewsets.ModelViewSet):
    """CPAlead daily/weekly/net30 payout schedule."""
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        from .models_cpalead_extra import PayoutSchedule
        u = self.request.user
        if u.is_staff: return PayoutSchedule.objects.all()
        return PayoutSchedule.objects.filter(user=u)

    def get_serializer_class(self):
        from rest_framework import serializers
        from .models_cpalead_extra import PayoutSchedule
        class S(serializers.ModelSerializer):
            can_payout_now = serializers.BooleanField(read_only=True)
            class Meta:
                model = PayoutSchedule
                fields = ["id","user","frequency","minimum_threshold","auto_payout",
                          "fast_pay_enabled","hold_days","hold_released",
                          "last_payout_date","last_payout_amount","total_payouts",
                          "can_payout_now","created_at","updated_at"]
                read_only_fields = ["user","hold_released","total_payouts","last_payout_date","last_payout_amount","created_at"]
        return S

    @action(detail=False, methods=["get"])
    def my(self, request):
        from .models_cpalead_extra import PayoutSchedule
        from .models import Wallet
        try:
            wallet = Wallet.objects.get(user=request.user)
            sched, _ = PayoutSchedule.objects.get_or_create(
                user=request.user, wallet=wallet,
                defaults={"frequency":"net30","minimum_threshold":Decimal("50")}
            )
            return Response({"success":True,"data":self.get_serializer(sched).data})
        except Exception as e:
            return Response({"success":False,"error":str(e)}, status=400)

    @action(detail=False, methods=["post"], permission_classes=[IsAdminUser], url_path="run-daily")
    def run_daily(self, request):
        from .services import PayoutService
        result = PayoutService.process_daily_payouts()
        return Response({"success":True,"data":result})


# ── Publisher Level ─────────────────────────────────────────

class PublisherLevelViewSet(viewsets.ReadOnlyModelViewSet):
    """CPAlead publisher quality level."""
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        from .models_cpalead_extra import PublisherLevel
        u = self.request.user
        if u.is_staff: return PublisherLevel.objects.all()
        return PublisherLevel.objects.filter(user=u)

    def get_serializer_class(self):
        from rest_framework import serializers
        from .models_cpalead_extra import PublisherLevel
        class S(serializers.ModelSerializer):
            can_upgrade = serializers.BooleanField(read_only=True)
            class Meta:
                model = PublisherLevel
                fields = ["id","user","level","quality_score","total_earnings","fraud_flags","payout_freq","can_upgrade","created_at","updated_at"]
        return S

    @action(detail=False, methods=["get"])
    def my(self, request):
        from .models_cpalead_extra import PublisherLevel
        from .models import Wallet
        try:
            wallet = Wallet.objects.get(user=request.user)
            pl, _ = PublisherLevel.objects.get_or_create(user=request.user, wallet=wallet)
            return Response({"success":True,"data":{
                "level": pl.level, "level_name": dict(pl.LEVELS).get(pl.level,""),
                "quality_score": float(pl.quality_score),
                "total_earnings": float(pl.total_earnings),
                "payout_frequency": pl.payout_freq,
                "can_upgrade": pl.can_upgrade(),
            }})
        except Exception as e:
            return Response({"success":False,"error":str(e)}, status=400)


# ── Points ──────────────────────────────────────────────────

class PointsLedgerViewSet(viewsets.ReadOnlyModelViewSet):
    """CPAlead virtual currency points system."""
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        from .models_cpalead_extra import PointsLedger
        u = self.request.user
        if u.is_staff: return PointsLedger.objects.all()
        return PointsLedger.objects.filter(user=u)

    def get_serializer_class(self):
        from rest_framework import serializers
        from .models_cpalead_extra import PointsLedger
        class S(serializers.ModelSerializer):
            dollar_value = serializers.SerializerMethodField()
            class Meta:
                model = PointsLedger
                fields = ["id","user","total_points","lifetime_points","redeemed_points","points_per_dollar","current_tier","dollar_value","updated_at"]
            def get_dollar_value(self, obj):
                return round(obj.total_points / obj.points_per_dollar, 2) if obj.points_per_dollar else 0
        return S

    @action(detail=False, methods=["get"])
    def my(self, request):
        from .models_cpalead_extra import PointsLedger
        from .models import Wallet
        try:
            wallet = Wallet.objects.get(user=request.user)
            pl, _ = PointsLedger.objects.get_or_create(user=request.user, wallet=wallet)
            return Response({"success":True,"data":{
                "total_points": pl.total_points,
                "lifetime_points": pl.lifetime_points,
                "current_tier": pl.current_tier or "No Tier",
                "dollar_value": round(pl.total_points / pl.points_per_dollar, 2) if pl.points_per_dollar else 0,
            }})
        except Exception as e:
            return Response({"success":False,"error":str(e)}, status=400)


# ── Simple viewsets for remaining models ────────────────────

class PerformanceBonusViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    def get_queryset(self):
        from .models_cpalead_extra import PerformanceBonus
        u = self.request.user
        if u.is_staff: return PerformanceBonus.objects.all()
        return PerformanceBonus.objects.filter(user=u, status="active")
    def get_permissions(self):
        if self.action in ("create","update","partial_update","destroy"): return [IsAdminUser()]
        return [IsAuthenticated()]
    def get_serializer_class(self):
        from rest_framework import serializers
        from .models_cpalead_extra import PerformanceBonus
        class S(serializers.ModelSerializer):
            is_active_now = serializers.BooleanField(read_only=True)
            class Meta: model=PerformanceBonus; fields=["id","user","wallet","bonus_type","status","bonus_percent","period","total_paid","max_bonus","starts_at","expires_at","note","is_active_now","created_at"]
        return S


class GeoRateViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdminUser]
    def get_queryset(self):
        from .models_cpalead_extra import GeoRate
        return GeoRate.objects.all()
    def get_serializer_class(self):
        from rest_framework import serializers
        from .models_cpalead_extra import GeoRate
        class S(serializers.ModelSerializer):
            class Meta: model=GeoRate; fields="__all__"
        return S
    @action(detail=False, methods=["get"], permission_classes=[IsAuthenticated])
    def check(self, request):
        from .services import WalletService
        country = request.query_params.get("country","BD")
        mult = WalletService._get_geo_multiplier(country)
        return Response({"country":country,"multiplier":float(mult)})


class ReferralProgramViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]
    def get_queryset(self):
        from .models_cpalead_extra import ReferralProgram
        u = self.request.user
        if u.is_staff: return ReferralProgram.objects.all()
        return ReferralProgram.objects.filter(referrer=u)
    def get_serializer_class(self):
        from rest_framework import serializers
        from .models_cpalead_extra import ReferralProgram
        class S(serializers.ModelSerializer):
            is_valid = serializers.BooleanField(read_only=True)
            class Meta: model=ReferralProgram; fields=["id","referrer","referred","level","commission_rate","is_active","duration_months","total_earned","starts_at","expires_at","is_valid","created_at"]
        return S


class InstantPayoutViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    def get_queryset(self):
        from .models_cpalead_extra import InstantPayout
        u = self.request.user
        if u.is_staff: return InstantPayout.objects.all()
        return InstantPayout.objects.filter(user=u)
    def get_serializer_class(self):
        from rest_framework import serializers
        from .models_cpalead_extra import InstantPayout
        class S(serializers.ModelSerializer):
            class Meta: model=InstantPayout; fields=["id","payout_id","user","wallet","amount","fee","net_amount","fee_percent","method","destination","status","arrival_time","gateway_ref","failure_reason","created_at"]
        return S
    def create(self, request, *args, **kwargs):
        try:
            from .services_extra import InstantPayoutService
            from .models import Wallet
            wallet = Wallet.objects.get(user=request.user)
            ip = InstantPayoutService.create(
                request.user, wallet,
                Decimal(str(request.data.get("amount",0))),
                request.data.get("method","bkash"),
                request.data.get("destination",""),
            )
            return Response({"success":True,"payout_id":str(ip.payout_id),"fee":float(ip.fee),"net":float(ip.net_amount)}, status=201)
        except Exception as e:
            return Response({"success":False,"error":str(e)}, status=400)


class MassPayoutJobViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdminUser]
    def get_queryset(self):
        from .models_cpalead_extra import MassPayoutJob
        return MassPayoutJob.objects.all()
    def get_serializer_class(self):
        from rest_framework import serializers
        from .models_cpalead_extra import MassPayoutJob
        class S(serializers.ModelSerializer):
            class Meta: model=MassPayoutJob; fields=["id","job_id","title","status","total_amount","total_count","success_count","failed_count","payout_type","method","note","created_by","created_at","completed_at"]
        return S
    def create(self, request, *args, **kwargs):
        try:
            from .services_extra import MassPayoutService
            job = MassPayoutService.create_job(
                title=request.data.get("title","Mass Payout"),
                items=request.data.get("items",[]),
                payout_type=request.data.get("payout_type","general"),
                method=request.data.get("method","bkash"),
                created_by=request.user,
                note=request.data.get("note",""),
            )
            from .tasks_extra import process_mass_payout_job
            process_mass_payout_job.delay(job.id)
            return Response({"success":True,"job_id":str(job.job_id),"total":float(job.total_amount),"count":job.total_count}, status=201)
        except Exception as e:
            return Response({"success":False,"error":str(e)}, status=400)


class DisputeCaseViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    def get_queryset(self):
        from .models_cpalead_extra import DisputeCase
        u = self.request.user
        if u.is_staff: return DisputeCase.objects.all()
        return DisputeCase.objects.filter(user=u)
    def get_serializer_class(self):
        from rest_framework import serializers
        from .models_cpalead_extra import DisputeCase
        class S(serializers.ModelSerializer):
            class Meta: model=DisputeCase; fields=["id","case_id","user","wallet","transaction","withdrawal","reason","status","outcome","disputed_amount","refunded_amount","description","evidence","resolved_at","due_by","created_at"]
        return S
    def create(self, request, *args, **kwargs):
        try:
            from .services_extra import DisputeService
            from .models import Wallet
            wallet = Wallet.objects.get(user=request.user)
            case = DisputeService.open(
                request.user, wallet,
                transaction_id=request.data.get("transaction_id"),
                withdrawal_id=request.data.get("withdrawal_id"),
                reason=request.data.get("reason","other"),
                description=request.data.get("description",""),
                disputed_amount=Decimal(str(request.data.get("disputed_amount",0))) if request.data.get("disputed_amount") else None,
            )
            return Response({"success":True,"case_id":str(case.case_id),"status":case.status}, status=201)
        except Exception as e:
            return Response({"success":False,"error":str(e)}, status=400)


class RefundRequestViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    def get_queryset(self):
        from .models_cpalead_extra import RefundRequest
        u = self.request.user
        if u.is_staff: return RefundRequest.objects.all()
        return RefundRequest.objects.filter(user=u)
    def get_serializer_class(self):
        from rest_framework import serializers
        from .models_cpalead_extra import RefundRequest
        class S(serializers.ModelSerializer):
            class Meta: model=RefundRequest; fields=["id","refund_id","user","wallet","original_txn","reason","status","requested_amount","approved_amount","description","processed_at","rejection_reason","created_at"]
        return S


class FraudScoreViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAdminUser]
    def get_queryset(self):
        from .models_cpalead_extra import FraudScore
        return FraudScore.objects.all()
    def get_serializer_class(self):
        from rest_framework import serializers
        from .models_cpalead_extra import FraudScore
        class S(serializers.ModelSerializer):
            class Meta: model=FraudScore; fields=["id","user","wallet","score","risk_level","is_blocked","signals","velocity_score","ip_risk_score","amount_risk_score","kyc_score","pattern_score","created_at"]
        return S


class AMLFlagViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdminUser]
    def get_queryset(self):
        from .models_cpalead_extra import AMLFlag
        return AMLFlag.objects.all()
    def get_serializer_class(self):
        from rest_framework import serializers
        from .models_cpalead_extra import AMLFlag
        class S(serializers.ModelSerializer):
            class Meta: model=AMLFlag; fields=["id","flag_id","user","wallet","flag_type","status","description","suspicious_amount","evidence","assigned_to","resolved_at","reported_to","created_at"]
        return S


class EarningOfferViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    def get_queryset(self):
        from .models_cpalead_extra import EarningOffer
        u = self.request.user
        if u.is_staff: return EarningOffer.objects.all()
        return EarningOffer.objects.filter(is_active=True)
    def get_permissions(self):
        if self.action in ("create","update","partial_update","destroy"): return [IsAdminUser()]
        return [IsAuthenticated()]
    def get_serializer_class(self):
        from rest_framework import serializers
        from .models_cpalead_extra import EarningOffer
        class S(serializers.ModelSerializer):
            is_capped = serializers.BooleanField(read_only=True)
            class Meta: model=EarningOffer; fields=["id","offer_id","title","description","offer_type","geo_tier","payout","payout_currency","payout_bdt","daily_cap","conversions_today","total_conversions","is_active","requires_kyc","min_publisher_level","advertiser","offer_url","icon_url","starts_at","ends_at","is_capped","created_at"]
        return S
    @action(detail=True, methods=["post"])
    def convert(self, request, pk=None):
        """Record a CPA/CPI conversion for this offer."""
        try:
            from .services_extra import OfferService
            from .models import Wallet
            wallet = Wallet.objects.get(user=request.user)
            result = OfferService.record_conversion(
                offer_id=int(pk), user=request.user, wallet=wallet,
                click_id=request.data.get("click_id",""),
                ip_address=getattr(request,"safe_ip",request.META.get("REMOTE_ADDR","")),
                country_code=request.data.get("country_code",""),
                device_type=request.data.get("device_type",""),
            )
            return Response({"success":True,"data":result})
        except Exception as e:
            return Response({"success":False,"error":str(e)}, status=400)


class WithdrawalWhitelistViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    def get_queryset(self):
        from .models_cpalead_extra import WithdrawalWhitelist
        u = self.request.user
        if u.is_staff: return WithdrawalWhitelist.objects.all()
        return WithdrawalWhitelist.objects.filter(user=u)
    def get_serializer_class(self):
        from rest_framework import serializers
        from .models_cpalead_extra import WithdrawalWhitelist
        class S(serializers.ModelSerializer):
            is_unlocked = serializers.BooleanField(read_only=True)
            class Meta: model=WithdrawalWhitelist; fields=["id","user","wallet","method_type","account","label","is_active","activated_at","is_trusted","is_unlocked","created_at"]
        return S


class SecurityEventViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]
    def get_queryset(self):
        from .models_cpalead_extra import SecurityEvent
        u = self.request.user
        if u.is_staff: return SecurityEvent.objects.all()
        return SecurityEvent.objects.filter(user=u)
    def get_serializer_class(self):
        from rest_framework import serializers
        from .models_cpalead_extra import SecurityEvent
        class S(serializers.ModelSerializer):
            is_locked = serializers.BooleanField(read_only=True)
            class Meta: model=SecurityEvent; fields=["id","user","event_type","lock_hours","lock_until","is_resolved","is_locked","ip_address","created_at"]
        return S


class WebhookEndpointViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    def get_queryset(self):
        from .models_cpalead_extra import WebhookEndpoint
        u = self.request.user
        if u.is_staff: return WebhookEndpoint.objects.all()
        return WebhookEndpoint.objects.filter(user=u)
    def get_serializer_class(self):
        from rest_framework import serializers
        from .models_cpalead_extra import WebhookEndpoint
        class S(serializers.ModelSerializer):
            class Meta: model=WebhookEndpoint; fields=["id","endpoint_id","user","url","subscribed_events","is_active","last_called_at","last_status","failure_count","created_at"]
            extra_kwargs = {"secret":{"write_only":True}}
        return S


class TaxRecordViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]
    def get_queryset(self):
        from .models_cpalead_extra import TaxRecord
        u = self.request.user
        if u.is_staff: return TaxRecord.objects.all()
        return TaxRecord.objects.filter(user=u)
    def get_serializer_class(self):
        from rest_framework import serializers
        from .models_cpalead_extra import TaxRecord
        class S(serializers.ModelSerializer):
            class Meta: model=TaxRecord; fields=["id","user","wallet","tax_year","status","total_income","total_withdrawn","total_fees","total_bonuses","total_referral","transaction_count","tin_number","pdf_url","generated_at","created_at"]
        return S
    @action(detail=False, methods=["post"], permission_classes=[IsAdminUser])
    def generate(self, request):
        try:
            from .services_extra import TaxService
            from .models import Wallet
            year = int(request.data.get("year", timezone.now().year - 1))
            user_id = request.data.get("user_id")
            if user_id:
                from django.contrib.auth import get_user_model
                user = get_user_model().objects.get(id=user_id)
                wallet = Wallet.objects.get(user=user)
                rec = TaxService.generate(user, wallet, year)
                return Response({"success":True,"record_id":rec.id,"income":float(rec.total_income)})
            else:
                count = 0
                for wallet in Wallet.objects.select_related("user"):
                    try: TaxService.generate(wallet.user, wallet, year); count += 1
                    except Exception: pass
                return Response({"success":True,"generated":count,"year":year})
        except Exception as e:
            return Response({"success":False,"error":str(e)}, status=400)


class WithdrawalBatchViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdminUser]
    def get_queryset(self):
        from .models_cpalead_extra import MassPayoutJob
        return MassPayoutJob.objects.all()
    def get_serializer_class(self):
        from rest_framework import serializers
        from .models_cpalead_extra import MassPayoutJob
        class S(serializers.ModelSerializer):
            class Meta: model=MassPayoutJob; fields=["id","job_id","title","status","total_amount","total_count","success_count","failed_count","created_at","completed_at"]
        return S
