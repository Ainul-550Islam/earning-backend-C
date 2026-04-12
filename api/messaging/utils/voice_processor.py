"""
Voice Message Processor — Waveform generation + Speech-to-Text transcription.
Supports OpenAI Whisper, Google STT, Azure Speech.
"""
from __future__ import annotations
import logging
import math
from typing import Optional

logger = logging.getLogger(__name__)


def generate_waveform(audio_data: bytes, num_samples: int = 64) -> list[float]:
    """
    Generate waveform amplitude data from audio bytes.
    Returns list of `num_samples` normalized values [0.0..1.0].
    Supports WAV, MP3, OGG via pydub (if installed).
    Falls back to random-ish values derived from byte content.
    """
    if not audio_data:
        return [0.0] * num_samples

    try:
        import io
        from pydub import AudioSegment
        audio = AudioSegment.from_file(io.BytesIO(audio_data))
        samples = audio.get_array_of_samples()
        chunk_size = max(1, len(samples) // num_samples)
        waveform = []
        max_val = float(2 ** (audio.sample_width * 8 - 1))
        for i in range(num_samples):
            chunk = samples[i * chunk_size: (i + 1) * chunk_size]
            if chunk:
                rms = math.sqrt(sum(s ** 2 for s in chunk) / len(chunk))
                normalized = min(1.0, rms / max_val)
            else:
                normalized = 0.0
            waveform.append(round(normalized, 3))
        return waveform
    except ImportError:
        logger.debug("generate_waveform: pydub not installed, using fallback.")
        return _fallback_waveform(audio_data, num_samples)
    except Exception as exc:
        logger.warning("generate_waveform: failed: %s", exc)
        return _fallback_waveform(audio_data, num_samples)


def _fallback_waveform(audio_data: bytes, num_samples: int) -> list[float]:
    """Deterministic pseudo-waveform from byte values."""
    chunk_size = max(1, len(audio_data) // num_samples)
    waveform = []
    for i in range(num_samples):
        chunk = audio_data[i * chunk_size: (i + 1) * chunk_size]
        if chunk:
            avg = sum(chunk) / len(chunk) / 255.0
            waveform.append(round(avg, 3))
        else:
            waveform.append(0.0)
    return waveform


def get_audio_duration(audio_data: bytes) -> float:
    """Return audio duration in seconds. Requires pydub."""
    try:
        import io
        from pydub import AudioSegment
        audio = AudioSegment.from_file(io.BytesIO(audio_data))
        return round(len(audio) / 1000.0, 2)
    except Exception:
        return 0.0


def transcribe_audio(
    audio_data: bytes,
    language: str = "",
    provider: str = "whisper",
) -> dict:
    """
    Transcribe audio to text.
    Returns: {text, language, confidence, provider, error}
    """
    if provider == "whisper":
        return _transcribe_whisper(audio_data, language)
    elif provider == "google":
        return _transcribe_google(audio_data, language)
    elif provider == "azure":
        return _transcribe_azure(audio_data, language)
    else:
        return {"text": "", "language": language, "confidence": 0.0, "provider": provider, "error": "unknown provider"}


def _transcribe_whisper(audio_data: bytes, language: str = "") -> dict:
    """Transcribe using OpenAI Whisper API."""
    from django.conf import settings
    import requests
    import io

    api_key = getattr(settings, "OPENAI_API_KEY", None)
    if not api_key:
        return {"text": "", "language": language, "confidence": 0.0, "provider": "whisper", "error": "OPENAI_API_KEY not set"}

    try:
        files = {"file": ("voice.ogg", io.BytesIO(audio_data), "audio/ogg")}
        data = {"model": "whisper-1", "response_format": "verbose_json"}
        if language:
            data["language"] = language

        resp = requests.post(
            "https://api.openai.com/v1/audio/transcriptions",
            headers={"Authorization": f"Bearer {api_key}"},
            files=files,
            data=data,
            timeout=60,
        )
        resp.raise_for_status()
        result = resp.json()
        return {
            "text": result.get("text", ""),
            "language": result.get("language", language),
            "confidence": 0.95,
            "provider": "whisper",
            "error": "",
        }
    except Exception as exc:
        logger.error("_transcribe_whisper: %s", exc)
        return {"text": "", "language": language, "confidence": 0.0, "provider": "whisper", "error": str(exc)[:200]}


def _transcribe_google(audio_data: bytes, language: str = "en-US") -> dict:
    """Transcribe using Google Cloud Speech-to-Text."""
    from django.conf import settings
    import requests
    import base64

    api_key = getattr(settings, "GOOGLE_STT_API_KEY", None)
    if not api_key:
        return {"text": "", "language": language, "confidence": 0.0, "provider": "google", "error": "GOOGLE_STT_API_KEY not set"}

    try:
        audio_b64 = base64.b64encode(audio_data).decode()
        payload = {
            "config": {
                "encoding": "OGG_OPUS",
                "sampleRateHertz": 16000,
                "languageCode": language or "en-US",
                "enableAutomaticPunctuation": True,
                "model": "latest_long",
            },
            "audio": {"content": audio_b64},
        }
        resp = requests.post(
            f"https://speech.googleapis.com/v1/speech:recognize?key={api_key}",
            json=payload,
            timeout=30,
        )
        resp.raise_for_status()
        results = resp.json().get("results", [])
        if not results:
            return {"text": "", "language": language, "confidence": 0.0, "provider": "google", "error": "no_results"}

        text = " ".join(r["alternatives"][0]["transcript"] for r in results if r.get("alternatives"))
        confidence = results[0]["alternatives"][0].get("confidence", 0.0) if results else 0.0

        return {
            "text": text.strip(),
            "language": language,
            "confidence": round(confidence, 3),
            "provider": "google",
            "error": "",
        }
    except Exception as exc:
        logger.error("_transcribe_google: %s", exc)
        return {"text": "", "language": language, "confidence": 0.0, "provider": "google", "error": str(exc)[:200]}


def _transcribe_azure(audio_data: bytes, language: str = "en-US") -> dict:
    """Transcribe using Azure Cognitive Services Speech."""
    from django.conf import settings
    import requests

    key = getattr(settings, "AZURE_SPEECH_KEY", None)
    region = getattr(settings, "AZURE_SPEECH_REGION", "eastus")
    if not key:
        return {"text": "", "language": language, "confidence": 0.0, "provider": "azure", "error": "AZURE_SPEECH_KEY not set"}

    try:
        resp = requests.post(
            f"https://{region}.stt.speech.microsoft.com/speech/recognition/conversation/cognitiveservices/v1",
            params={"language": language or "en-US"},
            headers={
                "Ocp-Apim-Subscription-Key": key,
                "Content-Type": "audio/ogg; codecs=opus",
            },
            data=audio_data,
            timeout=30,
        )
        resp.raise_for_status()
        result = resp.json()
        return {
            "text": result.get("DisplayText", ""),
            "language": language,
            "confidence": 0.9,
            "provider": "azure",
            "error": "" if result.get("RecognitionStatus") == "Success" else result.get("RecognitionStatus", ""),
        }
    except Exception as exc:
        logger.error("_transcribe_azure: %s", exc)
        return {"text": "", "language": language, "confidence": 0.0, "provider": "azure", "error": str(exc)[:200]}
