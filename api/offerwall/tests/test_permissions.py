"""
tests/test_permissions.py

Tests for offerwall permission classes:
  - IsOfferProvider
  - IsOfferAdmin
  - IsConversionApprover
  - IsPublisher
  - IsOwnerOrAdmin

Run: python manage.py test api.offerwall.tests.test_permissions
"""
from decimal import Decimal
from unittest.mock import MagicMock
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from rest_framework.test import APIRequestFactory

User = get_user_model()


def make_user(username, is_staff=False):
    u = User.objects.create_user(username, password='pass')
    u.is_staff = is_staff
    u.save()
    return u


def make_request(user=None, method='GET'):
    factory = APIRequestFactory()
    req = getattr(factory, method.lower())('/')
    req.user = user or MagicMock(is_authenticated=False, is_staff=False)
    return req


# ─────────────────────────────────────────────────────────────────────────────
# IsOfferProvider
# ─────────────────────────────────────────────────────────────────────────────

class IsOfferProviderTest(TestCase):
    def setUp(self):
        from api.offerwall.permissions import IsOfferProvider
        self.perm = IsOfferProvider()
        self.user = make_user('isofferprov')

    def test_get_request_allowed(self):
        req = make_request(self.user, 'GET')
        self.assertTrue(self.perm.has_permission(req, None))

    def test_post_request_requires_auth(self):
        req = make_request(self.user, 'POST')
        self.assertTrue(self.perm.has_permission(req, None))

    def test_unauthenticated_post_denied(self):
        anon = MagicMock()
        anon.is_authenticated = False
        anon.is_staff = False
        req = make_request(anon, 'POST')
        req.user = anon
        # has_permission should return False for unauthenticated
        result = self.perm.has_permission(req, None)
        self.assertFalse(result)

    def test_admin_can_edit_any_offer(self):
        from api.offerwall.models import OfferProvider, Offer
        admin = make_user('opa_admin', is_staff=True)
        prov  = OfferProvider.objects.create(
            name='P', provider_type='tapjoy', status='active',
            api_key='k', revenue_share=Decimal('70'))
        offer = Offer.objects.create(
            provider=prov, external_offer_id='OPA1', title='O',
            payout=Decimal('1'), reward_amount=Decimal('0.7'), status='active')
        req = make_request(admin, 'PUT')
        self.assertTrue(self.perm.has_object_permission(req, None, offer))


# ─────────────────────────────────────────────────────────────────────────────
# IsOfferAdmin
# ─────────────────────────────────────────────────────────────────────────────

class IsOfferAdminTest(TestCase):
    def setUp(self):
        from api.offerwall.permissions import IsOfferAdmin
        self.perm  = IsOfferAdmin()
        self.admin = make_user('isoffadm', is_staff=True)
        self.user  = make_user('isoffadm_regular')

    def test_staff_user_allowed(self):
        req = make_request(self.admin)
        self.assertTrue(self.perm.has_permission(req, None))

    def test_regular_user_denied(self):
        req = make_request(self.user)
        self.assertFalse(self.perm.has_permission(req, None))

    def test_unauthenticated_denied(self):
        anon = MagicMock(is_authenticated=False, is_staff=False)
        req  = make_request(anon)
        req.user = anon
        self.assertFalse(self.perm.has_permission(req, None))


# ─────────────────────────────────────────────────────────────────────────────
# IsConversionApprover
# ─────────────────────────────────────────────────────────────────────────────

class IsConversionApproverTest(TestCase):
    def setUp(self):
        from api.offerwall.permissions import IsConversionApprover
        self.perm    = IsConversionApprover()
        self.admin   = make_user('ica_admin', is_staff=True)
        self.regular = make_user('ica_regular')
        self.approver = make_user('ica_approver')
        group, _ = Group.objects.get_or_create(name='conversion_approvers')
        self.approver.groups.add(group)

    def test_staff_allowed(self):
        req = make_request(self.admin)
        self.assertTrue(self.perm.has_permission(req, None))

    def test_approver_group_member_allowed(self):
        req = make_request(self.approver)
        self.assertTrue(self.perm.has_permission(req, None))

    def test_regular_user_denied(self):
        req = make_request(self.regular)
        self.assertFalse(self.perm.has_permission(req, None))

    def test_user_cannot_approve_own_conversion(self):
        import uuid
        from api.offerwall.models import OfferProvider, Offer, OfferConversion
        prov  = OfferProvider.objects.create(
            name='ICAProv', provider_type='tapjoy', status='active',
            api_key='k', revenue_share=Decimal('70'))
        offer = Offer.objects.create(
            provider=prov, external_offer_id='ICA1', title='O',
            payout=Decimal('1'), reward_amount=Decimal('0.7'), status='active')
        conv = OfferConversion.objects.create(
            offer=offer, user=self.approver,
            conversion_id=uuid.uuid4().hex,
            payout_amount=Decimal('1'), reward_amount=Decimal('0.7'),
            status='pending')
        req      = make_request(self.approver, 'POST')
        allowed  = self.perm.has_object_permission(req, None, conv)
        self.assertFalse(allowed)

    def test_approver_can_approve_others_conversion(self):
        import uuid
        from api.offerwall.models import OfferProvider, Offer, OfferConversion
        owner = make_user('ica_conv_owner')
        prov  = OfferProvider.objects.create(
            name='ICAProv2', provider_type='tapjoy', status='active',
            api_key='k2', revenue_share=Decimal('70'))
        offer = Offer.objects.create(
            provider=prov, external_offer_id='ICA2', title='O',
            payout=Decimal('1'), reward_amount=Decimal('0.7'), status='active')
        conv = OfferConversion.objects.create(
            offer=offer, user=owner,
            conversion_id=uuid.uuid4().hex,
            payout_amount=Decimal('1'), reward_amount=Decimal('0.7'),
            status='pending')
        req     = make_request(self.approver, 'POST')
        allowed = self.perm.has_object_permission(req, None, conv)
        self.assertTrue(allowed)


# ─────────────────────────────────────────────────────────────────────────────
# IsPublisher
# ─────────────────────────────────────────────────────────────────────────────

class IsPublisherTest(TestCase):
    def setUp(self):
        from api.offerwall.permissions import IsPublisher
        self.perm  = IsPublisher()
        self.admin = make_user('ispub_admin', is_staff=True)
        self.user  = make_user('ispub_user')
        self.user2 = make_user('ispub_user2')

    def test_authenticated_get_allowed(self):
        req = make_request(self.user, 'GET')
        self.assertTrue(self.perm.has_permission(req, None))

    def test_admin_can_access_any_lock(self):
        obj = MagicMock(publisher=self.user)
        req = make_request(self.admin, 'PUT')
        self.assertTrue(self.perm.has_object_permission(req, None, obj))

    def test_owner_can_access_own_lock(self):
        obj = MagicMock(publisher=self.user)
        req = make_request(self.user, 'PUT')
        self.assertTrue(self.perm.has_object_permission(req, None, obj))

    def test_non_owner_cannot_access_others_lock(self):
        obj = MagicMock(publisher=self.user)
        req = make_request(self.user2, 'PUT')
        self.assertFalse(self.perm.has_object_permission(req, None, obj))


# ─────────────────────────────────────────────────────────────────────────────
# IsOwnerOrAdmin
# ─────────────────────────────────────────────────────────────────────────────

class IsOwnerOrAdminTest(TestCase):
    def setUp(self):
        from api.offerwall.permissions import IsOwnerOrAdmin
        self.perm  = IsOwnerOrAdmin()
        self.admin = make_user('ioa_admin', is_staff=True)
        self.user  = make_user('ioa_user')
        self.user2 = make_user('ioa_user2')

    def test_unauthenticated_denied(self):
        anon = MagicMock(is_authenticated=False)
        req  = make_request(anon)
        req.user = anon
        self.assertFalse(self.perm.has_permission(req, None))

    def test_authenticated_get_allowed(self):
        req = make_request(self.user, 'GET')
        self.assertTrue(self.perm.has_object_permission(req, None, MagicMock(user=self.user)))

    def test_admin_can_put_any_object(self):
        obj = MagicMock(user=self.user)
        req = make_request(self.admin, 'PUT')
        self.assertTrue(self.perm.has_object_permission(req, None, obj))

    def test_owner_can_put_own_object(self):
        obj = MagicMock(user=self.user, spec=['user'])
        req = make_request(self.user, 'PUT')
        self.assertTrue(self.perm.has_object_permission(req, None, obj))

    def test_non_owner_cannot_put_others_object(self):
        obj = MagicMock(user=self.user, spec=['user'])
        req = make_request(self.user2, 'PUT')
        self.assertFalse(self.perm.has_object_permission(req, None, obj))

    def test_owner_field_fallback_to_created_by(self):
        obj = MagicMock(spec=['created_by'])
        obj.created_by = self.user
        req = make_request(self.user, 'DELETE')
        self.assertTrue(self.perm.has_object_permission(req, None, obj))
