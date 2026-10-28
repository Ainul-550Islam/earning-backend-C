# api/support/integrations/project_specific/voice_ticket_handler.py
"""
Voice Ticket Handler — convert voice messages to support tickets.

Handles:
  - WhatsApp voice messages → tickets
  - Telegram voice messages → tickets
  - In-app voice recordings → tickets
  
Uses ai_engine for speech-to-text if available.
"""
import logging
logger = logging.getLogger(__name__)


class VoiceTicketHandler:
    """Convert voice/audio messages to support tickets."""

    def transcribe_audio(self, audio_file) -> str:
        """Transcribe audio file to text using ai_engine."""
        try:
            # Try your ai_engine translation/transcription if available
            from api.ai_engine.NLP_ENGINES.translation_engine import TranslationEngine
            engine = TranslationEngine()
            if hasattr(engine, "transcribe"):
                return engine.transcribe(audio_file)
        except Exception:
            pass

        # Fallback: try OpenAI Whisper
        try:
            import openai
            from django.conf import settings
            client = openai.OpenAI(api_key=getattr(settings, "OPENAI_API_KEY", ""))
            transcript = client.audio.transcriptions.create(
                model = "whisper-1",
                file  = audio_file,
            )
            return transcript.text
        except Exception as e:
            logger.debug(f"VoiceTicketHandler.transcribe_audio: {e}")
            return ""

    def create_ticket_from_voice(self, user, audio_file, channel: str = "whatsapp") -> object:
        """
        Transcribe voice message and create support ticket.
        """
        transcript = self.transcribe_audio(audio_file)
        if not transcript:
            transcript = "Voice message received — unable to transcribe. Please reply to this ticket in text."

        from api.support.services import ticket_service
        # Try to auto-classify
        try:
            from api.support.integrations.project_specific.ai_engine_adapter import ai_engine_adapter
            fake_ticket_data = type("T", (), {"subject": "", "description": transcript, "category": "other", "user": user})()
            intent = ai_engine_adapter.classify_ticket_intent(fake_ticket_data)
            category = intent.get("intent", "other")
        except Exception:
            category = "other"

        ticket = ticket_service.create(user, {
            "subject":     f"Voice message ({channel})",
            "description": "VOICE MESSAGE TRANSCRIPT:\n\n" + transcript,
            "category":    category,
            "priority":    "medium",
            "channel":     channel,
        })
        return ticket

    def process_whatsapp_voice(self, user, media_id: str) -> object:
        """Process voice message from WhatsApp webhook."""
        try:
            from django.conf import settings
            import requests
            # Download WhatsApp media
            token = getattr(settings, "WHATSAPP_API_TOKEN", "")
            headers = {"Authorization": f"Bearer {token}"}
            response = requests.get(
                f"https://graph.facebook.com/v17.0/{media_id}",
                headers=headers, timeout=10
            )
            if response.ok:
                audio_url = response.json().get("url", "")
                audio_data = requests.get(audio_url, headers=headers, timeout=30)
                import io
                return self.create_ticket_from_voice(user, io.BytesIO(audio_data.content), "whatsapp")
        except Exception as e:
            logger.debug(f"process_whatsapp_voice: {e}")
        return None


voice_handler = VoiceTicketHandler()