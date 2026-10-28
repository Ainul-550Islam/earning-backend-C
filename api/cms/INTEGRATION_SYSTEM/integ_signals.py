# cms/INTEGRATION_SYSTEM/integ_signals.py
"""
CMS Integration System — Django signals fired at key business events.
These are the canonical signals that bridge CMS internals to external integrations.
"""
from django.dispatch import Signal

# ── CPAlead / Offer signals ───────────────────────────────────────────────────
cpalead_postback_approved = Signal()
# kwargs: user, payout_usd, lead_id, offer_id, virtual_amount, ip

cpalead_postback_rejected = Signal()
# kwargs: user, lead_id, reason

offer_clicked = Signal()
# kwargs: user, offer_id, ip, subid

content_unlocked = Signal()
# kwargs: user, locker_id, locker_type

# ── Reward signals ────────────────────────────────────────────────────────────
cms_reward_earned = Signal()
# kwargs: user, amount, currency, source_type, lead_id, virtual_amount

cms_reward_approved = Signal()
# kwargs: user, transaction_id, amount

cms_reward_paid = Signal()
# kwargs: user, transaction_id, amount, payment_method

# ── Survey signals ────────────────────────────────────────────────────────────
cms_survey_started = Signal()
# kwargs: user, survey_id, completion_id

cms_survey_completed = Signal()
# kwargs: user, survey_id, completion_id, quality_score, reward_usd

cms_survey_response = Signal()
# kwargs: user, survey_id, completion_id, response_count

# ── Withdrawal signals ────────────────────────────────────────────────────────
cms_withdrawal_requested = Signal()
# kwargs: user, amount_usd, method, request_id

cms_withdrawal_approved = Signal()
# kwargs: user, amount_usd, method, request_id, approved_by

cms_withdrawal_rejected = Signal()
# kwargs: user, amount_usd, method, request_id, reason

# ── User lifecycle signals ───────────────────────────────────────────────────
cms_user_registered = Signal()
# kwargs: user, method

cms_user_level_up = Signal()
# kwargs: user, old_level, new_level

cms_user_segment_changed = Signal()
# kwargs: user, old_segments, new_segments

# ── Content signals ───────────────────────────────────────────────────────────
cms_content_unlocked = Signal()
# kwargs: user, content_id, content_type

cms_page_viewed = Signal()
# kwargs: user, page_id, ip

cms_blog_post_read = Signal()
# kwargs: user, post_id, ip

# ── Gamification signals ──────────────────────────────────────────────────────
cms_quiz_completed = Signal()
# kwargs: user, quiz_id, attempt_id, reward_coins

cms_referral_bonus = Signal()
# kwargs: referrer, referred, bonus_usd, lead_id

cms_streak_milestone = Signal()
# kwargs: user, streak_days, bonus_coins, milestone_title

# ── System signals ────────────────────────────────────────────────────────────
cms_health_alert = Signal()
# kwargs: level, title, message, extra

cms_error_occurred = Signal()
# kwargs: error_type, message, severity, context


def connect_integration_receivers():
    """
    Connect lightweight integration receivers to all CMS signals.
    Called from apps.py → _register_integration_system().
    Each receiver logs to the EventBus — nothing heavy here.
    """
    import logging
    logger = logging.getLogger('cms.integration')

    def _on_postback_approved(sender, user, payout_usd, lead_id,
                               virtual_amount=0, **kwargs):
        try:
            from .event_bus import EventBus
            EventBus.publish('postback_approved', {
                'user_id': getattr(user, 'id', None),
                'payout_usd': float(payout_usd),
                'lead_id': lead_id,
                'virtual_amount': float(virtual_amount),
            })
        except Exception as e:
            logger.debug(f'[IntegSignal] postback_approved EventBus error: {e}')

    def _on_reward_earned(sender, user, amount, currency, source_type,
                          lead_id='', virtual_amount=0, **kwargs):
        try:
            from .event_bus import EventBus
            EventBus.publish('reward_earned', {
                'user_id': getattr(user, 'id', None),
                'amount': float(amount),
                'currency': currency,
                'source_type': source_type,
                'lead_id': lead_id,
                'virtual_amount': float(virtual_amount),
            })
        except Exception as e:
            logger.debug(f'[IntegSignal] reward_earned EventBus error: {e}')

    def _on_survey_completed(sender, user, survey_id, completion_id,
                              quality_score=0, reward_usd=0, **kwargs):
        try:
            from .event_bus import EventBus
            EventBus.publish('survey_completed', {
                'user_id': getattr(user, 'id', None),
                'survey_id': survey_id,
                'completion_id': completion_id,
                'quality_score': float(quality_score),
                'reward_usd': float(reward_usd),
            })
        except Exception as e:
            logger.debug(f'[IntegSignal] survey_completed EventBus error: {e}')

    def _on_withdrawal_requested(sender, user, amount_usd, method,
                                  request_id=0, **kwargs):
        try:
            from .event_bus import EventBus
            EventBus.publish('withdrawal_requested', {
                'user_id': getattr(user, 'id', None),
                'amount_usd': float(amount_usd),
                'method': method,
                'request_id': request_id,
            })
        except Exception as e:
            logger.debug(f'[IntegSignal] withdrawal_requested EventBus error: {e}')

    cpalead_postback_approved.connect(_on_postback_approved,
                                       dispatch_uid='integ_postback_approved')
    cms_reward_earned.connect(_on_reward_earned,
                               dispatch_uid='integ_reward_earned')
    cms_survey_completed.connect(_on_survey_completed,
                                  dispatch_uid='integ_survey_completed')
    cms_withdrawal_requested.connect(_on_withdrawal_requested,
                                      dispatch_uid='integ_withdrawal_requested')

    logger.debug('[IntegSignals] 4 integration receivers connected.')
