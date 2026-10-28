# api/djoyalty/tests/test_device_viewset.py
"""
CustomerDeviceViewSet tests -- register, deregister, my_devices, admin_all。
All 4 actions were previously untested (viewset was new this session)。
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

User = get_user_model()


def _setup():
    from djoyalty.models.core import Tenant, Customer
    t = Tenant.objects.create(name=f'DevCo-{Tenant.objects.count()}',
                               slug=f'dev-{Tenant.objects.count()}', is_active=True)
    u = User.objects.create_user(username=f'dv_{User.objects.count()}', password='pw')
    c = Customer.objects.create(tenant=t, user=u, code=f'DV{Customer.objects.count():04d}', is_active=True)
    return t, c

def _admin():
    u = User.objects.create_user(username=f'dva_{User.objects.count()}', password='pw', is_staff=True)
    cli = APIClient(); cli.force_authenticate(user=u)
    return cli

def _cli(customer):
    c = APIClient(); c.force_authenticate(user=customer.user)
    return c


class DeviceRegisterTest(TestCase):
    def setUp(self):
        self.tenant, self.customer = _setup()
        self.cli = _cli(self.customer)

    def test_register_android_device(self):
        resp = self.cli.post('/api/loyalty/devices/register/', {
            'customer_id': self.customer.pk,
            'token':       'FCM_TOKEN_ANDROID_ABCDEF',
            'platform':    'android',
            'device_id':   'device-001',
            'app_version': '2.5.0',
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data['status'], 'registered')
        self.assertEqual(resp.data['platform'], 'android')

    def test_register_ios_device(self):
        resp = self.cli.post('/api/loyalty/devices/register/', {
            'customer_id': self.customer.pk,
            'token':       'APNS_TOKEN_IOS_XYZUVW',
            'platform':    'ios',
            'device_id':   'device-ios-001',
        })
        self.assertIn(resp.status_code, [status.HTTP_200_OK, status.HTTP_201_CREATED])
        self.assertIn(resp.data['status'], ['registered', 'updated'])

    def test_register_updates_existing(self):
        """Second registration with same device_id updates rather than creates duplicate."""
        payload = {
            'customer_id': self.customer.pk,
            'token':       'OLD_TOKEN',
            'platform':    'android',
            'device_id':   'device-dup',
        }
        self.cli.post('/api/loyalty/devices/register/', payload)
        payload['token'] = 'NEW_TOKEN'
        resp = self.cli.post('/api/loyalty/devices/register/', payload)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['status'], 'updated')
        from djoyalty.models.audit import CustomerDevice
        self.assertEqual(
            CustomerDevice.objects.filter(device_id='device-dup').count(), 1
        )

    def test_register_requires_token(self):
        resp = self.cli.post('/api/loyalty/devices/register/', {
            'customer_id': self.customer.pk, 'platform': 'android',
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_invalid_platform(self):
        resp = self.cli.post('/api/loyalty/devices/register/', {
            'customer_id': self.customer.pk,
            'token':       'TOKEN',
            'platform':    'windows_phone',
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_requires_auth(self):
        anon = APIClient()
        resp = anon.post('/api/loyalty/devices/register/', {
            'customer_id': self.customer.pk, 'token': 'T', 'platform': 'android',
        })
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)


class DeviceDeregisterTest(TestCase):
    def setUp(self):
        self.tenant, self.customer = _setup()
        self.cli = _cli(self.customer)
        from djoyalty.models.audit import CustomerDevice
        self.device = CustomerDevice.objects.create(
            customer=self.customer, tenant=self.tenant,
            push_token='TOKEN_TO_DEREGISTER', platform='android',
            device_id='dreg-001', is_active=True,
        )

    def test_deregister_device(self):
        resp = self.cli.post('/api/loyalty/devices/deregister/', {
            'customer_id': self.customer.pk,
            'token':       'TOKEN_TO_DEREGISTER',
        })
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['status'], 'deregistered')
        self.assertGreater(resp.data['updated'], 0)
        self.device.refresh_from_db()
        self.assertFalse(self.device.is_active)

    def test_deregister_requires_token(self):
        resp = self.cli.post('/api/loyalty/devices/deregister/', {
            'customer_id': self.customer.pk,
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


class DeviceMyDevicesTest(TestCase):
    def setUp(self):
        self.tenant, self.customer = _setup()
        self.cli = _cli(self.customer)
        from djoyalty.models.audit import CustomerDevice
        CustomerDevice.objects.create(
            customer=self.customer, tenant=self.tenant,
            push_token='MY_TOKEN_1', platform='android',
            device_id='my-001', is_active=True,
        )
        CustomerDevice.objects.create(
            customer=self.customer, tenant=self.tenant,
            push_token='MY_TOKEN_2', platform='ios',
            device_id='my-002', is_active=True,
        )

    def test_my_devices_returns_active(self):
        resp = self.cli.get(f'/api/loyalty/devices/my-devices/?customer_id={self.customer.pk}')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('devices', resp.data)
        self.assertEqual(len(resp.data['devices']), 2)
        device = resp.data['devices'][0]
        for field in ('device_id', 'platform', 'app_version', 'registered_at'):
            self.assertIn(field, device)

    def test_my_devices_excludes_inactive(self):
        from djoyalty.models.audit import CustomerDevice
        CustomerDevice.objects.create(
            customer=self.customer, tenant=self.tenant,
            push_token='INACTIVE', platform='android',
            device_id='inactive-001', is_active=False,
        )
        resp = self.cli.get(f'/api/loyalty/devices/my-devices/?customer_id={self.customer.pk}')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data['devices']), 2)


class DeviceAdminTest(TestCase):
    def setUp(self):
        self.tenant, self.customer = _setup()
        self.admin = _admin()
        from djoyalty.models.audit import CustomerDevice
        CustomerDevice.objects.create(
            customer=self.customer, tenant=self.tenant,
            push_token='ADMIN_TOKEN', platform='android',
            device_id='admin-001', is_active=True,
        )

    def test_admin_all_devices(self):
        resp = self.admin.get('/api/loyalty/devices/admin/all/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('count', resp.data)
        self.assertIn('devices', resp.data)
        self.assertGreaterEqual(resp.data['count'], 1)

    def test_admin_filter_by_platform(self):
        resp = self.admin.get('/api/loyalty/devices/admin/all/?platform=android')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        for d in resp.data['devices']:
            self.assertEqual(d['platform'], 'android')

    def test_admin_requires_admin(self):
        cli = _cli(self.customer)
        resp = cli.get('/api/loyalty/devices/admin/all/')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
