"""
api/support/notifications/email_notifier.py
FILE 26/70 — Full Email Notification System

HTML email templates সহ সব support notifications।
Django's email backend ব্যবহার করে।

Settings:
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
    EMAIL_HOST = 'smtp.gmail.com'
    EMAIL_PORT = 587
    EMAIL_HOST_USER = 'support@yoursite.com'
    EMAIL_HOST_PASSWORD = 'app_password'
    EMAIL_USE_TLS = True
    DEFAULT_FROM_EMAIL = 'Support Team <support@yoursite.com>'
    SITE_URL = 'https://yoursite.com'
    SITE_NAME = 'YourSite'
"""
import logging
from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from django.utils import timezone

logger   = logging.getLogger(__name__)
SITE_URL = getattr(settings, 'SITE_URL',  'https://yoursite.com')
SITE_NAME= getattr(settings, 'SITE_NAME', 'Support')
FROM_EMAIL = getattr(settings, 'DEFAULT_FROM_EMAIL', 'support@yoursite.com')


class EmailNotifier:
    """
    Full-featured email notification system।
    HTML + plain text fallback।
    Template-based emails।
    """

    # ──────────────────────────────────────────
    # TICKET NOTIFICATIONS
    # ──────────────────────────────────────────
    def ticket_created(self, ticket) -> bool:
        """Ticket create হলে user-কে confirmation পাঠাও"""
        subject = f'[{ticket.ticket_id}] Support Ticket Created — {ticket.subject[:50]}'
        context = {
            'ticket_id':   ticket.ticket_id,
            'username':    ticket.user.username,
            'subject':     ticket.subject,
            'category':    ticket.category.replace('_',' ').title(),
            'priority':    ticket.priority.upper(),
            'status':      ticket.status.replace('_',' ').title(),
            'ticket_url':  f'{SITE_URL}/support/tickets/{ticket.ticket_id}/',
            'sla_hours':   self._get_sla_hours(ticket.priority),
            'site_name':   SITE_NAME,
            'year':        timezone.now().year,
        }
        html = self._render_html('ticket_created.html', context)
        text = self._render_text_ticket_created(context)
        return self._send(ticket.user.email, subject, text, html)

    def ticket_replied(self, ticket, reply_content: str, from_agent: bool = True) -> bool:
        """Reply আসলে opposite party-কে notify করো"""
        if from_agent:
            # Agent replied → notify user
            to_email = ticket.user.email
            subject  = f'[{ticket.ticket_id}] Support Team Replied — {ticket.subject[:40]}'
            context  = {
                'ticket_id':    ticket.ticket_id,
                'username':     ticket.user.username,
                'reply':        reply_content[:800],
                'reply_from':   'Support Team',
                'ticket_url':   f'{SITE_URL}/support/tickets/{ticket.ticket_id}/',
                'site_name':    SITE_NAME,
                'year':         timezone.now().year,
            }
        else:
            # User replied → notify agent
            if not ticket.assigned_to:
                return False
            to_email = ticket.assigned_to.email
            subject  = f'[{ticket.ticket_id}] User Replied — {ticket.subject[:40]}'
            context  = {
                'ticket_id':  ticket.ticket_id,
                'username':   ticket.assigned_to.username,
                'reply':      reply_content[:800],
                'reply_from': ticket.user.username,
                'ticket_url': f'{SITE_URL}/admin/support/tickets/{ticket.ticket_id}/',
                'site_name':  SITE_NAME,
                'year':       timezone.now().year,
            }

        html = self._render_html('ticket_replied.html', context)
        text = self._render_text_reply(context)
        return self._send(to_email, subject, text, html)

    def ticket_resolved(self, ticket) -> bool:
        """Ticket resolve হলে user-কে notify + CSAT request"""
        subject = f'[{ticket.ticket_id}] Your Issue Has Been Resolved ✅'
        context = {
            'ticket_id':  ticket.ticket_id,
            'username':   ticket.user.username,
            'subject':    ticket.subject,
            'resolution': ticket.admin_response[:500] if ticket.admin_response else '',
            'ticket_url': f'{SITE_URL}/support/tickets/{ticket.ticket_id}/',
            'rate_url':   f'{SITE_URL}/support/tickets/{ticket.ticket_id}/rate/',
            'site_name':  SITE_NAME,
            'year':       timezone.now().year,
        }
        html = self._render_html('ticket_resolved.html', context)
        text = self._render_text_resolved(context)
        return self._send(ticket.user.email, subject, text, html)

    def ticket_closed(self, ticket) -> bool:
        """Ticket close notification"""
        subject = f'[{ticket.ticket_id}] Ticket Closed'
        context = {
            'ticket_id': ticket.ticket_id,
            'username':  ticket.user.username,
            'subject':   ticket.subject,
            'ticket_url':f'{SITE_URL}/support/tickets/{ticket.ticket_id}/',
            'site_name': SITE_NAME,
            'year':      timezone.now().year,
        }
        html = self._render_html('ticket_closed.html', context)
        text = (
            f'Hello {ticket.user.username},\n\n'
            f'Your ticket #{ticket.ticket_id} has been closed.\n'
            f'If you need further help, please create a new ticket.\n\n'
            f'{SITE_NAME} Support Team'
        )
        return self._send(ticket.user.email, subject, text, html)

    def csat_request(self, ticket) -> bool:
        """CSAT rating request — 24 hours after resolution"""
        subject = f'How was your support experience? Rate us ⭐'
        context = {
            'ticket_id': ticket.ticket_id,
            'username':  ticket.user.username,
            'rate_url':  f'{SITE_URL}/support/tickets/{ticket.ticket_id}/rate/',
            'rate_1':    f'{SITE_URL}/support/tickets/{ticket.ticket_id}/rate/?rating=1',
            'rate_2':    f'{SITE_URL}/support/tickets/{ticket.ticket_id}/rate/?rating=2',
            'rate_3':    f'{SITE_URL}/support/tickets/{ticket.ticket_id}/rate/?rating=3',
            'rate_4':    f'{SITE_URL}/support/tickets/{ticket.ticket_id}/rate/?rating=4',
            'rate_5':    f'{SITE_URL}/support/tickets/{ticket.ticket_id}/rate/?rating=5',
            'site_name': SITE_NAME,
            'year':      timezone.now().year,
        }
        html = self._render_html('csat_request.html', context)
        text = (
            f'Hello {ticket.user.username},\n\n'
            f'Your ticket #{ticket.ticket_id} was recently resolved.\n'
            f'How would you rate your support experience? (1-5)\n\n'
            f'Rate here: {context["rate_url"]}\n\n'
            f'Thank you!\n{SITE_NAME} Support Team'
        )
        return self._send(ticket.user.email, subject, text, html)

    # ──────────────────────────────────────────
    # AGENT NOTIFICATIONS
    # ──────────────────────────────────────────
    def agent_assigned(self, ticket, agent) -> bool:
        """Agent-কে assignment notification"""
        subject = f'[{ticket.ticket_id}] New Ticket Assigned — {ticket.priority.upper()}'
        context = {
            'ticket_id':  ticket.ticket_id,
            'agent_name': agent.username,
            'subject':    ticket.subject,
            'category':   ticket.category.replace('_',' ').title(),
            'priority':   ticket.priority.upper(),
            'user':       ticket.user.username,
            'description':ticket.description[:300],
            'ticket_url': f'{SITE_URL}/admin/support/tickets/{ticket.ticket_id}/',
            'site_name':  SITE_NAME,
            'year':       timezone.now().year,
        }
        html = self._render_html('agent_assignment.html', context)
        text = self._render_text_assignment(context)
        return self._send(agent.email, subject, text, html)

    def sla_warning(self, ticket, agent, breach_type: str, minutes_remaining: float) -> bool:
        """SLA warning — breach কাছে"""
        subject  = f'⚠️ SLA Warning: {ticket.ticket_id} — {int(minutes_remaining)}m remaining'
        hours_rem= round(minutes_remaining / 60, 1)
        context  = {
            'ticket_id':       ticket.ticket_id,
            'agent_name':      agent.username,
            'subject':         ticket.subject,
            'breach_type':     breach_type.replace('_',' ').title(),
            'minutes_remaining':int(minutes_remaining),
            'hours_remaining': hours_rem,
            'ticket_url':      f'{SITE_URL}/admin/support/tickets/{ticket.ticket_id}/',
            'site_name':       SITE_NAME,
            'year':            timezone.now().year,
        }
        html = self._render_html('sla_breach_warning.html', context)
        text = (
            f'Hello {agent.username},\n\n'
            f'SLA Warning for Ticket {ticket.ticket_id}:\n'
            f'Breach Type: {breach_type}\n'
            f'Time Remaining: {int(minutes_remaining)} minutes\n\n'
            f'Please respond immediately!\n'
            f'Ticket: {context["ticket_url"]}\n\n'
            f'{SITE_NAME} Support Team'
        )
        return self._send(agent.email, subject, text, html)

    def sla_breach(self, ticket, agent, breach_type: str, overdue_hours: float) -> bool:
        """SLA breach notification"""
        subject = f'🚨 SLA BREACH: {ticket.ticket_id} — {breach_type.replace("_"," ").title()}'
        context = {
            'ticket_id':    ticket.ticket_id,
            'agent_name':   agent.username if agent else 'Unassigned',
            'subject':      ticket.subject,
            'breach_type':  breach_type.replace('_',' ').title(),
            'overdue_hours':round(overdue_hours, 1),
            'priority':     ticket.priority.upper(),
            'ticket_url':   f'{SITE_URL}/admin/support/tickets/{ticket.ticket_id}/',
            'site_name':    SITE_NAME,
            'year':         timezone.now().year,
        }
        html = self._render_html('sla_breach_warning.html', context)
        text = (
            f'URGENT: SLA BREACH\n\n'
            f'Ticket: {ticket.ticket_id}\n'
            f'Breach: {breach_type}\n'
            f'Overdue: {round(overdue_hours, 1)} hours\n'
            f'Priority: {ticket.priority.upper()}\n\n'
            f'Immediate action required!\n'
            f'{context["ticket_url"]}'
        )
        return self._send(agent.email if agent else FROM_EMAIL, subject, text, html)

    def escalation_notice(self, ticket, supervisor) -> bool:
        """Escalation notification to supervisor"""
        subject = f'🔴 Ticket Escalated: {ticket.ticket_id}'
        context = {
            'ticket_id':   ticket.ticket_id,
            'supervisor':  supervisor.username,
            'subject':     ticket.subject,
            'priority':    ticket.priority.upper(),
            'category':    ticket.category,
            'user':        ticket.user.username,
            'assigned_to': ticket.assigned_to.username if ticket.assigned_to else 'Unassigned',
            'ticket_url':  f'{SITE_URL}/admin/support/tickets/{ticket.ticket_id}/',
            'site_name':   SITE_NAME,
            'year':        timezone.now().year,
        }
        html = self._render_html('escalation_notice.html', context)
        text = (
            f'Hello {supervisor.username},\n\n'
            f'Ticket {ticket.ticket_id} has been escalated.\n'
            f'Priority: {ticket.priority.upper()}\n'
            f'User: {ticket.user.username}\n'
            f'Assigned To: {context["assigned_to"]}\n\n'
            f'Please review: {context["ticket_url"]}'
        )
        return self._send(supervisor.email, subject, text, html)

    # ──────────────────────────────────────────
    # DIGEST
    # ──────────────────────────────────────────
    def daily_digest(self, admin_email: str, stats: dict) -> bool:
        """Daily summary email to admin"""
        subject  = f'📊 Daily Support Digest — {timezone.now().strftime("%d %b %Y")}'
        context  = {**stats, 'site_name': SITE_NAME, 'year': timezone.now().year}
        html     = self._render_html('daily_report.html', context)
        text     = (
            f'Daily Support Summary\n'
            f'Date: {timezone.now().strftime("%d %b %Y")}\n\n'
            f'Tickets Created: {stats.get("created", 0)}\n'
            f'Tickets Resolved: {stats.get("resolved", 0)}\n'
            f'Open Tickets: {stats.get("open", 0)}\n'
            f'SLA Compliance: {stats.get("sla_rate", 0)}%\n'
            f'CSAT Score: {stats.get("csat", 0)}/5.0\n'
        )
        return self._send(admin_email, subject, text, html)

    def chat_transcript(self, session, user_email: str) -> bool:
        """Chat transcript email"""
        subject = f'Your Support Chat Transcript — {session.started_at.strftime("%d %b %Y")}'
        try:
            transcript = session.transcript.content
        except Exception:
            transcript = 'Transcript not available.'

        context = {
            'session_id': str(session.session_id)[:8],
            'username':   session.user.username,
            'started_at': session.started_at.strftime('%d %b %Y %H:%M'),
            'ended_at':   session.ended_at.strftime('%d %b %Y %H:%M') if session.ended_at else '',
            'transcript': transcript,
            'site_name':  SITE_NAME,
            'year':       timezone.now().year,
        }
        html = self._render_html('chat_transcript.html', context)
        return self._send(user_email, subject, transcript, html)

    # ──────────────────────────────────────────
    # BULK EMAIL
    # ──────────────────────────────────────────
    def send_bulk(self, recipients: list, subject: str, message: str) -> dict:
        """Bulk email পাঠাও"""
        sent   = 0
        failed = 0
        for email in recipients:
            if self._send(email, subject, message):
                sent += 1
            else:
                failed += 1
        return {'sent': sent, 'failed': failed, 'total': len(recipients)}

    # ──────────────────────────────────────────
    # CORE SEND
    # ──────────────────────────────────────────
    def _send(self, to_email: str, subject: str, text: str, html: str = None) -> bool:
        if not to_email:
            logger.warning('Email send skipped: no recipient')
            return False

        try:
            if html:
                msg = EmailMultiAlternatives(
                    subject      = subject,
                    body         = text,
                    from_email   = FROM_EMAIL,
                    to           = [to_email],
                )
                msg.attach_alternative(html, 'text/html')
                msg.send(fail_silently=False)
            else:
                send_mail(
                    subject        = subject,
                    message        = text,
                    from_email     = FROM_EMAIL,
                    recipient_list = [to_email],
                    fail_silently  = False,
                )

            logger.info(f'Email sent: {subject[:50]} → {to_email}')
            self._log_notification(to_email, subject, 'email', 'sent')
            return True

        except Exception as e:
            logger.error(f'Email failed to {to_email}: {e}')
            self._log_notification(to_email, subject, 'email', 'failed', str(e))
            return False

    # ──────────────────────────────────────────
    # TEMPLATE RENDERING
    # ──────────────────────────────────────────
    def _render_html(self, template_name: str, context: dict) -> str:
        try:
            return render_to_string(f'support/{template_name}', context)
        except Exception as e:
            logger.warning(f'Template render failed [{template_name}]: {e}')
            return ''

    def _render_text_ticket_created(self, ctx: dict) -> str:
        return (
            f'Hello {ctx["username"]},\n\n'
            f'Your support ticket has been created successfully.\n\n'
            f'Ticket ID: {ctx["ticket_id"]}\n'
            f'Subject: {ctx["subject"]}\n'
            f'Priority: {ctx["priority"]}\n'
            f'Expected response: Within {ctx["sla_hours"]} hours\n\n'
            f'Track your ticket: {ctx["ticket_url"]}\n\n'
            f'Best regards,\n{ctx["site_name"]} Support Team'
        )

    def _render_text_reply(self, ctx: dict) -> str:
        return (
            f'Hello {ctx["username"]},\n\n'
            f'{ctx["reply_from"]} replied to your ticket #{ctx["ticket_id"]}:\n\n'
            f'{ctx["reply"]}\n\n'
            f'View ticket: {ctx["ticket_url"]}\n\n'
            f'Best regards,\n{ctx["site_name"]} Support Team'
        )

    def _render_text_resolved(self, ctx: dict) -> str:
        return (
            f'Hello {ctx["username"]},\n\n'
            f'Your ticket #{ctx["ticket_id"]} has been resolved.\n\n'
            f'Resolution: {ctx["resolution"]}\n\n'
            f'Please rate your experience: {ctx["rate_url"]}\n\n'
            f'Best regards,\n{ctx["site_name"]} Support Team'
        )

    def _render_text_assignment(self, ctx: dict) -> str:
        return (
            f'Hello {ctx["agent_name"]},\n\n'
            f'New ticket assigned to you:\n\n'
            f'Ticket ID: {ctx["ticket_id"]}\n'
            f'Priority: {ctx["priority"]}\n'
            f'Category: {ctx["category"]}\n'
            f'User: {ctx["user"]}\n'
            f'Subject: {ctx["subject"]}\n'
            f'Description: {ctx["description"]}\n\n'
            f'View ticket: {ctx["ticket_url"]}\n\n'
            f'{ctx["site_name"]} Support Team'
        )

    def _get_sla_hours(self, priority: str) -> int:
        return {'urgent': 2, 'high': 8, 'medium': 24, 'low': 48}.get(priority, 24)

    def _log_notification(self, email: str, subject: str, channel: str, status: str, error: str = '') -> None:
        try:
            from api.support.models import SupportNotificationLog
            from django.contrib.auth import get_user_model
            User = get_user_model()
            user = User.objects.filter(email=email).first()
            if user:
                SupportNotificationLog.objects.create(
                    user      = user,
                    channel   = channel,
                    event     = subject[:50],
                    status    = status,
                    error_msg = error,
                )
        except Exception:
            pass


# Singleton
email_notifier = EmailNotifier()