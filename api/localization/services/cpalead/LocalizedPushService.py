# services/cpalead/LocalizedPushService.py
"""Push notification localization — sends in user's language."""
import logging
from typing import Dict, Optional
logger = logging.getLogger(__name__)


PUSH_TEMPLATES = {
    "offer_completed": {
        "en": {"title": "You earned {amount}! 🎉", "body": "Offer completed! Check your balance."},
        "bn": {"title": "আপনি {amount} আয় করেছেন! 🎉", "body": "অফার সম্পন্ন! আপনার ব্যালেন্স দেখুন।"},
        "hi": {"title": "आपने {amount} कमाया! 🎉", "body": "ऑफर पूर्ण! अपना बैलेंस देखें।"},
        "ar": {"title": "ربحت {amount}! 🎉", "body": "اكتمل العرض! تحقق من رصيدك."},
        "ur": {"title": "آپ نے {amount} کمایا! 🎉", "body": "آفر مکمل! اپنا بیلنس چیک کریں۔"},
        "es": {"title": "¡Ganaste {amount}! 🎉", "body": "¡Oferta completada! Revisa tu saldo."},
        "fr": {"title": "Vous avez gagné {amount}! 🎉", "body": "Offre terminée! Vérifiez votre solde."},
        "id": {"title": "Kamu menghasilkan {amount}! 🎉", "body": "Penawaran selesai! Cek saldo kamu."},
        "ms": {"title": "Anda memperoleh {amount}! 🎉", "body": "Tawaran selesai! Semak baki anda."},
        "tr": {"title": "{amount} kazandınız! 🎉", "body": "Teklif tamamlandı! Bakiyenizi kontrol edin."},
    },
    "withdrawal_approved": {
        "en": {"title": "Withdrawal Approved ✅", "body": "Your {amount} withdrawal is on the way!"},
        "bn": {"title": "উত্তোলন অনুমোদিত ✅", "body": "আপনার {amount} উত্তোলন প্রক্রিয়াধীন!"},
        "hi": {"title": "निकासी अनुमोदित ✅", "body": "आपकी {amount} निकासी प्रक्रिया में है!"},
        "ar": {"title": "تمت الموافقة على السحب ✅", "body": "سحبك بمبلغ {amount} في الطريق!"},
    },
    "new_offer": {
        "en": {"title": "New offer available! 💰", "body": "Earn {amount} — complete it now!"},
        "bn": {"title": "নতুন অফার উপলব্ধ! 💰", "body": "{amount} আয় করুন — এখনই সম্পন্ন করুন!"},
        "hi": {"title": "नया ऑफर उपलब्ध! 💰", "body": "{amount} कमाएं — अभी पूरा करें!"},
        "ar": {"title": "عرض جديد متاح! 💰", "body": "اكسب {amount} — أكمله الآن!"},
    },
}


class LocalizedPushService:
    """Push notification localization service."""

    def send(self, template_name: str, user, context: Dict, language_code: str = None) -> bool:
        """User-এর ভাষায় push notification পাঠায়।"""
        try:
            lang = language_code or self._get_user_language(user)
            template = PUSH_TEMPLATES.get(template_name, {})
            content = template.get(lang) or template.get("en", {})
            if not content:
                return False
            title = content["title"].format(**context)
            body = content["body"].format(**context)
            # FCM/APNS integration point
            logger.info(f"Push: [{lang}] {title} | {body}")
            # FCM/APNS integration: set PUSH_FCM_SERVER_KEY in settings, tokens stored in UserDevice model
            return True
        except Exception as e:
            logger.error(f"LocalizedPushService.send failed: {e}")
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
        return {name: list(langs.keys()) for name, langs in PUSH_TEMPLATES.items()}
