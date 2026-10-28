# api/support/tests/test_repositories.py
"""Tests for repository layer."""
from django.test import TestCase


def make_user(un='repo_u'):
    from django.contrib.auth import get_user_model
    User = get_user_model()
    return User.objects.create_user(username=un, email=f'{un}@t.com', password='p')


class TicketRepositoryTest(TestCase):
    def test_get_by_ticket_id(self):
        from api.support.models import SupportTicket
        from api.support.repositories import ticket_repo
        u = make_user('tr1')
        t = SupportTicket.objects.create(
            user=u, subject='S', description='D', category='technical'
        )
        result = ticket_repo.get_by_ticket_id(t.ticket_id)
        self.assertIsNotNone(result)
        self.assertEqual(result.id, t.id)

    def test_get_nonexistent(self):
        from api.support.repositories import ticket_repo
        result = ticket_repo.get_by_ticket_id('TKT000000')
        self.assertIsNone(result)

    def test_create(self):
        from api.support.repositories import ticket_repo
        u = make_user('tr2')
        t = ticket_repo.create(
            user=u, subject='S', description='D', category='technical'
        )
        self.assertIsNotNone(t.id)

    def test_count_by_status(self):
        from api.support.repositories import ticket_repo
        counts = ticket_repo.count_by_status()
        self.assertIsInstance(counts, dict)


class DisputeRepositoryTest(TestCase):
    def test_create_offer_dispute(self):
        from api.support.repositories import dispute_repo
        u = make_user('dr1')
        d = dispute_repo.create_offer_dispute(
            user=u, offer_id='OFF1', expected_amount=50
        )
        self.assertIsNotNone(d.id)

    def test_count_weekly_disputes(self):
        from api.support.repositories import dispute_repo
        u     = make_user('dr2')
        count = dispute_repo.count_user_disputes_this_week(u)
        self.assertEqual(count, 0)


class SLARepositoryTest(TestCase):
    def test_create_sla(self):
        from api.support.models import SupportTicket
        from api.support.repositories import sla_repo
        from django.utils import timezone
        from datetime import timedelta
        u      = make_user('sla_r')
        ticket = SupportTicket.objects.create(
            user=u, subject='S', description='D', category='technical'
        )
        sla = sla_repo.create_for_ticket(
            ticket,
            first_response_due=timezone.now() + timedelta(hours=8),
            resolution_due=timezone.now() + timedelta(hours=48),
        )
        self.assertIsNotNone(sla.id)

    def test_get_for_ticket(self):
        from api.support.models import SupportTicket, TicketSLA
        from api.support.repositories import sla_repo
        from django.utils import timezone
        from datetime import timedelta
        u      = make_user('sla_r2')
        ticket = SupportTicket.objects.create(
            user=u, subject='S', description='D', category='technical'
        )
        TicketSLA.objects.create(
            ticket=ticket,
            first_response_due=timezone.now() + timedelta(hours=8),
            resolution_due=timezone.now() + timedelta(hours=48),
        )
        sla = sla_repo.get_for_ticket(ticket)
        self.assertIsNotNone(sla)