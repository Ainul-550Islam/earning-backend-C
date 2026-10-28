# api/support/services/automation/CannedResponseService.py  — WORLD #1
import logging
logger = logging.getLogger(__name__)

class CannedResponseService:
    def search(self, shortcut: str = '', category: str = '') -> list:
        from api.support.models import CannedResponse
        from api.support.serializers import CannedResponseSerializer
        qs = CannedResponse.objects.filter(is_active=True)
        if shortcut:
            qs = qs.filter(shortcut_key__icontains=shortcut)
        if category:
            qs = qs.filter(category=category)
        return CannedResponseSerializer(qs[:20], many=True).data

    def use(self, canned_id: int) -> str:
        from api.support.models import CannedResponse
        try:
            r = CannedResponse.objects.get(id=canned_id)
            CannedResponse.objects.filter(id=canned_id).update(usage_count=r.usage_count+1)
            return r.content
        except CannedResponse.DoesNotExist:
            return ''

    def suggest_for_ticket(self, ticket) -> list:
        from api.support.models import CannedResponse
        from api.support.serializers import CannedResponseSerializer
        qs = CannedResponse.objects.filter(is_active=True, category=ticket.category or 'general')[:5]
        return CannedResponseSerializer(qs, many=True).data

canned_response_service = CannedResponseService()