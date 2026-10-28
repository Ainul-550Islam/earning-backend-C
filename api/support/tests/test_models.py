# api/support/tests/test_models.py
"""Tests for all support models."""
from django.test import TestCase
from django.utils import timezone


def make_user(username='u1', staff=False):
    from django.contrib.auth import get_user_model
    User = get_user_model()
    return User.objects.create_user(
        username=username, email=f'{username}@test.com',
        password='pass', is_staff=staff
    )

def make_ticket(user=None, **kw):
    from api.support.models import SupportTicket
    user = user or make_user('ticket_user')
    kw.setdefault('subject',     'Test')
    kw.setdefault('description', 'Test description text')
    kw.setdefault('category',    'technical')
    return SupportTicket.objects.create(user=user, **kw)


class SupportTicketModelTest(TestCase):
    def test_ticket_id_auto_generated(self):
        t = make_ticket()
        self.assertTrue(t.ticket_id.startswith('TKT'))

    def test_ticket_id_unique(self):
        u = make_user('u_unique')
        t1 = make_ticket(user=u)
        t2 = make_ticket(user=u)
        self.assertNotEqual(t1.ticket_id, t2.ticket_id)

    def test_default_status_open(self):
        self.assertEqual(make_ticket().status, 'open')

    def test_default_priority_medium(self):
        self.assertEqual(make_ticket().priority, 'medium')

    def test_str_includes_ticket_id(self):
        u = make_user('str_u')
        t = make_ticket(user=u)
        self.assertIn(t.ticket_id, str(t))
        self.assertIn(u.username, str(t))

    def test_resolved_at_null(self):
        self.assertIsNone(make_ticket().resolved_at)

    def test_escalated_false_by_default(self):
        self.assertFalse(make_ticket().escalated)


class SupportSettingsModelTest(TestCase):
    def test_singleton(self):
        from api.support.models import SupportSettings
        a, _ = SupportSettings.objects.get_or_create(id=1)
        b, _ = SupportSettings.objects.get_or_create(id=1)
        self.assertEqual(a.id, b.id)

    def test_str(self):
        from api.support.models import SupportSettings
        obj, _ = SupportSettings.objects.get_or_create(id=1)
        self.assertEqual(str(obj), 'Support Settings')


class FAQModelTest(TestCase):
    def setUp(self):
        from api.support.models import FAQ
        self.faq = FAQ.objects.create(
            question='Test?', answer='Answer.', category='general', is_active=True
        )

    def test_str(self):
        self.assertIn('Test?', str(self.faq))

    def test_helpful_ratio_zero(self):
        self.assertEqual(self.faq.helpful_ratio, 0)

    def test_helpful_ratio_calculation(self):
        self.faq.helpful_yes = 3
        self.faq.helpful_no  = 1
        self.faq.save()
        self.assertEqual(self.faq.helpful_ratio, 75.0)


class OfferDisputeModelTest(TestCase):
    def test_create_dispute(self):
        from api.support.models import OfferDispute
        u = make_user('dispute_u')
        d = OfferDispute.objects.create(
            user=u, offer_id='OFF001', expected_amount=50, status='pending'
        )
        self.assertEqual(d.status, 'pending')
        self.assertEqual(float(d.expected_amount), 50.0)


class TicketMessageModelTest(TestCase):
    def test_create_message(self):
        from api.support.models import TicketMessage
        u = make_user('msg_u')
        t = make_ticket(user=u)
        m = TicketMessage.objects.create(
            ticket=t, sender=u, content='Test message', is_agent=False
        )
        self.assertFalse(m.is_agent)
        self.assertFalse(m.is_internal)


class SupportAgentModelTest(TestCase):
    def test_create_agent(self):
        from api.support.models import SupportAgent
        u = make_user('agent_u', staff=True)
        a = SupportAgent.objects.create(user=u, role='agent')
        self.assertTrue(a.is_active)
        self.assertTrue(a.is_available)
        self.assertIn(u.username, str(a))


class TicketSLAModelTest(TestCase):
    def test_is_breached_false_by_default(self):
        from api.support.models import TicketSLA
        t   = make_ticket()
        sla = TicketSLA.objects.create(
            ticket=t,
            first_response_due=timezone.now() + __import__('datetime').timedelta(hours=8),
            resolution_due=timezone.now() + __import__('datetime').timedelta(hours=48),
        )
        self.assertFalse(sla.is_breached)