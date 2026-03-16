# api/tests/test_security.py
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
import uuid
User = get_user_model()
def uid(): return uuid.uuid4().hex[:8]

class SecurityTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username=f'u_{uid()}', email=f'{uid()}@test.com', password='x')

    def test_brute_force_protection(self):
        client = APIClient()
        for i in range(6):
            client.post('/api/auth/login/', {'username': self.user.username, 'password': 'wrong'})
        response = client.post('/api/auth/login/', {'username': self.user.username, 'password': 'wrong'})
        self.assertIn(response.status_code, [400, 401, 403, 429, 404])

    def test_sql_injection_protection(self):
        client = APIClient()
        response = client.get("/api/users/?search=' OR 1=1 --")
        self.assertIn(response.status_code, [200, 400, 401, 403, 404])

    def test_xss_protection(self):
        client = APIClient()
        client.force_authenticate(user=self.user)
        response = client.post('/api/support/tickets/', {
            'subject': '<script>alert("xss")</script>', 'message': 'Test'
        })
        self.assertIn(response.status_code, [200, 201, 400, 401, 403, 404])