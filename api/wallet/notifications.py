# api/wallet/notifications.py
"""
Wallet notification system — push, email, SMS, in-app.
Supports: Firebase FCM (push), Django email (SMTP), Twilio (SMS),
          in-app notifications (WalletNotification model).

Usage:
    from .notifications import WalletNotifier
    WalletNotifier.send(user_id=1, event_type="wallet_credited", data={"amount":"500"})
"""
import logging
from typing import Optional
from django.utils import timezone

logger = logging.getLogger("wallet.notifications")


class WalletNotifier:
    """Central notification dispatcher."""

    @staticmethod
    def send(user_id: int, event_type: str, data: dict,
             channels: list = None) -> dict:
        """
        Send notification to user across configured channels.
        channels: ["push", "email", "sms", "in_app"] or None (use defaults)
        """
        if channels is None:
            channels = WalletNotifier._get_user_channels(user_id, event_type)

        results = {}
        template = NotificationTemplate.get(event_type, data)

        if "in_app" in channels:
            results["in_app"] = WalletNotifier._save_in_app(user_id, event_type, template, data)

        if "push" in channels:
            results["push"] = WalletNotifier._send_push(user_id, template, data)

        if "email" in channels:
            results["email"] = WalletNotifier._send_email(user_id, template, data)

        if "sms" in channels:
            results["sms"] = WalletNotifier._send_sms(user_id, template, data)

        return results

    @staticmethod
    def _get_user_channels(user_id: int, event_type: str) -> list:
        """Get user preferred notification channels."""
        channels = ["in_app"]
        try:
            from .models.notification import NotificationPreference
            prefs = NotificationPreference.objects.filter(user_id=user_id).first()
            if prefs:
                if prefs.push_enabled:   channels.append("push")
                if prefs.email_enabled:  channels.append("email")
                if prefs.sms_enabled:    channels.append("sms")
            else:
                channels.extend(["push", "email"])
        except Exception:
            channels.extend(["push"])
        return channels

    @staticmethod
    def _save_in_app(user_id: int, event_type: str, template: dict, data: dict) -> bool:
        """Save in-app notification to database."""
        try:
            from .models.notification import WalletNotification
            WalletNotification.objects.create(
                user_id=user_id,
                event_type=event_type,
                title=template.get("title", "Wallet Update"),
                message=template.get("body", ""),
                data=data,
                is_read=False,
            )
            return True
        except Exception as e:
            logger.error(f"In-app notification failed user={user_id}: {e}")
            return False

    @staticmethod
    def _send_push(user_id: int, template: dict, data: dict) -> bool:
        """Send Firebase FCM push notification."""
        from django.conf import settings
        FCM_KEY = getattr(settings, "FCM_SERVER_KEY", "")
        if not FCM_KEY:
            return False

        try:
            import requests
            from django.contrib.auth import get_user_model
            User = get_user_model()
            user = User.objects.get(id=user_id)
            fcm_token = getattr(user, "fcm_token", "") or ""
            if not fcm_token:
                return False

            payload = {
                "to": fcm_token,
                "notification": {
                    "title": template.get("title", "Wallet"),
                    "body":  template.get("body", ""),
                    "sound": "default",
                },
                "data": {k: str(v) for k, v in data.items()},
            }
            resp = requests.post(
                "https://fcm.googleapis.com/fcm/send",
                json=payload,
                headers={"Authorization": f"key={FCM_KEY}", "Content-Type": "application/json"},
                timeout=10,
            )
            return resp.status_code == 200
        except Exception as e:
            logger.debug(f"Push notification failed user={user_id}: {e}")
            return False

    @staticmethod
    def _send_email(user_id: int, template: dict, data: dict) -> bool:
        """Send email notification."""
        try:
            from django.core.mail import send_mail
            from django.conf import settings
            from django.contrib.auth import get_user_model
            User = get_user_model()
            user = User.objects.get(id=user_id)
            if not user.email:
                return False

            send_mail(
                subject=template.get("title", "Wallet Notification"),
                message=template.get("body", ""),
                from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@wallet.com"),
                recipient_list=[user.email],
                fail_silently=True,
            )
            return True
        except Exception as e:
            logger.debug(f"Email notification failed user={user_id}: {e}")
            return False

    @staticmethod
    def _send_sms(user_id: int, template: dict, data: dict) -> bool:
        """Send SMS via Twilio (or local SMS gateway)."""
        from django.conf import settings
        TWILIO_SID = getattr(settings, "TWILIO_ACCOUNT_SID", "")
        if not TWILIO_SID:
            return False
        try:
            from twilio.rest import Client
            client = Client(TWILIO_SID, getattr(settings, "TWILIO_AUTH_TOKEN", ""))
            from django.contrib.auth import get_user_model
            user = get_user_model().objects.get(id=user_id)
            phone = getattr(user, "phone_number", "") or ""
            if not phone:
                return False
            client.messages.create(
                body=template.get("sms", template.get("body", ""))[:160],
                from_=getattr(settings, "TWILIO_PHONE", ""),
                to=phone,
            )
            return True
        except Exception as e:
            logger.debug(f"SMS failed user={user_id}: {e}")
            return False


class NotificationTemplate:
    """Notification message templates for all wallet events."""

    TEMPLATES = {
        "wallet_created": {
            "title": "Welcome! Your Wallet is Ready 🎉",
            "body":  "Your wallet has been created. Start earning today!",
            "sms":   "Your wallet is ready. Start earning now!",
        },
        "wallet_credited": {
            "title": "💰 Money Received",
            "body":  "Your wallet has been credited with {amount} BDT. Balance: {balance_after} BDT.",
            "sms":   "Wallet credited: +{amount} BDT",
        },
        "withdrawal_requested": {
            "title": "⏳ Withdrawal Pending",
            "body":  "Withdrawal of {amount} BDT via {gateway} is pending. Net amount: {net_amount} BDT.",
            "sms":   "Withdrawal {amount} BDT pending.",
        },
        "withdrawal_completed": {
            "title": "✅ Withdrawal Completed",
            "body":  "Your withdrawal of {amount} BDT has been sent. Ref: {gateway_ref}",
            "sms":   "Withdrawal {amount} BDT sent! Ref: {gateway_ref}",
        },
        "withdrawal_failed": {
            "title": "❌ Withdrawal Failed",
            "body":  "Withdrawal of {amount} BDT failed. Reason: {error}. Funds returned.",
            "sms":   "Withdrawal failed. Funds returned to wallet.",
        },
        "kyc_approved": {
            "title": "✅ KYC Verified — Level {level}",
            "body":  "KYC Level {level} approved! Daily withdrawal limit: {new_daily_limit} BDT.",
            "sms":   "KYC Level {level} approved!",
        },
        "kyc_rejected": {
            "title": "❌ KYC Rejected",
            "body":  "KYC verification rejected. Please resubmit correct documents.",
            "sms":   "KYC rejected. Please resubmit documents.",
        },
        "streak_milestone": {
            "title": "🔥 {days}-Day Streak Bonus!",
            "body":  "Amazing! You've earned {days} days in a row. Bonus: +{bonus} BDT added!",
            "sms":   "Streak bonus! +{bonus} BDT for {days} days.",
        },
        "publisher_level_upgraded": {
            "title": "🏆 Publisher Level {new_level} Unlocked!",
            "body":  "Congratulations! You're now Level {new_level}. New payout: {new_payout_freq}.",
            "sms":   "Level {new_level} unlocked! Payout: {new_payout_freq}",
        },
        "fraud_detected": {
            "title": "🚨 Account Temporarily Locked",
            "body":  "Suspicious activity detected. Your account is under review. Contact support.",
            "sms":   "Account locked for review. Contact support.",
        },
        "aml_flagged": {
            "title": "⚠️ Account Under Review",
            "body":  "Your account requires compliance review. Withdrawals are temporarily paused.",
            "sms":   "Compliance review needed. Contact support.",
        },
        "bonus_expiring": {
            "title": "⏰ Bonus Expiring Soon!",
            "body":  "{amount} BDT bonus expires soon. Withdraw to avoid losing it!",
            "sms":   "Bonus {amount} BDT expiring soon!",
        },
        "dispute_resolved": {
            "title": "⚖️ Dispute Resolved",
            "body":  "Your dispute has been resolved. Refund: {refunded_amount} BDT.",
            "sms":   "Dispute resolved. Refund: {refunded_amount} BDT",
        },
        "transfer_completed": {
            "title": "💸 Transfer Completed",
            "body":  "{amount} BDT transferred successfully.",
            "sms":   "Transfer {amount} BDT done.",
        },
    }

    @classmethod
    def get(cls, event_type: str, data: dict) -> dict:
        """Get formatted template for event type."""
        tmpl = cls.TEMPLATES.get(event_type, {
            "title": "Wallet Update",
            "body":  "Your wallet has been updated.",
            "sms":   "Wallet update.",
        })
        result = {}
        for key, value in tmpl.items():
            try:
                result[key] = value.format(**{k: str(v) for k, v in data.items()})
            except (KeyError, ValueError):
                result[key] = value
        return result
