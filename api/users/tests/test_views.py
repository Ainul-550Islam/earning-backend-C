from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from ..factories import UserFactory


class UserRegistrationTest(APITestCase):
    
    def test_user_registration(self):
        url = reverse('user-register')
        data = {
            'username': 'testuser',
            'email': 'test@example.com',
            'phone': '+8801700000000',
            'password': 'Test@1234',
            'confirm_password': 'Test@1234'
        }
        
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('user_id', response.data['data'])


class UserLoginTest(APITestCase):
    
    def setUp(self):
        self.user = UserFactory()
    
    def test_user_login(self):
        url = reverse('user-login')
        data = {
            'username_or_email': self.user.username,
            'password': 'testpass123'
        }
        
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data['data'])