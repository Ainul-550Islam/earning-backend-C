"""api/support/ai_advanced/ai_dispute_resolver.py FILE 13"""
import logging, requests, re
from django.conf import settings
logger = logging.getLogger(__name__)
API_KEY = getattr(settings, "ANTHROPIC_API_KEY", "")

class AIDisputeResolver:
    SYSTEM = "CPA network dispute specialist. Output: RECOMMENDATION: approve/reject/investigate/needs_proof | CONFIDENCE: 0.0-1.0 | REASON: brief | ACTION: specific step"
    def analyze(self, ticket) -> dict:
        if not API_KEY: return {"recommendation":"investigate","confidence":0.3,"reason":"AI unavailable"}
        try:
            from api.support.models import SupportTicket
            history = SupportTicket.objects.filter(user=ticket.user).count()
            resp = requests.post("https://api.anthropic.com/v1/messages",
                headers={"x-api-key":API_KEY,"anthropic-version":"2023-06-01","content-type":"application/json"},
                json={"model":"claude-haiku-4-5-20251001","max_tokens":150,"system":self.SYSTEM,
                      "messages":[{"role":"user","content":f"Ticket:\n{ticket.description[:600]}\n\nUser tickets: {history}\n\nAnalyze:"}]}, timeout=15)
            if resp.status_code == 200:
                text = resp.json()["content"][0]["text"]
                result = {"recommendation":"investigate","confidence":0.5,"reason":text[:200]}
                for rec in ["approve","reject","investigate","needs_proof"]:
                    if rec in text.lower(): result["recommendation"] = rec; break
                m = re.search(r"CONFIDENCE[:\s]+([0-9.]+)", text, re.IGNORECASE)
                if m: result["confidence"] = min(float(m.group(1)), 1.0)
                return result
        except Exception as e:
            logger.error(f"AI dispute: {e}")
        return {"recommendation":"investigate","confidence":0.3}

ai_dispute_resolver = AIDisputeResolver()