"""api/support/ai_advanced/screenshot_analyzer.py FILE 11 — AI Screenshot Analyzer"""
import logging, base64, requests, re
from django.conf import settings
logger = logging.getLogger(__name__)
API_KEY = getattr(settings, 'ANTHROPIC_API_KEY', '')

class ScreenshotAnalyzer:
    SYSTEM = "CPA support specialist. Analyze screenshot. Output: ERROR:<msg> | CODE:<code> | ACTION:<what user did> | SOLUTION:<fix>"
    
    def analyze_image(self, image_data: bytes, media_type: str = 'image/png', context: str = '') -> dict:
        if not API_KEY:
            return {'success': False, 'error': 'ANTHROPIC_API_KEY not set'}
        try:
            b64  = base64.standard_b64encode(image_data).decode('utf-8')
            resp = requests.post('https://api.anthropic.com/v1/messages',
                headers={'x-api-key': API_KEY, 'anthropic-version': '2023-06-01', 'content-type': 'application/json'},
                json={'model': 'claude-sonnet-4-20250514', 'max_tokens': 400, 'system': self.SYSTEM,
                      'messages': [{'role': 'user', 'content': [
                          {'type': 'image', 'source': {'type': 'base64', 'media_type': media_type, 'data': b64}},
                          {'type': 'text', 'text': f'Analyze. Context: {context}'},
                      ]}]}, timeout=30)
            if resp.status_code == 200:
                text = resp.json()["content"][0]["text"]
                result = {"success": True, "raw": text}
                for key, pat in [("extracted_error","ERROR:(.+?)(?:\\||\\n|$)"),("error_code","CODE:(.+?)(?:\\||\\n|$)"),("action","ACTION:(.+?)(?:\\||\\n|$)"),("solution","SOLUTION:(.+?)(?:\\||\\n|$)")]:
                    m = re.search(pat, text, re.IGNORECASE)
                    result[key] = m.group(1).strip()[:200] if m else ""
                return result
            return {"success": False, "error": f"API {resp.status_code}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def analyze_from_url(self, url: str, context: str = "") -> dict:
        try:
            r = requests.get(url, timeout=15)
            ct = r.headers.get("content-type","image/png").split(";")[0]
            return self.analyze_image(r.content, ct, context)
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def analyze_ticket_attachments(self, ticket) -> list:
        from api.support.models import TicketAttachment
        results = []
        for att in TicketAttachment.objects.filter(ticket=ticket, file_type__startswith="image/")[:3]:
            try:
                with open(att.file.path, "rb") as f:
                    result = self.analyze_image(f.read(), att.file_type, ticket.subject)
                result["attachment_id"] = att.id
                results.append(result)
                if result.get("solution"):
                    from api.support.models import TicketMessage
                    from django.contrib.auth import get_user_model
                    bot = get_user_model().objects.filter(is_superuser=True).first()
                    if bot:
                        TicketMessage.objects.create(ticket=ticket, sender=bot, is_agent=True, is_internal=True, content=f"AI Screenshot:\n{result.get('raw','')}")
            except Exception as e:
                results.append({"error": str(e)})
        return results

screenshot_analyzer = ScreenshotAnalyzer()