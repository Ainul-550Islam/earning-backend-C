import os
"""
api/support/integrations/email_to_ticket.py
FILE 1/70 — Email-to-Ticket IMAP Integration

User যে email পাঠায় সেটা auto ticket হয়ে যাবে।
Celery beat-এ প্রতি ৫ মিনিটে run করো।

pip install imaplib2 email-validator
Settings:
    SUPPORT_EMAIL_HOST     = 'imap.gmail.com'
    SUPPORT_EMAIL_USER     = 'support@yoursite.com'
    SUPPORT_EMAIL_PASSWORD = os.environ.get('SUPPORT_EMAIL_PASSWORD', '')
    SUPPORT_EMAIL_PORT     = 993
"""
import imaplib
import email
import logging
import re
from email.header import decode_header
from email.utils import parseaddr
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


class EmailToTicketConverter:
    """
    IMAP inbox monitor করো।
    নতুন email → SupportTicket তৈরি করো।
    Reply email → existing ticket-এ message যোগ করো।
    """

    # Settings
    IMAP_HOST     = getattr(settings, 'SUPPORT_EMAIL_HOST',     'imap.gmail.com')
    IMAP_PORT     = getattr(settings, 'SUPPORT_EMAIL_PORT',     993)
    IMAP_USER     = getattr(settings, 'SUPPORT_EMAIL_USER',     '')
    IMAP_PASSWORD = getattr(settings, 'SUPPORT_EMAIL_PASSWORD', '')
    IMAP_FOLDER   = getattr(settings, 'SUPPORT_EMAIL_FOLDER',   'INBOX')

    # Email size limit 10MB
    MAX_EMAIL_SIZE = 10 * 1024 * 1024

    # ─────────────────────────────────────
    # MAIN ENTRY POINT
    # ─────────────────────────────────────
    def process_inbox(self) -> dict:
        """
        Inbox check করো।
        প্রতিটি unread email process করো।
        Returns: summary stats
        """
        if not self.IMAP_USER or not self.IMAP_PASSWORD:
            logger.warning('Email-to-ticket: IMAP credentials not configured.')
            return {'processed': 0, 'created': 0, 'replied': 0, 'errors': 0}

        stats = {'processed': 0, 'created': 0, 'replied': 0, 'errors': 0}

        try:
            mail = self._connect()
            mail.select(self.IMAP_FOLDER)

            # Unread emails fetch
            _, message_ids = mail.search(None, 'UNSEEN')
            ids = message_ids[0].split()

            logger.info(f'Email-to-ticket: {len(ids)} unread emails found.')

            for email_id in ids:
                try:
                    result = self._process_email(mail, email_id)
                    stats['processed'] += 1
                    if result == 'created':
                        stats['created'] += 1
                    elif result == 'replied':
                        stats['replied'] += 1
                except Exception as e:
                    logger.error(f'Email process failed [{email_id}]: {e}')
                    stats['errors'] += 1

            mail.logout()

        except Exception as e:
            logger.error(f'IMAP connection failed: {e}')
            stats['errors'] += 1

        logger.info(f'Email-to-ticket stats: {stats}')
        return stats

    # ─────────────────────────────────────
    # PROCESS SINGLE EMAIL
    # ─────────────────────────────────────
    def _process_email(self, mail, email_id) -> str:
        """
        Single email process করো।
        Returns: 'created' | 'replied' | 'skipped'
        """
        _, msg_data = mail.fetch(email_id, '(RFC822)')
        raw_email   = msg_data[0][1]

        if len(raw_email) > self.MAX_EMAIL_SIZE:
            logger.warning(f'Email too large, skipping: {email_id}')
            return 'skipped'

        msg         = email.message_from_bytes(raw_email)
        subject     = self._decode_subject(msg.get('Subject', 'No Subject'))
        from_email  = parseaddr(msg.get('From', ''))[1].lower().strip()
        body        = self._extract_body(msg)
        attachments = self._extract_attachments(msg)

        if not from_email or not self._is_valid_email(from_email):
            return 'skipped'

        # Spam check
        if self._is_spam(subject, body):
            mail.store(email_id, '+FLAGS', '\\Seen')
            return 'skipped'

        # Check if reply to existing ticket
        ticket_id = self._extract_ticket_id(subject)
        if ticket_id:
            result = self._add_reply_to_ticket(ticket_id, from_email, body, attachments)
            if result:
                mail.store(email_id, '+FLAGS', '\\Seen')
                return 'replied'

        # Create new ticket
        ticket = self._create_ticket_from_email(from_email, subject, body, attachments)
        if ticket:
            # Send confirmation email
            self._send_confirmation(from_email, ticket)
            mail.store(email_id, '+FLAGS', '\\Seen')
            return 'created'

        return 'skipped'

    # ─────────────────────────────────────
    # CREATE TICKET FROM EMAIL
    # ─────────────────────────────────────
    def _create_ticket_from_email(self, from_email: str, subject: str, body: str, attachments: list) -> object:
        """Email থেকে ticket তৈরি করো"""
        try:
            from django.contrib.auth import get_user_model
            from api.support.models import SupportTicket
            from api.support.choices import CATEGORY_PRIORITY_MAP

            User = get_user_model()

            # User খুঁজে বের করো অথবা guest হিসেবে রাখো
            user = self._get_or_create_user(from_email)

            # Category auto-detect
            category = self._detect_category(subject + ' ' + body)
            priority = CATEGORY_PRIORITY_MAP.get(category, 'medium')

            ticket = SupportTicket.objects.create(
                user        = user,
                category    = category,
                subject     = subject[:200],
                description = body[:5000],
                priority    = priority,
                status      = 'open',
                channel     = 'email',
                tenant      = getattr(user, 'tenant', None),
            )

            # Attachments
            if attachments:
                ticket.attachments = [a['filename'] for a in attachments]
                ticket.save(update_fields=['attachments'])

            logger.info(f'Ticket created from email: {ticket.ticket_id} ← {from_email}')
            return ticket

        except Exception as e:
            logger.error(f'Create ticket from email failed: {e}')
            return None

    # ─────────────────────────────────────
    # ADD REPLY TO EXISTING TICKET
    # ─────────────────────────────────────
    def _add_reply_to_ticket(self, ticket_id: str, from_email: str, body: str, attachments: list) -> bool:
        """Existing ticket-এ email reply যোগ করো"""
        try:
            from api.support.models import SupportTicket, TicketMessage

            ticket = SupportTicket.objects.filter(
                ticket_id=ticket_id
            ).exclude(status__in=['closed', 'spam']).first()

            if not ticket:
                return False

            # Determine if agent or user
            is_agent = (from_email != ticket.user.email.lower())

            TicketMessage.objects.create(
                ticket   = ticket,
                sender   = ticket.user,
                content  = f'[Via Email from {from_email}]\n\n{body[:5000]}',
                is_agent = is_agent,
            )

            # Update ticket status
            if is_agent:
                ticket.status             = 'waiting_user'
                ticket.admin_responded_at = timezone.now()
            else:
                ticket.status = 'in_progress'
            ticket.save(update_fields=['status', 'admin_responded_at'])

            logger.info(f'Email reply added to ticket: {ticket_id}')
            return True

        except Exception as e:
            logger.error(f'Add email reply failed: {e}')
            return False

    # ─────────────────────────────────────
    # HELPER METHODS
    # ─────────────────────────────────────
    def _connect(self):
        mail = imaplib.IMAP4_SSL(self.IMAP_HOST, self.IMAP_PORT)
        mail.login(self.IMAP_USER, self.IMAP_PASSWORD)
        return mail

    def _decode_subject(self, subject: str) -> str:
        decoded = decode_header(subject)
        parts   = []
        for part, encoding in decoded:
            if isinstance(part, bytes):
                parts.append(part.decode(encoding or 'utf-8', errors='replace'))
            else:
                parts.append(str(part))
        return ''.join(parts).strip()

    def _extract_body(self, msg) -> str:
        body = ''
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == 'text/plain':
                    try:
                        body = part.get_payload(decode=True).decode(
                            part.get_content_charset() or 'utf-8', errors='replace'
                        )
                        break
                    except Exception:
                        pass
        else:
            try:
                body = msg.get_payload(decode=True).decode(
                    msg.get_content_charset() or 'utf-8', errors='replace'
                )
            except Exception:
                body = str(msg.get_payload())
        return self._clean_email_body(body)

    def _clean_email_body(self, body: str) -> str:
        """Quote lines এবং signature remove করো"""
        lines    = body.split('\n')
        clean    = []
        for line in lines:
            stripped = line.strip()
            # Quote এবং signature markers skip
            if stripped.startswith('>'):
                continue
            if stripped in ['--', '___', '---']:
                break
            clean.append(line)
        return '\n'.join(clean).strip()

    def _extract_attachments(self, msg) -> list:
        attachments = []
        for part in msg.walk():
            if part.get_content_disposition() == 'attachment':
                filename = part.get_filename()
                if filename:
                    attachments.append({
                        'filename': self._decode_subject(filename),
                        'content':  part.get_payload(decode=True),
                        'mimetype': part.get_content_type(),
                    })
        return attachments[:5]  # Max 5 attachments

    def _extract_ticket_id(self, subject: str) -> str | None:
        """Subject থেকে ticket ID বের করো: [TKT123456]"""
        match = re.search(r'\[?(TKT\d{6})\]?', subject, re.IGNORECASE)
        return match.group(1) if match else None

    def _detect_category(self, text: str) -> str:
        """Email content থেকে category detect করো"""
        text = text.lower()
        if any(w in text for w in ['payment', 'paid', 'charge', 'bkash', 'nagad']):
            return 'payment'
        if any(w in text for w in ['withdraw', 'withdrawal', 'cashout']):
            return 'withdrawal'
        if any(w in text for w in ['coin', 'balance', 'reward', 'earn']):
            return 'coins'
        if any(w in text for w in ['fraud', 'hack', 'stolen', 'scam']):
            return 'fraud'
        if any(w in text for w in ['account', 'login', 'password', 'suspend']):
            return 'account'
        if any(w in text for w in ['kyc', 'verify', 'verification', 'document']):
            return 'kyc'
        if any(w in text for w in ['technical', 'bug', 'error', 'crash', 'not working']):
            return 'technical'
        return 'other'

    def _is_spam(self, subject: str, body: str) -> bool:
        """Basic spam check"""
        spam_keywords = [
            'unsubscribe', 'click here to win', 'free money',
            'earn $1000', 'make money fast', 'buy followers',
            'casino', 'lottery', 'bitcoin investment',
        ]
        text = (subject + ' ' + body).lower()
        return sum(1 for kw in spam_keywords if kw in text) >= 2

    def _is_valid_email(self, email_addr: str) -> bool:
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email_addr))

    def _get_or_create_user(self, email_addr: str):
        """Email দিয়ে user খুঁজে বের করো অথবা ghost user তৈরি করো"""
        from django.contrib.auth import get_user_model
        User = get_user_model()

        user = User.objects.filter(email__iexact=email_addr).first()
        if user:
            return user

        # Ghost user — email-only user
        username = f'email_{email_addr.split("@")[0]}_{User.objects.count()}'
        user     = User.objects.create(
            username   = username[:150],
            email      = email_addr,
            is_active  = True,
        )
        user.set_unusable_password()
        user.save()
        return user

    def _send_confirmation(self, to_email: str, ticket) -> None:
        """Ticket creation confirmation email পাঠাও"""
        try:
            from django.core.mail import send_mail
            send_mail(
                subject     = f'[{ticket.ticket_id}] Support Ticket Created',
                message     = (
                    f'Hello,\n\n'
                    f'Your support ticket has been created.\n\n'
                    f'Ticket ID: {ticket.ticket_id}\n'
                    f'Subject: {ticket.subject}\n'
                    f'Priority: {ticket.priority.upper()}\n\n'
                    f'To reply, simply reply to this email.\n\n'
                    f'Our team will respond within 24 hours.\n\n'
                    f'Best regards,\nSupport Team'
                ),
                from_email  = self.IMAP_USER,
                recipient_list = [to_email],
                fail_silently  = True,
            )
        except Exception as e:
            logger.warning(f'Confirmation email failed: {e}')


# Singleton
email_to_ticket = EmailToTicketConverter()