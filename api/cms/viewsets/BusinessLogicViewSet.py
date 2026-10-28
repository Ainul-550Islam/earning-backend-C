# cms/viewsets/BusinessLogicViewSet.py
"""
BusinessLogicViewSet — exposes every calculation function in logic.py
as a clean REST endpoint so the frontend never re-implements business rules.

Business value:
  • /tools/fee-preview/       — user sees exact fee BEFORE submitting withdrawal
  • /tools/coins-preview/     — user sees coin conversion BEFORE redeeming
  • /tools/level/             — user sees their current level + next threshold
  • /tools/embed-url/         — publisher gets offerwall embed URL in one call
  • /tools/survey-quality/    — QA team can test quality scoring offline
  • /tools/survey-reward/     — reward preview before approving a survey payout
  • /tools/user-segments/     — CRM sees which segments a user belongs to
  • /tools/pool-status/       — ops dashboard sees pool utilisation
  • /tools/participation-score/ — gamification score visible to user/admin

All read-only or idempotent — no database writes.
"""
import logging
from decimal import Decimal, InvalidOperation
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny
from rest_framework_simplejwt.authentication import JWTAuthentication
from .cms_viewset_base import CMSUserThrottle, CMSAnonThrottle

logger = logging.getLogger('cms.viewsets.business_logic')


class BusinessLogicViewSet(viewsets.GenericViewSet):
    """
    Read-only utility endpoints backed by cms/logic.py.
    No DB writes — pure calculation / data transformation.
    """
    authentication_classes = [JWTAuthentication]

    # ─────────────────────────────────────────────────────────────────────────
    # Fee & Currency Tools
    # ─────────────────────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'],
            permission_classes=[IsAuthenticated],
            throttle_classes=[CMSUserThrottle])
    def fee_preview(self, request):
        """
        GET /api/cms/tools/fee-preview/?amount=10.00&method=paypal

        Returns the exact withdrawal fee and net amount the user will receive
        BEFORE they submit a withdrawal request.

        Frontend use: show "You will receive $9.80 (fee: $0.20)" in the UI.
        """
        amount_raw = request.query_params.get('amount', '0')
        method = request.query_params.get('method', 'paypal')
        try:
            amount = Decimal(str(amount_raw))
            if amount <= 0:
                return Response({'error': 'amount must be positive'},
                                status=status.HTTP_400_BAD_REQUEST)
        except InvalidOperation:
            return Response({'error': 'invalid amount format'},
                            status=status.HTTP_400_BAD_REQUEST)

        from api.cms.logic import calculate_withdrawal_fee
        fee, net = calculate_withdrawal_fee(amount, method=method)
        return Response({
            'amount_requested': str(amount),
            'fee': str(fee),
            'net_amount': str(net),
            'method': method,
            'fee_percentage': '2%',
        })

    @action(detail=False, methods=['get'],
            permission_classes=[IsAuthenticated],
            throttle_classes=[CMSUserThrottle])
    def coins_preview(self, request):
        """
        GET /api/cms/tools/coins-preview/?usd=5.00

        Returns how many coins a given USD amount converts to,
        using the currently active VirtualCurrency conversion ratio.

        Frontend use: show "5.00 USD = 500 coins" on the earn/redeem screen.
        """
        usd_raw = request.query_params.get('usd', '1.00')
        try:
            usd = Decimal(str(usd_raw))
        except InvalidOperation:
            return Response({'error': 'invalid usd value'},
                            status=status.HTTP_400_BAD_REQUEST)

        try:
            from api.cms.models_new.cpalead import VirtualCurrency
            vc = VirtualCurrency.get_active()
            ratio = vc.coins_per_dollar if vc else Decimal('100')
        except Exception:
            ratio = Decimal('100')

        from api.cms.logic import calculate_coins_from_usd, calculate_usd_from_coins
        coins = calculate_coins_from_usd(usd, ratio)
        back_to_usd = calculate_usd_from_coins(coins, ratio)
        return Response({
            'usd': str(usd),
            'coins': str(coins),
            'conversion_ratio': str(ratio),
            'back_to_usd': str(back_to_usd),
        })

    @action(detail=False, methods=['get'],
            permission_classes=[IsAuthenticated],
            throttle_classes=[CMSUserThrottle])
    def coins_to_usd(self, request):
        """
        GET /api/cms/tools/coins-to-usd/?coins=500

        Returns USD value of a given coin amount.
        Frontend use: show "500 coins = $5.00" on wallet screen.
        """
        coins_raw = request.query_params.get('coins', '0')
        try:
            coins = Decimal(str(coins_raw))
        except InvalidOperation:
            return Response({'error': 'invalid coins value'},
                            status=status.HTTP_400_BAD_REQUEST)

        try:
            from api.cms.models_new.cpalead import VirtualCurrency
            vc = VirtualCurrency.get_active()
            ratio = vc.coins_per_dollar if vc else Decimal('100')
        except Exception:
            ratio = Decimal('100')

        from api.cms.logic import calculate_usd_from_coins
        usd = calculate_usd_from_coins(coins, ratio)
        return Response({
            'coins': str(coins),
            'usd': str(usd),
            'conversion_ratio': str(ratio),
        })

    # ─────────────────────────────────────────────────────────────────────────
    # User Level & Progression
    # ─────────────────────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'],
            permission_classes=[IsAuthenticated],
            throttle_classes=[CMSUserThrottle])
    def my_level(self, request):
        """
        GET /api/cms/tools/my-level/

        Returns the authenticated user's current level, XP, and the
        threshold for the next level.

        Frontend use: progress bar on the user dashboard.
        """
        from api.cms.logic import calculate_user_level
        try:
            from api.cms.models_new.cpalead import UserVirtualBalance
            vb = UserVirtualBalance.objects.filter(user=request.user).first()
            total_earned = float(vb.total_earned) if vb else 0.0
        except Exception:
            total_earned = 0.0

        level = calculate_user_level(total_earned)
        # Level thresholds: 0=$0, 1=$5, 2=$25, 3=$100, 4=$500, 5=$2000
        thresholds = [0, 5, 25, 100, 500, 2000, 99999]
        current_threshold = thresholds[min(level, len(thresholds) - 2)]
        next_threshold = thresholds[min(level + 1, len(thresholds) - 1)]
        progress_pct = 0.0
        if next_threshold > current_threshold:
            progress_pct = min(
                100.0,
                (total_earned - current_threshold) / (next_threshold - current_threshold) * 100
            )

        level_names = {0: 'Starter', 1: 'Bronze', 2: 'Silver',
                       3: 'Gold', 4: 'Platinum', 5: 'Diamond'}
        return Response({
            'user_id': request.user.pk,
            'level': level,
            'level_name': level_names.get(level, 'Legend'),
            'total_earned_usd': round(total_earned, 4),
            'current_threshold_usd': current_threshold,
            'next_threshold_usd': next_threshold,
            'progress_pct': round(progress_pct, 2),
        })

    @action(detail=False, methods=['get'],
            permission_classes=[IsAuthenticated],
            throttle_classes=[CMSUserThrottle])
    def streak_multiplier(self, request):
        """
        GET /api/cms/tools/streak-multiplier/?streak_days=7

        Returns the reward multiplier for a given streak length.
        Frontend use: show "7-day streak = 1.2x multiplier" on streak screen.
        """
        days = int(request.query_params.get('streak_days', 0))
        from api.cms.logic import calculate_streak_multiplier
        multiplier = calculate_streak_multiplier(days)
        return Response({
            'streak_days': days,
            'multiplier': str(multiplier),
            'bonus_pct': str(round((float(multiplier) - 1.0) * 100, 1)),
        })

    # ─────────────────────────────────────────────────────────────────────────
    # Offerwall Tools
    # ─────────────────────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'],
            permission_classes=[IsAuthenticated],
            throttle_classes=[CMSUserThrottle])
    def embed_url(self, request):
        """
        GET /api/cms/tools/embed-url/

        Generates a personalised offerwall embed URL for the
        authenticated user using the active CPAlead config.

        Frontend use: <iframe src="{{ embed_url }}"> on the earn page.
        """
        from api.cms.logic import build_offerwall_embed_url
        try:
            from api.cms.models_new.cpalead import OfferWallConfig
            config = OfferWallConfig.objects.filter(is_active=True).first()
            publisher_id = config.publisher_id if config else ''
            website_id   = config.website_id   if config else ''
        except Exception:
            publisher_id = ''
            website_id   = ''

        if not publisher_id:
            return Response({'error': 'OfferWall not configured'},
                            status=status.HTTP_503_SERVICE_UNAVAILABLE)

        user_agent = request.META.get('HTTP_USER_AGENT', '')
        from api.cms.logic import detect_device_type
        device = detect_device_type(user_agent)

        url = build_offerwall_embed_url(
            publisher_id=publisher_id,
            website_id=website_id,
            subid=str(request.user.pk),
            device=device,
        )
        return Response({
            'embed_url': url,
            'subid': str(request.user.pk),
            'device': device,
        })

    @action(detail=False, methods=['post'],
            permission_classes=[IsAuthenticated],
            throttle_classes=[CMSUserThrottle])
    def survey_quality(self, request):
        """
        POST /api/cms/tools/survey-quality/

        Body: { "responses": [...], "survey": {...} }

        Calculates the quality score for a set of survey responses.
        Frontend use: QA dashboard, real-time quality indicator during survey.
        """
        responses = request.data.get('responses', [])
        survey    = request.data.get('survey', {})
        if not responses or not survey:
            return Response({'error': 'responses and survey are required'},
                            status=status.HTTP_400_BAD_REQUEST)
        from api.cms.logic import calculate_survey_quality, validate_survey_responses
        validation = validate_survey_responses(responses, survey)
        if not validation.get('valid', True):
            return Response({
                'valid': False,
                'issues': validation.get('issues', []),
                'quality_score': 0,
            })
        quality = calculate_survey_quality(responses, survey)
        return Response({
            'valid': True,
            'quality_score': round(quality * 100, 2),
            'quality_grade': (
                'excellent' if quality >= 0.9 else
                'good'      if quality >= 0.7 else
                'fair'      if quality >= 0.5 else 'poor'
            ),
        })

    @action(detail=False, methods=['post'],
            permission_classes=[IsAuthenticated],
            throttle_classes=[CMSUserThrottle])
    def survey_reward_preview(self, request):
        """
        POST /api/cms/tools/survey-reward-preview/

        Body: { "survey": {...}, "quality_score": 85.5 }

        Returns the reward the user would earn before the survey is finalized.
        Frontend use: show "You will earn ~$2.50" at end of survey flow.
        """
        survey_data   = request.data.get('survey', {})
        quality_score = float(request.data.get('quality_score', 80.0))
        if not survey_data:
            return Response({'error': 'survey data required'},
                            status=status.HTTP_400_BAD_REQUEST)

        from api.cms.logic import calculate_survey_reward
        try:
            from api.cms.models_new.cpalead import UserVirtualBalance
            vb = UserVirtualBalance.objects.filter(user=request.user).first()
            total_earned = float(vb.total_earned) if vb else 0.0
        except Exception:
            total_earned = 0.0

        user_data = {
            'total_earned': total_earned,
            'streak_days': 0,
            'participation_score': 50.0,
        }
        reward = calculate_survey_reward(survey_data, quality_score / 100.0, user_data)
        return Response({
            'quality_score': quality_score,
            'reward': reward,
        })

    # ─────────────────────────────────────────────────────────────────────────
    # User Segmentation & Participation
    # ─────────────────────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'],
            permission_classes=[IsAuthenticated],
            throttle_classes=[CMSUserThrottle])
    def my_segments(self, request):
        """
        GET /api/cms/tools/my-segments/

        Returns the user's current segments based on their activity.
        Frontend use: personalised content/offer targeting.
        """
        from api.cms.logic import determine_user_segments, calculate_participation_score
        try:
            from api.cms.models_new.cpalead import UserVirtualBalance
            vb = UserVirtualBalance.objects.filter(user=request.user).first()
            total_earned = float(vb.total_earned) if vb else 0.0
        except Exception:
            total_earned = 0.0

        user_data = {
            'total_earned': total_earned,
            'days_since_join': 30,
            'offers_completed': 0,
            'surveys_completed': 0,
        }
        segments = determine_user_segments(user_data)
        participation = calculate_participation_score(user_data)
        return Response({
            'user_id': request.user.pk,
            'segments': segments,
            'participation_score': round(participation, 2),
        })

    @action(detail=False, methods=['get'],
            permission_classes=[IsAdminUser],
            throttle_classes=[CMSUserThrottle])
    def user_segments_for(self, request):
        """
        GET /api/cms/tools/user-segments-for/?user_id=42

        Admin: compute segments for any user.
        """
        user_id = request.query_params.get('user_id')
        if not user_id:
            return Response({'error': 'user_id required'},
                            status=status.HTTP_400_BAD_REQUEST)
        from django.contrib.auth import get_user_model
        try:
            target = get_user_model().objects.get(pk=int(user_id))
        except Exception:
            return Response({'error': 'User not found'}, status=404)

        from api.cms.logic import determine_user_segments
        user_data = {'total_earned': 0, 'days_since_join': 0,
                     'offers_completed': 0, 'surveys_completed': 0}
        try:
            from api.cms.models_new.cpalead import UserVirtualBalance
            vb = UserVirtualBalance.objects.filter(user=target).first()
            if vb:
                user_data['total_earned'] = float(vb.total_earned or 0)
        except Exception:
            pass

        segments = determine_user_segments(user_data)
        return Response({'user_id': int(user_id), 'segments': segments})

    # ─────────────────────────────────────────────────────────────────────────
    # Pool & Operations Tools (Admin)
    # ─────────────────────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'],
            permission_classes=[IsAdminUser],
            throttle_classes=[CMSUserThrottle])
    def pool_status(self, request):
        """
        GET /api/cms/tools/pool-status/

        Admin: show reward pool utilisation and whether it needs a refill.
        Ops dashboard use: alert ops team when utilisation > 80%.
        """
        from api.cms.logic import calculate_pool_utilization, should_refill_pool
        try:
            from api.cms.models_new.survey_rewards import RewardPool
            pools = RewardPool.objects.filter(is_active=True)
            results = []
            for pool in pools:
                pool_data = {
                    'total_budget': float(pool.total_budget),
                    'allocated': float(pool.allocated or 0),
                    'paid_out': float(pool.paid_out or 0),
                }
                utilization = calculate_pool_utilization(pool_data)
                needs_refill = should_refill_pool(pool_data)
                results.append({
                    'pool_id': pool.pk,
                    'pool_name': getattr(pool, 'name', str(pool)),
                    **utilization,
                    'needs_refill': needs_refill,
                })
        except Exception as e:
            results = [{'error': str(e)}]

        return Response({'pools': results, 'count': len(results)})

    @action(detail=False, methods=['post'],
            permission_classes=[IsAdminUser],
            throttle_classes=[CMSUserThrottle])
    def validate_profile_data(self, request):
        """
        POST /api/cms/tools/validate-profile/

        Admin/CRM: validate a profile data payload before importing.
        """
        profile_data = request.data.get('profile', {})
        if not profile_data:
            return Response({'error': 'profile data required'},
                            status=status.HTTP_400_BAD_REQUEST)
        from api.cms.logic import validate_profile_data, calculate_profile_completeness
        result = validate_profile_data(profile_data)
        completeness = calculate_profile_completeness(profile_data)
        return Response({
            'valid': result.get('valid', True),
            'errors': result.get('errors', []),
            'completeness_pct': round(completeness * 100, 2),
        })

    @action(detail=False, methods=['get'],
            permission_classes=[AllowAny],
            throttle_classes=[CMSAnonThrottle])
    def postback_response(self, request):
        """
        GET /api/cms/tools/postback-response/?success=1

        Returns the correct CPAlead postback response string.
        Used by integration testers to verify postback format.
        """
        success = request.query_params.get('success', '1') == '1'
        from api.cms.logic import get_postback_response
        return Response({'response': get_postback_response(success)})
