# api/notifications/services/JourneyService.py
"""
JourneyService — Multi-step notification journeys (like Braze Canvas).

Automates sequences like:
  Step 1: Welcome email (immediately)
  Step 2: Push — first task reminder (Day 1, 10am)
  Step 3: Email — still haven't done first task? (Day 3)
  Step 4: SMS — final nudge (Day 7)

Pre-built journeys for earning site:
  - ONBOARDING        : Welcome → First Task → KYC → First Withdrawal
  - REENGAGEMENT      : Inactive user win-back (Day 3, 7, 14)
  - REFERRAL          : Invite friends drip sequence
  - WITHDRAWAL_FLOW   : Pending → Processing → Complete follow-ups
  - TASK_COMPLETION   : Task done → Reward → Next task suggestion
  - STREAK            : Daily reward streak maintenance
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional
from django.utils import timezone
logger = logging.getLogger(__name__)


@dataclass
class JourneyStep:
    """A single step in a notification journey."""
    step_id: str
    name: str
    channel: str                   # 'in_app' | 'push' | 'email' | 'sms' | 'slack'
    notification_type: str
    title_template: str
    message_template: str
    delay_hours: float = 0         # Hours after previous step (0 = immediate)
    delay_days: int = 0            # Days after previous step
    priority: str = 'medium'
    condition_fn: Optional[Callable] = None  # callable(user) → bool: skip if False
    send_push: bool = False
    send_email: bool = False
    exit_if: Optional[Callable] = None  # callable(user) → bool: exit journey if True


@dataclass
class Journey:
    """Multi-step notification journey."""
    journey_id: str
    name: str
    description: str
    steps: List[JourneyStep] = field(default_factory=list)
    is_active: bool = True
    entry_condition: Optional[Callable] = None  # callable(user) → bool


class JourneyService:
    """
    Executes multi-step notification journeys.
    Each step is scheduled as a Celery task with the appropriate delay.
    """

    # Pre-built journeys for earning site
    JOURNEYS: Dict[str, Journey] = {}

    def __init__(self):
        self._register_builtin_journeys()

    def _register_builtin_journeys(self):
        """Register all pre-built earning site journeys."""

        # ── ONBOARDING JOURNEY ──────────────────────────────────────
        self.JOURNEYS['onboarding'] = Journey(
            journey_id='onboarding',
            name='New User Onboarding',
            description='Welcome → First task → KYC → First withdrawal',
            steps=[
                JourneyStep(
                    step_id='welcome',
                    name='Welcome',
                    channel='in_app',
                    notification_type='announcement',
                    title_template='স্বাগতম {username}! 🎉',
                    message_template='আপনার account তৈরি হয়েছে। প্রথম task করে আয় শুরু করুন!',
                    delay_hours=0,
                    send_push=True,
                    send_email=True,
                ),
                JourneyStep(
                    step_id='first_task_reminder',
                    name='First Task Reminder',
                    channel='push',
                    notification_type='task_assigned',
                    title_template='আপনার জন্য ৳50 উপার্জনের সুযোগ!',
                    message_template='এখনো প্রথম task করেননি। আজই শুরু করুন এবং ৳50 পান!',
                    delay_days=1,
                    priority='high',
                    # Skip if user already completed a task
                    condition_fn=lambda user: not _user_has_completed_task(user),
                ),
                JourneyStep(
                    step_id='kyc_reminder',
                    name='KYC Reminder',
                    channel='in_app',
                    notification_type='kyc_submitted',
                    title_template='KYC সম্পন্ন করুন — Withdraw করতে পারবেন',
                    message_template='Withdraw করতে হলে KYC verify করতে হবে। মাত্র 2 মিনিটে করুন!',
                    delay_days=3,
                    condition_fn=lambda user: not _user_kyc_verified(user),
                ),
                JourneyStep(
                    step_id='first_withdrawal_nudge',
                    name='First Withdrawal Nudge',
                    channel='email',
                    notification_type='withdrawal_pending',
                    title_template='আপনার ৳{balance} withdraw করুন!',
                    message_template='আপনার wallet এ ৳{balance} জমা আছে। এখনই withdraw করুন!',
                    delay_days=7,
                    condition_fn=lambda user: _user_has_balance(user),
                ),
            ]
        )

        # ── REENGAGEMENT JOURNEY ────────────────────────────────────
        self.JOURNEYS['reengagement'] = Journey(
            journey_id='reengagement',
            name='Inactive User Win-Back',
            description='Bring back users who haven\'t logged in for 3+ days',
            steps=[
                JourneyStep(
                    step_id='miss_you_3d',
                    name='3-Day Miss You',
                    channel='push',
                    notification_type='announcement',
                    title_template='আমরা আপনাকে miss করছি! 😢',
                    message_template='৩ দিন ধরে দেখা নেই। আজ task করুন, নতুন offer আছে!',
                    delay_days=0,
                    priority='medium',
                ),
                JourneyStep(
                    step_id='miss_you_7d',
                    name='7-Day Miss You',
                    channel='email',
                    notification_type='announcement',
                    title_template='আপনার জন্য বিশেষ offer!',
                    message_template='৭ দিন পর ফিরে আসুন। আপনার জন্য bonus task অপেক্ষা করছে!',
                    delay_days=4,
                    exit_if=lambda user: _user_logged_in_recently(user, days=4),
                ),
                JourneyStep(
                    step_id='final_nudge',
                    name='Final Reengagement',
                    channel='sms',
                    notification_type='announcement',
                    title_template='শেষ সুযোগ!',
                    message_template='আপনার account এ ৳{balance} পড়ে আছে। আজই login করুন!',
                    delay_days=7,
                    priority='high',
                    condition_fn=lambda user: _user_has_balance(user),
                    exit_if=lambda user: _user_logged_in_recently(user, days=7),
                ),
            ]
        )

        # ── REFERRAL DRIP ───────────────────────────────────────────
        self.JOURNEYS['referral_drip'] = Journey(
            journey_id='referral_drip',
            name='Referral Invitation Drip',
            description='Encourage users to refer friends over 2 weeks',
            steps=[
                JourneyStep(
                    step_id='invite_intro',
                    name='Introduce Referral',
                    channel='in_app',
                    notification_type='announcement',
                    title_template='বন্ধুকে আমন্ত্রণ করুন — ৳50 বোনাস পান!',
                    message_template='প্রতিটি সফল referral এ আপনি ৳50 এবং বন্ধুও ৳50 পাবেন!',
                    delay_hours=0,
                ),
                JourneyStep(
                    step_id='invite_reminder',
                    name='Referral Reminder',
                    channel='push',
                    notification_type='referral_completed',
                    title_template='এখনো কাউকে invite করেননি?',
                    message_template='আপনার referral link শেয়ার করুন। প্রতি বন্ধুর জন্য ৳50!',
                    delay_days=3,
                    condition_fn=lambda user: not _user_has_referrals(user),
                ),
            ]
        )

        # ── STREAK MAINTENANCE ──────────────────────────────────────
        self.JOURNEYS['streak'] = Journey(
            journey_id='streak',
            name='Daily Streak Maintenance',
            description='Keep users engaged with daily streak rewards',
            steps=[
                JourneyStep(
                    step_id='streak_reminder',
                    name='Daily Streak Reminder',
                    channel='push',
                    notification_type='streak_reward',
                    title_template='🔥 Streak বজায় রাখুন! Day {streak_count}',
                    message_template='আজকের task করুন। {streak_count} দিনের streak ভাঙবেন না!',
                    delay_hours=0,
                    priority='high',
                ),
            ]
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def enroll_user(self, user, journey_id: str, context: Dict = None) -> Dict:
        """
        Enroll a user in a journey. Schedules all steps as Celery tasks.

        Args:
            user:       Django User instance.
            journey_id: Journey identifier.
            context:    Extra template variables.

        Returns:
            Dict with success, journey_id, steps_scheduled.
        """
        journey = self.JOURNEYS.get(journey_id)
        if not journey:
            return {'success': False, 'error': f'Journey "{journey_id}" not found'}

        if not journey.is_active:
            return {'success': False, 'error': f'Journey "{journey_id}" is not active'}

        if journey.entry_condition and not journey.entry_condition(user):
            return {'success': False, 'error': 'User does not meet entry condition', 'skipped': True}

        context = context or {}
        context.setdefault('username', getattr(user, 'username', ''))

        steps_scheduled = 0
        cumulative_delay = timedelta()

        for step in journey.steps:
            step_delay = timedelta(
                hours=step.delay_hours,
                days=step.delay_days,
            )
            cumulative_delay += step_delay
            run_at = timezone.now() + cumulative_delay

            try:
                from notifications.tasks.journey_tasks import execute_journey_step_task
                execute_journey_step_task.apply_async(
                    args=[user.pk, journey_id, step.step_id, context],
                    eta=run_at,
                )
                steps_scheduled += 1
            except Exception as exc:
                logger.warning(f'JourneyService.enroll_user step {step.step_id}: {exc}')

        logger.info(f'JourneyService: enrolled user #{user.pk} in "{journey_id}" ({steps_scheduled} steps)')
        return {'success': True, 'journey_id': journey_id, 'steps_scheduled': steps_scheduled}

    def execute_step(self, user, journey_id: str, step_id: str, context: Dict = None) -> Dict:
        """Execute a single journey step for a user (called by Celery task)."""
        journey = self.JOURNEYS.get(journey_id)
        if not journey:
            return {'success': False, 'error': f'Journey not found: {journey_id}'}

        step = next((s for s in journey.steps if s.step_id == step_id), None)
        if not step:
            return {'success': False, 'error': f'Step not found: {step_id}'}

        # Check exit condition
        if step.exit_if:
            try:
                if step.exit_if(user):
                    logger.info(f'JourneyService: exit condition met for user #{user.pk} at {step_id}')
                    return {'success': True, 'skipped': True, 'reason': 'exit_condition'}
            except Exception:
                pass

        # Check step condition
        if step.condition_fn:
            try:
                if not step.condition_fn(user):
                    return {'success': True, 'skipped': True, 'reason': 'condition_not_met'}
            except Exception:
                pass

        # Render templates
        ctx = context or {}
        ctx.setdefault('username', getattr(user, 'username', ''))
        try:
            title = step.title_template.format(**ctx)
            message = step.message_template.format(**ctx)
        except (KeyError, ValueError):
            title = step.title_template
            message = step.message_template

        # Send notification
        try:
            from notifications.services import notification_service
            notification = notification_service.create_notification(
                user=user,
                title=title,
                message=message,
                notification_type=step.notification_type,
                channel=step.channel,
                priority=step.priority,
                metadata={'journey_id': journey_id, 'step_id': step_id, **ctx},
            )
            if notification:
                success = notification_service.send_notification(notification)
                return {'success': success, 'step_id': step_id, 'notification_id': notification.pk}
        except Exception as exc:
            logger.error(f'JourneyService.execute_step {step_id}: {exc}')
            return {'success': False, 'error': str(exc)}

        return {'success': False, 'error': 'Notification creation failed'}

    def list_journeys(self) -> List[Dict]:
        """Return summary of all registered journeys."""
        return [
            {
                'journey_id': j.journey_id,
                'name': j.name,
                'description': j.description,
                'steps': len(j.steps),
                'is_active': j.is_active,
            }
            for j in self.JOURNEYS.values()
        ]

    def register_journey(self, journey: Journey):
        """Register a custom journey (called by other modules via integ_config)."""
        self.JOURNEYS[journey.journey_id] = journey
        logger.info(f'JourneyService: registered journey "{journey.journey_id}"')

    def unenroll_user(self, user, journey_id: str) -> Dict:
        """
        Revoke all pending journey tasks for a user.
        Uses Celery task revocation by task name pattern.
        """
        try:
            from celery import current_app
            inspector = current_app.control.inspect()
            scheduled = inspector.scheduled() or {}
            revoked = 0
            for worker_tasks in scheduled.values():
                for task in worker_tasks:
                    args = task.get('request', {}).get('args', [])
                    if args and len(args) >= 2 and args[0] == user.pk and args[1] == journey_id:
                        current_app.control.revoke(task['request']['id'])
                        revoked += 1
            return {'success': True, 'revoked_steps': revoked}
        except Exception as exc:
            return {'success': False, 'error': str(exc)}


# ------------------------------------------------------------------
# Condition helpers (used in step condition_fn)
# ------------------------------------------------------------------

def _user_has_completed_task(user) -> bool:
    try:
        return __import__('tasks.models', fromlist=['UserTaskCompletion']).UserTaskCompletion.objects.filter(
            user=user, status='approved'
        ).exists()
    except Exception:
        return False

def _user_kyc_verified(user) -> bool:
    try:
        return __import__('kyc.models', fromlist=['KYC']).KYC.objects.filter(
            user=user, status='verified'
        ).exists()
    except Exception:
        return False

def _user_has_balance(user, min_amount=10) -> bool:
    try:
        wallet = __import__('wallet.models', fromlist=['Wallet']).Wallet.objects.filter(user=user).first()
        return wallet and float(wallet.current_balance) >= min_amount
    except Exception:
        return False

def _user_logged_in_recently(user, days=3) -> bool:
    from django.utils import timezone as tz
    from datetime import timedelta
    last_login = getattr(user, 'last_login', None)
    if not last_login:
        return False
    return last_login >= tz.now() - timedelta(days=days)

def _user_has_referrals(user) -> bool:
    try:
        return __import__('referral.models', fromlist=['Referral']).Referral.objects.filter(
            referrer=user
        ).exists()
    except Exception:
        return False


    # ------------------------------------------------------------------
    # Entry / Exit conditions
    # ------------------------------------------------------------------

    def evaluate_entry_condition(self, user, journey_id: str) -> dict:
        """
        Evaluate if a user meets the entry condition for a journey.
        Returns {'allowed': bool, 'reason': str}
        """
        journey = self.JOURNEYS.get(journey_id)
        if not journey:
            return {'allowed': False, 'reason': 'journey_not_found'}
        if not journey.is_active:
            return {'allowed': False, 'reason': 'journey_inactive'}
        if journey.entry_condition:
            try:
                allowed = journey.entry_condition(user)
                return {'allowed': allowed, 'reason': '' if allowed else 'entry_condition_not_met'}
            except Exception as exc:
                logger.warning(f'evaluate_entry_condition {journey_id}: {exc}')
        return {'allowed': True, 'reason': 'no_condition'}

    def add_conversion_event(self, journey_id: str, step_id: str,
                              conversion_action: str, window_hours: int = 24):
        """
        Register a conversion event for a journey step.
        Conversion is tracked when user performs `conversion_action`
        within `window_hours` of receiving the step's notification.
        """
        journey = self.JOURNEYS.get(journey_id)
        if not journey:
            return False
        for step in journey.steps:
            if step.step_id == step_id:
                if not hasattr(step, 'conversion_action'):
                    step.conversion_action = conversion_action
                    step.conversion_window_hours = window_hours
                return True
        return False

    def track_conversion(self, user, journey_id: str, step_id: str) -> dict:
        """
        Record a conversion for a specific journey step.
        Called when a user completes the target action (e.g. first task, first withdrawal).
        """
        try:
            from django.core.cache import cache
            cache_key = f'journey:conversion:{user.pk}:{journey_id}:{step_id}'
            if cache.get(cache_key):
                return {'success': True, 'already_tracked': True}
            cache.set(cache_key, {
                'user_id': user.pk, 'journey_id': journey_id, 'step_id': step_id,
                'converted_at': timezone.now().isoformat(),
            }, 86400 * 30)  # Keep for 30 days
            logger.info(f'JourneyService: conversion tracked user #{user.pk} {journey_id}/{step_id}')
            return {'success': True, 'converted': True}
        except Exception as exc:
            return {'success': False, 'error': str(exc)}

    def get_conversion_stats(self, journey_id: str, step_id: str = None) -> dict:
        """Return conversion statistics for a journey."""
        journey = self.JOURNEYS.get(journey_id)
        if not journey:
            return {'error': 'Journey not found'}
        return {
            'journey_id': journey_id,
            'name': journey.name,
            'steps': [
                {'step_id': s.step_id, 'name': s.name,
                 'has_conversion': hasattr(s, 'conversion_action')}
                for s in journey.steps
            ],
        }


# Singleton
journey_service = JourneyService()
