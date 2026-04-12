"""AD_CREATIVES/localization_creative.py — Multi-language creative localization."""


LANGUAGE_CTAS = {
    "en": "Learn More",
    "bn": "আরও জানুন",
    "hi": "अधिक जानें",
    "ar": "اعرف أكثر",
    "fr": "En savoir plus",
    "es": "Saber más",
    "pt": "Saiba mais",
    "id": "Pelajari Lebih",
    "tr": "Daha fazla öğren",
    "ur": "مزید جانیں",
}

LANGUAGE_INSTALL_LABELS = {
    "en": "Install Now",
    "bn": "এখনই ইনস্টল করুন",
    "hi": "अभी इंस्टॉल करें",
    "ar": "ثبّت الآن",
    "fr": "Installer maintenant",
}


class CreativeLocalizationEngine:
    """Translates creative copy to user language."""

    @classmethod
    def localize_cta(cls, language: str = "en") -> str:
        return LANGUAGE_CTAS.get(language, LANGUAGE_CTAS["en"])

    @classmethod
    def localize_install_label(cls, language: str = "en") -> str:
        return LANGUAGE_INSTALL_LABELS.get(language, LANGUAGE_INSTALL_LABELS["en"])

    @classmethod
    def get_rtl_languages(cls) -> list:
        return ["ar", "he", "ur", "fa"]

    @classmethod
    def is_rtl(cls, language: str) -> bool:
        return language in cls.get_rtl_languages()

    @classmethod
    def localize_creative(cls, creative_dict: dict, language: str) -> dict:
        localized = dict(creative_dict)
        localized["cta_text"] = cls.localize_cta(language)
        localized["rtl"]      = cls.is_rtl(language)
        return localized
