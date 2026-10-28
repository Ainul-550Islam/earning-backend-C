# api/djoyalty/tests/test_badge_extended.py
"""
Extended BadgeViewSet tests -- award, award_bulk, trigger_check, revoke, eligible।
Previously 0 of these 5 actions were tested。
"""
from decimal import Decimal
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

User = get_user_model()


def _setup():
    from djoyalty.models.core import Tenant, Customer
    from djoyalty.models.engagement import Badge
    tenant = Tenant.objects.create(name='BadgeCo', slug=f'b-{Tenant.objects.count()}', is_active=True)
    u = User.objects.create_user(username=f'bu_{User.objects.count()}', password='pw')
    customer = Customer.objects.create(tenant=tenant, user=u,
                                       code=f'B{Customer.objects.count():04d}', is_active=True)
    badge = Badge.objects.create(
        name='Bronze Badge', trigger='points_balance', threshold=Decimal('100'),
        points_reward=Decimal('50'), is_active=True, icon='🥉',
    )
    return tenant, customer, badge


def _admin():
    u = User.objects.create_user(username=f'ba_{User.objects.count()}', password='pw', is_staff=True)
    c = APIClient(); c.force_authenticate(user=u)
    return c

def _cli(customer):
    c = APIClient(); c.force_authenticate(user=customer.user)
    return c


class BadgeCatalogTest(TestCase):
    def setUp(self):
        self.tenant, self.customer, self.badge = _setup()
        self.cli   = _cli(self.customer)
        self.admin = _admin()

    def test_list_badges(self):
        resp = self.cli.get('/api/loyalty/badges/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_badge_detail(self):
        resp = self.cli.get(f'/api/loyalty/badges/{self.badge.pk}/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['name'], 'Bronze Badge')

    def test_my_badges_empty(self):
        resp = self.cli.get(
            f'/api/loyalty/badges/my-badges/?customer_id={self.customer.pk}'
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIsInstance(resp.data, list)

    def test_eligible_badges(self):
        resp = self.cli.get(
            f'/api/loyalty/badges/eligible/?customer_id={self.customer.pk}'
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('eligible', resp.data)
        if resp.data['eligible']:
            e = resp.data['eligible'][0]
            self.assertIn('badge', e)
            self.assertIn('progress_pct', e)
            self.assertIn('points_needed', e)


class BadgeAwardTest(TestCase):
    def setUp(self):
        self.tenant, self.customer, self.badge = _setup()
        self.admin = _admin()
        self.cli   = _cli(self.customer)

    @patch('djoyalty.viewsets.engagement.BadgeViewSet.BadgeService.award_specific')
    def test_admin_awards_badge(self, mock_award):
        from djoyalty.models.engagement import UserBadge
        mock_ub = MagicMock(spec=UserBadge)
        mock_ub.id        = 1
        mock_ub.badge     = self.badge
        mock_ub.customer  = self.customer
        mock_ub.earned_at = None
        mock_award.return_value = mock_ub
        resp = self.admin.post('/api/loyalty/badges/award/', {
            'customer_id': self.customer.pk,
            'badge_id':    self.badge.pk,
            'reason':      'Exceptional customer',
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data['status'], 'awarded')
        mock_award.assert_called_once()

    def test_award_requires_customer_and_badge(self):
        resp = self.admin.post('/api/loyalty/badges/award/', {'reason': 'test'})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_award_requires_admin(self):
        resp = self.cli.post('/api/loyalty/badges/award/', {
            'customer_id': self.customer.pk, 'badge_id': self.badge.pk,
        })
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_award_prevents_duplicate(self):
        from djoyalty.models.engagement import UserBadge
        UserBadge.objects.create(customer=self.customer, badge=self.badge)
        resp = self.admin.post('/api/loyalty/badges/award/', {
            'customer_id': self.customer.pk, 'badge_id': self.badge.pk,
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('already has', resp.data.get('error', ''))

    @patch('djoyalty.viewsets.engagement.BadgeViewSet.BadgeService.award_specific')
    def test_award_bulk(self, mock_award):
        from djoyalty.models.core import Customer
        from djoyalty.models.engagement import UserBadge
        c2 = Customer.objects.create(
            tenant=self.tenant,
            user=User.objects.create_user(username=f'b2_{User.objects.count()}', password='pw'),
            code=f'B2{Customer.objects.count():04d}', is_active=True,
        )
        mock_ub = MagicMock(spec=UserBadge)
        mock_award.return_value = mock_ub
        resp = self.admin.post('/api/loyalty/badges/award-bulk/', {
            'badge_id':     self.badge.pk,
            'customer_ids': [self.customer.pk, c2.pk],
            'reason':       'Campaign reward',
        })
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('awarded', resp.data)
        self.assertIn('skipped', resp.data)

    def test_award_bulk_requires_admin(self):
        resp = self.cli.post('/api/loyalty/badges/award-bulk/', {
            'badge_id': self.badge.pk, 'customer_ids': [self.customer.pk],
        })
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)


class BadgeTriggerCheckTest(TestCase):
    def setUp(self):
        self.tenant, self.customer, self.badge = _setup()
        self.admin = _admin()

    @patch('djoyalty.viewsets.engagement.BadgeViewSet.BadgeService.check_and_award')
    def test_trigger_check_awards_eligible(self, mock_check):
        from djoyalty.models.engagement import UserBadge
        mock_ub = MagicMock(spec=UserBadge)
        mock_check.return_value = [mock_ub]
        resp = self.admin.post('/api/loyalty/badges/trigger-check/', {
            'customer_id': self.customer.pk,
            'trigger':     'points_balance',
        })
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('badges_awarded', resp.data)
        self.assertEqual(resp.data['badges_awarded'], 1)
        mock_check.assert_called_once()

    @patch('djoyalty.viewsets.engagement.BadgeViewSet.BadgeService.check_and_award')
    def test_trigger_check_no_badges(self, mock_check):
        mock_check.return_value = []
        resp = self.admin.post('/api/loyalty/badges/trigger-check/', {
            'customer_id': self.customer.pk, 'trigger': 'purchase_count',
        })
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['badges_awarded'], 0)


class BadgeRevokeTest(TestCase):
    def setUp(self):
        self.tenant, self.customer, self.badge = _setup()
        self.admin = _admin()

    def test_revoke_existing_badge(self):
        from djoyalty.models.engagement import UserBadge
        ub = UserBadge.objects.create(customer=self.customer, badge=self.badge)
        resp = self.admin.delete(f'/api/loyalty/badges/{ub.pk}/revoke/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['status'], 'revoked')
        self.assertFalse(UserBadge.objects.filter(pk=ub.pk).exists())

    def test_revoke_nonexistent(self):
        resp = self.admin.delete('/api/loyalty/badges/99999/revoke/')
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_revoke_requires_admin(self):
        from djoyalty.models.engagement import UserBadge
        ub = UserBadge.objects.create(customer=self.customer, badge=self.badge)
        cli = _cli(self.customer)
        resp = cli.delete(f'/api/loyalty/badges/{ub.pk}/revoke/')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
