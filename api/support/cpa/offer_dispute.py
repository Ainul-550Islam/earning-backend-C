"""
api/support/cpa/offer_dispute.py
FILE 2 — CPA Offer Dispute System

Publisher claim: "I completed the offer but didn't get credited."
System auto-verify করবে postback logs, click logs।
Evidence collect করবে।
Auto-resolve করবে যদি proof থাকে।

This is CPAlead's #1 most common support issue.
"""
import logging
from django.utils import timezone
from django.conf import settings
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

logger = logging.getLogger(__name__)


class OfferDisputeSystem:
    """
    Offer dispute auto-resolution।
    Publisher claim করলে auto-check করো।
    """

    DISPUTE_STATUSES = [
        ('pending',       'Pending Review'),
        ('investigating', 'Under Investigation'),
        ('approved',      'Approved — Credits Added'),
        ('rejected',      'Rejected — Invalid Claim'),
        ('escalated',     'Escalated to Network'),
        ('needs_proof',   'Proof Required'),
    ]

    # Auto-resolve confidence threshold
    AUTO_RESOLVE_THRESHOLD = 0.85

    # ─────────────────────────────────────────
    # CREATE DISPUTE
    # ─────────────────────────────────────────
    def create_dispute(self, user, data: dict) -> dict:
        """
        New offer dispute create করো।
        Auto-verify করার চেষ্টা করো।
        """
        offer_id       = data.get('offer_id', '')
        offer_name     = data.get('offer_name', '')
        expected_amount= data.get('expected_amount', 0)
        completion_date= data.get('completion_date', '')
        proof_url      = data.get('proof_url', '')
        description    = data.get('description', '')
        click_id       = data.get('click_id', '')

        # Auto-verify
        verification = self._auto_verify(user, offer_id, click_id, completion_date)

        # Create ticket
        from api.support.models import SupportTicket
        subject = f'Offer Not Credited: {offer_name or offer_id}'
        body    = (
            f'OFFER DISPUTE\n'
            f'═══════════════════════════════\n'
            f'Offer ID: {offer_id}\n'
            f'Offer Name: {offer_name}\n'
            f'Expected Amount: {expected_amount}\n'
            f'Completion Date: {completion_date}\n'
            f'Click ID: {click_id}\n'
            f'Proof URL: {proof_url}\n\n'
            f'Description:\n{description}\n\n'
            f'AUTO-VERIFICATION RESULT:\n'
            f'Status: {verification["status"]}\n'
            f'Confidence: {verification["confidence"]:.0%}\n'
            f'Details: {verification["details"]}\n'
        )

        ticket = SupportTicket.objects.create(
            user        = user,
            category    = 'coins',
            subject     = subject[:200],
            description = body,
            priority    = 'high',
            status      = 'open',
            channel     = 'web',
            tenant      = getattr(user, 'tenant', None),
        )

        # Save dispute record
        dispute = self._save_dispute(user, ticket, data, verification)

        # Auto-resolve if high confidence
        if (verification['confidence'] >= self.AUTO_RESOLVE_THRESHOLD and
                verification['status'] == 'verified'):
            return self._auto_approve(ticket, dispute, expected_amount, verification)

        elif verification['status'] == 'not_found':
            self._request_proof(ticket)

        return {
            'ticket_id':    ticket.ticket_id,
            'dispute_id':   dispute.get('id', ''),
            'status':       'investigating',
            'auto_verified':verification['confidence'] >= 0.7,
            'verification': verification,
            'message':      self._get_message(verification),
            'next_steps':   self._get_next_steps(verification),
        }

    # ─────────────────────────────────────────
    # AUTO VERIFICATION
    # ─────────────────────────────────────────
    def _auto_verify(self, user, offer_id: str, click_id: str, completion_date: str) -> dict:
        """
        Postback logs, click logs auto-check করো।
        Integration-dependent — override করো।
        """
        result = {
            'status':     'unknown',
            'confidence': 0.0,
            'details':    [],
            'found_in':   [],
        }

        checks = []

        # 1. Check click log
        click_found = self._check_click_log(user, offer_id, click_id)
        if click_found:
            checks.append(('Click log found', 0.4))
            result['found_in'].append('click_log')
            result['details'].append(f'✅ Click recorded for offer {offer_id}')
        else:
            result['details'].append(f'❌ No click found for offer {offer_id}')

        # 2. Check postback/pixel
        postback_found = self._check_postback_log(user, offer_id, click_id)
        if postback_found:
            checks.append(('Postback received', 0.5))
            result['found_in'].append('postback_log')
            result['details'].append('✅ Postback/pixel fire confirmed')
        else:
            result['details'].append('❌ No postback received from advertiser')

        # 3. Check if already credited
        already_credited = self._check_already_credited(user, offer_id)
        if already_credited:
            result['status']     = 'already_credited'
            result['confidence'] = 0.95
            result['details'].append('⚠️ Credits already applied to account')
            return result

        # 4. Check duplicate claim
        duplicate = self._check_duplicate_claim(user, offer_id)
        if duplicate:
            result['status']     = 'duplicate'
            result['confidence'] = 0.95
            result['details'].append('⚠️ Duplicate dispute — already processed')
            return result

        # Calculate confidence
        total_confidence = sum(score for _, score in checks)
        result['confidence'] = min(total_confidence, 1.0)

        if result['confidence'] >= 0.85:
            result['status'] = 'verified'
        elif result['confidence'] >= 0.4:
            result['status'] = 'partial'
        else:
            result['status'] = 'not_found'

        return result

    def _check_click_log(self, user, offer_id: str, click_id: str) -> bool:
        """Check click log — override with actual DB query"""
        try:
            from django.apps import apps
            # Try common click log models
            for app_label, model_name in [('earning','ClickLog'),('offers','Click'),('tracking','ClickLog')]:
                try:
                    model = apps.get_model(app_label, model_name)
                    qs    = model.objects.filter(user=user)
                    if offer_id:
                        qs = qs.filter(offer_id=offer_id)
                    if click_id:
                        qs = qs.filter(click_id=click_id)
                    return qs.exists()
                except Exception:
                    continue
        except Exception:
            pass
        return False

    def _check_postback_log(self, user, offer_id: str, click_id: str) -> bool:
        """Check postback/pixel fire log"""
        try:
            from django.apps import apps
            for app_label, model_name in [('earning','PostbackLog'),('offers','Postback'),('tracking','PostbackLog')]:
                try:
                    model = apps.get_model(app_label, model_name)
                    return model.objects.filter(click_id=click_id).exists() if click_id else False
                except Exception:
                    continue
        except Exception:
            pass
        return False

    def _check_already_credited(self, user, offer_id: str) -> bool:
        """Check if offer already credited"""
        try:
            from django.apps import apps
            for app_label, model_name in [('earning','EarningTransaction'),('earning','Earning')]:
                try:
                    model = apps.get_model(app_label, model_name)
                    return model.objects.filter(user=user, offer_id=offer_id).exists()
                except Exception:
                    continue
        except Exception:
            pass
        return False

    def _check_duplicate_claim(self, user, offer_id: str) -> bool:
        """Already submitted dispute for this offer?"""
        try:
            from api.support.cpa.models import OfferDispute
            return OfferDispute.objects.filter(
                user=user, offer_id=offer_id,
                status__in=['pending','investigating','approved']
            ).exists()
        except Exception:
            return False

    # ─────────────────────────────────────────
    # AUTO APPROVE
    # ─────────────────────────────────────────
    def _auto_approve(self, ticket, dispute: dict, amount: float, verification: dict) -> dict:
        """High-confidence verified → auto approve + credit"""
        try:
            # Add credit
            self._add_missing_credit(ticket.user, amount, ticket.ticket_id)

            # Resolve ticket
            from api.support.models import TicketMessage
            from django.contrib.auth import get_user_model
            User   = get_user_model()
            system = User.objects.filter(is_superuser=True).first()

            if system:
                TicketMessage.objects.create(
                    ticket      = ticket,
                    sender      = system,
                    content     = (
                        f'🤖 AUTO-RESOLVED by verification system\n\n'
                        f'✅ Your offer completion has been verified and credits have been applied.\n\n'
                        f'Amount Credited: {amount}\n'
                        f'Verification: {", ".join(verification["found_in"])}\n\n'
                        f'The credits should reflect in your account within a few minutes.'
                    ),
                    is_agent    = True,
                    is_internal = False,
                )

            ticket.status    = 'resolved'
            ticket.admin_response = f'Auto-approved. Credits added: {amount}'
            ticket.resolved_at    = timezone.now()
            ticket.save(update_fields=['status','admin_response','resolved_at'])

            return {
                'ticket_id':   ticket.ticket_id,
                'status':      'auto_approved',
                'credits_added': amount,
                'message':     f'✅ Your dispute has been auto-approved! {amount} credits added.',
            }
        except Exception as e:
            logger.error(f'Auto-approve failed: {e}')
            return {'ticket_id': ticket.ticket_id, 'status': 'investigating'}

    def _add_missing_credit(self, user, amount: float, reference: str) -> bool:
        """Add credits to user account"""
        try:
            from django.apps import apps
            for app_label, model_name in [('earning','EarningTransaction'),('wallet','Transaction')]:
                try:
                    model = apps.get_model(app_label, model_name)
                    model.objects.create(
                        user        = user,
                        amount      = amount,
                        transaction_type = 'dispute_credit',
                        reference   = reference,
                        note        = 'Offer dispute auto-credit',
                    )
                    logger.info(f'Credits added: {amount} for {user.username}')
                    return True
                except Exception:
                    continue
        except Exception as e:
            logger.error(f'Add credit failed: {e}')
        return False

    def _request_proof(self, ticket) -> None:
        """Ask user for proof"""
        from api.support.models import TicketMessage
        from django.contrib.auth import get_user_model
        User   = get_user_model()
        system = User.objects.filter(is_superuser=True).first()
        if system:
            TicketMessage.objects.create(
                ticket   = ticket,
                sender   = system,
                content  = (
                    'We could not automatically verify your offer completion.\n\n'
                    'Please provide the following:\n'
                    '1. Screenshot of offer completion confirmation\n'
                    '2. Date and time of completion\n'
                    '3. Any confirmation email or code\n'
                    '4. Click ID (if available)\n\n'
                    'Our team will review within 24 hours.'
                ),
                is_agent = True,
            )
            ticket.status = 'waiting_user'
            ticket.save(update_fields=['status'])

    def _save_dispute(self, user, ticket, data: dict, verification: dict) -> dict:
        """Save dispute to DB"""
        try:
            from api.support.cpa.models import OfferDispute
            dispute = OfferDispute.objects.create(
                user             = user,
                ticket           = ticket,
                offer_id         = data.get('offer_id', ''),
                offer_name       = data.get('offer_name', ''),
                expected_amount  = data.get('expected_amount', 0),
                click_id         = data.get('click_id', ''),
                verification_status = verification['status'],
                confidence_score = verification['confidence'],
            )
            return {'id': str(dispute.id)}
        except Exception:
            return {}

    def _get_message(self, verification: dict) -> str:
        messages = {
            'verified':        '✅ Your offer completion is verified! Credits will be applied.',
            'partial':         '🔍 Partial verification found. Our team will review within 24 hours.',
            'not_found':       '⚠️ Could not verify automatically. Please provide proof.',
            'already_credited':'ℹ️ Our records show this offer was already credited to your account.',
            'duplicate':       'ℹ️ A dispute for this offer is already being processed.',
        }
        return messages.get(verification['status'], 'Your dispute is under review.')

    def _get_next_steps(self, verification: dict) -> list:
        if verification['status'] == 'not_found':
            return ['Upload screenshot of completion', 'Provide click ID', 'Wait for 24hr review']
        if verification['status'] == 'partial':
            return ['Provide additional proof', 'Wait for agent review (24hrs)']
        return ['Wait for credits to appear', 'Contact us if issue persists']

    # ─────────────────────────────────────────
    # DISPUTE LIST + STATS
    # ─────────────────────────────────────────
    def get_user_disputes(self, user, limit: int = 10) -> list:
        try:
            from api.support.cpa.models import OfferDispute
            disputes = OfferDispute.objects.filter(user=user).order_by('-created_at')[:limit]
            return [{
                'id':           str(d.id),
                'offer_id':     d.offer_id,
                'offer_name':   d.offer_name,
                'status':       d.status,
                'amount':       float(d.expected_amount),
                'created_at':   d.created_at.isoformat(),
                'ticket_id':    d.ticket.ticket_id if d.ticket else '',
            } for d in disputes]
        except Exception:
            return []

    def get_dispute_stats(self, days: int = 30) -> dict:
        try:
            from api.support.cpa.models import OfferDispute
            from django.db.models import Count, Avg
            from datetime import timedelta
            since = timezone.now() - timedelta(days=days)
            qs    = OfferDispute.objects.filter(created_at__gte=since)
            return {
                'total':        qs.count(),
                'approved':     qs.filter(status='approved').count(),
                'rejected':     qs.filter(status='rejected').count(),
                'auto_resolved':qs.filter(verification_status='verified').count(),
                'approval_rate':round(qs.filter(status='approved').count() / max(qs.count(),1) * 100, 1),
            }
        except Exception:
            return {}


offer_dispute_system = OfferDisputeSystem()


@api_view(['POST'])
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def submit_offer_dispute(request):
    """POST /support/cpa/dispute/offer/"""
    result = offer_dispute_system.create_dispute(request.user, request.data)
    code   = status.HTTP_201_CREATED if 'error' not in result else 400
    return Response({'success': 'error' not in result, **result}, status=code)
@permission_classes([IsAuthenticated])
def my_disputes(request):
    """GET /support/cpa/dispute/my/"""
    return Response({
        'success':  True,
        'disputes': offer_dispute_system.get_user_disputes(request.user),
    })