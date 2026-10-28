"""
test_utils_voice_processor_coverage_boost.py
==============================================
Real-execution coverage for messaging/utils/voice_processor.py.

ffmpeg is available in this sandbox, so pydub's real WAV decoding path is
exercised directly with real (synthetically generated via the stdlib
`wave` module) audio bytes - no mocking needed for the "happy path" audio
processing. Only the external HTTP calls to OpenAI/Google/Azure and the
pydub-not-installed fallback are mocked, since those genuinely aren't
available/desirable to hit for real in a test.
"""
from __future__ import annotations

import builtins
import io
import wave
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest
from django.test import override_settings

from api.messaging.utils import voice_processor as vp

pytestmark = pytest.mark.django_db(transaction=False)


def _make_wav_bytes(num_frames=800, sample_width=2, channels=1, framerate=8000, pattern=b"\x10\x00"):
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(sample_width)
        w.setframerate(framerate)
        w.writeframes(pattern * num_frames)
    return buf.getvalue()


@contextmanager
def _no_pydub():
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "pydub" or name.startswith("pydub."):
            raise ImportError(f"No module named {name!r}")
        return real_import(name, *args, **kwargs)

    with patch("builtins.__import__", side_effect=fake_import):
        yield


# ---------------------------------------------------------------------------
# generate_waveform
# ---------------------------------------------------------------------------

class TestGenerateWaveform:
    def test_empty_audio_returns_zeros(self):
        result = vp.generate_waveform(b"", num_samples=16)
        assert result == [0.0] * 16

    def test_real_wav_produces_normalized_waveform(self):
        wav_bytes = _make_wav_bytes(num_frames=2000, pattern=b"\xff\x7f")  # near-max amplitude
        result = vp.generate_waveform(wav_bytes, num_samples=32)
        assert len(result) == 32
        assert all(0.0 <= v <= 1.0 for v in result)
        assert any(v > 0 for v in result)  # not all silence

    def test_more_samples_requested_than_available_hits_empty_chunk_branch(self):
        # A very short clip with a large num_samples means the tail
        # iterations slice past the end of the sample array -> empty
        # chunk -> normalized = 0.0 branch.
        wav_bytes = _make_wav_bytes(num_frames=5)
        result = vp.generate_waveform(wav_bytes, num_samples=200)
        assert len(result) == 200
        assert 0.0 in result

    def test_import_error_falls_back(self):
        with _no_pydub():
            result = vp.generate_waveform(b"some raw bytes here", num_samples=8)
        assert len(result) == 8

    def test_invalid_audio_bytes_falls_back(self):
        # Not valid audio in any format pydub/ffmpeg understands.
        result = vp.generate_waveform(b"definitely not audio data \x00\x01", num_samples=8)
        assert len(result) == 8


class TestFallbackWaveform:
    def test_deterministic_and_normalized(self):
        data = bytes(range(256)) * 4
        w1 = vp._fallback_waveform(data, 16)
        w2 = vp._fallback_waveform(data, 16)
        assert w1 == w2
        assert len(w1) == 16
        assert all(0.0 <= v <= 1.0 for v in w1)

    def test_empty_chunk_tail_when_more_samples_than_bytes(self):
        result = vp._fallback_waveform(b"\x01\x02\x03", 10)
        assert len(result) == 10
        assert 0.0 in result


# ---------------------------------------------------------------------------
# get_audio_duration
# ---------------------------------------------------------------------------

class TestGetAudioDuration:
    def test_real_wav_returns_duration_seconds(self):
        wav_bytes = _make_wav_bytes(num_frames=8000, framerate=8000)  # ~1 second
        duration = vp.get_audio_duration(wav_bytes)
        assert duration == pytest.approx(1.0, abs=0.05)

    def test_invalid_audio_returns_zero(self):
        assert vp.get_audio_duration(b"not audio") == 0.0

    def test_empty_bytes_returns_zero(self):
        assert vp.get_audio_duration(b"") == 0.0


# ---------------------------------------------------------------------------
# transcribe_audio dispatcher
# ---------------------------------------------------------------------------

class TestTranscribeAudioDispatch:
    def test_dispatches_to_whisper_by_default(self):
        with patch("messaging.utils.voice_processor._transcribe_whisper") as m:
            m.return_value = {"provider": "whisper"}
            result = vp.transcribe_audio(b"x")
        m.assert_called_once()
        assert result["provider"] == "whisper"

    def test_dispatches_to_google(self):
        with patch("messaging.utils.voice_processor._transcribe_google") as m:
            m.return_value = {"provider": "google"}
            result = vp.transcribe_audio(b"x", provider="google")
        m.assert_called_once()
        assert result["provider"] == "google"

    def test_dispatches_to_azure(self):
        with patch("messaging.utils.voice_processor._transcribe_azure") as m:
            m.return_value = {"provider": "azure"}
            result = vp.transcribe_audio(b"x", provider="azure")
        m.assert_called_once()
        assert result["provider"] == "azure"

    def test_unknown_provider_returns_error_dict(self):
        result = vp.transcribe_audio(b"x", provider="carrier-pigeon")
        assert result["error"] == "unknown provider"
        assert result["provider"] == "carrier-pigeon"


# ---------------------------------------------------------------------------
# _transcribe_whisper
# ---------------------------------------------------------------------------

class TestTranscribeWhisper:
    def test_no_api_key_returns_error(self):
        with override_settings():
            from django.conf import settings
            if hasattr(settings, "OPENAI_API_KEY"):
                delattr(settings, "OPENAI_API_KEY")
            result = vp._transcribe_whisper(b"audio")
        assert result["error"] == "OPENAI_API_KEY not set"
        assert result["provider"] == "whisper"

    @override_settings(OPENAI_API_KEY="sk-test-key")
    def test_successful_transcription(self):
        fake_response = MagicMock()
        fake_response.raise_for_status.return_value = None
        fake_response.json.return_value = {"text": "hello there", "language": "en"}

        with patch("messaging.utils.voice_processor.requests.post", return_value=fake_response) as mock_post:
            result = vp._transcribe_whisper(b"audio-bytes", language="en")

        assert result == {
            "text": "hello there", "language": "en", "confidence": 0.95,
            "provider": "whisper", "error": "",
        }
        assert mock_post.call_args.kwargs["data"]["language"] == "en"

    @override_settings(OPENAI_API_KEY="sk-test-key")
    def test_no_language_omits_language_field(self):
        fake_response = MagicMock()
        fake_response.raise_for_status.return_value = None
        fake_response.json.return_value = {"text": "hi"}
        with patch("messaging.utils.voice_processor.requests.post", return_value=fake_response) as mock_post:
            vp._transcribe_whisper(b"audio-bytes")
        assert "language" not in mock_post.call_args.kwargs["data"]

    @override_settings(OPENAI_API_KEY="sk-test-key")
    def test_request_failure_returns_error(self):
        with patch(
            "messaging.utils.voice_processor.requests.post",
            side_effect=ConnectionError("network down"),
        ):
            result = vp._transcribe_whisper(b"audio")
        assert result["provider"] == "whisper"
        assert result["confidence"] == 0.0
        assert "network down" in result["error"]


# ---------------------------------------------------------------------------
# _transcribe_google
# ---------------------------------------------------------------------------

class TestTranscribeGoogle:
    def test_no_api_key_returns_error(self):
        with override_settings():
            from django.conf import settings
            if hasattr(settings, "GOOGLE_STT_API_KEY"):
                delattr(settings, "GOOGLE_STT_API_KEY")
            result = vp._transcribe_google(b"audio")
        assert result["error"] == "GOOGLE_STT_API_KEY not set"

    @override_settings(GOOGLE_STT_API_KEY="g-test-key")
    def test_successful_transcription_joins_alternatives(self):
        fake_response = MagicMock()
        fake_response.raise_for_status.return_value = None
        fake_response.json.return_value = {
            "results": [
                {"alternatives": [{"transcript": "hello", "confidence": 0.88}]},
                {"alternatives": [{"transcript": "world", "confidence": 0.5}]},
            ]
        }
        with patch("messaging.utils.voice_processor.requests.post", return_value=fake_response):
            result = vp._transcribe_google(b"audio", language="en-US")

        assert result["text"] == "hello world"
        assert result["confidence"] == 0.88
        assert result["error"] == ""

    @override_settings(GOOGLE_STT_API_KEY="g-test-key")
    def test_no_results_returns_no_results_error(self):
        fake_response = MagicMock()
        fake_response.raise_for_status.return_value = None
        fake_response.json.return_value = {"results": []}
        with patch("messaging.utils.voice_processor.requests.post", return_value=fake_response):
            result = vp._transcribe_google(b"audio")
        assert result["error"] == "no_results"

    @override_settings(GOOGLE_STT_API_KEY="g-test-key")
    def test_request_failure_returns_error(self):
        with patch(
            "messaging.utils.voice_processor.requests.post",
            side_effect=TimeoutError("timed out"),
        ):
            result = vp._transcribe_google(b"audio")
        assert "timed out" in result["error"]


# ---------------------------------------------------------------------------
# _transcribe_azure
# ---------------------------------------------------------------------------

class TestTranscribeAzure:
    def test_no_api_key_returns_error(self):
        with override_settings():
            from django.conf import settings
            if hasattr(settings, "AZURE_SPEECH_KEY"):
                delattr(settings, "AZURE_SPEECH_KEY")
            result = vp._transcribe_azure(b"audio")
        assert result["error"] == "AZURE_SPEECH_KEY not set"

    @override_settings(AZURE_SPEECH_KEY="az-test-key", AZURE_SPEECH_REGION="westus")
    def test_successful_transcription(self):
        fake_response = MagicMock()
        fake_response.raise_for_status.return_value = None
        fake_response.json.return_value = {
            "DisplayText": "hello azure", "RecognitionStatus": "Success",
        }
        with patch("messaging.utils.voice_processor.requests.post", return_value=fake_response) as mock_post:
            result = vp._transcribe_azure(b"audio", language="en-US")

        assert result["text"] == "hello azure"
        assert result["error"] == ""
        assert "westus" in mock_post.call_args[0][0]

    @override_settings(AZURE_SPEECH_KEY="az-test-key")
    def test_non_success_recognition_status_becomes_error(self):
        fake_response = MagicMock()
        fake_response.raise_for_status.return_value = None
        fake_response.json.return_value = {
            "DisplayText": "", "RecognitionStatus": "NoMatch",
        }
        with patch("messaging.utils.voice_processor.requests.post", return_value=fake_response):
            result = vp._transcribe_azure(b"audio")
        assert result["error"] == "NoMatch"

    @override_settings(AZURE_SPEECH_KEY="az-test-key")
    def test_request_failure_returns_error(self):
        with patch(
            "messaging.utils.voice_processor.requests.post",
            side_effect=RuntimeError("boom"),
        ):
            result = vp._transcribe_azure(b"audio")
        assert "boom" in result["error"]

    @override_settings(AZURE_SPEECH_KEY="az-test-key")
    def test_default_region_used_when_not_configured(self):
        fake_response = MagicMock()
        fake_response.raise_for_status.return_value = None
        fake_response.json.return_value = {"DisplayText": "x", "RecognitionStatus": "Success"}
        with patch("messaging.utils.voice_processor.requests.post", return_value=fake_response) as mock_post:
            vp._transcribe_azure(b"audio")
        assert "eastus" in mock_post.call_args[0][0]
