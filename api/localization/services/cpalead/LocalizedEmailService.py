# services/cpalead/LocalizedEmailService.py
"""Locale-aware email template service — sends emails in user's language."""
import logging
from typing import Dict, Optional
logger = logging.getLogger(__name__)


class LocalizedEmailService:
    """Send emails in user's preferred language with locale-aware formatting."""

    EMAIL_TEMPLATES = {
        "withdrawal_approved": {
            "en": {
                "subject": "Your withdrawal of {amount} has been approved!",
                "body": "Hi {name},\n\nGreat news! Your withdrawal of {amount} has been approved and will be processed within {days} business days.\n\nThank you for using our platform!",
            },
            "bn": {
                "subject": "আপনার {amount} উত্তোলনের অনুরোধ অনুমোদিত হয়েছে!",
                "body": "প্রিয় {name},\n\nসুখবর! আপনার {amount} উত্তোলনের অনুরোধ অনুমোদিত হয়েছে এবং {days} কার্যদিবসের মধ্যে প্রক্রিয়া করা হবে।\n\nআমাদের প্ল্যাটফর্ম ব্যবহার করার জন্য ধন্যবাদ!",
            },
            "hi": {
                "subject": "आपकी {amount} की निकासी अनुमोदित हो गई!",
                "body": "प्रिय {name},\n\nखुशखबरी! आपकी {amount} की निकासी अनुमोदित हो गई है और {days} कार्य दिवसों में प्रक्रिया की जाएगी।",
            },
            "ar": {
                "subject": "تمت الموافقة على سحبك بمبلغ {amount}!",
                "body": "عزيزي {name},\n\nأخبار رائعة! تمت الموافقة على طلب سحب {amount} وسيتم معالجته خلال {days} أيام عمل.",
            },
        },
        "offer_completed": {
            "en": {
                "subject": "🎉 You earned {amount}!",
                "body": "Hi {name},\n\nCongratulations! You just completed an offer and earned {amount}. Your balance has been updated.",
            },
            "bn": {
                "subject": "🎉 আপনি {amount} আয় করেছেন!",
                "body": "প্রিয় {name},\n\nঅভিনন্দন! আপনি একটি অফার সম্পন্ন করেছেন এবং {amount} আয় করেছেন। আপনার ব্যালেন্স আপডেট হয়েছে।",
            },
        },
        "welcome": {
            "en": {
                "subject": "Welcome to our earning platform!",
                "body": "Hi {name},\n\nWelcome! Start completing offers to earn money. Your referral code is: {referral_code}",
            },
            "bn": {
                "subject": "আমাদের আয়ের প্ল্যাটফর্মে স্বাগতম!",
                "body": "প্রিয় {name},\n\nস্বাগতম! অর্থ উপার্জনের জন্য অফার সম্পন্ন করা শুরু করুন। আপনার রেফারেল কোড: {referral_code}",
            },
        },
    }

    def send(
        self, template_name: str, user, context: Dict,
        language_code: str = None, fallback_lang: str = "en"
    ) -> bool:
        """User-এর ভাষায় email পাঠায়।"""
        try:
            from django.core.mail import send_mail
            from django.conf import settings

            lang = language_code or self._get_user_language(user)
            template = self.EMAIL_TEMPLATES.get(template_name, {})
            content = template.get(lang) or template.get(fallback_lang, {})
            if not content:
                logger.error(f"No email template: {template_name}/{lang}")
                return False

            subject = content["subject"].format(**context)
            body = content["body"].format(**context)

            email = getattr(user, "email", str(user))
            send_mail(
                subject=subject,
                message=body,
                from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@example.com"),
                recipient_list=[email],
                fail_silently=False,
            )
            logger.info(f"Email sent: {template_name} to {email} in {lang}")
            return True
        except Exception as e:
            logger.error(f"LocalizedEmailService.send failed: {e}")
            return False

    def _get_user_language(self, user) -> str:
        try:
            from ..models.core import UserLanguagePreference
            pref = UserLanguagePreference.objects.filter(user=user).select_related("ui_language").first()
            if pref and pref.ui_language:
                return pref.ui_language.code
        except Exception:
            pass
        return "en"

    def get_supported_templates(self) -> Dict:
        return {
            name: list(langs.keys())
            for name, langs in self.EMAIL_TEMPLATES.items()
        }
