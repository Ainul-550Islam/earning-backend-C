# api/support/services.py  — WORLD #1 COMPLETE
"""
World #1 support business logic.
AI, SLA, routing, notifications সব এখানে।
"""
import logging
import random
from datetime import timedelta
from typing import Optional
from django.utils import timezone
from django.conf import settings
from django.db.models import Avg, Count, Q

logger = logging.getLogger(__name__)

ANTHROPIC_API_KEY = getattr(settings, 'ANTHROPIC_API_KEY', '')
SITE_URL          = getattr(settings, 'SITE_URL', 'https://yoursite.com')
SITE_NAME         = getattr(settings, 'SITE_NAME', 'Support')


# ══════════════════════════════════════════════════════
# TICKET SERVICE
# ══════════════════════════════════════════════════════
class TicketService:

    CATEGORY_PRIORITY_MAP = {
        'fraud':      'urgent',
        'payment':    'high',
        'withdrawal': 'high',
        'kyc':        'medium',
        'coins':      'medium',
        'account':    'medium',
        'technical':  'medium',
        'referral':   'low',
        'offer':      'low',
        'other':      'low',
    }

    SLA_HOURS = {
        'urgent': {'first_response': 1,  'resolution': 4},
        'high':   {'first_response': 4,  'resolution': 24},
        'medium': {'first_response': 8,  'resolution': 48},
        'low':    {'first_response': 24, 'resolution': 72},
    }

    def create(self, user, data: dict, request=None):
        """Create ticket with auto-classification + SLA setup"""
        from .models import SupportTicket, TicketSLA

        category = data.get('category', 'other')
        priority = data.get('priority') or self.CATEGORY_PRIORITY_MAP.get(category, 'medium')

        # Channel detection
        channel = data.get('channel', 'web')

        ticket = SupportTicket.objects.create(
            user        = user,
            category    = category,
            subject     = data.get('subject', '')[:200],
            description = data.get('description', ''),
            priority    = priority,
            status      = 'open',
            channel     = channel,
            screenshot  = data.get('screenshot'),
            tenant      = getattr(user, 'tenant', None),
        )

        # Setup SLA
        self._setup_sla(ticket)

        # Auto-assign
        self._auto_assign(ticket)

        # AI classify (async if Celery available)
        self._ai_classify_async(ticket)

        # Notify
        self._notify_ticket_created(ticket)

        logger.info(f'Ticket created: {ticket.ticket_id} | user={user.username} | priority={priority}')
        return ticket

    def add_message(self, ticket_id: str, sender, content: str, is_agent: bool = False, is_internal: bool = False):
        """Add message to ticket thread"""
        from .models import SupportTicket, TicketMessage

        if str(ticket_id).startswith('TKT'):
            ticket = SupportTicket.objects.get(ticket_id=ticket_id)
        else:
            ticket = SupportTicket.objects.get(id=ticket_id)

        if ticket.status in ['closed', 'spam']:
            raise ValueError('Ticket is closed. Please create a new ticket.')

        message = TicketMessage.objects.create(
            ticket      = ticket,
            sender      = sender,
            content     = content,
            is_agent    = is_agent,
            is_internal = is_internal,
        )

        # Update ticket
        ticket.message_count += 1
        if is_agent:
            ticket.admin_response    = content
            ticket.admin_responded_at= timezone.now()
            ticket.status            = 'waiting_user'
            if not ticket.first_response_at:
                ticket.first_response_at = timezone.now()
            # SLA first response
            try:
                if not ticket.sla.first_response_at:
                    ticket.sla.first_response_at = timezone.now()
                    ticket.sla.save(update_fields=['first_response_at'])
            except Exception:
                pass
        else:
            if ticket.status == 'waiting_user':
                ticket.status = 'in_progress'

        ticket.save(update_fields=[
            'admin_response', 'admin_responded_at', 'status',
            'message_count', 'first_response_at'
        ])

        # Notify
        self._notify_message(ticket, sender, is_agent)

        return message

    def resolve(self, ticket_id: str, agent, resolution: str = ''):
        """Resolve ticket"""
        from .models import SupportTicket

        if str(ticket_id).startswith('TKT'):
            ticket = SupportTicket.objects.get(ticket_id=ticket_id)
        else:
            ticket = SupportTicket.objects.get(id=ticket_id)

        ticket.status      = 'resolved'
        ticket.resolved_at = timezone.now()
        if resolution:
            ticket.admin_response    = resolution
            ticket.admin_responded_at= timezone.now()
        ticket.save()

        # SLA resolution
        try:
            ticket.sla.resolution_at = timezone.now()
            ticket.sla.save(update_fields=['resolution_at'])
        except Exception:
            pass

        # CSAT request after 24 hours
        self._schedule_csat_request(ticket)
        self._notify_ticket_resolved(ticket)

        return ticket

    def close(self, ticket_id: str, user):
        from .models import SupportTicket
        if str(ticket_id).startswith('TKT'):
            ticket = SupportTicket.objects.get(ticket_id=ticket_id)
        else:
            ticket = SupportTicket.objects.get(id=ticket_id)

        if not user.is_staff and ticket.user != user:
            raise PermissionError('Not your ticket.')

        ticket.status = 'closed'
        if not ticket.resolved_at:
            ticket.resolved_at = timezone.now()
        ticket.save(update_fields=['status', 'resolved_at'])
        return ticket

    def get_stats(self, tenant=None) -> dict:
        """Dashboard stats"""
        from .models import SupportTicket
        from django.utils import timezone
        from datetime import timedelta

        qs = SupportTicket.objects.all()
        if tenant:
            qs = qs.filter(tenant=tenant)

        today = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)

        # Avg response time
        responded = qs.filter(admin_responded_at__isnull=False)
        avg_resp  = 0
        if responded.exists():
            times    = [(t.admin_responded_at - t.created_at).total_seconds() / 3600 for t in responded]
            avg_resp = round(sum(times) / len(times), 1)

        return {
            'total':          qs.count(),
            'open':           qs.filter(status='open').count(),
            'in_progress':    qs.filter(status='in_progress').count(),
            'waiting_user':   qs.filter(status='waiting_user').count(),
            'resolved':       qs.filter(status='resolved').count(),
            'closed':         qs.filter(status='closed').count(),
            'urgent':         qs.filter(priority='urgent').count(),
            'high':           qs.filter(priority='high').count(),
            'unanswered':     qs.filter(Q(admin_response='') | Q(admin_response__isnull=True)).count(),
            'escalated':      qs.filter(escalated=True, status__in=['open','in_progress']).count(),
            'today':          qs.filter(created_at__gte=today).count(),
            'avg_response_hours': avg_resp,
        }

    def _setup_sla(self, ticket):
        """Setup SLA deadlines based on priority"""
        from .models import TicketSLA
        sla_config = self.SLA_HOURS.get(ticket.priority, self.SLA_HOURS['medium'])
        now        = timezone.now()

        TicketSLA.objects.get_or_create(
            ticket=ticket,
            defaults={
                'first_response_due': now + timedelta(hours=sla_config['first_response']),
                'resolution_due':     now + timedelta(hours=sla_config['resolution']),
            }
        )

    def _auto_assign(self, ticket):
        """Auto-assign to least-loaded available agent"""
        from .models import SupportAgent
        from django.db.models import Count, Q

        try:
            agents = SupportAgent.objects.filter(
                is_active=True, is_available=True,
                tenant=ticket.tenant if ticket.tenant else None,
            ).annotate(
                active_count=Count('user__assigned_support_tickets',
                    filter=Q(user__assigned_support_tickets__status__in=['open','in_progress','waiting_user']))
            ).order_by('active_count')

            if agents.exists():
                agent = agents.first()
                if agent.active_count < agent.max_concurrent:
                    ticket.assigned_to = agent.user
                    ticket.save(update_fields=['assigned_to'])
        except Exception as e:
            logger.warning(f'Auto-assign failed: {e}')

    def _ai_classify_async(self, ticket):
        """AI classify in background"""
        try:
            from .ai_service import classify_ticket_async
            classify_ticket_async(ticket.id)
        except Exception:
            # AI not required
            pass

    def _notify_ticket_created(self, ticket):
        """Email + push notification"""
        try:
            from .notification_service import notify_ticket_created
            notify_ticket_created(ticket)
        except Exception as e:
            logger.warning(f'Ticket created notification failed: {e}')

    def _notify_message(self, ticket, sender, is_agent: bool):
        try:
            from .notification_service import notify_new_reply
            notify_new_reply(ticket, sender, is_agent)
        except Exception as e:
            logger.warning(f'Reply notification failed: {e}')

    def _notify_ticket_resolved(self, ticket):
        try:
            from .notification_service import notify_ticket_resolved
            notify_ticket_resolved(ticket)
        except Exception as e:
            logger.warning(f'Resolved notification failed: {e}')

    def _schedule_csat_request(self, ticket):
        """Schedule CSAT email 24hr after resolution"""
        try:
            from .tasks import send_csat_request_task
            send_csat_request_task.apply_async(
                args=[ticket.id],
                countdown=24 * 3600,
            )
        except Exception:
            pass


# ══════════════════════════════════════════════════════
# SLA SERVICE
# ══════════════════════════════════════════════════════
class SLAService:

    def check_breaches(self) -> dict:
        """Check all active tickets for SLA breaches"""
        from .models import SupportTicket
        stats = {'checked': 0, 'breached': 0}

        tickets = SupportTicket.objects.filter(
            status__in=['open','in_progress','waiting_user']
        ).select_related('sla')

        for ticket in tickets:
            try:
                result = self._check_ticket(ticket)
                stats['checked'] += 1
                if result:
                    stats['breached'] += 1
            except Exception as e:
                logger.error(f'SLA check failed for {ticket.ticket_id}: {e}')

        return stats

    def _check_ticket(self, ticket) -> bool:
        """Returns True if breached"""
        try:
            sla = ticket.sla
        except Exception:
            return False

        now      = timezone.now()
        breached = False

        # First response breach
        if (sla.first_response_due and not sla.first_response_at and
                not sla.first_response_breached and now > sla.first_response_due):
            sla.first_response_breached = True
            sla.save(update_fields=['first_response_breached'])
            ticket.escalated    = True
            ticket.escalated_at = now
            ticket.save(update_fields=['escalated', 'escalated_at'])
            self._notify_breach(ticket, 'first_response')
            breached = True

        # Resolution breach
        if (sla.resolution_due and not sla.resolution_at and
                not sla.resolution_breached and now > sla.resolution_due):
            sla.resolution_breached = True
            sla.save(update_fields=['resolution_breached'])
            self._notify_breach(ticket, 'resolution')
            breached = True

        # Warning (1 hour before)
        if (sla.first_response_due and not sla.first_response_at and
                not sla.warning_sent and not sla.first_response_breached):
            warning_at = sla.first_response_due - timedelta(hours=1)
            if now >= warning_at:
                sla.warning_sent = True
                sla.save(update_fields=['warning_sent'])
                self._notify_warning(ticket)

        return breached

    def _notify_breach(self, ticket, breach_type: str):
        try:
            from .notification_service import notify_sla_breach
            notify_sla_breach(ticket, breach_type)
        except Exception as e:
            logger.warning(f'SLA breach notification failed: {e}')

    def _notify_warning(self, ticket):
        try:
            from .notification_service import notify_sla_warning
            notify_sla_warning(ticket)
        except Exception as e:
            logger.warning(f'SLA warning notification failed: {e}')

    def get_compliance_report(self, days: int = 30) -> dict:
        from .models import TicketSLA
        since  = timezone.now() - timedelta(days=days)
        slas   = TicketSLA.objects.filter(created_at__gte=since)
        total  = slas.count()
        if not total:
            return {'total': 0, 'compliance_rate': 100.0}

        fr_breach  = slas.filter(first_response_breached=True).count()
        res_breach = slas.filter(resolution_breached=True).count()
        any_breach = max(fr_breach, res_breach)

        return {
            'period_days':     days,
            'total':           total,
            'fr_breached':     fr_breach,
            'res_breached':    res_breach,
            'compliance_rate': round((total - any_breach) / total * 100, 1),
        }


# ══════════════════════════════════════════════════════
# LIVECHAT SERVICE
# ══════════════════════════════════════════════════════
class LiveChatService:

    def start_session(self, user) -> object:
        """Start new chat session — queue or assign"""
        from .models import LiveChatSession, SupportAgent
        from django.db.models import Count, Q

        session = LiveChatSession.objects.create(
            user   = user,
            status = 'waiting',
            tenant = getattr(user, 'tenant', None),
        )

        # Try to assign available agent
        agent = SupportAgent.objects.filter(
            is_active=True, is_available=True
        ).annotate(
            chat_count=Count('user__agent_chat_sessions',
                filter=Q(user__agent_chat_sessions__status='active'))
        ).order_by('chat_count').first()

        if agent:
            session.agent  = agent.user
            session.status = 'active'
            session.save(update_fields=['agent', 'status'])
        else:
            # Set queue position
            waiting = LiveChatSession.objects.filter(status='waiting').count()
            session.queue_position = waiting
            session.save(update_fields=['queue_position'])

        return session

    def send_message(self, session_id: str, sender, content: str, is_agent: bool = False) -> object:
        from .models import LiveChatSession, LiveChatMessage
        import uuid

        try:
            session = LiveChatSession.objects.get(session_id=session_id)
        except LiveChatSession.DoesNotExist:
            raise ValueError('Chat session not found.')

        if session.status == 'ended':
            raise ValueError('Chat session has ended.')

        return LiveChatMessage.objects.create(
            session  = session,
            sender   = sender,
            content  = content,
            is_agent = is_agent,
        )

    def end_session(self, session_id: str) -> bool:
        from .models import LiveChatSession
        updated = LiveChatSession.objects.filter(session_id=session_id).update(
            status   = 'ended',
            ended_at = timezone.now(),
        )
        return updated > 0


# ══════════════════════════════════════════════════════
# KB SERVICE
# ══════════════════════════════════════════════════════
class KBService:

    def search(self, query: str, limit: int = 10) -> list:
        """Simple KB search"""
        from .models import KBArticle
        if len(query.strip()) < 2:
            return []

        articles = KBArticle.objects.filter(
            status='published', is_public=True
        ).filter(
            Q(title__icontains=query) |
            Q(body__icontains=query) |
            Q(summary__icontains=query)
        )[:limit]

        return [{'id': a.id, 'title': a.title, 'slug': a.slug, 'summary': a.summary[:100]} for a in articles]

    def suggest_for_ticket(self, ticket) -> list:
        """Suggest KB articles for a ticket"""
        query = f"{ticket.subject} {ticket.category}"
        return self.search(query, limit=3)

    def get_popular(self, limit: int = 5) -> list:
        from .models import KBArticle
        articles = KBArticle.objects.filter(
            status='published', is_public=True
        ).order_by('-view_count')[:limit]
        return [{'id': a.id, 'title': a.title, 'slug': a.slug, 'view_count': a.view_count} for a in articles]


# ══════════════════════════════════════════════════════
# OFFER DISPUTE SERVICE (CPA specific)
# ══════════════════════════════════════════════════════
class OfferDisputeService:

    def create_dispute(self, user, data: dict) -> dict:
        from .models import OfferDispute, SupportTicket

        offer_id    = data.get('offer_id', '')
        offer_name  = data.get('offer_name', '')
        amount      = data.get('expected_amount', 0)
        click_id    = data.get('click_id', '')
        description = data.get('description', '')

        # Auto-verify
        verification = self._auto_verify(user, offer_id, click_id)

        # Create ticket
        ticket = SupportTicket.objects.create(
            user        = user,
            category    = 'coins',
            subject     = f'Offer Dispute: {offer_name or offer_id}'[:200],
            description = (
                f'OFFER DISPUTE\n'
                f'Offer ID: {offer_id}\n'
                f'Offer Name: {offer_name}\n'
                f'Expected Amount: {amount}\n'
                f'Click ID: {click_id}\n\n'
                f'Description: {description}\n\n'
                f'Auto-Verification: {verification["status"]} (confidence: {verification["confidence"]:.0%})'
            ),
            priority    = 'high',
            status      = 'open',
            channel     = 'web',
            tenant      = getattr(user, 'tenant', None),
        )

        # Save dispute record
        dispute = OfferDispute.objects.create(
            user               = user,
            ticket             = ticket,
            offer_id           = offer_id,
            offer_name         = offer_name,
            expected_amount    = amount,
            click_id           = click_id,
            verification_status= verification['status'],
            confidence_score   = verification['confidence'],
            tenant             = getattr(user, 'tenant', None),
        )

        # Auto-approve if high confidence
        if verification['confidence'] >= 0.85 and verification['status'] == 'verified':
            self._auto_approve(ticket, dispute, amount)
            return {
                'ticket_id':     ticket.ticket_id,
                'dispute_id':    dispute.id,
                'status':        'auto_approved',
                'message':       f'✅ Verified! {amount} credits will be added shortly.',
                'auto_resolved': True,
            }

        return {
            'ticket_id':     ticket.ticket_id,
            'dispute_id':    dispute.id,
            'status':        'investigating',
            'verification':  verification,
            'message':       self._get_message(verification),
            'auto_resolved': False,
        }

    def _auto_verify(self, user, offer_id: str, click_id: str) -> dict:
        """Try to verify offer completion from DB"""
        result = {'status': 'unknown', 'confidence': 0.0, 'details': []}

        # Check if already credited
        try:
            from django.apps import apps
            for app, model in [('offerwall','OfferCompletion'),('earning','EarningTransaction')]:
                try:
                    m = apps.get_model(app, model)
                    if m.objects.filter(user=user, offer_id=offer_id).exists():
                        result['status']     = 'already_credited'
                        result['confidence'] = 0.95
                        result['details']    = ['Offer already credited to account']
                        return result
                except Exception:
                    continue
        except Exception:
            pass

        # Check click log
        try:
            from django.apps import apps
            for app, model in [('postback','PostbackLog'),('offerwall','ClickLog')]:
                try:
                    m  = apps.get_model(app, model)
                    qs = m.objects.filter(user=user) if hasattr(m, 'user') else m.objects.all()
                    if offer_id:
                        qs = qs.filter(offer_id=offer_id)
                    if qs.exists():
                        result['status']     = 'partial'
                        result['confidence'] = 0.5
                        result['details']    = ['Click found in system']
                        return result
                except Exception:
                    continue
        except Exception:
            pass

        result['status']     = 'not_found'
        result['confidence'] = 0.1
        result['details']    = ['No records found. Please provide proof.']
        return result

    def _auto_approve(self, ticket, dispute, amount):
        from .models import TicketMessage
        from django.contrib.auth import get_user_model
        bot = get_user_model().objects.filter(is_superuser=True).first()
        if bot:
            TicketMessage.objects.create(
                ticket=ticket, sender=bot, is_agent=True,
                content=f'✅ AUTO-RESOLVED: Offer completion verified. {amount} credits added to your account.'
            )
        ticket.status    = 'resolved'
        ticket.resolved_at = timezone.now()
        ticket.admin_response = f'Auto-approved. Credits added: {amount}'
        ticket.save()
        dispute.status = 'approved'
        dispute.resolved_at = timezone.now()
        dispute.save()

    def _get_message(self, v: dict) -> str:
        msgs = {
            'already_credited': 'Our records show this offer was already credited.',
            'partial':          'Partial verification found. Review within 24 hours.',
            'not_found':        'Could not verify automatically. Please provide proof.',
        }
        return msgs.get(v['status'], 'Dispute is under review.')


# ══════════════════════════════════════════════════════
# NOTIFICATION SERVICE
# ══════════════════════════════════════════════════════
class NotificationService:

    def notify_ticket_created(self, ticket):
        """Ticket create হলে user-কে email পাঠাও"""
        self._send_email(
            to       = ticket.user.email,
            subject  = f'[{ticket.ticket_id}] Support Ticket Created',
            body     = (
                f'Hello {ticket.user.username},\n\n'
                f'Your support ticket has been created.\n\n'
                f'Ticket ID: {ticket.ticket_id}\n'
                f'Subject: {ticket.subject}\n'
                f'Priority: {ticket.priority.upper()}\n\n'
                f'We will respond within the SLA timeframe.\n\n'
                f'View your ticket: {SITE_URL}/support/tickets/{ticket.ticket_id}/\n\n'
                f'{SITE_NAME} Support Team'
            )
        )
        # In-app notification
        self._send_in_app(ticket.user, f'Ticket #{ticket.ticket_id} created', 'ticket_created', ticket.id)

    def notify_new_reply(self, ticket, sender, is_agent: bool):
        if is_agent:
            self._send_email(
                to      = ticket.user.email,
                subject = f'[{ticket.ticket_id}] Support Team Replied',
                body    = (
                    f'Hello {ticket.user.username},\n\n'
                    f'Support team has replied to your ticket #{ticket.ticket_id}.\n\n'
                    f'View reply: {SITE_URL}/support/tickets/{ticket.ticket_id}/\n\n'
                    f'{SITE_NAME} Support Team'
                )
            )
            self._send_in_app(ticket.user, f'New reply on #{ticket.ticket_id}', 'ticket_reply', ticket.id)
        else:
            # Agent notification
            if ticket.assigned_to:
                self._send_in_app(ticket.assigned_to, f'User replied on #{ticket.ticket_id}', 'ticket_reply', ticket.id)

    def notify_ticket_resolved(self, ticket):
        self._send_email(
            to      = ticket.user.email,
            subject = f'[{ticket.ticket_id}] Ticket Resolved ✅',
            body    = (
                f'Hello {ticket.user.username},\n\n'
                f'Your ticket #{ticket.ticket_id} has been resolved!\n\n'
                f'Please rate your experience: {SITE_URL}/support/tickets/{ticket.ticket_id}/rate/\n\n'
                f'{SITE_NAME} Support Team'
            )
        )
        self._send_in_app(ticket.user, f'Ticket #{ticket.ticket_id} resolved!', 'ticket_resolved', ticket.id)

    def notify_sla_breach(self, ticket, breach_type: str):
        if ticket.assigned_to:
            self._send_in_app(
                ticket.assigned_to,
                f'🚨 SLA BREACH: {ticket.ticket_id} — {breach_type}',
                'sla_breach', ticket.id
            )

    def notify_sla_warning(self, ticket):
        if ticket.assigned_to:
            self._send_in_app(
                ticket.assigned_to,
                f'⚠️ SLA Warning: {ticket.ticket_id} approaching deadline',
                'sla_warning', ticket.id
            )

    def _send_email(self, to: str, subject: str, body: str):
        try:
            from django.core.mail import send_mail
            from django.conf import settings as django_settings
            send_mail(
                subject        = subject,
                message        = body,
                from_email     = getattr(django_settings, 'DEFAULT_FROM_EMAIL', 'noreply@support.com'),
                recipient_list = [to],
                fail_silently  = True,
            )
            logger.info(f'Email sent: {subject[:40]} → {to}')
        except Exception as e:
            logger.error(f'Email failed to {to}: {e}')

    def _send_in_app(self, user, message: str, event_type: str, ref_id=None):
        """Send via notifications app"""
        try:
            from api.notifications.models import Notification
            Notification.objects.create(
                user    = user,
                title   = message,
                message = message,
                category= 'support',
                data    = {'event': event_type, 'ref_id': str(ref_id) if ref_id else ''},
            )
        except Exception:
            # notifications app সব same interface নাও থাকতে পারে
            try:
                from api.notifications.tasks import send_notification_task
                from api.notifications.models import Notification as N
                n = N.objects.create(
                    recipient = user,
                    title     = 'Support Update',
                    body      = message,
                )
                send_notification_task.delay(str(n.id))
            except Exception as e:
                logger.debug(f'In-app notification failed: {e}')


# ══════════════════════════════════════════════════════
# SINGLETONS
# ══════════════════════════════════════════════════════
ticket_service        = TicketService()
sla_service           = SLAService()
livechat_service      = LiveChatService()
kb_service            = KBService()
offer_dispute_service = OfferDisputeService()
notification_service  = NotificationService()


# ── Notification helper shortcuts ────────────────────
def notify_ticket_created(ticket):
    notification_service.notify_ticket_created(ticket)

def notify_new_reply(ticket, sender, is_agent):
    notification_service.notify_new_reply(ticket, sender, is_agent)

def notify_ticket_resolved(ticket):
    notification_service.notify_ticket_resolved(ticket)

def notify_sla_breach(ticket, breach_type):
    notification_service.notify_sla_breach(ticket, breach_type)

def notify_sla_warning(ticket):
    notification_service.notify_sla_warning(ticket)


# ══════════════════════════════════════════════════════
# OLD SYSTEM BRIDGE  (Backward Compatibility)
# ══════════════════════════════════════════════════════
class SupportService:
    """
    পুরনো (simple support) system এর SupportService।
    নতুন WORLD #1 system এর সাথে cross-talk করে।
    পুরনো code যে method call করত সব কাজ করবে।

    পুরনো system:
        from api.support.services import SupportService
        stats = SupportService.get_ticket_stats()   ← এখনো কাজ করবে

    নতুন system cross-talk:
        SupportService.create_ticket()    → TicketService.create()
        SupportService.get_sla_status()   → SLAService.get_ticket_sla_status()
        SupportService.notify_*()         → NotificationService.*()
        SupportService.get_portal_home()  → services/SupportService.py
    """

    @staticmethod
    def get_ticket_stats(tenant=None) -> dict:
        """Status-wise ticket count (পুরনো API)।"""
        try:
            from .models import SupportTicket
            from django.db.models import Count
            qs = SupportTicket.objects.all()
            if tenant:
                qs = qs.filter(tenant=tenant)
            return {row['status']: row['count']
                    for row in qs.values('status').annotate(count=Count('id'))}
        except Exception as e:
            logger.error(f'SupportService.get_ticket_stats: {e}')
            return {}

    @staticmethod
    def create_ticket(user, data: dict, request=None):
        """নতুন TicketService দিয়ে ticket create করো।"""
        try:
            return ticket_service.create(user, data, request=request)
        except Exception as e:
            logger.error(f'SupportService.create_ticket error: {e}')
            from .models import SupportTicket
            return SupportTicket.objects.create(
                user=user,
                description=data.get('description', ''),
                category=data.get('category', 'other'),
                subject=data.get('subject', ''),
            )

    @staticmethod
    def get_settings(tenant=None):
        """SupportSettings singleton।"""
        try:
            from .models import SupportSettings
            if tenant:
                obj, _ = SupportSettings.objects.get_or_create(tenant=tenant)
            else:
                obj, _ = SupportSettings.objects.get_or_create(id=1)
            return obj
        except Exception as e:
            logger.error(f'SupportService.get_settings: {e}')
            return None

    @staticmethod
    def is_support_online(tenant=None) -> bool:
        obj = SupportService.get_settings(tenant=tenant)
        if obj:
            return obj.is_support_online and not obj.maintenance_mode
        return False

    @staticmethod
    def needs_app_update(version_code: int, tenant=None) -> dict:
        try:
            obj = SupportService.get_settings(tenant=tenant)
            if not obj:
                return {'needs_update': False}
            return {
                'needs_update':       version_code < obj.latest_version_code,
                'latest_version':     obj.latest_version_name,
                'latest_version_code': obj.latest_version_code,
                'update_message':     obj.update_message,
                'play_store_url':     obj.play_store_url,
                'force_update':       obj.force_update,
            }
        except Exception as e:
            logger.error(f'SupportService.needs_app_update: {e}')
            return {'needs_update': False}

    @staticmethod
    def notify_ticket_update(ticket, event: str = 'updated'):
        """নতুন NotificationService দিয়ে notification পাঠাও।"""
        try:
            if event == 'created':
                notification_service.notify_ticket_created(ticket)
            elif event == 'resolved':
                notification_service.notify_ticket_resolved(ticket)
            else:
                notification_service.notify_new_reply(ticket, ticket.user, is_agent=False)
        except Exception as e:
            logger.warning(f'SupportService.notify_ticket_update: {e}')

    @staticmethod
    def get_sla_status(ticket) -> Optional[dict]:
        """নতুন SLAService দিয়ে SLA status নাও।"""
        try:
            return sla_service.get_ticket_sla_status(ticket)
        except Exception as e:
            logger.debug(f'SupportService.get_sla_status: {e}')
            return None

    @staticmethod
    def get_faqs(category: str = None, tenant=None) -> list:
        try:
            from .models import FAQ
            qs = FAQ.objects.filter(is_active=True)
            if category:
                qs = qs.filter(category=category)
            if tenant:
                qs = qs.filter(tenant=tenant)
            return list(qs.values('id', 'question', 'answer', 'category', 'order'))
        except Exception as e:
            logger.error(f'SupportService.get_faqs: {e}')
            return []

    @staticmethod
    def get_portal_home(user, tenant=None) -> dict:
        """নতুন services/SupportService.py থেকে portal home data।"""
        try:
            from .services.SupportService import support_service as _ss
            return _ss.get_portal_home(user)
        except Exception as e:
            logger.debug(f'SupportService.get_portal_home fallback: {e}')
            try:
                from .models import SupportTicket, SupportSettings
                qs = SupportTicket.objects.filter(user=user)
                if tenant:
                    qs = qs.filter(tenant=tenant)
                obj, _ = SupportSettings.objects.get_or_create(id=1)
                return {
                    'open_tickets':       qs.filter(status__in=['open', 'in_progress', 'waiting_user']).count(),
                    'total_tickets':      qs.count(),
                    'support_online':     obj.is_support_online,
                    'maintenance_mode':   obj.maintenance_mode,
                    'maintenance_message': obj.maintenance_message,
                }
            except Exception as e2:
                logger.error(f'SupportService.get_portal_home error: {e2}')
                return {}