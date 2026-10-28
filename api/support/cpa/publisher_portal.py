"""
api/support/cpa/publisher_portal.py
FILE 1 — CPA Publisher Support Portal

CPAlead-এর মতো Publisher-দের জন্য আলাদা support portal।
Publisher-specific issues: offer not credited, payment hold, fraud accusations।

Features:
- Publisher tier-based SLA (VIP → 1hr, Standard → 8hr)
- Offer dispute system
- Earnings verification
- Account manager assignment
- Publisher health score
"""
import logging
from datetime import timedelta
from django.utils import timezone
from django.conf import settings
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

logger = logging.getLogger(__name__)

# Publisher Tiers
PUBLISHER_TIERS = {
    'vip':      {'label': 'VIP Publisher',      'sla_first_response': 1,  'sla_resolution': 4,   'color': '#f59e0b', 'priority': 'urgent'},
    'gold':     {'label': 'Gold Publisher',     'sla_first_response': 2,  'sla_resolution': 8,   'color': '#ca8a04', 'priority': 'high'},
    'silver':   {'label': 'Silver Publisher',   'sla_first_response': 4,  'sla_resolution': 24,  'color': '#6b7280', 'priority': 'medium'},
    'standard': {'label': 'Standard Publisher', 'sla_first_response': 8,  'sla_resolution': 48,  'color': '#3b82f6', 'priority': 'medium'},
    'new':      {'label': 'New Publisher',      'sla_first_response': 24, 'sla_resolution': 72,  'color': '#10b981', 'priority': 'low'},
}

ADVERTISER_TIERS = {
    'enterprise': {'label': 'Enterprise',  'sla_first_response': 0.5, 'sla_resolution': 2,  'priority': 'urgent'},
    'premium':    {'label': 'Premium',     'sla_first_response': 1,   'sla_resolution': 4,  'priority': 'urgent'},
    'standard':   {'label': 'Standard',   'sla_first_response': 4,   'sla_resolution': 24, 'priority': 'high'},
}


class PublisherSupportPortal:
    """Publisher-specific support portal logic"""

    # ─────────────────────────────────────────
    # PUBLISHER TIER DETECTION
    # ─────────────────────────────────────────
    def get_publisher_tier(self, user) -> dict:
        """User-এর publisher tier detect করো"""
        try:
            # Try earning profile
            profile = getattr(user, 'earning_profile', None) or getattr(user, 'profile', None)
            if profile:
                tier_field = getattr(profile, 'publisher_tier', None) or \
                             getattr(profile, 'account_tier', None) or \
                             getattr(profile, 'tier', None)
                if tier_field and tier_field in PUBLISHER_TIERS:
                    return {'tier': tier_field, **PUBLISHER_TIERS[tier_field]}

            # Auto-detect from earnings
            tier = self._auto_detect_tier(user)
            return {'tier': tier, **PUBLISHER_TIERS.get(tier, PUBLISHER_TIERS['standard'])}

        except Exception as e:
            logger.warning(f'Tier detection failed: {e}')
            return {'tier': 'standard', **PUBLISHER_TIERS['standard']}

    def _auto_detect_tier(self, user) -> str:
        """Earnings-based tier auto-detection"""
        try:
            # Calculate total earnings / activity
            from api.support.models import SupportTicket
            ticket_count = SupportTicket.objects.filter(user=user).count()

            # Check if user has earning model
            try:
                # Try common earning model names
                for model_name in ['EarningTransaction', 'Transaction', 'Earning']:
                    try:
                        from django.apps import apps
                        model = apps.get_model('earning', model_name)
                        total = model.objects.filter(user=user).count()
                        if total > 1000: return 'vip'
                        if total > 500:  return 'gold'
                        if total > 100:  return 'silver'
                        if total > 10:   return 'standard'
                        return 'new'
                    except Exception:
                        continue
            except Exception:
                pass

            # Fallback: ticket history based
            if ticket_count > 20: return 'silver'
            if ticket_count > 5:  return 'standard'
            return 'new'
        except Exception:
            return 'standard'

    # ─────────────────────────────────────────
    # PUBLISHER TICKET CREATE
    # ─────────────────────────────────────────
    def create_publisher_ticket(self, user, data: dict) -> object:
        """Publisher ticket create — tier-based SLA apply"""
        from api.support.models import SupportTicket

        tier_data = self.get_publisher_tier(user)
        priority  = data.get('priority') or tier_data['priority']

        # CPA-specific categories
        cpa_category = data.get('cpa_category', 'other')
        subject      = data.get('subject', '')
        description  = data.get('description', '')

        # Auto-enrich subject for CPA issues
        category_prefixes = {
            'offer_not_credited':  '[OFFER] ',
            'payment_dispute':     '[PAYMENT] ',
            'fraud_accusation':    '[FRAUD] ',
            'withdrawal_issue':    '[WITHDRAWAL] ',
            'account_suspended':   '[ACCOUNT] ',
            'postback_issue':      '[POSTBACK] ',
        }
        prefix = category_prefixes.get(cpa_category, '')

        ticket = SupportTicket.objects.create(
            user        = user,
            category    = self._map_cpa_category(cpa_category),
            subject     = f'{prefix}{subject}'[:200],
            description = description,
            priority    = priority,
            status      = 'open',
            channel     = data.get('channel', 'web'),
            tenant      = getattr(user, 'tenant', None),
        )

        # Tag with tier
        try:
            from api.support.models import TicketTag, TicketTagging
            tag, _ = TicketTag.objects.get_or_create(name=f'publisher-{tier_data["tier"]}')
            TicketTagging.objects.get_or_create(ticket=ticket, tag=tag)
            if cpa_category != 'other':
                cat_tag, _ = TicketTag.objects.get_or_create(name=cpa_category.replace('_', '-'))
                TicketTagging.objects.get_or_create(ticket=ticket, tag=cat_tag)
        except Exception:
            pass

        # Auto-assign to account manager if VIP/Gold
        if tier_data['tier'] in ['vip', 'gold']:
            self._assign_account_manager(ticket, user)

        logger.info(f'Publisher ticket created: {ticket.ticket_id} | tier={tier_data["tier"]} | cat={cpa_category}')
        return ticket

    def _map_cpa_category(self, cpa_cat: str) -> str:
        mapping = {
            'offer_not_credited':  'coins',
            'payment_dispute':     'payment',
            'withdrawal_issue':    'withdrawal',
            'fraud_accusation':    'fraud',
            'account_suspended':   'account',
            'postback_issue':      'technical',
            'kyc_issue':           'kyc',
        }
        return mapping.get(cpa_cat, 'other')

    def _assign_account_manager(self, ticket, user) -> None:
        """VIP publishers get dedicated account manager"""
        try:
            from api.support.models import SupportAgent
            # Find agent tagged as 'account_manager'
            am = SupportAgent.objects.filter(
                role      = 'account_manager',
                is_active = True,
                is_available = True,
            ).order_by('?').first()

            if not am:
                # Fallback to supervisor
                am = SupportAgent.objects.filter(
                    role__in  = ['supervisor', 'manager'],
                    is_active = True,
                ).first()

            if am:
                ticket.assigned_to = am.user
                ticket.save(update_fields=['assigned_to'])
                logger.info(f'VIP ticket {ticket.ticket_id} → AM: {am.user.username}')
        except Exception as e:
            logger.warning(f'AM assignment failed: {e}')

    # ─────────────────────────────────────────
    # PUBLISHER HEALTH SCORE
    # ─────────────────────────────────────────
    def get_publisher_health_score(self, user) -> dict:
        """
        Publisher account health score 0-100।
        Factors: ticket frequency, fraud flags, payment history, activity।
        """
        score   = 100
        factors = {}

        try:
            from api.support.models import SupportTicket, TicketRating
            from django.utils import timezone
            from datetime import timedelta

            since_30 = timezone.now() - timedelta(days=30)
            tickets  = SupportTicket.objects.filter(user=user, created_at__gte=since_30)

            # Too many tickets → lower health
            ticket_count = tickets.count()
            if ticket_count > 10:
                deduct = min(30, (ticket_count - 10) * 3)
                score -= deduct
                factors['high_ticket_count'] = f'-{deduct} pts (too many tickets: {ticket_count})'

            # Fraud tickets → major penalty
            fraud_count = tickets.filter(category='fraud').count()
            if fraud_count > 0:
                deduct = fraud_count * 15
                score -= deduct
                factors['fraud_tickets'] = f'-{deduct} pts ({fraud_count} fraud reports)'

            # SLA breach on their tickets (slow resolution = our fault, not theirs)
            # Spam tickets
            spam_count = tickets.filter(status='spam').count()
            if spam_count > 0:
                score -= spam_count * 10
                factors['spam_tickets'] = f'-{spam_count * 10} pts (spam submissions)'

            # Positive: good ratings given
            good_ratings = TicketRating.objects.filter(
                user=user, rating__gte=4, created_at__gte=since_30
            ).count()
            if good_ratings > 0:
                bonus = min(10, good_ratings * 2)
                score += bonus
                factors['good_ratings'] = f'+{bonus} pts (good feedback)'

        except Exception as e:
            logger.warning(f'Health score failed: {e}')

        score = max(0, min(100, score))
        level = 'excellent' if score >= 90 else 'good' if score >= 70 else 'fair' if score >= 50 else 'poor'

        return {
            'score':   score,
            'level':   level,
            'color':   {'excellent':'#16a34a','good':'#0ea5e9','fair':'#ca8a04','poor':'#dc2626'}[level],
            'factors': factors,
            'advice':  self._health_advice(level),
        }

    def _health_advice(self, level: str) -> str:
        advice = {
            'excellent': 'Your account is in excellent standing. Keep it up!',
            'good':      'Your account is in good standing.',
            'fair':      'Your account has some issues. Please review our terms of service.',
            'poor':      'Your account health is poor. Please contact support immediately.',
        }
        return advice.get(level, '')

    # ─────────────────────────────────────────
    # PORTAL HOME DATA
    # ─────────────────────────────────────────
    def get_portal_home(self, user) -> dict:
        from api.support.models import SupportTicket

        tier_data     = self.get_publisher_tier(user)
        health        = self.get_publisher_health_score(user)
        open_tickets  = SupportTicket.objects.filter(
            user=user, status__in=['open','in_progress','waiting_user']
        ).count()
        account_manager = self._get_account_manager(user)

        return {
            'publisher_tier':    tier_data,
            'health_score':      health,
            'open_tickets':      open_tickets,
            'account_manager':   account_manager,
            'sla_promise':       f'First response within {tier_data["sla_first_response"]} hour(s)',
            'quick_actions':     self._get_quick_actions(tier_data['tier']),
            'announcements':     self._get_announcements(),
        }

    def _get_account_manager(self, user) -> dict | None:
        try:
            from api.support.models import SupportAgent
            am = SupportAgent.objects.filter(
                role='account_manager', is_active=True
            ).first()
            if am:
                return {
                    'name':   am.user.username,
                    'email':  am.user.email,
                    'available': am.is_available,
                }
        except Exception:
            pass
        return None

    def _get_quick_actions(self, tier: str) -> list:
        actions = [
            {'label': '💰 Report Missing Payment',    'category': 'payment_dispute'},
            {'label': '🪙 Offer Not Credited',         'category': 'offer_not_credited'},
            {'label': '💸 Withdrawal Issue',           'category': 'withdrawal_issue'},
            {'label': '🔒 Account Suspended',          'category': 'account_suspended'},
            {'label': '📋 KYC Help',                   'category': 'kyc_issue'},
            {'label': '🔧 Postback/Pixel Issue',       'category': 'postback_issue'},
        ]
        if tier in ['vip', 'gold']:
            actions.insert(0, {'label': '⭐ Contact Account Manager', 'category': 'am_request'})
        return actions

    def _get_announcements(self) -> list:
        try:
            from api.support.cpa.announcement_system import announcement_system
            return announcement_system.get_active()
        except Exception:
            return []


# ─────────────────────────────────────────
# API VIEWS
# ─────────────────────────────────────────
publisher_portal = PublisherSupportPortal()


@api_view(['GET'])
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def publisher_portal_home(request):
    """GET /support/publisher/home/"""
    data = publisher_portal.get_portal_home(request.user)
    return Response({'success': True, **data})

@permission_classes([IsAuthenticated])
def publisher_tier(request):
    """GET /support/publisher/tier/"""
    return Response({'success': True, 'tier': publisher_portal.get_publisher_tier(request.user)})

@permission_classes([IsAuthenticated])
def publisher_health(request):
    """GET /support/publisher/health/"""
    return Response({'success': True, 'health': publisher_portal.get_publisher_health_score(request.user)})
@permission_classes([IsAuthenticated])
def create_publisher_ticket(request):
    """POST /support/publisher/ticket/"""
    try:
        ticket = publisher_portal.create_publisher_ticket(request.user, request.data)
        return Response({
            'success':   True,
            'ticket_id': ticket.ticket_id,
            'priority':  ticket.priority,
            'message':   f'Ticket #{ticket.ticket_id} created with {ticket.priority} priority.',
        }, status=status.HTTP_201_CREATED)
    except Exception as e:
        return Response({'error': str(e)}, status=400)