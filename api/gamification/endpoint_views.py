"""
Thin endpoint views wired to the specific URL names expected by test_endpoints.py.
Each view delegates to the appropriate service/viewset logic.
"""
from __future__ import annotations
import logging
import uuid
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response

from api.gamification.models import Badge, UserBadge, Streak, DailyChallenge, UserDailyChallenge, LevelConfig
from api.gamification.services import (
    BadgeService, StreakService, ChallengeService, LevelService,
)
from api.gamification.exceptions import GamificationServiceError, DuplicateAchievementError
from api.gamification.serializers import (
    BadgeSerializer, UserBadgeSerializer, StreakSerializer,
    DailyChallengeSerializer, UserDailyChallengeSerializer, LevelConfigSerializer
)

User = get_user_model()
logger = logging.getLogger(__name__)


def _ok(data, count=None):
    if count is None:
        count = len(data) if isinstance(data, list) else 1
    return Response({'success': True, 'data': data, 'count': count})


def _err(msg, code=status.HTTP_400_BAD_REQUEST):
    from rest_framework import status as _s
    error_types = {
        _s.HTTP_400_BAD_REQUEST: 'bad_request',
        _s.HTTP_401_UNAUTHORIZED: 'unauthorized',
        _s.HTTP_403_FORBIDDEN: 'forbidden',
        _s.HTTP_404_NOT_FOUND: 'not_found',
        _s.HTTP_409_CONFLICT: 'conflict',
        _s.HTTP_429_TOO_MANY_REQUESTS: 'rate_limited',
        _s.HTTP_500_INTERNAL_SERVER_ERROR: 'server_error',
    }
    from django.utils import timezone as _tz
    return Response({
        'success': False,
        'error': str(msg),
        'error_type': error_types.get(code, 'error'),
        'timestamp': _tz.now().isoformat(),
    }, status=code)


# ── Badge endpoints ───────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_badges(request, user_id):
    try:
        badges = UserBadge.objects.filter(user_id=user_id).select_related('badge')
        s = UserBadgeSerializer(badges, many=True)
        return _ok(s.data)
    except (ValueError, Exception):
        return _err('Invalid user_id', status.HTTP_404_NOT_FOUND)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def badge_check_eligibility(request, user_id):
    """Check which badges the user is eligible for given criteria."""
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return _err('User not found', status.HTTP_404_NOT_FOUND)

    # If a specific badge_id provided, check that badge
    badge_id = request.data.get('badge_id')
    if badge_id:
        try:
            badge = Badge.objects.get(id=badge_id)
            eligible = BadgeService.check_user_badge_eligibility(user=user, badge=badge)
            return _ok({'eligible': eligible, 'badge_id': str(badge_id)})
        except Badge.DoesNotExist:
            return _err('Badge not found', status.HTTP_404_NOT_FOUND)
        except Exception as exc:
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)

    # Require at least one criteria field for bulk check
    criteria_fields = ['user_points', 'streak_days', 'achievement_count', 'contest_wins', 'referral_count']
    if not any(f in request.data for f in criteria_fields):
        return _err('At least one criteria field is required', status.HTTP_400_BAD_REQUEST)

    # Otherwise evaluate all badges against supplied criteria
    try:
        eligible_badges = BadgeService.check_user_badge_eligibility(
            user_id=user.id,
            user_points=int(request.data.get('user_points', 0)),
            streak_days=int(request.data.get('streak_days', 0)),
            achievement_count=int(request.data.get('achievement_count', 0)),
            contest_wins=int(request.data.get('contest_wins', 0)),
            referral_count=int(request.data.get('referral_count', 0)),
        )
        s = BadgeSerializer(eligible_badges, many=True)
        return _ok(s.data)
    except GamificationServiceError as exc:
        return _err(str(exc), status.HTTP_400_BAD_REQUEST)
    except Exception as exc:
        return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def badge_award(request, user_id):
    """Award badge(s) to user. Accepts badge_id or criteria for bulk award."""
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return _err('User not found', status.HTTP_404_NOT_FOUND)

    badge_id = request.data.get('badge_id')
    if badge_id:
        try:
            badge = Badge.objects.get(id=badge_id)
            result = BadgeService.award_badge_to_user(user=user, badge=badge)
            s = UserBadgeSerializer(result)
            return _ok(s.data, count=1)
        except Badge.DoesNotExist:
            return _err('Badge not found', status.HTTP_404_NOT_FOUND)
        except Exception as exc:
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)

    # Bulk: award all eligible badges based on criteria
    try:
        eligible_badges = BadgeService.check_user_badge_eligibility(
            user_id=user.id,
            user_points=int(request.data.get('user_points', 0)),
            streak_days=int(request.data.get('streak_days', 0)),
            achievement_count=int(request.data.get('achievement_count', 0)),
            contest_wins=int(request.data.get('contest_wins', 0)),
            referral_count=int(request.data.get('referral_count', 0)),
        )
        awarded = []
        for badge in eligible_badges:
            try:
                ub = BadgeService.award_badge_to_user(user=user, badge=badge)
                awarded.append(UserBadgeSerializer(ub).data)
            except Exception:
                pass
        return _ok(awarded)
    except Exception as exc:
        return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


# ── Streak endpoints ──────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_streak(request, user_id):
    try:
        streak = StreakService.get_or_create_user_streak(user_id=user_id)
        s = StreakSerializer(streak)
        return _ok(s.data, count=1)
    except Exception as exc:
        return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def streak_update(request, user_id):
    activity_date = request.data.get('activity_date')
    if not activity_date:
        return _err('activity_date is required', status.HTTP_400_BAD_REQUEST)
    try:
        from datetime import date as _date
        try:
            act_date = _date.fromisoformat(str(activity_date))
        except ValueError:
            return _err('Invalid activity_date format', status.HTTP_400_BAD_REQUEST)
        streak, was_extended, days_added = StreakService.update_user_activity(
            user_id=user_id, activity_date=act_date
        )
        s = StreakSerializer(streak)
        return Response({
            'success': True,
            'data': s.data,
            'count': 1,
            'was_extended': was_extended,
            'days_added': days_added,
        })
    except GamificationServiceError as exc:
        return _err(str(exc), status.HTTP_400_BAD_REQUEST)
    except Exception as exc:
        return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def streak_statistics(request, user_id):
    try:
        stats = StreakService.get_streak_statistics(user_id=user_id)
        return _ok(stats, count=1)
    except Exception as exc:
        return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


# ── Challenge endpoints ───────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def challenge_list(request):
    qs = DailyChallenge.objects.filter(is_active=True)
    challenge_type = request.query_params.get('challenge_type')
    if challenge_type:
        qs = qs.filter(challenge_type=challenge_type)
    s = DailyChallengeSerializer(qs, many=True)
    return _ok(s.data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_challenge_progress(request, user_id):
    qs = UserDailyChallenge.objects.filter(user_id=user_id)
    s = UserDailyChallengeSerializer(qs, many=True)
    return _ok(s.data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def challenge_start(request, user_id):
    challenge_id = request.data.get('challenge_id')
    if not challenge_id:
        return _err('challenge_id is required', status.HTTP_400_BAD_REQUEST)
    try:

        result = ChallengeService.start_user_challenge(user_id=user_id, challenge_id=challenge_id)
        s = UserDailyChallengeSerializer(result)
        return _ok(s.data, count=1)
    except (GamificationServiceError, DuplicateAchievementError) as exc:
        return _err(str(exc), status.HTTP_400_BAD_REQUEST)
    except Exception as exc:
        return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def challenge_update(request, user_id):
    challenge_id = request.data.get('challenge_id')
    increment = request.data.get('increment_amount', request.data.get('progress', 1))
    if not challenge_id:
        return _err('challenge_id is required', status.HTTP_400_BAD_REQUEST)
    # Validate challenge_id looks like a UUID (not arbitrary string)
    import uuid as _uuid
    try:
        _uuid.UUID(str(challenge_id))
    except ValueError:
        return _err('Invalid challenge_id', status.HTTP_400_BAD_REQUEST)
    try:

        try:
            inc_val = int(increment)
        except (TypeError, ValueError):
            inc_val = 1
        result, completed = ChallengeService.update_challenge_progress(
            user_id=user_id, challenge_id=challenge_id, increment_amount=inc_val
        )
        from django.utils import timezone as _tz
        if completed and result.completed_at is None:
            result.completed_at = _tz.now()
            result.save(update_fields=['completed_at'])
        s = UserDailyChallengeSerializer(result)
        return Response({
            'success': True,
            'data': s.data,
            'count': 1,
            'completed': completed,
        })
    except GamificationServiceError as exc:
        return _err(str(exc), status.HTTP_400_BAD_REQUEST)
    except Exception as exc:
        return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


# ── Level endpoints ───────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def level_list(request):
    qs = LevelConfig.objects.all().order_by('level_number')
    is_active = request.query_params.get('is_active')
    if is_active is not None:
        qs = qs.filter(is_active=is_active.lower() == 'true')
    s = LevelConfigSerializer(qs, many=True)
    return _ok(s.data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_level(request, user_id):
    try:
        from api.gamification.models import UserAchievement
        total_points = sum(
            a.points_awarded
            for a in UserAchievement.objects.filter(user_id=user_id, is_awarded=True)
        )
        level_config = LevelService.get_user_level(user_points=total_points)
        current_level_num = level_config.level_number if level_config else 0
        return _ok({
            'total_points': total_points,
            'current_level': current_level_num,
            'level_config': str(level_config.id) if level_config else None,
        }, count=1)
    except Exception:
        return _ok({'total_points': 0, 'current_level': 0, 'level_config': None}, count=1)
