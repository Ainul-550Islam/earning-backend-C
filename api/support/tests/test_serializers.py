# api/support/tests/test_serializers.py
"""Tests for support serializers."""
from django.test import TestCase


def make_user(username='ser_u'):
    from django.contrib.auth import get_user_model
    User = get_user_model()
    return User.objects.create_user(
        username=username, email=f'{username}@t.com', password='p'
    )


class SupportTicketSerializerTest(TestCase):
    def test_serializes_ticket(self):
        from api.support.serializers import SupportTicketSerializer
        from api.support.models import SupportTicket
        user   = make_user('ser_u1')
        ticket = SupportTicket.objects.create(
            user=user, subject='Test', description='Desc', category='technical'
        )
        data = SupportTicketSerializer(ticket).data
        self.assertEqual(data['ticket_id'], ticket.ticket_id)
        self.assertIn('status', data)
        self.assertIn('priority', data)
        self.assertIn('category', data)

    def test_validates_required_fields(self):
        from api.support.serializers import SupportTicketSerializer
        ser = SupportTicketSerializer(data={})
        self.assertFalse(ser.is_valid())


class FAQSerializerTest(TestCase):
    def test_serializes_faq(self):
        from api.support.serializers import FAQSerializer
        from api.support.models import FAQ
        faq  = FAQ.objects.create(question='Q?', answer='A.', category='g', is_active=True)
        data = FAQSerializer(faq).data
        self.assertEqual(data['question'], 'Q?')
        self.assertIn('answer', data)

    def test_validates_required_fields(self):
        from api.support.serializers import FAQSerializer
        ser = FAQSerializer(data={})
        self.assertFalse(ser.is_valid())


class SupportSettingsSerializerTest(TestCase):
    def test_serializes_settings(self):
        from api.support.serializers import SupportSettingsSerializer
        from api.support.models import SupportSettings
        obj, _ = SupportSettings.objects.get_or_create(id=1)
        data   = SupportSettingsSerializer(obj).data
        self.assertIn('is_support_online', data)
        self.assertIn('telegram_group', data)