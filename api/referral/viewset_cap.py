# api/referral/viewset_cap.py
# Capability viewsets — advanced world-class features
# QR codes, viral stats, affiliate portal, credit wallet, tiers, streaks
# ============================================================

import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status

logger = logging.getLogger(__name__)


class QRCodeView(APIView):
    """GET /referral/qr/ — Get or generate QR code for user's primary referral code."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            from api.referral.services.ReferralCodeService import ReferralCodeService
            from api.referral.services.AdvancedReferralService import QRCodeService
            code = ReferralCodeService.get_or_create_primary_code(request.user)
            qr = QRCodeService.get_or_create(code)
            return Response({
                'code': code.code,
                'qr_image': qr.qr_image_data,
                'scan_count': qr.scan_count,
                'conversions': qr.conversions,
                'referral_url': f"/go/{code.code}/",
            })
        except Exception as e:
            return Response({'error': str(e)}, status=500)

    def post(self, request):
        """Regenerate QR with custom colors."""
        try:
            from api.referral.models import ReferralQRCode, ReferralCode
            from api.referral.services.AdvancedReferralService import QRCodeService
            code = ReferralCode.objects.filter(user=request.user, is_primary=True).first()
            if not code:
                return Response({'error': 'No primary code'}, status=404)
            qr, _ = ReferralQRCode.objects.get_or_create(referral_code=code)
            fg = request.data.get('fg_color', '#000000')
            bg = request.data.get('bg_color', '#FFFFFF')
            img_data = QRCodeService.regenerate(qr, fg_color=fg, bg_color=bg)
            return Response({'qr_image': img_data})
        except Exception as e:
            return Response({'error': str(e)}, status=500)


class ViralStatsView(APIView):
    """GET /referral/viral-stats/ — K-factor and viral coefficient dashboard."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            from api.referral.models import ViralCoefficient
            from django.utils import timezone
            today = timezone.now().date()
            today_data = ViralCoefficient.objects.filter(date=today).first()
            last_7 = ViralCoefficient.objects.order_by('-date')[:7]
            return Response({
                'today': {
                    'k_factor': float(today_data.k_factor) if today_data else 0,
                    'is_viral': today_data.is_viral if today_data else False,
                    'total_referrers': today_data.total_referrers if today_data else 0,
                    'conversion_rate': float(today_data.conversion_rate_pct) if today_data else 0,
                } if today_data else {},
                'trend': [
                    {
                        'date': str(v.date),
                        'k_factor': float(v.k_factor),
                        'is_viral': v.is_viral,
                    }
                    for v in last_7
                ],
            })
        except Exception as e:
            return Response({'error': str(e)}, status=500)


class StreakView(APIView):
    """GET /referral/streak/ — User's referral streak info."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            from api.referral.models import UserStreakTracker
            tracker = UserStreakTracker.objects.filter(user=request.user).first()
            if not tracker:
                return Response({
                    'current_streak': 0, 'longest_streak': 0,
                    'is_on_streak': False, 'has_multiplier': False,
                    'active_multiplier': 1.0,
                })
            return Response({
                'current_streak': tracker.current_streak_days,
                'longest_streak': tracker.longest_streak_days,
                'is_on_streak': tracker.is_on_streak,
                'has_multiplier': tracker.has_active_multiplier,
                'active_multiplier': float(tracker.active_multiplier),
                'multiplier_expires_at': tracker.multiplier_expires_at.isoformat() if tracker.multiplier_expires_at else None,
                'total_streak_bonuses': tracker.total_streak_bonuses,
            })
        except Exception as e:
            return Response({'error': str(e)}, status=500)


class UserTierView(APIView):
    """GET /referral/tier/ — User's commission tier info."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            from api.referral.models import UserCommissionTier, CommissionTierProgression
            tier_record = UserCommissionTier.objects.filter(
                user=request.user
            ).select_related('current_tier').first()

            if not tier_record:
                return Response({
                    'tier': 'bronze', 'icon': '🥉',
                    'l1_rate': 10.0, 'l2_rate': 5.0, 'l3_rate': 2.0,
                    'active_referrals': 0,
                    'next_tier': None,
                })

            current = tier_record.current_tier
            # Next tier
            next_tier = CommissionTierProgression.objects.filter(
                min_active_referrals__gt=tier_record.total_active_referrals,
                is_active=True,
            ).order_by('min_active_referrals').first()

            return Response({
                'tier': current.tier_level if current else 'bronze',
                'name': current.name if current else 'Bronze',
                'icon': current.icon if current else '🥉',
                'color': current.color_code if current else '#CD7F32',
                'l1_rate': float(tier_record.effective_l1_rate),
                'l2_rate': float(tier_record.effective_l2_rate),
                'l3_rate': float(tier_record.effective_l3_rate),
                'active_referrals': tier_record.total_active_referrals,
                'total_commission': float(tier_record.total_commission_earned),
                'perks': current.perks_description if current else '',
                'next_tier': {
                    'name': next_tier.name,
                    'min_referrals': next_tier.min_active_referrals,
                    'referrals_needed': next_tier.min_active_referrals - tier_record.total_active_referrals,
                } if next_tier else None,
            })
        except Exception as e:
            return Response({'error': str(e)}, status=500)


class CreditWalletView(APIView):
    """GET /referral/credits/ — Referral credit balance."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            from api.referral.models import ReferralCreditBalance
            balance, _ = ReferralCreditBalance.objects.get_or_create(user=request.user)
            recent = balance.transactions.order_by('-created_at')[:10]
            return Response({
                'balance': float(balance.balance),
                'pending': float(balance.pending_balance),
                'lifetime_earned': float(balance.lifetime_earned),
                'lifetime_spent': float(balance.lifetime_spent),
                'recent_transactions': [
                    {
                        'type': t.transaction_type,
                        'amount': float(t.amount),
                        'description': t.description,
                        'date': t.created_at.isoformat(),
                    }
                    for t in recent
                ],
            })
        except Exception as e:
            return Response({'error': str(e)}, status=500)


class AffiliateProfileView(APIView):
    """GET/POST /referral/affiliate/ — Affiliate profile."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            from api.referral.models import AffiliateProfile
            profile = AffiliateProfile.objects.filter(user=request.user).first()
            if not profile:
                return Response({'registered': False})
            return Response({
                'registered': True,
                'status': profile.status,
                'display_name': profile.display_name,
                'total_referrals': profile.total_referrals,
                'success_rate': float(profile.success_rate_pct),
                'traffic_type': profile.traffic_type,
                'is_public': profile.is_public,
            })
        except Exception as e:
            return Response({'error': str(e)}, status=500)

    def post(self, request):
        try:
            from api.referral.models import AffiliateProfile
            profile, created = AffiliateProfile.objects.get_or_create(
                user=request.user,
                defaults={
                    'display_name': request.data.get('display_name', ''),
                    'bio': request.data.get('bio', ''),
                    'website_url': request.data.get('website_url', ''),
                    'traffic_type': request.data.get('traffic_type', 'social'),
                    'monthly_traffic': request.data.get('monthly_traffic', 0),
                    'status': 'pending',
                }
            )
            return Response({'created': created, 'status': profile.status})
        except Exception as e:
            return Response({'error': str(e)}, status=500)


class SocialShareView(APIView):
    """GET /referral/share/ — Get social share URLs for all platforms."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            from api.referral.models import ReferralCode
            from api.referral.services.AdvancedReferralService import SocialShareService
            code = ReferralCode.objects.filter(
                user=request.user, is_primary=True, is_active=True
            ).first()
            if not code:
                return Response({'error': 'No active referral code'}, status=404)
            return Response({
                'code': code.code,
                'share_urls': SocialShareService.get_share_urls(code),
                'best_platform': SocialShareService.get_best_platform(code),
            })
        except Exception as e:
            return Response({'error': str(e)}, status=500)

    def post(self, request):
        """Record a share action."""
        try:
            from api.referral.models import ReferralCode
            from api.referral.services.AdvancedReferralService import SocialShareService
            platform = request.data.get('platform', 'other')
            code = ReferralCode.objects.filter(
                user=request.user, is_primary=True
            ).first()
            if code:
                SocialShareService.record_share(code, platform)
            return Response({'recorded': True})
        except Exception as e:
            return Response({'error': str(e)}, status=500)