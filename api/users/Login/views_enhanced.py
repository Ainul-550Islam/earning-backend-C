# api/users/views_enhanced.py
# ============================================================
# User System নতুন API Views
# users/urls.py তে import করে add করো
# ============================================================

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.db import transaction
import logging

from .services.UserEnhancedService import (
    ProfileCompletionService,
    StreakService,
    TierService,
    SocialLoginService,
)
from .services.SessionService import SessionService
from .utils import get_client_ip

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────
# PROFILE COMPLETION
# ──────────────────────────────────────────────────────────────

class ProfileCompletionView(APIView):
    """
    GET /api/users/profile/completion/
    Profile completion score + missing fields + unlocked features।
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        data = ProfileCompletionService.calculate(request.user)
        return Response({'success': True, **data})


# ──────────────────────────────────────────────────────────────
# DAILY STREAK
# ──────────────────────────────────────────────────────────────

class DailyCheckInView(APIView):
    """
    POST /api/users/daily-checkin/
    Login করলে এই endpoint call করো।
    Streak track করো + milestone bonus দাও।
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        result = StreakService.record_daily_login(request.user)

        # Tier upgrade check করো (daily)
        tier_result = TierService.check_and_upgrade_tier(request.user)
        if tier_result.get('upgraded'):
            result['tier_upgrade'] = tier_result

        return Response({'success': True, **result})


class StreakInfoView(APIView):
    """
    GET /api/users/streak/
    Current streak + milestones দেখাও।
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        info = StreakService.get_streak_info(request.user)
        return Response({'success': True, **info})


# ──────────────────────────────────────────────────────────────
# TIER SYSTEM
# ──────────────────────────────────────────────────────────────

class TierProgressView(APIView):
    """
    GET /api/users/tier/
    Current tier + benefits + next tier progress।
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        progress = TierService.get_tier_progress(request.user)
        return Response({'success': True, **progress})


class TierUpgradeCheckView(APIView):
    """
    POST /api/users/tier/check-upgrade/
    Manual tier upgrade check trigger করো।
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        result = TierService.check_and_upgrade_tier(request.user)
        return Response({'success': True, **result})


# ──────────────────────────────────────────────────────────────
# SOCIAL LOGIN
# ──────────────────────────────────────────────────────────────

class GoogleLoginView(APIView):
    """
    POST /api/users/auth/google/
    Body: {
        "id_token": "Google ID token from frontend",
        "referral_code": "optional"
    }
    """
    permission_classes = [AllowAny]

    @transaction.atomic
    def post(self, request):
        id_token = request.data.get('id_token', '').strip()
        referral_code = request.data.get('referral_code', '').strip()

        if not id_token:
            return Response({'error': 'Google id_token দিন।'}, status=status.HTTP_400_BAD_REQUEST)

        # Verify token
        social_data = SocialLoginService.verify_google_token(id_token)
        if not social_data['valid']:
            return Response({'error': social_data.get('error', 'Invalid token')}, status=status.HTTP_401_UNAUTHORIZED)

        try:
            user, created, tokens = SocialLoginService.get_or_create_social_user(
                provider='google',
                social_data=social_data,
                referral_code=referral_code,
            )

            # Session create করো
            session = SessionService.create_session(user, request, tokens['refresh'])

            # Daily check-in
            StreakService.record_daily_login(user)

            return Response({
                'success': True,
                'is_new_user': created,
                'access': tokens['access'],
                'refresh': tokens['refresh'],
                'session_id': session['session_id'],
                'user': {
                    'id': str(user.id),
                    'username': user.username,
                    'email': user.email,
                    'tier': user.tier,
                    'is_verified': user.is_verified,
                }
            }, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Google login error: {e}")
            return Response({'error': 'Server error।'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class FacebookLoginView(APIView):
    """
    POST /api/users/auth/facebook/
    Body: {
        "access_token": "Facebook access token from frontend",
        "referral_code": "optional"
    }
    """
    permission_classes = [AllowAny]

    @transaction.atomic
    def post(self, request):
        access_token = request.data.get('access_token', '').strip()
        referral_code = request.data.get('referral_code', '').strip()

        if not access_token:
            return Response({'error': 'Facebook access_token দিন।'}, status=status.HTTP_400_BAD_REQUEST)

        social_data = SocialLoginService.verify_facebook_token(access_token)
        if not social_data['valid']:
            return Response({'error': social_data.get('error', 'Invalid token')}, status=status.HTTP_401_UNAUTHORIZED)

        try:
            user, created, tokens = SocialLoginService.get_or_create_social_user(
                provider='facebook',
                social_data=social_data,
                referral_code=referral_code,
            )

            session = SessionService.create_session(user, request, tokens['refresh'])
            StreakService.record_daily_login(user)

            return Response({
                'success': True,
                'is_new_user': created,
                'access': tokens['access'],
                'refresh': tokens['refresh'],
                'session_id': session['session_id'],
                'user': {
                    'id': str(user.id),
                    'username': user.username,
                    'email': user.email,
                    'tier': user.tier,
                    'is_verified': user.is_verified,
                }
            }, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Facebook login error: {e}")
            return Response({'error': 'Server error।'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ──────────────────────────────────────────────────────────────
# USER DASHBOARD (সব info একসাথে)
# ──────────────────────────────────────────────────────────────

class UserDashboardView(APIView):
    """
    GET /api/users/dashboard/
    User এর সব info একটা call এ।
    Frontend home screen এ use করো।
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        # Wallet summary
        try:
            from api.wallet.services import WalletService
            wallet_summary = WalletService.get_wallet_summary(user)
        except Exception:
            wallet_summary = {}

        # Streak info
        streak_info = StreakService.get_streak_info(user)

        # Tier info
        tier_info = TierService.get_tier_progress(user)

        # Profile completion
        completion = ProfileCompletionService.calculate(user)

        # Referral stats (quick)
        try:
            from api.referral.services import ReferralService
            referral_stats = ReferralService.get_referral_stats(user)
        except Exception:
            referral_stats = {}

        return Response({
            'success': True,
            'user': {
                'id': str(user.id),
                'username': user.username,
                'email': user.email,
                'avatar': user.avatar.url if user.avatar else None,
                'tier': user.tier,
                'is_verified': user.is_verified,
                'referral_code': user.referral_code,
                'date_joined': user.created_at.strftime('%Y-%m-%d') if hasattr(user, 'created_at') else '',
            },
            'wallet': wallet_summary,
            'streak': streak_info,
            'tier': tier_info,
            'profile_completion': completion,
            'referral': {
                'code': referral_stats.get('referral_code', ''),
                'total': referral_stats.get('total_referrals', 0),
                'commission': referral_stats.get('total_commission', 0),
            },
        })