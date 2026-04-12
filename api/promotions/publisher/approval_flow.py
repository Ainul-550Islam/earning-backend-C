# =============================================================================
# promotions/publisher/approval_flow.py
# Publisher Registration & Approval — Instant + Manual review
# =============================================================================
from django.utils import timezone
from django.core.cache import cache
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework import status


class PublisherApproval:
    """
    Publisher onboarding: instant approval (CPAlead style)
    or manual review (MaxBounty style).
    """
    INSTANT_APPROVAL_COUNTRIES = ['US', 'GB', 'CA', 'AU', 'DE', 'FR']

    def check_instant_approval_eligibility(self, user_id: int, country: str, traffic_source: str) -> dict:
        """Check if publisher qualifies for instant approval."""
        is_eligible = (
            country.upper() in self.INSTANT_APPROVAL_COUNTRIES
            or traffic_source in ['organic', 'seo', 'social_media']
        )
        return {
            'eligible_for_instant': is_eligible,
            'country': country,
            'traffic_source': traffic_source,
            'review_type': 'instant' if is_eligible else 'manual',
            'estimated_review_time': 'Immediate' if is_eligible else '24-48 hours',
        }

    def submit_publisher_application(self, user_id: int, application_data: dict) -> dict:
        """Submit publisher application."""
        eligibility = self.check_instant_approval_eligibility(
            user_id=user_id,
            country=application_data.get('country', ''),
            traffic_source=application_data.get('traffic_source', ''),
        )
        app_record = {
            'user_id': user_id,
            'status': 'approved' if eligibility['eligible_for_instant'] else 'pending',
            'review_type': eligibility['review_type'],
            'submitted_at': timezone.now().isoformat(),
            'website': application_data.get('website', ''),
            'traffic_source': application_data.get('traffic_source', ''),
            'monthly_traffic': application_data.get('monthly_traffic', 0),
            'niche': application_data.get('niche', ''),
            'country': application_data.get('country', ''),
        }
        cache.set(f'publisher_app:{user_id}', app_record, timeout=3600 * 24 * 30)
        return {
            'application_status': app_record['status'],
            'message': (
                'Congratulations! Your publisher account is approved instantly.'
                if app_record['status'] == 'approved'
                else 'Application submitted. Our team will review within 24-48 hours.'
            ),
            'review_type': eligibility['review_type'],
            'next_steps': self._get_next_steps(app_record['status']),
        }

    def approve_publisher(self, admin_user_id: int, publisher_user_id: int, notes: str = '') -> dict:
        """Admin manually approves a publisher."""
        app_data = cache.get(f'publisher_app:{publisher_user_id}', {})
        app_data.update({
            'status': 'approved',
            'approved_by': admin_user_id,
            'approved_at': timezone.now().isoformat(),
            'admin_notes': notes,
        })
        cache.set(f'publisher_app:{publisher_user_id}', app_data, timeout=3600 * 24 * 365)
        return {'success': True, 'publisher_id': publisher_user_id, 'status': 'approved'}

    def reject_publisher(self, admin_user_id: int, publisher_user_id: int, reason: str) -> dict:
        app_data = cache.get(f'publisher_app:{publisher_user_id}', {})
        app_data.update({
            'status': 'rejected',
            'rejected_by': admin_user_id,
            'rejected_at': timezone.now().isoformat(),
            'rejection_reason': reason,
        })
        cache.set(f'publisher_app:{publisher_user_id}', app_data, timeout=3600 * 24 * 30)
        return {'success': True, 'publisher_id': publisher_user_id, 'status': 'rejected'}

    def get_publisher_status(self, user_id: int) -> dict:
        app_data = cache.get(f'publisher_app:{user_id}')
        if not app_data:
            return {'status': 'not_applied', 'user_id': user_id}
        return {
            'user_id': user_id,
            'status': app_data.get('status', 'pending'),
            'review_type': app_data.get('review_type', 'manual'),
            'submitted_at': app_data.get('submitted_at'),
        }

    def _get_next_steps(self, status: str) -> list:
        if status == 'approved':
            return [
                'Set up your payment method in Earnings > Payout Settings',
                'Choose campaigns from the Offer Wall',
                'Create your first Content Locker or Link Locker',
                'Add embed code to your website',
            ]
        return [
            'We will email you within 24-48 hours',
            'Ensure your website is active and has real traffic',
            'Prepare your traffic statistics for review',
        ]

    def get_pending_applications(self, limit: int = 50) -> list:
        """Admin: get pending publisher applications."""
        return []  # In production: query publisher application model


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def apply_publisher_view(request):
    approval = PublisherApproval()
    result = approval.submit_publisher_application(
        user_id=request.user.id,
        application_data=request.data,
    )
    return Response(result, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def publisher_status_view(request):
    approval = PublisherApproval()
    return Response(approval.get_publisher_status(request.user.id))


@api_view(['POST'])
@permission_classes([IsAdminUser])
def admin_approve_publisher_view(request, publisher_id):
    approval = PublisherApproval()
    result = approval.approve_publisher(
        admin_user_id=request.user.id,
        publisher_user_id=publisher_id,
        notes=request.data.get('notes', ''),
    )
    return Response(result)
