"""
Messaging Translator — Google Translate + DeepL integration.
Used by services.translate_message().
"""
from __future__ import annotations
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def detect_language(text: str) -> str:
    """Detect the language of a text string. Returns ISO 639-1 code."""
    from django.conf import settings
    import requests

    google_key = getattr(settings, "GOOGLE_TRANSLATE_API_KEY", None)
    if not google_key:
        return "unknown"

    try:
        resp = requests.post(
            "https://translation.googleapis.com/language/translate/v2/detect",
            json={"q": text[:500]},
            params={"key": google_key},
            timeout=3,
        )
        resp.raise_for_status()
        detections = resp.json().get("data", {}).get("detections", [[]])[0]
        if detections:
            return detections[0].get("language", "unknown")
    except Exception as exc:
        logger.warning("detect_language: failed: %s", exc)
    return "unknown"


def translate_text(text: str, target_lang: str, source_lang: Optional[str] = None) -> tuple[str, str]:
    """
    Translate text. Returns (translated_text, detected_source_lang).
    Tries Google Translate → DeepL → stub.
    """
    from . import notifier as _n  # noqa — just to ensure module loaded
    from django.conf import settings
    import requests

    # Google
    google_key = getattr(settings, "GOOGLE_TRANSLATE_API_KEY", None)
    if google_key:
        try:
            body = {"q": text, "target": target_lang, "format": "text"}
            if source_lang and source_lang != "unknown":
                body["source"] = source_lang
            resp = requests.post(
                "https://translation.googleapis.com/language/translate/v2",
                json=body,
                params={"key": google_key},
                timeout=5,
            )
            resp.raise_for_status()
            result = resp.json()["data"]["translations"][0]
            return result["translatedText"], result.get("detectedSourceLanguage", source_lang or "")
        except Exception as exc:
            logger.warning("translate_text (google): %s", exc)

    # DeepL
    deepl_key = getattr(settings, "DEEPL_API_KEY", None)
    if deepl_key:
        try:
            payload = {"text": text, "target_lang": target_lang.upper()}
            if source_lang and source_lang != "unknown":
                payload["source_lang"] = source_lang.upper()
            resp = requests.post(
                "https://api-free.deepl.com/v2/translate",
                headers={"Authorization": f"DeepL-Auth-Key {deepl_key}"},
                data=payload,
                timeout=5,
            )
            resp.raise_for_status()
            result = resp.json()["translations"][0]
            return result["text"], result.get("detected_source_language", "").lower()
        except Exception as exc:
            logger.warning("translate_text (deepl): %s", exc)

    # Stub
    return f"[{target_lang.upper()}] {text}", source_lang or "unknown"
