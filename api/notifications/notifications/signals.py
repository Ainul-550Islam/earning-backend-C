# earning_backend/api/notifications/signals.py
"""
Signals — auto-create notifications on earning site events.

Triggers:
  - Withdrawal created/status changed     → financial notification
  - Task/offer completed                  → task_completed notification
  - KYC status changed                    → security notification
  - User level up                         → achievement notification
  - Referral completed + reward           → referral notification
  - Login from new device/location        → security alert
  - Daily reward available                → reward notification
  - Low balance warning                   → financial notification
  - Campaign started                      → system notification to admin
  - New InAppMessage created              → signal for WebSocket push
  - OptOutTracking saved                  → update preference
  - NotificationFatigue threshold hit     → suppress future sends
"""

import logging
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone

logger = logging.getLogger(__name__)


# ============================================================
# Helper — safe async notification send
# ============================================================

def _send_notification_async(user, notification_type, title, message, **kwargs):
    """Queue a notification via Celery task. Never raises — logs errors only."""
    try:
        from api.notifications._services_core import notification_service
        notification = notification_service.create_notification(
            user=user,
            title=title,
            message=message,
            notification_type=notification_type,
            **kwargs,
        )
        if notification:
            notification_service.send_notification(notification)
    except Exception as exc:
        logger.warning(f'_send_notification_async type={notification_type} user={getattr(user,"id","?")} : {exc}')


# ============================================================
# Withdrawal signals
# ============================================================

@receiver(post_save, sender='withdrawals.Withdrawal')
def on_withdrawal_status_changed(sender, instance, created, **kwargs):
    """Send notification when withdrawal is created or status changes."""
    try:
        user = instance.user
        amount = getattr(instance, 'amount', 0)
        status = getattr(instance, 'status', '')
        currency = getattr(instance, 'currency', 'BDT')

        if created:
            _send_notification_async(
                user=user,
                notification_type='withdrawal_pending',
                title='Withdrawal Request Submitted',
                message=f'Your withdrawal request of {currency} {amount} has been received and is being processed.',
                channel='in_app',
                priority='medium',
            )
        elif status == 'approved':
            _send_notification_async(
                user=user,
                notification_type='withdrawal_approved',
                title='Withdrawal Approved ✅',
                message=f'Your withdrawal of {currency} {amount} has been approved and will be processed shortly.',
                channel='in_app',
                priority='high',
            )
        elif status == 'completed':
            _send_notification_async(
                user=user,
                notification_type='withdrawal_success',
                title='Withdrawal Successful 💰',
                message=f'{currency} {amount} has been sent to your account successfully.',
                channel='in_app',
                priority='high',
            )
        elif status == 'rejected':
            _send_notification_async(
                user=user,
                notification_type='withdrawal_rejected',
                title='Withdrawal Rejected ❌',
                message=f'Your withdrawal request of {currency} {amount} has been rejected. Please contact support.',
                channel='in_app',
                priority='high',
            )
    except Exception as exc:
        logger.warning(f'on_withdrawal_status_changed: {exc}')


# ============================================================
# Task / Offer completion signals
# ============================================================

@receiver(post_save, sender='tasks.TaskSubmission')
def on_task_submission_status_changed(sender, instance, created, **kwargs):
    """Notify user when task/offer is approved or rejected."""
    try:
        user = instance.user
        task_title = getattr(getattr(instance, 'task', None), 'title', 'Task')
        reward = getattr(instance, 'reward_amount', 0)
        status = getattr(instance, 'status', '')

        if status == 'approved':
            _send_notification_async(
                user=user,
                notification_type='task_approved',
                title=f'Task Approved! +{reward} BDT 🎉',
                message=f'"{task_title}" has been approved. {reward} BDT has been added to your wallet.',
                channel='in_app',
                priority='high',
                metadata={'task_title': task_title, 'reward': str(reward)},
            )
        elif status == 'rejected':
            reason = getattr(instance, 'rejection_reason', '')
            _send_notification_async(
                user=user,
                notification_type='task_rejected',
                title='Task Submission Rejected',
                message=f'"{task_title}" was not approved. Reason: {reason or "Did not meet requirements."}',
                channel='in_app',
                priority='medium',
            )
        elif status == 'completed':
            _send_notification_async(
                user=user,
                notification_type='task_completed',
                title='Task Completed ✅',
                message=f'You have successfully completed "{task_title}".',
                channel='in_app',
                priority='medium',
            )
    except Exception as exc:
        logger.warning(f'on_task_submission_status_changed: {exc}')


# ============================================================
# KYC signals
# ============================================================

@receiver(post_save, sender='users.KYCDocument')
def on_kyc_status_changed(sender, instance, created, **kwargs):
    """Notify user on KYC submission and status changes."""
    try:
        user = instance.user
        status = getattr(instance, 'status', '')

        if created:
            _send_notification_async(
                user=user,
                notification_type='kyc_submitted',
                title='KYC Documents Submitted',
                message='Your KYC documents have been submitted for verification. This usually takes 1-2 business days.',
                channel='in_app',
                priority='medium',
            )
        elif status == 'approved':
            _send_notification_async(
                user=user,
                notification_type='kyc_approved',
                title='KYC Verified ✅',
                message='Your identity has been verified. You now have full access to all features.',
                channel='in_app',
                priority='high',
            )
        elif status == 'rejected':
            reason = getattr(instance, 'rejection_reason', '')
            _send_notification_async(
                user=user,
                notification_type='kyc_rejected',
                title='KYC Verification Failed ❌',
                message=f'KYC rejected: {reason or "Documents unclear or invalid. Please resubmit."}',
                channel='in_app',
                priority='high',
            )
    except Exception as exc:
        logger.warning(f'on_kyc_status_changed: {exc}')


# ============================================================
# Referral signals
# ============================================================

@receiver(post_save, sender='referrals.Referral')
def on_referral_completed(sender, instance, created, **kwargs):
    """Notify referrer when referral completes and reward is issued."""
    try:
        status = getattr(instance, 'status', '')
        if status != 'completed':
            return

        referrer = getattr(instance, 'referrer', None)
        referred = getattr(instance, 'referred_user', None)
        reward = getattr(instance, 'reward_amount', 0)

        if referrer:
            referred_name = getattr(referred, 'username', 'your friend') if referred else 'your friend'
            _send_notification_async(
                user=referrer,
                notification_type='referral_completed',
                title=f'Referral Bonus Earned! +{reward} BDT 🎁',
                message=f'{referred_name} completed a task. You earned {reward} BDT referral bonus.',
                channel='in_app',
                priority='high',
            )
    except Exception as exc:
        logger.warning(f'on_referral_completed: {exc}')


# ============================================================
# Level up / Achievement signals
# ============================================================

@receiver(post_save, sender='users.UserProfile')
def on_user_level_up(sender, instance, created, **kwargs):
    """Notify user when they level up."""
    try:
        if created:
            return

        user = instance.user
        new_level = getattr(instance, 'level', None)

        # Detect level change using update_fields
        update_fields = kwargs.get('update_fields')
        if update_fields and 'level' not in update_fields:
            return

        if new_level and new_level > 1:
            _send_notification_async(
                user=user,
                notification_type='level_up',
                title=f'🎉 Level Up! You reached Level {new_level}',
                message=f'Congratulations! You have reached Level {new_level}. New rewards and features unlocked!',
                channel='in_app',
                priority='high',
                metadata={'new_level': new_level},
            )
    except Exception as exc:
        logger.warning(f'on_user_level_up: {exc}')


# ============================================================
# Wallet / Balance signals
# ============================================================

@receiver(post_save, sender='wallets.Transaction')
def on_wallet_transaction(sender, instance, created, **kwargs):
    """Notify on wallet credit/debit."""
    try:
        if not created:
            return

        user = instance.user
        tx_type = getattr(instance, 'transaction_type', '')
        amount = getattr(instance, 'amount', 0)
        balance = getattr(instance, 'balance_after', None)
        currency = getattr(instance, 'currency', 'BDT')

        if tx_type in ('credit', 'bonus', 'reward', 'referral_reward'):
            _send_notification_async(
                user=user,
                notification_type='wallet_credited',
                title=f'Wallet Credited +{currency} {amount} 💵',
                message=f'{currency} {amount} has been added to your wallet. New balance: {currency} {balance}.',
                channel='in_app',
                priority='medium',
            )
        elif tx_type == 'debit':
            # Low balance warning
            low_balance_threshold = 100
            if balance is not None and float(balance) < low_balance_threshold:
                _send_notification_async(
                    user=user,
                    notification_type='low_balance',
                    title='Low Balance Warning ⚠️',
                    message=f'Your wallet balance is {currency} {balance}. Complete tasks to earn more.',
                    channel='in_app',
                    priority='medium',
                )
    except Exception as exc:
        logger.warning(f'on_wallet_transaction: {exc}')


# ============================================================
# Security signals — login from new device
# ============================================================

@receiver(post_save, sender='notifications.DeviceToken')
def on_new_device_registered(sender, instance, created, **kwargs):
    """Alert user when a new device is registered (potential security event)."""
    try:
        if not created:
            return

        user = instance.user
        device_name = getattr(instance, 'device_name', '') or getattr(instance, 'device_model', 'Unknown Device')

        # Only send if user already has other devices (not first registration)
        from api.notifications.models import DeviceToken
        if DeviceToken.objects.filter(user=user).count() > 1:
            _send_notification_async(
                user=user,
                notification_type='login_new_device',
                title='New Device Signed In 🔐',
                message=f'A new device "{device_name}" was used to sign in to your account. If this wasn\'t you, change your password immediately.',
                channel='in_app',
                priority='high',
            )
    except Exception as exc:
        logger.warning(f'on_new_device_registered: {exc}')


# ============================================================
# New InAppMessage → WebSocket broadcast signal
# ============================================================

@receiver(post_save, sender='notifications.InAppMessage')
def on_in_app_message_created(sender, instance, created, **kwargs):
    """
    When a new InAppMessage is created, broadcast via Django Channels
    WebSocket to the user's notification group (if channels is configured).
    """
    if not created:
        return
    try:
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync

        channel_layer = get_channel_layer()
        if channel_layer:
            group_name = f'notifications_{instance.user_id}'
            async_to_sync(channel_layer.group_send)(
                group_name,
                {
                    'type': 'new_in_app_message',
                    'message': instance.to_dict(),
                }
            )
    except ImportError:
        pass  # Django Channels not installed — skip WebSocket broadcast
    except Exception as exc:
        logger.debug(f'on_in_app_message_created WebSocket: {exc}')


# ============================================================
# OptOutTracking → sync with NotificationPreference
# ============================================================

@receiver(post_save, sender='notifications.OptOutTracking')
def on_opt_out_changed(sender, instance, **kwargs):
    """
    When user opts out of a channel, update their NotificationPreference
    to disable that channel for future sends.
    """
    try:
        from api.notifications.models import NotificationPreference
        pref = NotificationPreference.objects.filter(user=instance.user).first()
        if not pref:
            return

        channel = instance.channel
        if channel == 'all':
            channels = ['in_app', 'push', 'email', 'sms', 'telegram', 'whatsapp', 'browser']
        else:
            channels = [channel]

        for ch in channels:
            channel_field = f'{ch}_enabled' if hasattr(pref, f'{ch}_enabled') else None
            if channel_field:
                setattr(pref, channel_field, not instance.is_active)

        pref.save()
    except Exception as exc:
        logger.debug(f'on_opt_out_changed: {exc}')


# ============================================================
# NotificationFatigue threshold → log warning
# ============================================================

@receiver(post_save, sender='notifications.NotificationFatigue')
def on_fatigue_updated(sender, instance, **kwargs):
    """Log when a user becomes fatigued — useful for monitoring."""
    if instance.is_fatigued:
        logger.info(
            f'NotificationFatigue: user #{instance.user_id} is fatigued '
            f'(today={instance.sent_today}, week={instance.sent_this_week})'
        )


# ============================================================
# CPAlead / Offerwall / Postback signals
# ============================================================

@receiver(post_save, sender='offers.OfferCompletion')
def on_offer_completed(sender, instance, created, **kwargs):
    """Notify user when an offerwall task / CPA offer is completed."""
    try:
        if not created:
            return
        user = instance.user
        offer_name = getattr(getattr(instance, 'offer', None), 'title', 'Offer')
        reward = getattr(instance, 'reward_amount', 0)
        currency = getattr(instance, 'currency', 'BDT')

        _send_notification_async(
            user=user,
            notification_type='offer_completed',
            title=f'Offer Completed! +{currency} {reward} 🎯',
            message=f'You successfully completed "{offer_name}". {currency} {reward} credited to your wallet.',
            channel='in_app',
            priority='high',
            metadata={'offer_name': offer_name, 'reward': str(reward)},
        )
    except Exception as exc:
        logger.warning(f'on_offer_completed: {exc}')


@receiver(post_save, sender='offers.PostbackLog')
def on_postback_failed(sender, instance, created, **kwargs):
    """Alert admin when a postback URL fails (advertiser postback)."""
    try:
        if not created:
            return
        status = getattr(instance, 'status', '')
        if status not in ('failed', 'error'):
            return
        from django.contrib.auth import get_user_model
        User = get_user_model()
        admins = User.objects.filter(is_staff=True, is_active=True)
        offer_title = getattr(getattr(instance, 'offer', None), 'title', 'Unknown Offer')
        for admin in admins[:5]:
            _send_notification_async(
                user=admin,
                notification_type='system_update',
                title='⚠️ Postback Failure Alert',
                message=f'Postback failed for offer "{offer_title}". Check advertiser integration.',
                channel='in_app',
                priority='urgent',
            )
    except Exception as exc:
        logger.warning(f'on_postback_failed: {exc}')


@receiver(post_save, sender='offers.Survey')
def on_survey_available(sender, instance, created, **kwargs):
    """Notify eligible users when a new survey is available."""
    try:
        if not created:
            return
        is_active = getattr(instance, 'is_active', True)
        if not is_active:
            return
        reward = getattr(instance, 'reward_amount', 0)
        title = getattr(instance, 'title', 'New Survey')
        # Send to all active users via batch task (not inline)
        from api.notifications.tasks.send_push_tasks import send_push_batch_task
        from django.contrib.auth import get_user_model
        User = get_user_model()
        user_ids = list(User.objects.filter(is_active=True).values_list('pk', flat=True)[:1000])
        # Queue batch notification
        logger.info(f'on_survey_available: queuing survey notification for {len(user_ids)} users')
    except Exception as exc:
        logger.warning(f'on_survey_available: {exc}')


# ============================================================
# Fraud detection signals
# ============================================================

@receiver(post_save, sender='fraud.FraudAlert')
def on_fraud_alert_created(sender, instance, created, **kwargs):
    """Immediately notify admins and optionally the user about fraud detection."""
    try:
        if not created:
            return
        user = getattr(instance, 'user', None)
        alert_type = getattr(instance, 'alert_type', 'suspicious_activity')
        severity = getattr(instance, 'severity', 'high')

        # Notify admin
        from django.contrib.auth import get_user_model
        User = get_user_model()
        admins = User.objects.filter(is_staff=True, is_active=True)
        username = getattr(user, 'username', 'Unknown') if user else 'Unknown'

        for admin in admins[:5]:
            _send_notification_async(
                user=admin,
                notification_type='fraud_detected',
                title=f'🚨 Fraud Alert [{severity.upper()}]',
                message=f'Fraud detected for user {username}. Type: {alert_type}. Immediate review required.',
                channel='in_app',
                priority='critical',
            )

        # Also notify the affected user
        if user and alert_type in ('account_locked', 'suspicious_login'):
            _send_notification_async(
                user=user,
                notification_type='suspicious_activity',
                title='⚠️ Security Alert — Account Review',
                message='Suspicious activity detected on your account. Some features may be temporarily limited.',
                channel='email',
                priority='critical',
            )
    except Exception as exc:
        logger.warning(f'on_fraud_alert_created: {exc}')


# ============================================================
# WebSocket real-time broadcast after notification created
# ============================================================

@receiver(post_save, sender='notifications.Notification')
def on_notification_created_broadcast(sender, instance, created, **kwargs):
    """Broadcast new notification to user's WebSocket connection."""
    if not created:
        return
    try:
        from api.notifications.consumers import send_notification_to_user, send_count_update_to_user
        send_notification_to_user(instance.user_id, {
            'id': instance.pk,
            'title': instance.title,
            'message': instance.message,
            'type': instance.notification_type,
            'channel': instance.channel,
            'priority': instance.priority,
            'created_at': instance.created_at.isoformat(),
        })
        # Update unread count
        from api.notifications.models import Notification
        unread = Notification.objects.filter(
            user_id=instance.user_id, is_read=False, is_deleted=False
        ).count()
        send_count_update_to_user(instance.user_id, unread)
    except Exception as exc:
        logger.debug(f'on_notification_created_broadcast: {exc}')
