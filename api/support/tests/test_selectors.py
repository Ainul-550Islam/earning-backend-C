# api/support/tests/test_selectors.py
"""Tests for selectors (read-only query layer)."""
from django.test import TestCase


def make_user(un='sel_u'):
    from django.contrib.auth import get_user_model
    User = get_user_model()
    return User.objects.create_user(username=un, email=f'{un}@t.com', password='p')


def make_ticket(user=None, **kw):
    from api.support.models import SupportTicket
    user = user or make_user()
    kw.setdefault('subject', 'S'); kw.setdefault('description', 'D text here')
    kw.setdefault('category', 'technical')
    return SupportTicket.objects.create(user=user, **kw)


class TicketSelectorTest(TestCase):
    def test_get_ticket_by_id(self):
        from api.support.selectors import get_ticket_by_id
        u = make_user('sel1')
        t = make_ticket(user=u)
        result = get_ticket_by_id(t.ticket_id)
        self.assertIsNotNone(result)
        self.assertEqual(result.ticket_id, t.ticket_id)

    def test_get_nonexistent_ticket(self):
        from api.support.selectors import get_ticket_by_id
        result = get_ticket_by_id('TKT999999')
        self.assertIsNone(result)

    def test_get_ticket_for_owner(self):
        from api.support.selectors import get_ticket_for_user
        u = make_user('sel2')
        t = make_ticket(user=u)
        result = get_ticket_for_user(t.ticket_id, u)
        self.assertIsNotNone(result)

    def test_get_ticket_for_wrong_user(self):
        from api.support.selectors import get_ticket_for_user
        owner = make_user('owner_sel')
        other = make_user('other_sel')
        t     = make_ticket(user=owner)
        result = get_ticket_for_user(t.ticket_id, other)
        self.assertIsNone(result)

    def test_list_tickets_for_user(self):
        from api.support.selectors import list_tickets_for_user
        u  = make_user('list_sel')
        make_ticket(user=u)
        qs = list_tickets_for_user(u)
        self.assertEqual(qs.count(), 1)

    def test_get_ticket_stats(self):
        from api.support.selectors import get_ticket_stats
        stats = get_ticket_stats()
        self.assertIsInstance(stats, dict)

    def test_get_open_ticket_count(self):
        from api.support.selectors import get_open_ticket_count
        u = make_user('cnt_sel')
        make_ticket(user=u, status='open')
        make_ticket(user=u, status='resolved')
        count = get_open_ticket_count(u)
        self.assertEqual(count, 1)


class FAQSelectorTest(TestCase):
    def test_list_active_faqs(self):
        from api.support.models import FAQ
        from api.support.selectors import list_active_faqs
        FAQ.objects.create(question='Q?', answer='A.', category='g', is_active=True)
        FAQ.objects.create(question='Q2?', answer='A2.', category='g', is_active=False)
        qs = list_active_faqs()
        self.assertEqual(qs.count(), 1)

    def test_get_faq_by_id(self):
        from api.support.models import FAQ
        from api.support.selectors import get_faq_by_id
        faq    = FAQ.objects.create(question='Q?', answer='A.', category='g', is_active=True)
        result = get_faq_by_id(faq.id)
        self.assertIsNotNone(result)

    def test_get_nonexistent_faq(self):
        from api.support.selectors import get_faq_by_id
        result = get_faq_by_id(99999)
        self.assertIsNone(result)