# api/tests/test_support.py
from django.test import TestCase
from django.contrib.auth import get_user_model
import uuid

User = get_user_model()
def uid(): return uuid.uuid4().hex[:8]


class SupportTicketTest(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username=f'u_{uid()}', email=f'{uid()}@test.com', password='x'
        )

    def test_create_ticket(self):
        from api.support.models import SupportTicket
        ticket = SupportTicket.objects.create(
            user=self.user,
            category='technical',       # ✅ required field
            subject='App not loading',
            description='Test desc',    # ✅ description (not message)
            status='open',
            priority='medium',
        )
        self.assertEqual(ticket.status, 'open')

    def test_ticket_close(self):
        from api.support.models import SupportTicket
        ticket = SupportTicket.objects.create(
            user=self.user,
            category='other',
            subject=f'Test_{uid()}',
            description='Test',
            status='open',
            priority='low',
        )
        ticket.status = 'closed'
        ticket.save()
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, 'closed')

    def test_faq_creation(self):
        from api.support.models import FAQ
        faq = FAQ.objects.create(
            question='How to withdraw?',
            answer='Go to wallet.',
            is_active=True
        )
        self.assertTrue(faq.is_active)