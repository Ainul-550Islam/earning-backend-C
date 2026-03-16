from django.test import TestCase
from ..serializers import UserSerializer, UserRegistrationSerializer
from ..factories import UserFactory


class UserSerializerTest(TestCase):
    
    def setUp(self):
        self.user = UserFactory()
    
    def test_user_serializer(self):
        serializer = UserSerializer(instance=self.user)
        data = serializer.data
        
        self.assertEqual(data['username'], self.user.username)
        self.assertEqual(data['email'], self.user.email)
        self.assertIn('profile', data)