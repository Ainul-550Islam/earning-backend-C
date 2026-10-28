"""
SmartLink GDPR Views
Article 15: Right of access — GET  /api/smartlink/publisher/gdpr/my-data/
Article 17: Right to erasure — POST /api/smartlink/publisher/gdpr/my-data/anonymize/
Article 20: Data portability  — GET  /api/smartlink/publisher/gdpr/my-data/export/
"""
import json
import logging

from django.http import HttpResponse
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

logger = logging.getLogger('smartlink.gdpr')


class GDPRDataAccessView(APIView):
    """
    GDPR Article 15 — Right of access.
    Returns a summary of all personal data held for the authenticated publisher.

    GET  /api/smartlink/publisher/gdpr/my-data/
         → summary of data held (counts + categories)

    GET  /api/smartlink/publisher/gdpr/my-data/?format=json_export
         → full JSON export (downloadable)

    POST /api/smartlink/publisher/gdpr/my-data/
         Body: {"action": "anonymize", "confirm": "DELETE MY DATA"}
         → GDPR Art.17 erasure — anonymize all PII
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from api.smartlink.services.gdpr.GDPRAnonymizationService import GDPRAnonymizationService
        svc = GDPRAnonymizationService()
        summary = svc.get_publisher_data_summary(request.user)

        fmt = request.query_params.get('export', '') or request.query_params.get('format', '')

        if fmt in ('json_export', '1', 'true', 'yes'):
            # Full portable export
            export = self._build_full_export(request.user, summary)
            response = HttpResponse(
                json.dumps(export, indent=2, default=str),
                content_type='application/json',
            )
            response['Content-Disposition'] = (
                f'attachment; filename="smartlink_data_{request.user.pk}.json"'
            )
            return response

        return Response(summary)

    def post(self, request):
        action = request.data.get('action', '')
        confirm = request.data.get('confirm', '')

        if action == 'anonymize':
            if confirm != 'DELETE MY DATA':
                return Response(
                    {
                        'detail': (
                            'To confirm erasure, send '
                            '{"action": "anonymize", "confirm": "DELETE MY DATA"}. '
                            'This action is irreversible.'
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            from api.smartlink.services.gdpr.GDPRAnonymizationService import GDPRAnonymizationService
            result = GDPRAnonymizationService().anonymize_publisher(request.user)
            logger.warning(
                f"GDPR erasure completed: user#{request.user.pk} result={result}"
            )
            return Response({
                'message': (
                    'Your personal data has been anonymized. '
                    'Aggregated analytics are retained as permitted by GDPR Art.89.'
                ),
                'anonymized': result,
            })

        return Response(
            {'detail': f"Unknown action '{action}'. Supported: anonymize"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    def _build_full_export(self, user, summary: dict) -> dict:
        """Build a portable JSON export of all user data (Art.20 portability)."""
        from api.smartlink.models import SmartLink, Click
        from api.smartlink.models.click import ClickSession
        from api.smartlink.models.billing import PublisherProfile, PublisherWallet, PayoutRecord

        export = {
            'gdpr_export': True,
            'article': 'Art.20 Data Portability',
            'user': {
                'id': user.pk,
                'username': user.username,
                'email': user.email,
                'date_joined': str(user.date_joined),
            },
            'summary': summary,
        }

        try:
            profile = user.publisher_profile
            export['profile'] = {
                'company_name': profile.company_name,
                'phone': profile.phone,
                'country_code': profile.country_code,
                'payment_method': profile.payment_method,
                'gdpr_consent': profile.gdpr_consent,
                'gdpr_consent_at': str(profile.gdpr_consent_at),
                'is_anonymized': profile.data_anonymized,
            }
        except Exception:
            export['profile'] = None

        try:
            wallet = user.wallet
            export['wallet'] = {
                'balance_usd': str(wallet.balance_usd),
                'lifetime_earned': str(wallet.lifetime_earned),
                'lifetime_paid': str(wallet.lifetime_paid),
            }
        except Exception:
            export['wallet'] = None

        export['smartlinks'] = list(
            SmartLink.objects.filter(publisher=user).values(
                'slug', 'name', 'type', 'is_active', 'total_clicks',
                'total_conversions', 'created_at',
            )[:1000]
        )

        export['payouts'] = list(
            PayoutRecord.objects.filter(publisher=user).values(
                'reference_id', 'period_from', 'period_to',
                'net_amount', 'currency', 'status', 'created_at',
            )[:500]
        )

        return export
