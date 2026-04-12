# =============================================================================
# promotions/kyc/kyc_manager.py
# KYC (Know Your Customer) — required for large withdrawals
# Verify ID for $500+ payouts — prevent fraud/money laundering
# =============================================================================
from decimal import Decimal
from django.utils import timezone
from django.core.cache import cache
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework import status
import logging

logger = logging.getLogger(__name__)

KYC_THRESHOLD = Decimal('500.00')  # Require KYC for withdrawals above this
KYC_DOCUMENTS = ['passport', 'national_id', 'drivers_license']


class KYCManager:
    """KYC verification for large payouts."""
    KYC_PREFIX = 'kyc:'

    def submit_kyc(self, user_id: int, document_type: str, document_number: str,
                   full_name: str, date_of_birth: str, address: str,
                   document_front_url: str, document_back_url: str = '') -> dict:
        if document_type not in KYC_DOCUMENTS:
            return {'error': f'Invalid document type. Use: {", ".join(KYC_DOCUMENTS)}'}
        kyc_data = {
            'user_id': user_id,
            'document_type': document_type,
            'document_number': document_number[:20],
            'full_name': full_name,
            'date_of_birth': date_of_birth,
            'address': address,
            'document_front_url': document_front_url,
            'document_back_url': document_back_url,
            'status': 'pending',
            'submitted_at': timezone.now().isoformat(),
            'reviewed_at': None,
            'reviewer_notes': '',
        }
        cache.set(f'{self.KYC_PREFIX}{user_id}', kyc_data, timeout=3600 * 24 * 365)
        return {
            'status': 'submitted',
            'message': 'KYC documents submitted. Review takes 1-2 business days.',
            'estimated_review': '1-2 business days',
        }

    def get_kyc_status(self, user_id: int) -> dict:
        kyc = cache.get(f'{self.KYC_PREFIX}{user_id}')
        if not kyc:
            return {
                'status': 'not_submitted',
                'kyc_required_at': str(KYC_THRESHOLD),
                'message': f'KYC required for withdrawals above ${KYC_THRESHOLD}',
            }
        return {
            'status': kyc['status'],
            'submitted_at': kyc.get('submitted_at'),
            'reviewed_at': kyc.get('reviewed_at'),
            'document_type': kyc.get('document_type'),
        }

    def approve_kyc(self, admin_id: int, user_id: int, notes: str = '') -> dict:
        kyc = cache.get(f'{self.KYC_PREFIX}{user_id}')
        if not kyc: return {'error': 'KYC not found'}
        kyc['status'] = 'approved'
        kyc['reviewed_at'] = timezone.now().isoformat()
        kyc['reviewer_notes'] = notes
        kyc['reviewed_by'] = admin_id
        cache.set(f'{self.KYC_PREFIX}{user_id}', kyc, timeout=3600 * 24 * 365)
        logger.info(f'KYC approved: user={user_id} by admin={admin_id}')
        return {'status': 'approved', 'user_id': user_id}

    def reject_kyc(self, admin_id: int, user_id: int, reason: str) -> dict:
        kyc = cache.get(f'{self.KYC_PREFIX}{user_id}')
        if not kyc: return {'error': 'KYC not found'}
        kyc['status'] = 'rejected'
        kyc['reviewed_at'] = timezone.now().isoformat()
        kyc['reviewer_notes'] = reason
        cache.set(f'{self.KYC_PREFIX}{user_id}', kyc, timeout=3600 * 24 * 365)
        return {'status': 'rejected', 'reason': reason}

    def is_kyc_required(self, withdrawal_amount: Decimal) -> bool:
        return withdrawal_amount >= KYC_THRESHOLD

    def is_kyc_approved(self, user_id: int) -> bool:
        kyc = cache.get(f'{self.KYC_PREFIX}{user_id}')
        return kyc is not None and kyc.get('status') == 'approved'


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def submit_kyc_view(request):
    mgr = KYCManager()
    result = mgr.submit_kyc(
        user_id=request.user.id,
        document_type=request.data.get('document_type', ''),
        document_number=request.data.get('document_number', ''),
        full_name=request.data.get('full_name', ''),
        date_of_birth=request.data.get('date_of_birth', ''),
        address=request.data.get('address', ''),
        document_front_url=request.data.get('document_front_url', ''),
        document_back_url=request.data.get('document_back_url', ''),
    )
    if 'error' in result:
        return Response(result, status=status.HTTP_400_BAD_REQUEST)
    return Response(result, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def kyc_status_view(request):
    mgr = KYCManager()
    return Response(mgr.get_kyc_status(request.user.id))


@api_view(['POST'])
@permission_classes([IsAdminUser])
def approve_kyc_view(request, user_id):
    mgr = KYCManager()
    action = request.data.get('action', 'approve')
    if action == 'approve':
        return Response(mgr.approve_kyc(request.user.id, user_id, request.data.get('notes', '')))
    return Response(mgr.reject_kyc(request.user.id, user_id, request.data.get('reason', '')))
