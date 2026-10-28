"""api/support/ai_advanced/voice_to_ticket.py FILE 12"""
import logging, requests, os, tempfile
from django.conf import settings
logger = logging.getLogger(__name__)

class VoiceToTicket:
    def process(self, audio_data: bytes, user, source: str = "telegram") -> dict:
        transcript = self._transcribe(audio_data)
        if not transcript:
            return {"success": False, "error": "Transcription failed. Please type your issue."}
        from api.support.ai.ai_ticket_classifier import ai_classifier
        cls = ai_classifier.classify_text(transcript[:200], transcript)
        from api.support.models import SupportTicket
        ticket = SupportTicket.objects.create(
            user=user, category=cls.get("category","other"), subject=transcript[:100],
            description=f"[VOICE TRANSCRIPT - {source.upper()}]\n\n{transcript}",
            priority=cls.get("priority","medium"), status="open", channel=source,
            tenant=getattr(user,"tenant",None),
        )
        return {"success": True, "ticket_id": ticket.ticket_id, "transcript": transcript}

    def _transcribe(self, audio_data: bytes) -> str:
        key = getattr(settings, "OPENAI_API_KEY", "")
        if not key:
            return "[Voice transcription requires OPENAI_API_KEY]"
        try:
            with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as f:
                f.write(audio_data); tmp = f.name
            try:
                with open(tmp, "rb") as f:
                    r = requests.post("https://api.openai.com/v1/audio/transcriptions",
                        headers={"Authorization": f"Bearer {key}"},
                        files={"file": ("audio.ogg", f, "audio/ogg")},
                        data={"model": "whisper-1"}, timeout=30)
                return r.json().get("text","") if r.status_code == 200 else ""
            finally:
                os.unlink(tmp)
        except Exception as e:
            logger.error(f"Transcription error: {e}"); return ""

voice_to_ticket = VoiceToTicket()