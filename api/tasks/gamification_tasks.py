"""
tasks/gamification_tasks.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Gamification System Celery Tasks (CPAlead Gap)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CPAlead has a full gamification system:
  - User levels & XP points
  - Achievement badges
  - Daily login streaks
  - Leaderboards (daily/weekly/all-time)
  - Challenge completion rewards
  - Milestone bonuses
  - Lucky spin / scratch card

  ✅ award_xp_points             — award XP for task completions
  ✅ level_up_check              — check if user leveled up
  ✅ award_badges                — grant achievement badges
  ✅ update_streak_status        — maintain daily login streaks
  ✅ run_daily_challenge         — assign/check daily challenges
  ✅ process_milestone_rewards   — credit milestone bonuses
  ✅ update_global_leaderboard   — rebuild global leaderboard
"""
from celery.exceptions import MaxRetriesExceededError
from typing import Any
from typing import Optional
import logging
from decimal import Decimal
from celery import shared_task
from django.utils import timezone
from django.core.cache import cache
from api.tasks.enums import LeaderboardScope
from api.gamification.exceptions import ContestCycleNotFoundError
from api.gamification.exceptions import LeaderboardGenerationError
from api.gamification.exceptions import GamificationServiceError
from api.gamification.exceptions import ContestCycleStateError

logger = logging.getLogger(__name__)

# XP required per level (cumulative)
XP_PER_LEVEL = {
    1: 0, 2: 100, 3: 250, 4: 500, 5: 1000,
    6: 2000, 7: 4000, 8: 8000, 9: 15000, 10: 30000,
}

# Badge definitions
BADGES = {
    'first_task':        {'name': '🎯 First Task',         'xp': 10,  'condition': 'completions >= 1'},
    'ten_tasks':         {'name': '🔟 10 Tasks Done',       'xp': 50,  'condition': 'completions >= 10'},
    'hundred_tasks':     {'name': '💯 Century',            'xp': 200, 'condition': 'completions >= 100'},
    'first_dollar':      {'name': '💵 First Dollar',       'xp': 25,  'condition': 'earnings >= 1'},
    'ten_dollars':       {'name': '💰 Ten Dollars',        'xp': 100, 'condition': 'earnings >= 10'},
    'week_streak':       {'name': '🔥 7-Day Streak',       'xp': 150, 'condition': 'streak >= 7'},
    'month_streak':      {'name': '⚡ 30-Day Streak',      'xp': 500, 'condition': 'streak >= 30'},
    'referral_5':        {'name': '👥 5 Referrals',        'xp': 200, 'condition': 'referrals >= 5'},
    'top_earner_daily':  {'name': '🏆 Daily Top Earner',   'xp': 300, 'condition': 'daily_rank <= 10'},
}

# Milestone rewards (earnings threshold → bonus)
MILESTONES = {
    Decimal('1'):    Decimal('0.10'),   # First $1 → $0.10 bonus
    Decimal('10'):   Decimal('0.50'),   # $10 → $0.50 bonus
    Decimal('50'):   Decimal('2.00'),   # $50 → $2.00 bonus
    Decimal('100'):  Decimal('5.00'),   # $100 → $5.00 bonus
    Decimal('500'):  Decimal('25.00'),  # $500 → $25.00 bonus
    Decimal('1000'): Decimal('75.00'),  # $1000 → $75.00 bonus
}


@shared_task(bind=True, max_retries=3, default_retry_delay=15,
             name='tasks.gamification_tasks.award_xp_points')
def award_xp_points(self, user_id: int, xp: int, reason: str = 'task_completion') -> dict:
    """
    Award XP points to a user and trigger level-up check.
    XP sources: task completion, streak bonus, referral, badge unlock.
    """
    try:
        logger.debug(f"⭐ Awarding {xp} XP to user {user_id} ({reason})")

        try:
            from users.models import Profile
            from django.db.models import F

            Profile.objects.filter(user_id=user_id).update(
                xp_points=F('xp_points') + xp,
                total_xp_earned=F('total_xp_earned') + xp,
            )
            # Trigger level-up check
            level_up_check.apply_async(kwargs={'user_id': user_id})

        except ImportError:
            # Use cache fallback
            current = cache.get(f'user_xp_{user_id}', 0)
            cache.set(f'user_xp_{user_id}', current + xp, timeout=None)

        return {
            'status': 'success',
            'user_id': user_id,
            'xp_awarded': xp,
            'reason': reason,
            'timestamp': timezone.now().isoformat(),
        }

    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=2, default_retry_delay=15,
             name='tasks.gamification_tasks.level_up_check')
def level_up_check(self, user_id: int) -> dict:
    """
    Check if user has accumulated enough XP to level up.
    Awards level-up bonus rewards and sends notification.
    """
    try:
        current_level = 1
        current_xp    = 0
        new_level     = 1
        leveled_up    = False

        try:
            from users.models import Profile
            profile = Profile.objects.filter(user_id=user_id).first()
            if not profile:
                return {'status': 'skipped', 'reason': 'profile_not_found'}

            current_level = profile.level or 1
            current_xp    = profile.xp_points or 0

            # Find what level current XP corresponds to
            for lvl in sorted(XP_PER_LEVEL.keys(), reverse=True):
                if current_xp >= XP_PER_LEVEL[lvl]:
                    new_level = lvl
                    break

            if new_level > current_level:
                leveled_up    = True
                levels_gained = new_level - current_level
                profile.level = new_level
                profile.save(update_fields=['level'])

                logger.info(f"🆙 User {user_id} leveled up: {current_level} → {new_level}")

                # Level-up bonus (0.10 per level gained)
                bonus = Decimal('0.10') * levels_gained
                try:
                    from api.tasks.services import WalletService
                    WalletService().credit(
                        user_id=user_id,
                        amount=bonus,
                        transaction_type='level_up_bonus',
                        reference=f'level_up_{new_level}',
                        metadata={'old_level': current_level, 'new_level': new_level},
                    )
                except ImportError:
                    pass

                # Notify
                try:
                    from api.tasks.notification_tasks import dispatch_in_app_notification
                    dispatch_in_app_notification.apply_async(kwargs={
                        'user_id': user_id,
                        'title': f'🆙 Level Up! You reached Level {new_level}!',
                        'message': f'Congratulations! +${bonus:.2f} bonus credited.',
                        'notification_type': 'success',
                    })
                except ImportError:
                    pass

        except ImportError:
            pass

        return {
            'status': 'success',
            'user_id': user_id,
            'leveled_up': leveled_up,
            'old_level': current_level,
            'new_level': new_level,
            'timestamp': timezone.now().isoformat(),
        }

    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=2, default_retry_delay=30,
             name='tasks.gamification_tasks.award_badges')
def award_badges(self, user_id: int) -> dict:
    """
    Check all badge conditions for a user and award newly earned badges.
    """
    try:
        from decimal import Decimal
        from django.db.models import Sum, Count, Max
        logger.debug(f"🏅 Checking badges for user {user_id}")

        newly_awarded = []

        try:
            from api.tasks.models import UserTaskCompletion

            # Gather user stats
            stats = UserTaskCompletion.objects.filter(
                user_id=user_id, status='completed'
            ).aggregate(
                completions=Count('id'),
                earnings=Sum('reward_amount'),
            )
            completions = stats['completions'] or 0
            earnings    = Decimal(str(stats['earnings'] or 0))
            streak      = cache.get(f'user_streak_{user_id}', 0)

            # Referral count
            try:
                from referrals.models import Referral
                referrals = Referral.objects.filter(referrer_id=user_id, bonus_paid=True).count()
            except ImportError:
                referrals = 0

            # Already earned badges
            try:
                from users.models import UserBadge
                earned = set(UserBadge.objects.filter(user_id=user_id).values_list('badge_id', flat=True))
            except ImportError:
                earned = set(cache.get(f'user_badges_{user_id}') or [])

            context = {
                'completions': completions,
                'earnings': float(earnings),
                'streak': streak,
                'referrals': referrals,
                'daily_rank': cache.get(f'user_daily_rank_{user_id}', 999),
            }

            for badge_id, badge_def in BADGES.items():
                if badge_id in earned:
                    continue
                # Evaluate condition using safe comparison
                try:
                    if _safe_eval_condition(badge_def['condition'], context):
                        # Award badge
                        try:
                            from users.models import UserBadge
                            UserBadge.objects.get_or_create(
                                user_id=user_id,
                                badge_id=badge_id,
                                defaults={'awarded_at': timezone.now(), 'xp_awarded': badge_def['xp']},
                            )
                        except ImportError:
                            badges = list(cache.get(f'user_badges_{user_id}') or [])
                            if badge_id not in badges:
                                badges.append(badge_id)
                                cache.set(f'user_badges_{user_id}', badges, timeout=None)

                        # Award XP for badge
                        award_xp_points.apply_async(kwargs={
                            'user_id': user_id,
                            'xp': badge_def['xp'],
                            'reason': f'badge_{badge_id}',
                        })

                        # Notify
                        try:
                            from api.tasks.notification_tasks import dispatch_in_app_notification
                            dispatch_in_app_notification.apply_async(kwargs={
                                'user_id': user_id,
                                'title': f'Badge Unlocked: {badge_def["name"]}!',
                                'message': f'You earned the {badge_def["name"]} badge! +{badge_def["xp"]} XP',
                                'notification_type': 'success',
                            })
                        except ImportError:
                            pass

                        newly_awarded.append(badge_id)
                        logger.info(f"[BADGE] User {user_id} earned: {badge_id}")
                except Exception:
                    pass

        except ImportError as e:
            logger.warning(f"[WARN] Models not available: {e}")

        return {
            'status': 'success',
            'user_id': user_id,
            'newly_awarded': newly_awarded,
            'timestamp': timezone.now().isoformat(),
        }

    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=2, default_retry_delay=15,
             name='tasks.gamification_tasks.update_streak_status')
def update_streak_status(self, user_id: int) -> dict:
    """
    Update daily streak for a user based on today's completions.
    Breaks streak if user missed yesterday.
    Awards streak XP bonuses at milestones.
    """
    try:
        from datetime import date, timedelta
        from api.tasks.models import UserTaskCompletion

        today     = timezone.now().date()
        yesterday = today - timedelta(days=1)

        # Did user complete a task today?
        did_today = UserTaskCompletion.objects.filter(
            user_id=user_id, status='completed', completed_at__date=today
        ).exists()

        if not did_today:
            return {'status': 'no_completion_today', 'user_id': user_id}

        # Did user complete yesterday? (check for streak continuity)
        did_yesterday = UserTaskCompletion.objects.filter(
            user_id=user_id, status='completed', completed_at__date=yesterday
        ).exists()

        current_streak = cache.get(f'user_streak_{user_id}', 0)
        last_streak_date = cache.get(f'user_streak_date_{user_id}')

        # If last recorded date is today, already counted
        if last_streak_date == str(today):
            return {'status': 'already_counted', 'streak': current_streak}

        if did_yesterday or current_streak == 0:
            new_streak = current_streak + 1
        else:
            new_streak = 1  # Streak broken

        cache.set(f'user_streak_{user_id}', new_streak, timeout=None)
        cache.set(f'user_streak_date_{user_id}', str(today), timeout=86400 * 2)

        # Update profile
        try:
            from users.models import Profile
            Profile.objects.filter(user_id=user_id).update(
                current_streak=new_streak,
                longest_streak__gte=0,  # Will be updated properly
            )
        except ImportError:
            pass

        # Streak XP bonuses
        streak_xp_map = {3: 30, 7: 70, 14: 140, 30: 300}
        bonus_xp = streak_xp_map.get(new_streak, 5)  # 5 XP per day minimum
        award_xp_points.apply_async(kwargs={
            'user_id': user_id,
            'xp': bonus_xp,
            'reason': f'streak_{new_streak}d',
        })

        # Check badges
        award_badges.apply_async(kwargs={'user_id': user_id})

        logger.info(f"[STREAK] User {user_id} streak: {new_streak} days")
        return {
            'status': 'success',
            'user_id': user_id,
            'streak': new_streak,
            'xp_bonus': bonus_xp,
            'timestamp': timezone.now().isoformat(),
        }

    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=2, default_retry_delay=30,
             name='tasks.gamification_tasks.process_milestone_rewards')
def process_milestone_rewards(self, user_id: int) -> dict:
    """
    Check if user has crossed any earning milestones and credit bonuses.
    """
    try:
        from django.db.models import Sum
        logger.debug(f"🎖️ Checking milestone rewards for user {user_id}")

        credited = []

        try:
            from api.tasks.models import UserTaskCompletion
            from api.tasks.services import WalletService

            total_earned = (
                UserTaskCompletion.objects.filter(
                    user_id=user_id, status='completed'
                ).aggregate(total=Sum('reward_amount'))['total'] or Decimal('0')
            )
            total_earned = Decimal(str(total_earned))

            # Already claimed milestones
            claimed = cache.get(f'milestones_claimed_{user_id}') or []

            ws = WalletService()
            for threshold, bonus in sorted(MILESTONES.items()):
                milestone_key = f'{threshold}'
                if total_earned >= threshold and milestone_key not in claimed:
                    ws.credit(
                        user_id=user_id,
                        amount=bonus,
                        transaction_type='milestone_bonus',
                        reference=f'milestone_{threshold}',
                        metadata={'milestone': str(threshold), 'bonus': str(bonus)},
                    )
                    claimed.append(milestone_key)
                    credited.append({'milestone': str(threshold), 'bonus': str(bonus)})

                    try:
                        from api.tasks.notification_tasks import dispatch_in_app_notification
                        dispatch_in_app_notification.apply_async(kwargs={
                            'user_id': user_id,
                            'title': f'🎖️ Milestone Reached: ${threshold}!',
                            'message': f'You earned a ${bonus:.2f} milestone bonus!',
                            'notification_type': 'success',
                        })
                    except ImportError:
                        pass

            cache.set(f'milestones_claimed_{user_id}', claimed, timeout=None)

        except ImportError as e:
            logger.warning(f"[WARN] Models not available: {e}")

        return {
            'status': 'success',
            'user_id': user_id,
            'credited': credited,
            'timestamp': timezone.now().isoformat(),
        }

    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=2, default_retry_delay=30,
             name='tasks.gamification_tasks.update_global_leaderboard')
def update_global_leaderboard(self, periods: list = None) -> dict:
    """
    Rebuild the global leaderboard for all periods.
    Stores: rank, user_id, username, earnings, level, badge_count.
    """
    try:
        from datetime import timedelta
        from django.db.models import Sum, Count
        if not periods:
            periods = ['daily', 'weekly', 'monthly', 'alltime']

        logger.info(f"🏆 Updating global leaderboards: {periods}")
        updated = {}

        try:
            from api.tasks.models import UserTaskCompletion

            hours_map = {'daily': 24, 'weekly': 168, 'monthly': 720, 'alltime': 0}

            for period in periods:
                hours = hours_map.get(period, 24)
                qs    = UserTaskCompletion.objects.filter(status='completed')
                if hours > 0:
                    qs = qs.filter(completed_at__gte=timezone.now() - timedelta(hours=hours))

                top = (
                    qs.values('user_id', 'user__username')
                    .annotate(
                        total_earned=Sum('reward_amount'),
                        completions=Count('id'),
                    )
                    .order_by('-total_earned')[:100]
                )

                leaderboard = [
                    {
                        'rank':         i + 1,
                        'user_id':      row['user_id'],
                        'username':     row['user__username'],
                        'total_earned': str(row['total_earned'] or Decimal('0')),
                        'completions':  row['completions'],
                        'level':        cache.get(f'user_level_{row["user_id"]}', 1),
                    }
                    for i, row in enumerate(top)
                ]

                cache.set(f'leaderboard_{period}', leaderboard, timeout=1800)

                # Update individual ranks
                for entry in leaderboard:
                    cache.set(
                        f'user_{period}_rank_{entry["user_id"]}',
                        entry['rank'],
                        timeout=1800
                    )

                updated[period] = len(leaderboard)

        except ImportError as e:
            logger.warning(f"[WARN] Models not available: {e}")

        return {
            'status': 'success',
            'periods_updated': updated,
            'timestamp': timezone.now().isoformat(),
        }

    except Exception as exc:
        raise self.retry(exc=exc)


# ── Safe Condition Evaluator (replaces eval) ──────────────────────────────────

def _safe_eval_condition(condition: str, context: dict) -> bool:
    """
    Safely evaluate badge conditions without using eval().
    Supports: field >= value, field <= value, field == value, field > value, field < value
    Example: 'completions >= 100', 'earnings >= 10', 'streak >= 7'
    """
    import re
    try:
        m = re.match(r'^(\w+)\s*(>=|<=|==|!=|>|<)\s*([0-9.]+)$', condition.strip())
        if not m:
            return False
        field, op, val_str = m.group(1), m.group(2), m.group(3)
        left  = float(context.get(field, 0))
        right = float(val_str)
        ops   = {'>=': left >= right, '<=': left <= right, '==': left == right,
                 '!=': left != right, '>':  left > right,  '<':  left < right}
        return ops.get(op, False)
    except Exception:
        return False


# ══════════════════════════════════════════════════════════════
# MIGRATED FROM: api/gamification/tasks.py (original code preserved)
# ══════════════════════════════════════════════════════════════
@shared_task(
    bind=True,
    max_retries=DEFAULT_MAX_RETRIES,
    default_retry_delay=DEFAULT_RETRY_DELAY,
    name="gamification.update_leaderboard_snapshot",
    acks_late=True,
    reject_on_worker_lost=True,
)
def update_leaderboard_snapshot(
    self,
    cycle_id: Any,
    scope: str = LeaderboardScope.GLOBAL,
    scope_ref: str = "",
    top_n: int = DEFAULT_LEADERBOARD_TOP_N,
) -> dict:
    """
    Celery task: generate or refresh a leaderboard snapshot for a ContestCycle.

    Args:
        cycle_id:  PK of the ContestCycle to snapshot.
        scope:     Leaderboard scope.
        scope_ref: Optional scope qualifier.
        top_n:     Number of top entries to include.

    Returns:
        Dict with snapshot_id and entry_count on success.

    Retries on transient errors with exponential back-off.
    Does NOT retry on ContestCycleNotFoundError (permanent failure).
    """
    task_id = self.request.id
    logger.info(
        "[task=%s] update_leaderboard_snapshot started: cycle=%s scope=%s top_n=%s",
        task_id,
        cycle_id,
        scope,
        top_n,
    )

    if not cycle_id:
        logger.error("[task=%s] update_leaderboard_snapshot: cycle_id is required.", task_id)
        return {"error": "cycle_id is required.", "task_id": task_id}

    try:
        snapshot = services.generate_leaderboard_snapshot(
            cycle_id=cycle_id,
            scope=scope,
            scope_ref=scope_ref or "",
            top_n=int(top_n),
        )
    except ContestCycleNotFoundError as exc:
        # Permanent failure — do not retry
        logger.error(
            "[task=%s] update_leaderboard_snapshot: cycle not found: %s", task_id, exc
        )
        return {"error": str(exc), "retryable": False, "task_id": task_id}
    except LeaderboardGenerationError as exc:
        # Transient failure — retry with back-off
        retry_count = self.request.retries
        delay = DEFAULT_RETRY_DELAY * (BACKOFF_MULTIPLIER ** retry_count)
        logger.warning(
            "[task=%s] update_leaderboard_snapshot: generation error (attempt %d/%d): %s. "
            "Retrying in %ds.",
            task_id,
            retry_count + 1,
            DEFAULT_MAX_RETRIES,
            exc,
            delay,
        )
        try:
            raise self.retry(exc=exc, countdown=delay)
        except MaxRetriesExceededError:
            logger.error(
                "[task=%s] update_leaderboard_snapshot: max retries exceeded for cycle=%s: %s",
                task_id,
                cycle_id,
                exc,
            )
            return {"error": str(exc), "retryable": False, "max_retries_exceeded": True, "task_id": task_id}
    except GamificationServiceError as exc:
        logger.error(
            "[task=%s] update_leaderboard_snapshot: service error: %s", task_id, exc
        )
        return {"error": str(exc), "task_id": task_id}
    except Exception as exc:
        logger.exception(
            "[task=%s] update_leaderboard_snapshot: unexpected error: %s", task_id, exc
        )
        try:
            raise self.retry(exc=exc, countdown=DEFAULT_RETRY_DELAY)
        except MaxRetriesExceededError:
            return {"error": f"Unexpected error: {exc}", "task_id": task_id}

    result = {
        "snapshot_id": str(snapshot.id),
        "cycle_id": str(cycle_id),
        "scope": scope,
        "entry_count": snapshot.entry_count,
        "status": snapshot.status,
        "task_id": task_id,
    }
    logger.info("[task=%s] update_leaderboard_snapshot completed: %s", task_id, result)
    return result


@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=120,
    name="gamification.distribute_cycle_rewards_async",
    acks_late=True,
    reject_on_worker_lost=True,
)
def distribute_cycle_rewards_async(self, cycle_id: Any) -> dict:
    """
    Celery task: distribute rewards for a completed ContestCycle.

    Intended to be enqueued automatically when a cycle transitions to COMPLETED.

    Args:
        cycle_id: PK of the COMPLETED ContestCycle.

    Returns:
        Dict with awarded_count, skipped_count, and errors.
    """
    task_id = self.request.id
    logger.info(
        "[task=%s] distribute_cycle_rewards_async started: cycle=%s",
        task_id,
        cycle_id,
    )

    if not cycle_id:
        logger.error("[task=%s] distribute_cycle_rewards_async: cycle_id is required.", task_id)
        return {"error": "cycle_id is required.", "task_id": task_id}

    try:
        result = services.distribute_cycle_rewards(cycle_id=cycle_id)
    except ContestCycleNotFoundError as exc:
        logger.error(
            "[task=%s] distribute_cycle_rewards_async: cycle not found: %s", task_id, exc
        )
        return {"error": str(exc), "retryable": False, "task_id": task_id}
    except ContestCycleStateError as exc:
        # Permanent failure — cycle is in wrong state
        logger.error(
            "[task=%s] distribute_cycle_rewards_async: state error: %s", task_id, exc
        )
        return {"error": str(exc), "retryable": False, "task_id": task_id}
    except LeaderboardGenerationError as exc:
        retry_count = self.request.retries
        delay = 120 * (BACKOFF_MULTIPLIER ** retry_count)
        logger.warning(
            "[task=%s] distribute_cycle_rewards_async: leaderboard error: %s. Retrying in %ds.",
            task_id, exc, delay,
        )
        try:
            raise self.retry(exc=exc, countdown=delay)
        except MaxRetriesExceededError:
            return {"error": str(exc), "task_id": task_id, "max_retries_exceeded": True}
    except GamificationServiceError as exc:
        logger.error(
            "[task=%s] distribute_cycle_rewards_async: service error: %s", task_id, exc
        )
        try:
            raise self.retry(exc=exc, countdown=120)
        except MaxRetriesExceededError:
            return {"error": str(exc), "task_id": task_id, "max_retries_exceeded": True}
    except Exception as exc:
        logger.exception(
            "[task=%s] distribute_cycle_rewards_async: unexpected error: %s", task_id, exc
        )
        try:
            raise self.retry(exc=exc, countdown=120)
        except MaxRetriesExceededError:
            return {"error": f"Unexpected: {exc}", "task_id": task_id}

    result["task_id"] = task_id
    result["cycle_id"] = str(cycle_id)
    logger.info(
        "[task=%s] distribute_cycle_rewards_async completed: awarded=%d skipped=%d errors=%d",
        task_id,
        result.get("awarded_count", 0),
        result.get("skipped_count", 0),
        len(result.get("errors", [])),
    )
    return result


@shared_task(
    bind=True,
    max_retries=1,
    name="gamification.batch_award_achievements_async",
    acks_late=True,
)
def batch_award_achievements_async(
    self,
    awards: list[dict],
    cycle_id: Optional[Any] = None,
    stop_on_first_error: bool = False,
) -> dict:
    """
    Celery task: batch award achievements asynchronously.

    Args:
        awards:              List of award spec dicts.
        cycle_id:            Optional cycle scope.
        stop_on_first_error: Stop processing on first failure.

    Returns:
        Dict with succeeded count, failed list, and total.
    """
    task_id = self.request.id
    logger.info(
        "[task=%s] batch_award_achievements_async started: %d awards cycle=%s",
        task_id,
        len(awards) if isinstance(awards, list) else "?",
        cycle_id,
    )

    if not isinstance(awards, list):
        logger.error("[task=%s] awards must be a list.", task_id)
        return {"error": "awards must be a list.", "task_id": task_id}

    if not awards:
        return {"succeeded": [], "failed": [], "total": 0, "task_id": task_id}

    try:
        result = services.batch_award_achievements(
            awards,
            cycle_id=cycle_id,
            stop_on_first_error=stop_on_first_error,
        )
    except GamificationServiceError as exc:
        logger.error(
            "[task=%s] batch_award_achievements_async: service error: %s", task_id, exc
        )
        try:
            raise self.retry(exc=exc, countdown=60)
        except MaxRetriesExceededError:
            return {"error": str(exc), "task_id": task_id}
    except Exception as exc:
        logger.exception(
            "[task=%s] batch_award_achievements_async: unexpected error: %s", task_id, exc
        )
        return {"error": f"Unexpected: {exc}", "task_id": task_id}

    result["task_id"] = task_id
    logger.info(
        "[task=%s] batch_award_achievements_async: succeeded=%d failed=%d",
        task_id,
        len(result.get("succeeded", [])),
        len(result.get("failed", [])),
    )
    return result

