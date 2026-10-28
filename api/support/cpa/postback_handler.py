"""
api/support/cpa/postback_handler.py
FILE 10 — Postback/Pixel Tracking Issue Handler

Publisher: "আমার offer postback fire হচ্ছে না।"
Technical support: postback URL test করো।
Debug করো।
"""
import logging
import requests
from django.utils import timezone
logger = logging.getLogger(__name__)

class PostbackHandler:
    def create_postback_ticket(self, user, data: dict) -> dict:
        offer_id     = data.get('offer_id', '')
        postback_url = data.get('postback_url', '')
        click_id     = data.get('click_id', '')
        issue_type   = data.get('issue_type', 'not_firing')

        # Test postback URL
        test_result = self._test_postback_url(postback_url, click_id)

        from api.support.models import SupportTicket
        ticket = SupportTicket.objects.create(
            user        = user,
            category    = 'technical',
            subject     = f'Postback Issue: {issue_type} - Offer {offer_id}'[:200],
            description = (
                f'POSTBACK/PIXEL ISSUE\n'
                f'══════════════════════════\n'
                f'Offer ID: {offer_id}\n'
                f'Issue Type: {issue_type}\n'
                f'Postback URL: {postback_url[:200]}\n'
                f'Click ID: {click_id}\n\n'
                f'URL Test Result: {test_result["status"]}\n'
                f'Response Code: {test_result.get("response_code","N/A")}\n'
                f'Details: {test_result.get("details","")}\n\n'
                f'Description: {data.get("description","")}'
            ),
            priority    = 'high',
            status      = 'open',
            channel     = 'web',
            tenant      = getattr(user, 'tenant', None),
        )

        return {
            'ticket_id':   ticket.ticket_id,
            'test_result': test_result,
            'message':     'Postback issue submitted. Our technical team will investigate within 4 hours.',
        }

    def _test_postback_url(self, url: str, click_id: str) -> dict:
        if not url:
            return {'status': 'no_url', 'details': 'No postback URL provided'}
        try:
            test_url = url.replace('{click_id}', click_id or 'test123').replace('{CLICK_ID}', click_id or 'test123')
            resp     = requests.get(test_url[:500], timeout=10, allow_redirects=True)
            return {
                'status':        'success' if resp.status_code < 400 else 'error',
                'response_code': resp.status_code,
                'details':       f'URL responded with {resp.status_code}',
                'reachable':     True,
            }
        except requests.Timeout:
            return {'status': 'timeout', 'details': 'URL did not respond within 10 seconds', 'reachable': False}
        except Exception as e:
            return {'status': 'error', 'details': str(e)[:100], 'reachable': False}

postback_handler = PostbackHandler()