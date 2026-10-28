# api/support/tests/test_views.py
"""Tests for support views (function-based)."""
from rest_framework.test import APITestCase, APIClient
from rest_framework import status


def make_user(username='view_u', staff=False):
    from django.contrib.auth import get_user_model
    User = get_user_model()
    return User.objects.create_user(
        username=username, email=f'{username}@t.com', password='p', is_staff=staff
    )

def make_ticket(user=None, **kw):
    from api.support.models import SupportTicket
    user = user or make_user('t_u')
    kw.setdefault('subject', 'Test'); kw.setdefault('description', 'Test desc text')
    kw.setdefault('category', 'technical')
    return SupportTicket.objects.create(user=user, **kw)


class SettingsViewTest(APITestCase):
    def test_get_settings_200(self):
        r = self.client.get('/api/support/settings/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertIn('is_support_online', r.data)

    def test_version_check(self):
        r = self.client.get('/api/support/settings/?version_code=1')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertIn('needs_update', r.data)

    def test_patch_requires_admin(self):
        r = self.client.patch('/api/support/settings/', {'is_support_online': False})
        self.assertIn(r.status_code, [401, 403])


class TicketViewTest(APITestCase):
    def setUp(self):
        self.user  = make_user('tv_user')
        self.admin = make_user('tv_admin', staff=True)

    def test_list_requires_auth(self):
        r = APIClient().get('/api/support/tickets/')
        self.assertIn(r.status_code, [401, 403])

    def test_list_own_tickets(self):
        self.client.force_authenticate(user=self.user)
        make_ticket(user=self.user)
        r = self.client.get('/api/support/tickets/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)

    def test_admin_sees_all_tickets(self):
        other = make_user('other_tv')
        make_ticket(user=other)
        self.client.force_authenticate(user=self.admin)
        r = self.client.get('/api/support/tickets/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)

    def test_get_ticket_detail(self):
        self.client.force_authenticate(user=self.user)
        t = make_ticket(user=self.user)
        r = self.client.get(f'/api/support/tickets/{t.ticket_id}/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data['ticket_id'], t.ticket_id)

    def test_user_cannot_access_other_ticket(self):
        other = make_user('other_tv2')
        t     = make_ticket(user=other)
        self.client.force_authenticate(user=self.user)
        r = self.client.get(f'/api/support/tickets/{t.ticket_id}/')
        self.assertIn(r.status_code, [403, 404])

    def test_ticket_stats_admin_only(self):
        self.client.force_authenticate(user=self.user)
        r = self.client.get('/api/support/tickets/stats/')
        self.assertIn(r.status_code, [403, 401])

    def test_ticket_stats_as_admin(self):
        self.client.force_authenticate(user=self.admin)
        r = self.client.get('/api/support/tickets/stats/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)


class FAQViewTest(APITestCase):
    def test_list_public(self):
        from api.support.models import FAQ
        FAQ.objects.create(question='Q?', answer='A.', category='gen', is_active=True)
        r = self.client.get('/api/support/faqs/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)

    def test_detail_public(self):
        from api.support.models import FAQ
        faq = FAQ.objects.create(question='Q?', answer='A.', category='gen', is_active=True)
        r   = self.client.get(f'/api/support/faqs/{faq.id}/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)

    def test_create_requires_admin(self):
        user = make_user('faq_reg')
        self.client.force_authenticate(user=user)
        r = self.client.post('/api/support/faqs/', {'question':'Q?','answer':'A.','category':'gen'})
        self.assertIn(r.status_code, [403, 401])