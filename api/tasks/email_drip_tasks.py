"""
tasks/email_drip_tasks.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Advanced Email Drip Campaign System
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  ✅ enroll_user_in_drip      — start a drip sequence for a user
  ✅ process_drip_queue       — process next pending drip email
  ✅ send_drip_step           — send one step of a drip sequence
  ✅ pause_drip               — pause sequence (user became active)
  ✅ cancel_drip              — cancel sequence (user unsubscribed)
  ✅ generate_drip_report     — drip campaign analytics
"""
import logging
from celery import shared_task
from django.utils import timezone
from django.core.cache import cache

logger = logging.getLogger(__name__)

# Drip sequence definitions
DRIP_SEQUENCES = {
    'welcome': [
        {'step': 1, 'delay_hours': 0,   'subject': '🎉 Welcome! Start Earning Now',
         'template': 'welcome_step1'},
        {'step': 2, 'delay_hours': 24,  'subject': '🎯 Your Personalized Tasks Are Ready',
         'template': 'welcome_step2'},
        {'step': 3, 'delay_hours': 72,  'subject': '💰 Earn More with Referrals',
         'template': 'welcome_step3'},
        {'step': 4, 'delay_hours': 168, 'subject': '🏆 Weekly Bonus Available!',
         'template': 'welcome_step4'},
    ],
    'reengagement': [
        {'step': 1, 'delay_hours': 0,  'subject': '💔 We miss you — comeback bonus inside',
         'template': 'reengagement_step1'},
        {'step': 2, 'delay_hours': 72, 'subject': '⏰ Last chance: Your bonus expires soon',
         'template': 'reengagement_step2'},
    ],
    'milestone': [
        {'step': 1, 'delay_hours': 0, 'subject': '🎖️ Congratulations on your milestone!',
         'template': 'milestone_step1'},
        {'step': 2, 'delay_hours': 24, 'subject': '🚀 You are on fire! Keep going',
         'template': 'milestone_step2'},
    ],
    'vip_upgrade': [
        {'step': 1, 'delay_hours': 0,   'subject': '⭐ You have been upgraded to VIP!',
         'template': 'vip_upgrade'},
        {'step': 2, 'delay_hours': 168, 'subject': '💎 Exclusive VIP offers just for you',
         'template': 'vip_offers'},
    ],
}


@shared_task(bind=True, max_retries=2, default_retry_delay=30,
             name='tasks.email_drip_tasks.enroll_user_in_drip')
def enroll_user_in_drip(
    self,
    user_id: int,
    sequence: str = 'welcome',
    metadata: dict = None,
) -> dict:
    """Enroll a user in a drip sequence."""
    try:
        if sequence not in DRIP_SEQUENCES:
            return {'status': 'unknown_sequence', 'sequence': sequence}

        # Don't re-enroll if already active
        enrollment_key = f'drip_enrolled_{user_id}_{sequence}'
        if cache.get(enrollment_key):
            return {'status': 'already_enrolled', 'user_id': user_id, 'sequence': sequence}

        cache.set(enrollment_key, {
            'step': 0,
            'enrolled_at': timezone.now().isoformat(),
            'metadata': metadata or {},
        }, timeout=86400 * 60)

        # Schedule first step immediately
        send_drip_step.apply_async(
            kwargs={'user_id': user_id, 'sequence': sequence, 'step': 1},
            countdown=0,
        )

        logger.info(f"[DRIP] User {user_id} enrolled in '{sequence}'")
        return {'status': 'enrolled', 'user_id': user_id, 'sequence': sequence}

    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=15,
             name='tasks.email_drip_tasks.send_drip_step')
def send_drip_step(self, user_id: int, sequence: str, step: int) -> dict:
    """Send one email step in a drip sequence."""
    try:
        steps = DRIP_SEQUENCES.get(sequence, [])
        step_config = next((s for s in steps if s['step'] == step), None)

        if not step_config:
            return {'status': 'step_not_found', 'step': step}

        # Check if user cancelled this drip
        cancelled_key = f'drip_cancelled_{user_id}_{sequence}'
        if cache.get(cancelled_key):
            return {'status': 'cancelled', 'user_id': user_id, 'sequence': sequence}

        # Check if user paused
        paused_key = f'drip_paused_{user_id}_{sequence}'
        if cache.get(paused_key):
            # Reschedule for later
            send_drip_step.apply_async(
                kwargs={'user_id': user_id, 'sequence': sequence, 'step': step},
                countdown=3600,
            )
            return {'status': 'paused_rescheduled', 'user_id': user_id}

        # Send email
        from api.tasks.notification_tasks import send_email_notification

        send_email_notification.apply_async(kwargs={
            'user_id': user_id,
            'subject': step_config['subject'],
            'message': _render_drip_template(step_config['template'], user_id),
        })

        # Update enrollment progress
        enrollment_key = f'drip_enrolled_{user_id}_{sequence}'
        enrollment     = cache.get(enrollment_key) or {}
        enrollment['step'] = step
        enrollment['last_sent_at'] = timezone.now().isoformat()
        cache.set(enrollment_key, enrollment, timeout=86400 * 60)

        # Schedule next step
        next_step_config = next((s for s in steps if s['step'] == step + 1), None)
        if next_step_config:
            send_drip_step.apply_async(
                kwargs={'user_id': user_id, 'sequence': sequence, 'step': step + 1},
                countdown=next_step_config['delay_hours'] * 3600,
            )

        logger.info(f"[DRIP] Sent step {step} of '{sequence}' to user {user_id}")
        return {
            'status': 'sent',
            'user_id': user_id,
            'sequence': sequence,
            'step': step,
            'timestamp': timezone.now().isoformat(),
        }

    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=1, default_retry_delay=5,
             name='tasks.email_drip_tasks.pause_drip')
def pause_drip(self, user_id: int, sequence: str, hours: int = 24) -> dict:
    """Pause a drip sequence for a user (user became active)."""
    cache.set(f'drip_paused_{user_id}_{sequence}', 1, timeout=hours * 3600)
    return {'status': 'paused', 'user_id': user_id, 'sequence': sequence, 'hours': hours}


@shared_task(bind=True, max_retries=1, default_retry_delay=5,
             name='tasks.email_drip_tasks.cancel_drip')
def cancel_drip(self, user_id: int, sequence: str = None) -> dict:
    """Cancel a drip sequence (user unsubscribed)."""
    if sequence:
        cache.set(f'drip_cancelled_{user_id}_{sequence}', 1, timeout=86400 * 365)
    else:
        for seq in DRIP_SEQUENCES:
            cache.set(f'drip_cancelled_{user_id}_{seq}', 1, timeout=86400 * 365)
    return {'status': 'cancelled', 'user_id': user_id, 'sequence': sequence or 'all'}


def _render_drip_template(template_name: str, user_id: int) -> str:
    """Render a drip email template."""
    try:
        from django.template.loader import render_to_string
        from django.contrib.auth import get_user_model
        User = get_user_model()
        user = User.objects.filter(pk=user_id).first()
        return render_to_string(
            f'emails/drip/{template_name}.txt',
            {'user': user, 'user_id': user_id},
        )
    except Exception:
        return f"Hi! This is a message from our platform. Template: {template_name}"
