# api/support/integrations/project_specific/ai_sentiment_realtime.py
"""
Real-time Sentiment Analysis — detects user frustration during chat/ticket.

Uses your ai_engine.NLP_ENGINES.sentiment_analyzer.
Triggers automatic actions on high frustration:
  - Escalate ticket
  - Alert supervisor
  - Offer chat handoff
  - Prioritize in queue
"""
import logging
from django.utils import timezone
logger = logging.getLogger(__name__)


FRUSTRATION_KEYWORDS = [
    "ridiculous", "scam", "fraud", "terrible", "worst", "useless",
    "unacceptable", "disgrace", "lawsuit", "report", "cheating",
    "impossible", "never", "angry", "furious", "stealing",
    # Bangla frustration words
    "বাজে", "ধোকা", "প্রতারণা", "অসম্ভব",
]


class RealTimeSentimentAnalyzer:
    """Real-time sentiment monitoring for support interactions."""

    def analyze(self, text: str, use_ai_engine: bool = True) -> dict:
        """
        Analyze sentiment of a message/ticket description.
        Uses ai_engine if available, falls back to keyword-based.
        """
        if use_ai_engine:
            try:
                from api.ai_engine.NLP_ENGINES.sentiment_analyzer import SentimentAnalyzer
                analyzer = SentimentAnalyzer()
                result = analyzer.analyze(text)
                return self._normalize(result)
            except Exception:
                pass

        # Fallback: keyword-based
        return self._keyword_sentiment(text)

    def _normalize(self, ai_result: dict) -> dict:
        """Normalize ai_engine result to our format."""
        score = ai_result.get("score", 0.0)
        return {
            "sentiment":      ai_result.get("sentiment", "neutral"),
            "score":          score,
            "frustration":    "high" if score < -0.6 else "medium" if score < -0.3 else "low",
            "should_escalate":score < -0.7,
            "confidence":     ai_result.get("confidence", 0.8),
        }

    def _keyword_sentiment(self, text: str) -> dict:
        """Simple keyword-based frustration detection."""
        text_lower = text.lower()
        hits = sum(1 for kw in FRUSTRATION_KEYWORDS if kw in text_lower)
        score = -min(1.0, hits * 0.25)  # Each keyword = -0.25
        return {
            "sentiment":      "negative" if score < -0.3 else "neutral",
            "score":          score,
            "frustration":    "high" if score < -0.6 else "medium" if score < -0.3 else "low",
            "should_escalate":hits >= 3,
            "confidence":     0.6,
        }

    def monitor_ticket_conversation(self, ticket) -> dict:
        """
        Analyze all messages in a ticket for escalating frustration.
        Returns recommendation.
        """
        try:
            messages = ticket.messages.filter(is_agent=False).order_by("-created_at")[:5]
            if not messages.exists():
                return {"action": "none", "frustration": "low"}

            # Analyze recent messages
            scores = []
            for msg in messages:
                result = self.analyze(msg.content)
                scores.append(result["score"])

            avg_score = sum(scores) / len(scores) if scores else 0
            trend     = (scores[0] - scores[-1]) if len(scores) > 1 else 0

            result = {
                "avg_score":    round(avg_score, 2),
                "trend":        "worsening" if trend < -0.2 else "improving" if trend > 0.2 else "stable",
                "frustration":  "high" if avg_score < -0.5 else "medium" if avg_score < -0.2 else "low",
                "action":       "none",
            }

            if avg_score < -0.7:
                result["action"] = "escalate_immediately"
            elif avg_score < -0.5:
                result["action"] = "supervisor_alert"
            elif avg_score < -0.3:
                result["action"] = "offer_chat"

            return result
        except Exception as e:
            logger.debug(f"monitor_ticket_conversation: {e}")
            return {"action": "none", "frustration": "low"}

    def on_message_received(self, ticket, message_content: str) -> dict:
        """
        Called on every new ticket message — real-time sentiment check.
        Returns action to take immediately.
        """
        result = self.analyze(message_content)

        if result["should_escalate"] and not ticket.escalated:
            # Auto-escalate
            try:
                ticket.escalated    = True
                ticket.escalated_at = timezone.now()
                ticket.priority     = "urgent"
                ticket.save(update_fields=["escalated", "escalated_at", "priority"])
                result["auto_escalated"] = True
                logger.info(f"Ticket {ticket.ticket_id} auto-escalated due to sentiment score {result['score']}")
            except Exception as e:
                logger.debug(f"Auto-escalate failed: {e}")

        return result


sentiment_analyzer = RealTimeSentimentAnalyzer()