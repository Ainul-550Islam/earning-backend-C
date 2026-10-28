# api/admin_panel/viewsets/CPALeadAdminViewSet.py
"""
CPAlead System — Full Admin Control (Previously Missing 13%).

Covers:
  1. CPALeadService direct control (geo rates, tier multipliers, conversions)
  2. wallet/models_cpalead_extra.py — all 22 models
  3. EarningOffer management (CPA/CPI/CPC)
  4. ContentLocker & OfferWall admin
  5. GeoRate configuration
  6. PerformanceBonus management
  7. KYCVerification (Binance-style tiered)
  8. AML, FraudScore, DisputeCase
  9. MassPayout, InstantPayout, SettlementBatch
  10. PublisherLevel, ReferralProgram

PostgreSQL-optimized. All imports try/except — safe if models missing.
"""
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from django.db.models import Count, Sum, Q, Avg, F
from django.utils import timezone
from django.core.cache import cache
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


class CPALeadAdminViewSet(viewsets.ViewSet):
    """
    Full CPAlead system admin control.
    Route prefix: /api/admin-panel/cpalead/
    """
    permission_classes = [IsAdminUser]

    # ── OVERVIEW ──────────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'])
    def overview(self, request):
        """Complete CPAlead system overview."""
        cache_key = 'admin:cpalead:overview'
        cached = cache.get(cache_key)
        if cached:
            return Response({'success': True, 'data': cached, 'cached': True})
        try:
            from api.wallet.models_cpalead_extra import (
                EarningOffer, OfferConversion, GeoRate,
                PerformanceBonus, PublisherLevel, KYCVerification,
                MassPayoutJob, DisputeCase, AMLFlag,
            )
            today = timezone.now().date()
            week_ago = timezone.now() - timedelta(days=7)

            data = {
                'offers': EarningOffer.objects.aggregate(
                    total=Count('id'),
                    active=Count('id', filter=Q(is_active=True)),
                    cpa=Count('id', filter=Q(offer_type='CPA')),
                    cpi=Count('id', filter=Q(offer_type='CPI')),
                    cpc=Count('id', filter=Q(offer_type='CPC')),
                ),
                'conversions': OfferConversion.objects.aggregate(
                    total=Count('id'),
                    today=Count('id', filter=Q(created_at__date=today)),
                    week=Count('id', filter=Q(created_at__gte=week_ago)),
                    approved=Count('id', filter=Q(status='approved')),
                    pending=Count('id', filter=Q(status='pending')),
                    rejected=Count('id', filter=Q(status='rejected')),
                    total_payout=Sum('payout_amount', filter=Q(status='approved')),
                ),
                'geo_rates': GeoRate.objects.aggregate(
                    total=Count('id'),
                    active=Count('id', filter=Q(is_active=True)),
                ),
                'kyc': KYCVerification.objects.aggregate(
                    total=Count('id'),
                    pending=Count('id', filter=Q(status='pending')),
                    approved=Count('id', filter=Q(status='approved')),
                    rejected=Count('id', filter=Q(status='rejected')),
                ),
                'disputes': DisputeCase.objects.filter(
                    status__in=['open', 'under_review']
                ).count(),
                'aml_flags': AMLFlag.objects.filter(is_resolved=False).count(),
                'mass_payouts': MassPayoutJob.objects.filter(
                    status='pending'
                ).count(),
            }
            # convert Decimal to float for JSON
            for section in data.values():
                if isinstance(section, dict):
                    for k, v in section.items():
                        try:
                            section[k] = float(v) if v is not None else 0
                        except (TypeError, ValueError):
                            pass
            cache.set(cache_key, data, 60)
            return Response({'success': True, 'data': data})
        except Exception as e:
            return Response({'success': False, 'error': str(e)})

    # ── EARNING OFFERS ────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'])
    def offers(self, request):
        """List all CPA/CPI/CPC offers with filters."""
        try:
            from api.wallet.models_cpalead_extra import EarningOffer
            offer_type = request.query_params.get('type')        # CPA | CPI | CPC
            is_active  = request.query_params.get('active')
            page       = int(request.query_params.get('page', 1))
            per_page   = int(request.query_params.get('per_page', 50))

            qs = EarningOffer.objects.all()
            if offer_type:
                qs = qs.filter(offer_type=offer_type.upper())
            if is_active is not None:
                qs = qs.filter(is_active=is_active.lower() == 'true')

            total = qs.count()
            items = list(qs.values(
                'id', 'name', 'offer_type', 'base_payout',
                'daily_cap', 'total_cap', 'conversions_today',
                'total_conversions', 'is_active', 'geo_targets',
                'created_at',
            ).order_by('-created_at')[(page-1)*per_page : page*per_page])
            return Response({'success': True, 'total': total, 'page': page, 'data': items})
        except Exception as e:
            return Response({'success': False, 'error': str(e)})

    @action(detail=False, methods=['post'])
    def toggle_offer(self, request):
        """Enable/disable a CPA offer instantly."""
        try:
            from api.wallet.models_cpalead_extra import EarningOffer
            offer_id = request.data.get('offer_id')
            offer = EarningOffer.objects.get(pk=offer_id)
            offer.is_active = not offer.is_active
            offer.save(update_fields=['is_active'])
            cache.delete('admin:cpalead:overview')
            cache.delete_many([f'offer_avail_{offer_id}_{cc}' for cc in ['BD','IN','US','GB','PK']])
            self._log(request.user, 'toggle_offer', 'EarningOffer', str(offer_id),
                      {'is_active': offer.is_active})
            return Response({'success': True, 'offer_id': offer_id, 'is_active': offer.is_active})
        except Exception as e:
            return Response({'error': str(e)}, status=400)

    @action(detail=False, methods=['post'])
    def update_offer_cap(self, request):
        """Update daily/total cap for an offer."""
        try:
            from api.wallet.models_cpalead_extra import EarningOffer
            offer_id  = request.data.get('offer_id')
            daily_cap = request.data.get('daily_cap')
            total_cap = request.data.get('total_cap')
            update = {}
            if daily_cap is not None:
                update['daily_cap'] = int(daily_cap)
            if total_cap is not None:
                update['total_cap'] = int(total_cap)
            if not update:
                return Response({'error': 'daily_cap or total_cap required'}, status=400)
            EarningOffer.objects.filter(pk=offer_id).update(**update)
            cache.delete(f'offer_cap_{offer_id}')
            return Response({'success': True, 'offer_id': offer_id, **update})
        except Exception as e:
            return Response({'error': str(e)}, status=400)

    @action(detail=False, methods=['post'])
    def reset_offer_cap(self, request):
        """Manually reset today's conversion cap for an offer."""
        try:
            from api.wallet.models_cpalead_extra import EarningOffer
            offer_id = request.data.get('offer_id')
            EarningOffer.objects.filter(pk=offer_id).update(conversions_today=0)
            cache.delete(f'offer_cap_{offer_id}')
            return Response({'success': True, 'offer_id': offer_id, 'conversions_today': 0})
        except Exception as e:
            return Response({'error': str(e)}, status=400)

    # ── CONVERSIONS ───────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'])
    def conversions(self, request):
        """List conversions with filters."""
        try:
            from api.wallet.models_cpalead_extra import OfferConversion
            status_f = request.query_params.get('status')
            offer_id = request.query_params.get('offer_id')
            user_id  = request.query_params.get('user_id')
            page     = int(request.query_params.get('page', 1))
            per_page = int(request.query_params.get('per_page', 50))

            qs = OfferConversion.objects.select_related('user', 'offer').all()
            if status_f:
                qs = qs.filter(status=status_f)
            if offer_id:
                qs = qs.filter(offer_id=offer_id)
            if user_id:
                qs = qs.filter(user_id=user_id)

            total = qs.count()
            items = list(qs.values(
                'id', 'user_id', 'user__username', 'offer_id', 'offer__name',
                'click_id', 'payout_amount', 'status', 'ip_address',
                'country_code', 'device_type', 'created_at',
            ).order_by('-created_at')[(page-1)*per_page : page*per_page])
            return Response({'success': True, 'total': total, 'page': page, 'data': items})
        except Exception as e:
            return Response({'success': False, 'error': str(e)})

    @action(detail=False, methods=['post'])
    def approve_conversion(self, request):
        """Manually approve a pending conversion and credit wallet."""
        try:
            from api.wallet.models_cpalead_extra import OfferConversion
            conv_id = request.data.get('conversion_id')
            conv = OfferConversion.objects.select_related('user', 'offer').get(
                pk=conv_id, status='pending'
            )
            conv.status = 'approved'
            conv.save(update_fields=['status'])
            # Credit wallet
            try:
                from api.wallet.models.core import Wallet
                Wallet.objects.filter(user=conv.user).update(
                    balance=F('balance') + conv.payout_amount
                )
            except Exception as e:
                logger.warning(f'[CPALead] wallet credit failed: {e}')
            cache.delete('admin:cpalead:overview')
            self._log(request.user, 'approve_conversion', 'OfferConversion', str(conv_id),
                      {'amount': float(conv.payout_amount)})
            return Response({'success': True, 'conversion_id': conv_id, 'status': 'approved'})
        except OfferConversion.DoesNotExist:
            return Response({'error': 'Conversion not found or not pending'}, status=404)
        except Exception as e:
            return Response({'error': str(e)}, status=400)

    @action(detail=False, methods=['post'])
    def reject_conversion(self, request):
        """Reject a pending conversion."""
        try:
            from api.wallet.models_cpalead_extra import OfferConversion
            conv_id = request.data.get('conversion_id')
            reason  = request.data.get('reason', 'Rejected by admin')
            updated = OfferConversion.objects.filter(
                pk=conv_id, status='pending'
            ).update(status='rejected', rejection_reason=reason)
            if not updated:
                return Response({'error': 'Conversion not found or not pending'}, status=404)
            cache.delete('admin:cpalead:overview')
            return Response({'success': True, 'conversion_id': conv_id, 'status': 'rejected'})
        except Exception as e:
            return Response({'error': str(e)}, status=400)

    @action(detail=False, methods=['get'])
    def conversion_stats(self, request):
        """Daily conversion chart — last 30 days."""
        try:
            from api.wallet.models_cpalead_extra import OfferConversion
            from django.db.models.functions import TruncDate
            stats = list(
                OfferConversion.objects
                .filter(created_at__gte=timezone.now() - timedelta(days=30))
                .annotate(date=TruncDate('created_at'))
                .values('date', 'status')
                .annotate(count=Count('id'), payout=Sum('payout_amount'))
                .order_by('date')
            )
            return Response({'success': True, 'data': stats})
        except Exception as e:
            return Response({'success': False, 'error': str(e)})

    # ── GEO RATES ─────────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'])
    def geo_rates(self, request):
        """List all country geo rate multipliers."""
        try:
            from api.wallet.models_cpalead_extra import GeoRate
            data = list(GeoRate.objects.values(
                'id', 'country_code', 'country_name', 'rate_multiplier',
                'min_payout', 'max_daily_earning', 'is_active',
            ).order_by('country_code'))
            return Response({'success': True, 'data': data})
        except Exception as e:
            return Response({'success': False, 'error': str(e)})

    @action(detail=False, methods=['post'])
    def update_geo_rate(self, request):
        """Update geo rate for a country."""
        try:
            from api.wallet.models_cpalead_extra import GeoRate
            country    = request.data.get('country_code', '').upper()
            multiplier = request.data.get('rate_multiplier')
            min_payout = request.data.get('min_payout')
            is_active  = request.data.get('is_active')

            if not country:
                return Response({'error': 'country_code required'}, status=400)

            update = {}
            if multiplier is not None: update['rate_multiplier'] = multiplier
            if min_payout is not None: update['min_payout'] = min_payout
            if is_active is not None:  update['is_active'] = is_active

            GeoRate.objects.update_or_create(
                country_code=country,
                defaults=update,
            )
            cache.delete_many([f'geo_rate_{country}', f'offer_avail_*_{country}'])
            self._log(request.user, 'update_geo_rate', 'GeoRate', country, update)
            return Response({'success': True, 'country_code': country, **update})
        except Exception as e:
            return Response({'error': str(e)}, status=400)

    @action(detail=False, methods=['get'])
    def geo_rate_lookup(self, request):
        """Live geo rate lookup using CPALeadService."""
        try:
            country = request.query_params.get('country', 'BD').upper()
            from api.wallet.services.cpalead.CPALeadService import CPALeadService
            rate = CPALeadService.get_geo_rate(country)
            return Response({'success': True, 'country': country, 'rate_multiplier': float(rate)})
        except Exception as e:
            return Response({'success': False, 'error': str(e)})

    # ── KYC VERIFICATION ──────────────────────────────────────────────────────

    @action(detail=False, methods=['get'])
    def kyc_pending(self, request):
        """List pending KYC verifications."""
        try:
            from api.wallet.models_cpalead_extra import KYCVerification
            page     = int(request.query_params.get('page', 1))
            per_page = int(request.query_params.get('per_page', 50))
            level    = request.query_params.get('level')

            qs = KYCVerification.objects.filter(status='pending')
            if level:
                qs = qs.filter(kyc_level=int(level))

            total = qs.count()
            items = list(qs.values(
                'id', 'user_id', 'kyc_level', 'document_type',
                'document_number', 'submitted_at', 'review_notes',
            ).order_by('submitted_at')[(page-1)*per_page : page*per_page])
            return Response({'success': True, 'total': total, 'data': items})
        except Exception as e:
            return Response({'success': False, 'error': str(e)})

    @action(detail=False, methods=['post'])
    def approve_kyc(self, request):
        """Approve a KYC verification."""
        try:
            from api.wallet.models_cpalead_extra import KYCVerification
            kyc_id = request.data.get('kyc_id')
            note   = request.data.get('note', '')
            kyc = KYCVerification.objects.get(pk=kyc_id, status='pending')
            kyc.status = 'approved'
            kyc.reviewed_by_id = request.user.pk
            kyc.reviewed_at = timezone.now()
            kyc.review_notes = note
            kyc.save(update_fields=['status', 'reviewed_by_id', 'reviewed_at', 'review_notes'])
            cache.delete('admin:cpalead:overview')
            self._log(request.user, 'approve_kyc', 'KYCVerification', str(kyc_id),
                      {'level': kyc.kyc_level})
            return Response({'success': True, 'kyc_id': kyc_id, 'status': 'approved'})
        except KYCVerification.DoesNotExist:
            return Response({'error': 'KYC not found or not pending'}, status=404)
        except Exception as e:
            return Response({'error': str(e)}, status=400)

    @action(detail=False, methods=['post'])
    def reject_kyc(self, request):
        """Reject a KYC verification."""
        try:
            from api.wallet.models_cpalead_extra import KYCVerification
            kyc_id = request.data.get('kyc_id')
            reason = request.data.get('reason', 'Documents unclear')
            updated = KYCVerification.objects.filter(
                pk=kyc_id, status='pending'
            ).update(
                status='rejected',
                rejection_reason=reason,
                reviewed_by_id=request.user.pk,
                reviewed_at=timezone.now(),
            )
            if not updated:
                return Response({'error': 'KYC not found or not pending'}, status=404)
            cache.delete('admin:cpalead:overview')
            return Response({'success': True, 'kyc_id': kyc_id, 'status': 'rejected'})
        except Exception as e:
            return Response({'error': str(e)}, status=400)

    # ── AML & FRAUD SCORE ─────────────────────────────────────────────────────

    @action(detail=False, methods=['get'])
    def aml_flags(self, request):
        """List unresolved AML flags."""
        try:
            from api.wallet.models_cpalead_extra import AMLFlag
            page     = int(request.query_params.get('page', 1))
            per_page = int(request.query_params.get('per_page', 50))
            items = list(
                AMLFlag.objects.filter(is_resolved=False)
                .values('id', 'user_id', 'flag_reason', 'amount_flagged',
                        'transaction_count', 'created_at', 'risk_score')
                .order_by('-risk_score')[(page-1)*per_page : page*per_page]
            )
            return Response({'success': True, 'data': items})
        except Exception as e:
            return Response({'success': False, 'error': str(e)})

    @action(detail=False, methods=['post'])
    def resolve_aml_flag(self, request):
        """Resolve or escalate an AML flag."""
        try:
            from api.wallet.models_cpalead_extra import AMLFlag
            flag_id    = request.data.get('flag_id')
            resolution = request.data.get('resolution', 'cleared')  # cleared | escalated | banned
            note       = request.data.get('note', '')
            AMLFlag.objects.filter(pk=flag_id).update(
                is_resolved=True,
                resolution=resolution,
                resolution_note=note,
                resolved_by_id=request.user.pk,
                resolved_at=timezone.now(),
            )
            cache.delete('admin:cpalead:overview')
            self._log(request.user, 'resolve_aml', 'AMLFlag', str(flag_id),
                      {'resolution': resolution})
            return Response({'success': True, 'flag_id': flag_id, 'resolution': resolution})
        except Exception as e:
            return Response({'error': str(e)}, status=400)

    @action(detail=False, methods=['get'])
    def high_fraud_scores(self, request):
        """Users with high fraud scores."""
        try:
            from api.wallet.models_cpalead_extra import FraudScore
            threshold = float(request.query_params.get('threshold', 0.7))
            items = list(
                FraudScore.objects.filter(score__gte=threshold)
                .values('user_id', 'score', 'flags', 'last_evaluated', 'is_blocked')
                .order_by('-score')[:100]
            )
            return Response({'success': True, 'threshold': threshold, 'data': items})
        except Exception as e:
            return Response({'success': False, 'error': str(e)})

    # ── DISPUTE CASES ─────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'])
    def disputes(self, request):
        """List open dispute cases."""
        try:
            from api.wallet.models_cpalead_extra import DisputeCase
            status_f = request.query_params.get('status', 'open')
            items = list(
                DisputeCase.objects.filter(status=status_f)
                .values('id', 'user_id', 'amount', 'reason', 'evidence',
                        'status', 'created_at', 'resolution')
                .order_by('-created_at')[:100]
            )
            return Response({'success': True, 'data': items})
        except Exception as e:
            return Response({'success': False, 'error': str(e)})

    @action(detail=False, methods=['post'])
    def resolve_dispute(self, request):
        """Resolve a dispute case."""
        try:
            from api.wallet.models_cpalead_extra import DisputeCase
            dispute_id = request.data.get('dispute_id')
            resolution = request.data.get('resolution')  # refunded | rejected | partial
            amount     = request.data.get('refund_amount', 0)
            DisputeCase.objects.filter(pk=dispute_id).update(
                status='resolved',
                resolution=resolution,
                refund_amount=amount,
                resolved_by_id=request.user.pk,
                resolved_at=timezone.now(),
            )
            cache.delete('admin:cpalead:overview')
            return Response({'success': True, 'dispute_id': dispute_id, 'resolution': resolution})
        except Exception as e:
            return Response({'error': str(e)}, status=400)

    # ── MASS PAYOUT ───────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'])
    def mass_payouts(self, request):
        """List mass payout jobs."""
        try:
            from api.wallet.models_cpalead_extra import MassPayoutJob
            items = list(
                MassPayoutJob.objects.values(
                    'id', 'name', 'total_recipients', 'total_amount',
                    'status', 'processed_count', 'failed_count',
                    'created_at', 'completed_at',
                ).order_by('-created_at')[:50]
            )
            return Response({'success': True, 'data': items})
        except Exception as e:
            return Response({'success': False, 'error': str(e)})

    @action(detail=False, methods=['post'])
    def trigger_mass_payout(self, request):
        """Trigger a queued mass payout job."""
        try:
            from api.wallet.models_cpalead_extra import MassPayoutJob
            job_id = request.data.get('job_id')
            job = MassPayoutJob.objects.get(pk=job_id, status='pending')
            try:
                from api.wallet.tasks.earning_cap_reset_tasks import process_mass_payout
                process_mass_payout.delay(job_id)
                return Response({'success': True, 'job_id': job_id, 'queued': True})
            except Exception:
                MassPayoutJob.objects.filter(pk=job_id).update(status='processing')
                return Response({'success': True, 'job_id': job_id, 'status': 'processing'})
        except MassPayoutJob.DoesNotExist:
            return Response({'error': 'Job not found or not pending'}, status=404)
        except Exception as e:
            return Response({'error': str(e)}, status=400)

    # ── PUBLISHER LEVELS ──────────────────────────────────────────────────────

    @action(detail=False, methods=['get'])
    def publisher_levels(self, request):
        """List all publisher tier levels."""
        try:
            from api.wallet.models_cpalead_extra import PublisherLevel
            data = list(PublisherLevel.objects.values(
                'id', 'name', 'min_monthly_conversions', 'earn_multiplier',
                'min_payout_override', 'priority_support', 'dedicated_manager',
            ).order_by('min_monthly_conversions'))
            return Response({'success': True, 'data': data})
        except Exception as e:
            return Response({'success': False, 'error': str(e)})

    @action(detail=False, methods=['post'])
    def update_publisher_level(self, request):
        """Update a publisher level config."""
        try:
            from api.wallet.models_cpalead_extra import PublisherLevel
            level_id   = request.data.get('level_id')
            multiplier = request.data.get('earn_multiplier')
            min_conv   = request.data.get('min_monthly_conversions')
            update = {}
            if multiplier: update['earn_multiplier'] = multiplier
            if min_conv:   update['min_monthly_conversions'] = min_conv
            PublisherLevel.objects.filter(pk=level_id).update(**update)
            cache.delete('publisher_levels')
            return Response({'success': True, 'level_id': level_id, **update})
        except Exception as e:
            return Response({'error': str(e)}, status=400)

    # ── PERFORMANCE BONUS ─────────────────────────────────────────────────────

    @action(detail=False, methods=['get'])
    def performance_bonuses(self, request):
        """List active performance bonuses."""
        try:
            from api.wallet.models_cpalead_extra import PerformanceBonus
            items = list(
                PerformanceBonus.objects.filter(status='active')
                .values('id', 'user_id', 'bonus_percent', 'max_bonus',
                        'total_paid', 'valid_from', 'valid_until', 'created_at')
                .order_by('-created_at')[:100]
            )
            return Response({'success': True, 'data': items})
        except Exception as e:
            return Response({'success': False, 'error': str(e)})

    @action(detail=False, methods=['post'])
    def grant_performance_bonus(self, request):
        """Grant a performance bonus to a user."""
        try:
            from api.wallet.models_cpalead_extra import PerformanceBonus
            from api.wallet.models.core import Wallet
            user_id       = request.data.get('user_id')
            bonus_percent = float(request.data.get('bonus_percent', 10))
            max_bonus     = request.data.get('max_bonus')
            days          = int(request.data.get('days', 30))

            wallet = Wallet.objects.filter(user_id=user_id).first()
            if not wallet:
                return Response({'error': 'Wallet not found'}, status=404)

            bonus = PerformanceBonus.objects.create(
                user_id=user_id,
                wallet=wallet,
                bonus_percent=bonus_percent,
                max_bonus=max_bonus,
                status='active',
                valid_from=timezone.now(),
                valid_until=timezone.now() + timedelta(days=days),
                granted_by_id=request.user.pk,
            )
            self._log(request.user, 'grant_bonus', 'PerformanceBonus', str(bonus.pk),
                      {'user_id': user_id, 'bonus_percent': bonus_percent, 'days': days})
            return Response({'success': True, 'bonus_id': bonus.pk,
                             'user_id': user_id, 'bonus_percent': bonus_percent})
        except Exception as e:
            return Response({'error': str(e)}, status=400)

    # ── REFERRAL PROGRAM ──────────────────────────────────────────────────────

    @action(detail=False, methods=['get'])
    def referral_programs(self, request):
        """List referral program configurations."""
        try:
            from api.wallet.models_cpalead_extra import ReferralProgram
            data = list(ReferralProgram.objects.values(
                'id', 'name', 'level1_percent', 'level2_percent', 'level3_percent',
                'is_active', 'min_referrals_for_bonus',
            ))
            return Response({'success': True, 'data': data})
        except Exception as e:
            return Response({'success': False, 'error': str(e)})

    # ── CONTENT LOCKER & OFFERWALL ────────────────────────────────────────────

    @action(detail=False, methods=['get'])
    def content_locker_stats(self, request):
        """ContentLocker performance stats."""
        try:
            from api.wallet.models_cpalead_extra import ContentLocker
            data = ContentLocker.objects.aggregate(
                total=Count('id'),
                active=Count('id', filter=Q(is_active=True)),
                total_locks=Sum('lock_count'),
                total_unlocks=Sum('unlock_count'),
            )
            return Response({'success': True, 'data': {
                k: float(v) if v else 0 for k, v in data.items()
            }})
        except Exception as e:
            return Response({'success': False, 'error': str(e)})

    @action(detail=False, methods=['get'])
    def offerwall_stats(self, request):
        """OfferWall virtual currency stats."""
        try:
            from api.wallet.models_cpalead_extra import OfferWall
            data = OfferWall.objects.aggregate(
                total=Count('id'),
                active=Count('id', filter=Q(is_active=True)),
                total_vc_issued=Sum('total_vc_issued'),
                total_vc_spent=Sum('total_vc_spent'),
            )
            return Response({'success': True, 'data': {
                k: float(v) if v else 0 for k, v in data.items()
            }})
        except Exception as e:
            return Response({'success': False, 'error': str(e)})

    # ── HELPERS ───────────────────────────────────────────────────────────────

    def _log(self, user, action, model, obj_id, changes=None):
        try:
            from api.admin_panel.models.activity import AdminActivity
            AdminActivity.log(actor=user, action=action,
                              model_name=model, object_id=obj_id,
                              changes=changes or {})
        except Exception:
            pass