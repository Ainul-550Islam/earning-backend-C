# api/support/tests/test_services.py
"""Tests for support services."""
from django.test import TestCase
from django.utils import timezone
from unittest.mock import patch, MagicMock


def make_user(username='svc_u'):
    from django.contrib.auth import get_user_model
    User = get_user_model()
    return User.objects.create_user(username=username, email=f'{username}@t.com', password='p')

def make_ticket(user=None, **kw):
    from api.support.models import SupportTicket
    user = user or make_user('t_user')
    kw.setdefault('subject', 'Test subject'); kw.setdefault('description', 'Test desc text')
    kw.setdefault('category', 'technical')
    return SupportTicket.objects.create(user=user, **kw)


class TicketServiceTest(TestCase):
    @patch('support.services.TicketService._notify_created')
    @patch('support.services.TicketService._auto_assign')
    @patch('support.services.TicketService._setup_sla')
    @patch('support.services.TicketService._trigger_automation')
    def test_create_returns_ticket(self, m1, m2, m3, m4):
        from api.support.services import ticket_service
        user   = make_user('svc_create')
        ticket = ticket_service.create(user, {
            'subject': 'Test subject here',
            'description': 'Description text is long enough.',
            'category': 'technical',
        })
        self.assertIsNotNone(ticket.ticket_id)
        self.assertEqual(ticket.user, user)

    @patch('support.services.TicketService._notify_created')
    @patch('support.services.TicketService._auto_assign')
    @patch('support.services.TicketService._setup_sla')
    @patch('support.services.TicketService._trigger_automation')
    def test_fraud_category_gets_urgent(self, m1, m2, m3, m4):
        from api.support.services import ticket_service
        user = make_user('svc_fraud')
        t    = ticket_service.create(user, {
            'subject': 'Fraud issue here',
            'description': 'Someone hacked my account now.',
            'category': 'fraud',
        })
        self.assertEqual(t.priority, 'urgent')

    def test_get_stats_returns_dict(self):
        from api.support.services import ticket_service
        stats = ticket_service.get_stats()
        self.assertIsInstance(stats, dict)
        for key in ('total', 'open', 'resolved'):
            self.assertIn(key, stats)

    def test_add_message(self):
        from api.support.services import ticket_service
        user   = make_user('msg_svc')
        ticket = make_ticket(user=user)
        msg    = ticket_service.add_message(
            ticket.ticket_id, user, 'Hello there!', is_agent=False
        )
        self.assertIsNotNone(msg)
        self.assertEqual(msg.content, 'Hello there!')


class SLAServiceTest(TestCase):
    def test_setup_sla_creates_record(self):
        from api.support.services import sla_service
        from api.support.models import TicketSLA
        t = make_ticket()
        sla_service._setup_sla(t)
        self.assertTrue(TicketSLA.objects.filter(ticket=t).exists())
        sla = TicketSLA.objects.get(ticket=t)
        self.assertIsNotNone(sla.first_response_due)
        self.assertGreater(sla.first_response_due, timezone.now())

    def test_check_breaches_returns_dict(self):
        from api.support.services import sla_service
        result = sla_service.check_breaches()
        self.assertIn('checked', result)
        self.assertIn('breached', result)

    def test_sla_compliance_report(self):
        from api.support.services import sla_service
        report = sla_service.get_compliance_report(days=7)
        self.assertIn('compliance_rate', report)


class KBServiceTest(TestCase):
    def test_search_returns_list(self):
        from api.support.services import kb_service
        results = kb_service.search('test query', limit=5)
        self.assertIsInstance(results, list)

    def test_get_categories(self):
        from api.support.services import kb_service
        cats = kb_service.get_categories()
        self.assertIsInstance(cats, list)


class LiveChatServiceTest(TestCase):
    def test_start_creates_session(self):
        from api.support.services import livechat_service
        from api.support.models import ChatSession
        user    = make_user('chat_u')
        session = livechat_service.start(user)
        self.assertIsNotNone(session.session_id)
        self.assertEqual(session.user, user)

    def test_end_session(self):
        from api.support.services import livechat_service
        user    = make_user('chat_end')
        session = livechat_service.start(user)
        livechat_service.end(session.session_id)
        session.refresh_from_db()
        self.assertEqual(session.status, 'ended')