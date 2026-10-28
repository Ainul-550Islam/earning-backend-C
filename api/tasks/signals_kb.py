"""
api/tasks/signals_kb.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Knowledge Base (KB) Signal System for the Task Platform.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
A lightweight rule engine where:
  - Events trigger KB rules
  - Rules evaluate conditions against context
  - Matched rules fire configured actions (Celery tasks, cache updates, notifications)

This powers:
  • Automated task eligibility checks ("if user in US AND device=mobile → show CPI offer")
  • Dynamic reward adjustments ("if streak >= 7 → bonus 10%")
  • Fraud rule triggers ("if fraud_score > 70 → suspend account")
  • Campaign optimization triggers ("if CVR < 1% after 100 clicks → pause campaign")
  • Publisher tier upgrades ("if monthly_earnings >= $500 → upgrade to Gold")

Usage:
    from api.tasks.signals_kb import KBEngine, kb_signal

    # Register a rule
    kb_signal.connect(
        KBRule(
            name='vip_bonus_trigger',
            condition=lambda ctx: ctx.get('total_earnings', 0) >= 500,
            action='tasks.earning_tasks.distribute_bonus_rewards',
            action_kwargs_fn=lambda ctx: {'user_id': ctx['user_id']},
        )
    )

    # Fire the KB engine
    kb_signal.send(
        sender=None,
        event='user.milestone_reached',
        context={'user_id': 123, 'total_earnings': 520}
    )
"""

import logging
from typing import Any, Callable, Dict, List, Optional
from django.dispatch import Signal
from django.utils import timezone
from django.core.cache import cache

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# KB RULE
# ══════════════════════════════════════════════════════════════════════════════

class KBRule:
    """
    A single knowledge-base rule.

    Attributes:
        name:           Unique rule identifier
        event:          Event name this rule listens to (None = any event)
        condition:      Callable(context) → bool — must return True to fire
        action:         Celery task name OR callable
        action_kwargs_fn: Callable(context) → dict — kwargs for the action
        priority:       Lower = fires first (default 50)
        enabled:        Whether the rule is active
        max_fires_per_period: Optional rate limit (uses cache)
        period_seconds: Period for rate limit (default 3600)
        description:    Human-readable description
    """

    def __init__(
        self,
        name: str,
        condition: Callable[[Dict], bool],
        action: Any,                              # Celery task name str OR callable
        event: Optional[str] = None,
        action_kwargs_fn: Optional[Callable] = None,
        priority: int = 50,
        enabled: bool = True,
        max_fires_per_period: Optional[int] = None,
        period_seconds: int = 3600,
        description: str = '',
        async_action: bool = True,
        queue: str = 'default',
    ):
        self.name                  = name
        self.event                 = event
        self.condition             = condition
        self.action                = action
        self.action_kwargs_fn      = action_kwargs_fn or (lambda ctx: {})
        self.priority              = priority
        self.enabled               = enabled
        self.max_fires_per_period  = max_fires_per_period
        self.period_seconds        = period_seconds
        self.description           = description
        self.async_action          = async_action
        self.queue                 = queue

    def matches_event(self, event: str) -> bool:
        """Return True if this rule should be evaluated for the given event."""
        return self.event is None or self.event == event

    def is_rate_limited(self, context: Dict) -> bool:
        """Check if this rule has hit its fire rate limit."""
        if not self.max_fires_per_period:
            return False
        user_id  = context.get('user_id', 'global')
        rate_key = f'kb_rule_fires_{self.name}_{user_id}'
        fires    = cache.get(rate_key, 0)
        return fires >= self.max_fires_per_period

    def _increment_fire_count(self, context: Dict) -> None:
        """Increment the fire counter for rate limiting."""
        if not self.max_fires_per_period:
            return
        user_id  = context.get('user_id', 'global')
        rate_key = f'kb_rule_fires_{self.name}_{user_id}'
        count    = cache.get(rate_key, 0)
        cache.set(rate_key, count + 1, timeout=self.period_seconds)

    def evaluate(self, event: str, context: Dict) -> bool:
        """
        Evaluate the rule against the event and context.
        Returns True if the rule condition matched and action was fired.
        """
        if not self.enabled:
            return False
        if not self.matches_event(event):
            return False
        if self.is_rate_limited(context):
            logger.debug(f"[KB] Rule '{self.name}' rate-limited for user {context.get('user_id')}")
            return False

        try:
            if not self.condition(context):
                return False
        except Exception as e:
            logger.error(f"[KB] Rule '{self.name}' condition error: {e}")
            return False

        # Fire action
        try:
            kwargs = self.action_kwargs_fn(context)
            if callable(self.action):
                self.action(**kwargs)
            elif isinstance(self.action, str) and self.async_action:
                from celery import current_app
                current_app.send_task(self.action, kwargs=kwargs, queue=self.queue)
            elif isinstance(self.action, str):
                # Sync: import and call
                parts    = self.action.rsplit('.', 1)
                mod_path, fn_name = parts[0], parts[1]
                import importlib
                mod = importlib.import_module(mod_path)
                getattr(mod, fn_name)(**kwargs)

            self._increment_fire_count(context)
            logger.info(f"[KB] Rule '{self.name}' FIRED for event '{event}'")
            return True

        except Exception as e:
            logger.error(f"[KB] Rule '{self.name}' action error: {e}")
            return False

    def __repr__(self) -> str:
        return f"<KBRule name={self.name} event={self.event} priority={self.priority}>"


# ══════════════════════════════════════════════════════════════════════════════
# KB ENGINE
# ══════════════════════════════════════════════════════════════════════════════

class KBEngine:
    """
    Knowledge Base rule engine.
    Maintains a registry of KBRules and evaluates them on events.
    Thread-safe for read access; use register() before server startup.
    """

    def __init__(self):
        self._rules: List[KBRule] = []

    def register(self, rule: KBRule) -> 'KBEngine':
        """Register a KB rule. Returns self for chaining."""
        self._rules.append(rule)
        self._rules.sort(key=lambda r: r.priority)
        logger.debug(f"[KB] Registered rule: {rule.name}")
        return self

    def unregister(self, rule_name: str) -> bool:
        """Unregister a rule by name. Returns True if found."""
        before = len(self._rules)
        self._rules = [r for r in self._rules if r.name != rule_name]
        return len(self._rules) < before

    def disable(self, rule_name: str) -> bool:
        """Disable a rule without removing it."""
        for rule in self._rules:
            if rule.name == rule_name:
                rule.enabled = False
                return True
        return False

    def enable(self, rule_name: str) -> bool:
        """Enable a previously disabled rule."""
        for rule in self._rules:
            if rule.name == rule_name:
                rule.enabled = True
                return True
        return False

    def fire(self, event: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluate all rules for an event.
        Returns summary: {fired: [rule_names], skipped: int, errors: int}
        """
        context   = {**context, '_event': event, '_fired_at': timezone.now().isoformat()}
        fired     = []
        skipped   = 0

        for rule in self._rules:
            if not rule.matches_event(event):
                skipped += 1
                continue
            try:
                if rule.evaluate(event, context):
                    fired.append(rule.name)
            except Exception as e:
                logger.error(f"[KB] Engine error evaluating '{rule.name}': {e}")

        logger.debug(f"[KB] Event '{event}': {len(fired)} rules fired, {skipped} skipped")
        return {
            'event':   event,
            'fired':   fired,
            'count':   len(fired),
            'skipped': skipped,
            'context': {k: v for k, v in context.items() if not k.startswith('_')},
        }

    def list_rules(self) -> List[Dict]:
        """Return metadata for all registered rules."""
        return [
            {
                'name':        r.name,
                'event':       r.event,
                'priority':    r.priority,
                'enabled':     r.enabled,
                'description': r.description,
                'action':      str(r.action),
            }
            for r in self._rules
        ]

    def get_rule(self, name: str) -> Optional[KBRule]:
        """Get a rule by name."""
        return next((r for r in self._rules if r.name == name), None)

    def clear(self) -> None:
        """Remove all rules (use in testing)."""
        self._rules.clear()


# ══════════════════════════════════════════════════════════════════════════════
# DJANGO SIGNAL BRIDGE
# ══════════════════════════════════════════════════════════════════════════════

# Global KB signal — used to fire the KB engine from anywhere
kb_signal = Signal()


class KBSignalHandler:
    """
    Connects the kb_signal Django signal to the KBEngine.
    """

    def __init__(self, engine: KBEngine):
        self.engine = engine
        kb_signal.connect(self._handle, dispatch_uid='kb_engine_handler')

    def _handle(self, sender, event: str = '', context: Dict = None, **kwargs):
        """Handle an incoming KB signal."""
        if not event:
            return
        context = context or {}
        return self.engine.fire(event, context)


# ══════════════════════════════════════════════════════════════════════════════
# BUILT-IN PLATFORM RULES
# ══════════════════════════════════════════════════════════════════════════════

def register_platform_rules(engine: KBEngine) -> None:
    """
    Register all built-in platform KB rules.
    Called from apps.py or signals.py during startup.
    """

    # ── Task Completion Rules ──────────────────────────────────────────────

    engine.register(KBRule(
        name='streak_update_on_completion',
        event='task.completed',
        condition=lambda ctx: bool(ctx.get('user_id')),
        action='tasks.gamification_tasks.update_streak_status',
        action_kwargs_fn=lambda ctx: {'user_id': ctx['user_id']},
        priority=10,
        description='Update daily streak when user completes a task',
    ))

    engine.register(KBRule(
        name='xp_award_on_completion',
        event='task.completed',
        condition=lambda ctx: bool(ctx.get('user_id')),
        action='tasks.gamification_tasks.award_xp_points',
        action_kwargs_fn=lambda ctx: {
            'user_id': ctx['user_id'],
            'xp':      5,
            'reason':  'task_completion',
        },
        priority=15,
        description='Award 5 XP for each task completion',
    ))

    engine.register(KBRule(
        name='badge_check_on_completion',
        event='task.completed',
        condition=lambda ctx: bool(ctx.get('user_id')),
        action='tasks.gamification_tasks.award_badges',
        action_kwargs_fn=lambda ctx: {'user_id': ctx['user_id']},
        priority=20,
        description='Check for newly earned badges after task completion',
        max_fires_per_period=10,   # Max 10 badge checks per hour per user
        period_seconds=3600,
    ))

    engine.register(KBRule(
        name='community_points_on_completion',
        event='task.completed',
        condition=lambda ctx: float(ctx.get('reward_amount', 0)) > 0,
        action='tasks.community_tasks.award_community_points',
        action_kwargs_fn=lambda ctx: {
            'user_id':    ctx.get('user_id'),
            'amount_usd': str(ctx.get('reward_amount', '0')),
            'source':     'task_completion',
        },
        priority=25,
        description='Award community points proportional to earnings',
    ))

    engine.register(KBRule(
        name='milestone_check_on_completion',
        event='task.completed',
        condition=lambda ctx: bool(ctx.get('user_id')),
        action='tasks.gamification_tasks.process_milestone_rewards',
        action_kwargs_fn=lambda ctx: {'user_id': ctx['user_id']},
        priority=30,
        description='Check milestone bonuses on each completion',
        max_fires_per_period=5,
        period_seconds=3600,
    ))

    engine.register(KBRule(
        name='affiliate_commission_on_completion',
        event='task.completed',
        condition=lambda ctx: float(ctx.get('reward_amount', 0)) > 0,
        action='tasks.affiliate_tasks.process_affiliate_commission',
        action_kwargs_fn=lambda ctx: {
            'user_id':           ctx['user_id'],
            'conversion_amount': str(ctx.get('reward_amount', '0')),
            'conversion_type':   'task_completion',
        },
        priority=35,
        description='Process multi-level affiliate commissions on completion',
    ))

    # ── User Registration Rules ────────────────────────────────────────────

    engine.register(KBRule(
        name='welcome_drip_on_register',
        event='user.registered',
        condition=lambda ctx: bool(ctx.get('user_id')),
        action='tasks.email_drip_tasks.enroll_user_in_drip',
        action_kwargs_fn=lambda ctx: {
            'user_id':  ctx['user_id'],
            'sequence': 'welcome',
        },
        priority=10,
        description='Enroll new users in welcome email drip sequence',
        queue='emails',
    ))

    engine.register(KBRule(
        name='onboarding_tasks_on_register',
        event='user.registered',
        condition=lambda ctx: bool(ctx.get('user_id')),
        action='tasks.user_lifecycle_tasks.assign_onboarding_tasks',
        action_kwargs_fn=lambda ctx: {'user_id': ctx['user_id']},
        priority=20,
        description='Assign starter tasks to new users',
    ))

    # ── Offer Conversion Rules ─────────────────────────────────────────────

    engine.register(KBRule(
        name='credit_publisher_on_conversion',
        event='offer.converted',
        condition=lambda ctx: ctx.get('status') == 'approved' and bool(ctx.get('user_id')),
        action='tasks.cpalead_tasks.cpalead_credit_publisher',
        action_kwargs_fn=lambda ctx: {
            'user_id':       ctx['user_id'],
            'payout':        str(ctx.get('payout', '0')),
            'offer_id':      ctx.get('offer_id', ''),
            'conversion_id': str(ctx.get('conversion_id', '')),
            'transaction_id': ctx.get('transaction_id', ''),
        },
        priority=5,   # Highest priority — credit first
        description='Credit publisher wallet on approved CPA conversion',
        queue='payments',
    ))

    engine.register(KBRule(
        name='fraud_scan_on_conversion',
        event='offer.converted',
        condition=lambda ctx: bool(ctx.get('transaction_id')),
        action='tasks.cpalead_tasks.cpalead_fraud_scan_conversions',
        action_kwargs_fn=lambda ctx: {'lookback_hours': 1},
        priority=10,
        description='Run fraud scan after each conversion',
        queue='high',
        max_fires_per_period=1,   # Deduplicate: once per hour globally
        period_seconds=3600,
    ))

    # ── Fraud Detection Rules ──────────────────────────────────────────────

    engine.register(KBRule(
        name='suspend_on_critical_fraud',
        event='fraud.detected',
        condition=lambda ctx: int(ctx.get('fraud_score', 0)) >= 80,
        action=lambda user_id, fraud_score, **kw: (
            cache.set(f'user_suspended_{user_id}', True, timeout=86400)
        ),
        action_kwargs_fn=lambda ctx: {
            'user_id':    ctx.get('user_id'),
            'fraud_score': ctx.get('fraud_score'),
        },
        priority=1,   # Fire first
        async_action=False,  # Synchronous — immediate effect
        description='Suspend account when fraud score reaches critical level (80+)',
    ))

    engine.register(KBRule(
        name='notify_admin_on_high_fraud',
        event='fraud.detected',
        condition=lambda ctx: int(ctx.get('fraud_score', 0)) >= 60,
        action='tasks.notification_tasks.dispatch_in_app_notification',
        action_kwargs_fn=lambda ctx: {
            'user_id':           ctx.get('user_id'),
            'title':             '⚠️ Account Flagged',
            'message':           f'Fraud score: {ctx.get("fraud_score")}. Account under review.',
            'notification_type': 'warning',
        },
        priority=5,
        description='Notify user when account is flagged for fraud review',
    ))

    # ── Publisher Tier Rules ───────────────────────────────────────────────

    engine.register(KBRule(
        name='tier_upgrade_vip',
        event='user.milestone_reached',
        condition=lambda ctx: float(ctx.get('total_earnings', 0)) >= 500,
        action='tasks.user_lifecycle_tasks.identify_vip_users',
        action_kwargs_fn=lambda ctx: {},
        priority=10,
        description='Identify VIP users when they hit $500 total earnings',
        max_fires_per_period=1,
        period_seconds=86400,
    ))

    engine.register(KBRule(
        name='vip_upgrade_drip',
        event='user.milestone_reached',
        condition=lambda ctx: float(ctx.get('total_earnings', 0)) >= 500,
        action='tasks.email_drip_tasks.enroll_user_in_drip',
        action_kwargs_fn=lambda ctx: {
            'user_id':  ctx.get('user_id'),
            'sequence': 'vip_upgrade',
        },
        priority=15,
        description='Enroll user in VIP drip sequence at $500 earnings',
        queue='emails',
        max_fires_per_period=1,
        period_seconds=86400 * 365,  # Once per year
    ))

    # ── Payment Rules ──────────────────────────────────────────────────────

    engine.register(KBRule(
        name='fraud_check_before_withdrawal',
        event='payment.withdrawal_requested',
        condition=lambda ctx: bool(ctx.get('user_id')),
        action='tasks.fraud_detection_tasks.flag_suspicious_withdrawal',
        action_kwargs_fn=lambda ctx: {'lookback_hours': 1},
        priority=1,   # First check before processing
        description='Run fraud check before processing any withdrawal',
        queue='high',
    ))

    # ── KYC Rules ─────────────────────────────────────────────────────────

    engine.register(KBRule(
        name='update_limits_on_kyc_approval',
        event='kyc.approved',
        condition=lambda ctx: bool(ctx.get('user_id')),
        action='tasks.kyc_tasks.update_kyc_limits',
        action_kwargs_fn=lambda ctx: {},
        priority=5,
        description='Update withdrawal limits when KYC is approved',
    ))

    # ── Daily Streak Rules ─────────────────────────────────────────────────

    engine.register(KBRule(
        name='streak_bonus_at_7_days',
        event='user.streak_milestone',
        condition=lambda ctx: int(ctx.get('streak', 0)) in (7, 30, 60, 90),
        action='tasks.gamification_tasks.award_xp_points',
        action_kwargs_fn=lambda ctx: {
            'user_id': ctx['user_id'],
            'xp':      {7: 70, 30: 300, 60: 600, 90: 900}.get(ctx.get('streak', 0), 50),
            'reason':  f'streak_milestone_{ctx.get("streak")}d',
        },
        priority=10,
        description='Award bonus XP at 7/30/60/90-day streak milestones',
    ))

    # ── Quiz / Survey Rules ────────────────────────────────────────────────

    engine.register(KBRule(
        name='points_on_quiz_completion',
        event='quiz.completed',
        condition=lambda ctx: float(ctx.get('payout', 0)) > 0,
        action='tasks.community_tasks.award_community_points',
        action_kwargs_fn=lambda ctx: {
            'user_id':    ctx.get('user_id') or ctx.get('publisher_id'),
            'amount_usd': str(ctx.get('payout', '0')),
            'source':     'quiz_completion',
        },
        priority=20,
        description='Award community points for quiz completions',
    ))

    logger.info(f"[KB] {len(engine._rules)} platform rules registered")


# ══════════════════════════════════════════════════════════════════════════════
# GLOBAL ENGINE INSTANCE
# ══════════════════════════════════════════════════════════════════════════════

# Singleton KB engine
kb_engine   = KBEngine()
kb_handler  = KBSignalHandler(kb_engine)


def fire_kb_event(event: str, context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Fire a KB event directly (without Django signal overhead).
    Preferred for internal task calls.
    """
    return kb_engine.fire(event, context)


def fire_kb_signal(event: str, context: Dict[str, Any]) -> None:
    """
    Fire a KB event via the Django signal (from Django signal receivers).
    """
    kb_signal.send(sender=None, event=event, context=context)


def init_kb_engine() -> None:
    """
    Initialize the KB engine with platform rules.
    Called from apps.py or signals.py during startup.
    """
    kb_engine.clear()
    register_platform_rules(kb_engine)
    logger.info(f"[KB] Engine initialized with {len(kb_engine._rules)} rules")


__all__ = [
    'KBRule', 'KBEngine', 'KBSignalHandler', 'kb_signal',
    'kb_engine', 'kb_handler',
    'fire_kb_event', 'fire_kb_signal',
    'register_platform_rules', 'init_kb_engine',
]
