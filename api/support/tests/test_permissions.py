# api/support/tests/test_permissions.py
"""Tests for support permissions."""
from django.test import TestCase
from rest_framework.test import APIRequestFactory


def make_user(username='perm_u', staff=False):
    from django.contrib.auth import get_user_model
    User = get_user_model()
    return User.objects.create_user(
        username=username, email=f'{username}@t.com', password='p', is_staff=staff
    )


class IsSupportAgentTest(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

    def _req(self, user):
        req = self.factory.get('/')
        req.user = user
        return req

    def test_staff_is_agent(self):
        from api.support.permissions import IsSupportAgent
        user = make_user('staff_a', staff=True)
        self.assertTrue(IsSupportAgent().has_permission(self._req(user), None))

    def test_regular_user_is_not_agent(self):
        from api.support.permissions import IsSupportAgent
        user = make_user('reg_a')
        self.assertFalse(IsSupportAgent().has_permission(self._req(user), None))

    def test_user_with_agent_profile_is_agent(self):
        from api.support.permissions import IsSupportAgent
        from api.support.models import SupportAgent
        user  = make_user('agent_a')
        agent = SupportAgent.objects.create(user=user, role='agent', is_active=True)
        self.assertTrue(IsSupportAgent().has_permission(self._req(user), None))


class IsTicketOwnerTest(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

    def test_owner_can_access(self):
        from api.support.permissions import IsTicketOwnerOrAgent
        from api.support.models import SupportTicket
        user   = make_user('owner_t')
        ticket = SupportTicket.objects.create(
            user=user, subject='T', description='D', category='technical'
        )
        req    = self.factory.get('/')
        req.user = user
        self.assertTrue(IsTicketOwnerOrAgent().has_object_permission(req, None, ticket))

    def test_non_owner_cannot_access(self):
        from api.support.permissions import IsTicketOwnerOrAgent
        from api.support.models import SupportTicket
        owner  = make_user('real_owner')
        other  = make_user('not_owner')
        ticket = SupportTicket.objects.create(
            user=owner, subject='T', description='D', category='technical'
        )
        req      = self.factory.get('/')
        req.user = other
        self.assertFalse(IsTicketOwnerOrAgent().has_object_permission(req, None, ticket))

    def test_staff_can_access_any(self):
        from api.support.permissions import IsTicketOwnerOrAgent
        from api.support.models import SupportTicket
        owner  = make_user('owner_s')
        staff  = make_user('staff_s', staff=True)
        ticket = SupportTicket.objects.create(
            user=owner, subject='T', description='D', category='technical'
        )
        req      = self.factory.get('/')
        req.user = staff
        self.assertTrue(IsTicketOwnerOrAgent().has_object_permission(req, None, ticket))