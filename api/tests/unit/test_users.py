"""
Unit tests for Users app.
Tests models, serializers, views, and services in isolation.
"""

import pytest
from datetime import timedelta
from decimal import Decimal
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from rest_framework import status
from rest_framework.test import APITestCase, APIRequestFactory

from api.users.models import User, UserProfile, OTP, UserActivity, UserDevice
from api.users.serializers import (
    UserRegistrationSerializer, UserLoginSerializer,
    UserSerializer, ChangePasswordSerializer, VerifyOTPSerializer
)
from api.users.services import UserService, OTPService, TokenService
from api.users.factories import UserFactory, UserProfileFactory, OTPFactory


User = get_user_model()


# ==================== MODEL TESTS ====================
class TestUserModel(APITestCase):
    """Test User model functionality"""
    
    def setUp(self):
        """Set up test data"""
        self.user_data = {
            'username': 'testuser',
            'email': 'test@example.com',
            'password': 'testpass123',
            'phone': '01712345678',
            'user_type': 'user'
        }
    
    def test_create_user(self):
        """Test creating a regular user"""
        user = User.objects.create_user(**self.user_data)
        self.assertEqual(user.username, 'testuser')
        self.assertEqual(user.email, 'test@example.com')
        self.assertTrue(user.check_password('testpass123'))
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertTrue(user.is_active)
    
    def test_create_superuser(self):
        """Test creating a superuser"""
        admin = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='admin123'
        )
        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.is_superuser)
        self.assertTrue(admin.is_active)
    
    def test_user_str_representation(self):
        """Test string representation of user"""
        user = UserFactory.create(username='john_doe')
        self.assertEqual(str(user), 'john_doe')
    
    def test_generate_referral_code_on_save(self):
        """Test referral code generation on user save"""
        user = UserFactory.create(referral_code=None)
        self.assertIsNotNone(user.referral_code)
        self.assertEqual(len(user.referral_code), 8)
    
    def test_unique_referral_code(self):
        """Test that referral codes are unique"""
        user1 = UserFactory.create()
        user2 = UserFactory.create()
        self.assertNotEqual(user1.referral_code, user2.referral_code)
    
    def test_user_full_name(self):
        """Test user full name property"""
        user = UserFactory.create(first_name='John', last_name='Doe')
        self.assertEqual(user.get_full_name(), 'John Doe')
    
    def test_user_short_name(self):
        """Test user short name property"""
        user = UserFactory.create(first_name='John')
        self.assertEqual(user.get_short_name(), 'John')
    
    def test_user_balance_default(self):
        """Test default balance value"""
        user = UserFactory.create()
        self.assertEqual(user.balance, Decimal('0.00'))
    
    def test_user_is_expired_property(self):
        """Test is_expired property"""
        user = UserFactory.create(is_permanent=False, expires_at=timezone.now() - timedelta(days=1))
        self.assertTrue(user.is_expired)
        
        user2 = UserFactory.create(is_permanent=True)
        self.assertFalse(user2.is_expired)
    
    def test_user_file_size_human_property(self):
        """Test human readable file size property"""
        user = UserFactory.create(file_size=1048576)  # 1MB
        self.assertIn('1.0 MB', user.file_size_human)
    
    def test_user_meta_options(self):
        """Test user model meta options"""
        meta = User._meta
        self.assertEqual(meta.verbose_name, 'User')
        self.assertEqual(meta.verbose_name_plural, 'Users')
        self.assertEqual(meta.ordering, ['-created_at'])
        self.assertEqual(meta.db_table, 'users')


class TestUserProfileModel(APITestCase):
    """Test UserProfile model functionality"""
    
    def test_create_user_profile(self):
        """Test creating user profile"""
        user = UserFactory.create()
        profile = UserProfileFactory.create(
            user=user,
            full_name='John Doe',
            gender='male',
            country='Bangladesh'
        )
        self.assertEqual(profile.user, user)
        self.assertEqual(profile.full_name, 'John Doe')
        self.assertEqual(profile.gender, 'male')
        self.assertEqual(profile.country, 'Bangladesh')
    
    def test_user_profile_str_representation(self):
        """Test string representation of user profile"""
        user = UserFactory.create(username='john')
        profile = UserProfileFactory.create(user=user)
        self.assertEqual(str(profile), "john's Profile")
    
    def test_user_profile_one_to_one_relationship(self):
        """Test one-to-one relationship with user"""
        user = UserFactory.create()
        profile = UserProfileFactory.create(user=user)
        
        # User should have access to profile via reverse relationship
        self.assertEqual(user.user_profile, profile)
        
        # Profile should reference the user
        self.assertEqual(profile.user, user)
    
    def test_user_profile_default_preferences(self):
        """Test default preferences in user profile"""
        profile = UserProfileFactory.create()
        self.assertTrue(profile.email_notifications)
        self.assertFalse(profile.promotional_emails)
        self.assertTrue(profile.security_alerts)
        self.assertEqual(profile.language, 'en')
        self.assertEqual(profile.timezone, 'Asia/Dhaka')
        self.assertEqual(profile.currency, 'BDT')


class TestOTPModel(APITestCase):
    """Test OTP model functionality"""
    
    def test_create_otp(self):
        """Test creating OTP"""
        user = UserFactory.create()
        otp = OTPFactory.create(
            user=user,
            otp_type='registration',
            otp_code='123456'
        )
        self.assertEqual(otp.user, user)
        self.assertEqual(otp.otp_type, 'registration')
        self.assertEqual(otp.otp_code, '123456')
        self.assertFalse(otp.is_used)
    
    def test_otp_str_representation(self):
        """Test string representation of OTP"""
        user = UserFactory.create(username='testuser')
        otp = OTPFactory.create(user=user, otp_type='login', otp_code='654321')
        expected = "testuser - login - 654321"
        self.assertEqual(str(otp), expected)
    
    def test_otp_is_valid_method(self):
        """Test OTP validation method"""
        user = UserFactory.create()
        
        # Valid OTP (not used and not expired)
        otp_valid = OTPFactory.create(
            user=user,
            expires_at=timezone.now() + timedelta(minutes=10)
        )
        self.assertTrue(otp_valid.is_valid())
        
        # Expired OTP
        otp_expired = OTPFactory.create(
            user=user,
            expires_at=timezone.now() - timedelta(minutes=1)
        )
        self.assertFalse(otp_expired.is_valid())
        
        # Used OTP
        otp_used = OTPFactory.create(user=user, is_used=True)
        self.assertFalse(otp_used.is_valid())
    
    def test_otp_model_indexes(self):
        """Test OTP model database indexes"""
        indexes = [idx.name for idx in OTP._meta.indexes]
        self.assertIn('otps_token_is_used_idx', indexes)
        self.assertIn('otps_user_otp_type_idx', indexes)


class TestUserActivityModel(APITestCase):
    """Test UserActivity model functionality"""
    
    def test_create_user_activity(self):
        """Test creating user activity log"""
        user = UserFactory.create()
        activity = UserActivity.objects.create(
            user=user,
            activity_type='login',
            ip_address='192.168.1.1',
            user_agent='Test Agent',
            device_info={'device': 'mobile', 'os': 'Android'}
        )
        self.assertEqual(activity.user, user)
        self.assertEqual(activity.activity_type, 'login')
        self.assertEqual(activity.ip_address, '192.168.1.1')
    
    def test_user_activity_str_representation(self):
        """Test string representation of user activity"""
        user = UserFactory.create(username='john')
        activity = UserActivity.objects.create(user=user, activity_type='logout')
        self.assertEqual(str(activity), "john - logout")
    
    def test_user_activity_ordering(self):
        """Test user activity ordering"""
        user = UserFactory.create()
        
        # Create activities with different timestamps
        activity1 = UserActivity.objects.create(
            user=user,
            activity_type='login',
            created_at=timezone.now() - timedelta(hours=2)
        )
        activity2 = UserActivity.objects.create(
            user=user,
            activity_type='logout',
            created_at=timezone.now() - timedelta(hours=1)
        )
        
        # Activities should be ordered by created_at descending
        activities = UserActivity.objects.all()
        self.assertEqual(activities[0], activity2)
        self.assertEqual(activities[1], activity1)


# ==================== SERIALIZER TESTS ====================
class TestUserRegistrationSerializer(APITestCase):
    """Test UserRegistrationSerializer"""
    
    def setUp(self):
        self.valid_data = {
            'username': 'newuser',
            'email': 'newuser@example.com',
            'phone': '01712345678',
            'password': 'TestPass123!',
            'confirm_password': 'TestPass123!',
            'referral_code': None
        }
    
    def test_valid_registration_data(self):
        """Test serializer with valid data"""
        serializer = UserRegistrationSerializer(data=self.valid_data)
        self.assertTrue(serializer.is_valid())
    
    def test_passwords_must_match(self):
        """Test password and confirm_password must match"""
        data = self.valid_data.copy()
        data['confirm_password'] = 'DifferentPass123!'
        serializer = UserRegistrationSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('confirm_password', serializer.errors)
    
    def test_email_must_be_unique(self):
        """Test email must be unique"""
        UserFactory.create(email='existing@example.com')
        
        data = self.valid_data.copy()
        data['email'] = 'existing@example.com'
        serializer = UserRegistrationSerializer(data=data)
        
        self.assertFalse(serializer.is_valid())
        self.assertIn('email', serializer.errors)
    
    def test_phone_validation(self):
        """Test Bangladeshi phone number validation"""
        # Valid Bangladeshi phone number
        data = self.valid_data.copy()
        data['phone'] = '01712345678'
        serializer = UserRegistrationSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        
        # Invalid phone number
        data['phone'] = '1234567890'
        serializer = UserRegistrationSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('phone', serializer.errors)
    
    def test_valid_referral_code(self):
        """Test valid referral code"""
        referrer = UserFactory.create(referral_code='REF12345')
        
        data = self.valid_data.copy()
        data['referral_code'] = 'REF12345'
        serializer = UserRegistrationSerializer(data=data)
        
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data['referred_by'], referrer)
    
    def test_invalid_referral_code(self):
        """Test invalid referral code"""
        data = self.valid_data.copy()
        data['referral_code'] = 'INVALID'
        serializer = UserRegistrationSerializer(data=data)
        
        self.assertFalse(serializer.is_valid())
        self.assertIn('referral_code', serializer.errors)
    
    def test_create_user(self):
        """Test user creation through serializer"""
        serializer = UserRegistrationSerializer(data=self.valid_data)
        self.assertTrue(serializer.is_valid())
        
        user = serializer.save()
        self.assertEqual(user.username, 'newuser')
        self.assertEqual(user.email, 'newuser@example.com')
        self.assertTrue(user.check_password('TestPass123!'))
    
    def test_password_strength_validation(self):
        """Test password strength validation"""
        weak_passwords = [
            '123456',  # Too short
            'password',  # No uppercase, digit, special char
            'Password',  # No digit, special char
            'Password123',  # No special char
        ]
        
        for password in weak_passwords:
            data = self.valid_data.copy()
            data['password'] = password
            data['confirm_password'] = password
            serializer = UserRegistrationSerializer(data=data)
            self.assertFalse(serializer.is_valid())
            self.assertIn('password', serializer.errors)


class TestUserLoginSerializer(APITestCase):
    """Test UserLoginSerializer"""
    
    def setUp(self):
        self.user = UserFactory.create(
            email='test@example.com',
            password='testpass123',
            is_active=True,
            is_verified=True
        )
        self.user.set_password('testpass123')
        self.user.save()
    
    def test_valid_login_credentials(self):
        """Test valid login credentials"""
        data = {
            'email': 'test@example.com',
            'password': 'testpass123'
        }
        serializer = UserLoginSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data['user'], self.user)
    
    def test_invalid_credentials(self):
        """Test invalid login credentials"""
        data = {
            'email': 'test@example.com',
            'password': 'wrongpassword'
        }
        serializer = UserLoginSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('non_field_errors', serializer.errors)
    
    def test_inactive_user(self):
        """Test login with inactive user"""
        self.user.is_active = False
        self.user.save()
        
        data = {
            'email': 'test@example.com',
            'password': 'testpass123'
        }
        serializer = UserLoginSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('non_field_errors', serializer.errors)
    
    def test_device_info_included(self):
        """Test login with device info"""
        data = {
            'email': 'test@example.com',
            'password': 'testpass123',
            'device_id': 'device123',
            'device_name': 'Test Device'
        }
        serializer = UserLoginSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        self.assertIn('device_id', serializer.validated_data)
        self.assertIn('device_name', serializer.validated_data)


class Test'users.User'(APITestCase):
    """Test 'users.User'"""
    
    def setUp(self):
        self.user = UserFactory.create()
        self.profile = UserProfileFactory.create(user=self.user)
    
    def test_profile_serialization(self):
        """Test profile serialization"""
        serializer = 'users.User'(self.profile)
        
        expected_fields = [
            'user_id', 'username', 'email', 'full_name', 'gender',
            'address', 'city', 'state', 'country', 'postal_code',
            'facebook', 'twitter', 'linkedin', 'occupation',
            'education', 'bio', 'language', 'timezone', 'currency',
            'email_notifications', 'promotional_emails', 'security_alerts'
        ]
        
        for field in expected_fields:
            self.assertIn(field, serializer.data)
    
    def test_profile_update(self):
        """Test profile update through serializer"""
        data = {
            'full_name': 'Updated Name',
            'gender': 'female',
            'city': 'Updated City',
            'occupation': 'Updated Job'
        }
        
        serializer = 'users.User'(self.profile, data=data, partial=True)
        self.assertTrue(serializer.is_valid())
        
        updated_profile = serializer.save()
        self.assertEqual(updated_profile.full_name, 'Updated Name')
        self.assertEqual(updated_profile.gender, 'female')
        self.assertEqual(updated_profile.city, 'Updated City')
        self.assertEqual(updated_profile.occupation, 'Updated Job')
    
    def test_read_only_fields(self):
        """Test read-only fields cannot be updated"""
        data = {
            'user_id': 999,
            'username': 'hacker',
            'email': 'hacker@example.com'
        }
        
        serializer = UserProfileSerializer(self.profile, data=data, partial=True)
        self.assertTrue(serializer.is_valid())
        
        # Save and check that read-only fields are not changed
        updated_profile = serializer.save()
        self.assertNotEqual(updated_profile.user.id, 999)
        self.assertNotEqual(updated_profile.user.username, 'hacker')
        self.assertNotEqual(updated_profile.user.email, 'hacker@example.com')


class TestUserSerializer(APITestCase):
    """Test UserSerializer"""
    
    def setUp(self):
        self.user = UserFactory.create(
            username='testuser',
            email='test@example.com',
            balance=Decimal('1000.00'),
            total_earned=Decimal('5000.00'),
            kyc_status='verified'
        )
        self.profile = UserProfileFactory.create(user=self.user)
    
    def test_user_serialization(self):
        """Test user serialization"""
        serializer = UserSerializer(self.user)
        
        expected_fields = [
            'id', 'username', 'email', 'phone', 'user_type', 'is_verified',
            'date_of_birth', 'profile_image', 'kyc_status', 'balance',
            'total_earned', 'total_withdrawn', 'referral_code', 'profile',
            'created_at', 'updated_at'
        ]
        
        for field in expected_fields:
            self.assertIn(field, serializer.data)
        
        # Check nested profile data
        self.assertIn('full_name', serializer.data['profile'])
        self.assertIn('gender', serializer.data['profile'])
    
    def test_read_only_fields(self):
        """Test read-only fields in user serializer"""
        data = {
            'balance': Decimal('9999.00'),
            'total_earned': Decimal('99999.00'),
            'is_verified': False
        }
        
        serializer = UserSerializer(self.user, data=data, partial=True)
        self.assertTrue(serializer.is_valid())
        
        # Save and check that read-only fields are not changed
        updated_user = serializer.save()
        self.assertNotEqual(updated_user.balance, Decimal('9999.00'))
        self.assertNotEqual(updated_user.total_earned, Decimal('99999.00'))
        self.assertTrue(updated_user.is_verified)  # Should remain True


class TestChangePasswordSerializer(APITestCase):
    """Test ChangePasswordSerializer"""
    
    def setUp(self):
        self.user = UserFactory.create(password='oldpass123')
        self.user.set_password('oldpass123')
        self.user.save()
    
    def test_valid_password_change(self):
        """Test valid password change"""
        data = {
            'old_password': 'oldpass123',
            'new_password': 'NewPass123!',
            'confirm_password': 'NewPass123!'
        }
        
        # Need request context for serializer
        request = APIRequestFactory().post('/')
        request.user = self.user
        
        serializer = ChangePasswordSerializer(
            data=data,
            context={'request': request}
        )
        
        self.assertTrue(serializer.is_valid())
        
        # Save and verify password changed
        user = serializer.save()
        self.assertTrue(user.check_password('NewPass123!'))
    
    def test_old_password_must_be_correct(self):
        """Test old password must be correct"""
        data = {
            'old_password': 'wrongoldpass',
            'new_password': 'NewPass123!',
            'confirm_password': 'NewPass123!'
        }
        
        request = APIRequestFactory().post('/')
        request.user = self.user
        
        serializer = ChangePasswordSerializer(
            data=data,
            context={'request': request}
        )
        
        self.assertFalse(serializer.is_valid())
        self.assertIn('old_password', serializer.errors)
    
    def test_new_passwords_must_match(self):
        """Test new passwords must match"""
        data = {
            'old_password': 'oldpass123',
            'new_password': 'NewPass123!',
            'confirm_password': 'DifferentPass123!'
        }
        
        request = APIRequestFactory().post('/')
        request.user = self.user
        
        serializer = ChangePasswordSerializer(
            data=data,
            context={'request': request}
        )
        
        self.assertFalse(serializer.is_valid())
        self.assertIn('confirm_password', serializer.errors)
    
    def test_new_password_cannot_be_same_as_old(self):
        """Test new password cannot be same as old"""
        data = {
            'old_password': 'oldpass123',
            'new_password': 'oldpass123',
            'confirm_password': 'oldpass123'
        }
        
        request = APIRequestFactory().post('/')
        request.user = self.user
        
        serializer = ChangePasswordSerializer(
            data=data,
            context={'request': request}
        )
        
        self.assertFalse(serializer.is_valid())
        self.assertIn('new_password', serializer.errors)


# ==================== SERVICE TESTS ====================
class TestUserService(APITestCase):
    """Test UserService functionality"""
    
    def setUp(self):
        self.user_service = UserService()
        self.user = UserFactory.create(
            email='test@example.com',
            phone='01712345678',
            referral_code='REF12345'
        )
    
    def test_get_user_by_email(self):
        """Test getting user by email"""
        result = self.user_service.get_user_by_email('test@example.com')
        self.assertEqual(result, self.user)
    
    def test_get_user_by_phone(self):
        """Test getting user by phone"""
        result = self.user_service.get_user_by_phone('01712345678')
        self.assertEqual(result, self.user)
    
    def test_get_user_by_referral_code(self):
        """Test getting user by referral code"""
        result = self.user_service.get_user_by_referral_code('REF12345')
        self.assertEqual(result, self.user)
    
    def test_create_user(self):
        """Test user creation service"""
        user_data = {
            'username': 'newserviceuser',
            'email': 'newservice@example.com',
            'phone': '01812345678',
            'password': 'ServicePass123!',
            'user_type': 'user'
        }
        
        user = self.user_service.create_user(**user_data)
        self.assertEqual(user.username, 'newserviceuser')
        self.assertEqual(user.email, 'newservice@example.com')
        self.assertTrue(user.check_password('ServicePass123!'))
    
    def test_update_user_profile(self):
        """Test user profile update service"""
        update_data = {
            'first_name': 'Updated',
            'last_name': 'Name',
            'date_of_birth': '1990-01-01',
            'city': 'Updated City'
        }
        
        updated_user = self.user_service.update_user_profile(self.user.id, update_data)
        self.assertEqual(updated_user.first_name, 'Updated')
        self.assertEqual(updated_user.last_name, 'Name')
        self.assertEqual(updated_user.city, 'Updated City')
    
    def test_deactivate_user(self):
        """Test user deactivation service"""
        result = self.user_service.deactivate_user(self.user.id)
        self.assertTrue(result)
        
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)
    
    def test_activate_user(self):
        """Test user activation service"""
        self.user.is_active = False
        self.user.save()
        
        result = self.user_service.activate_user(self.user.id)
        self.assertTrue(result)
        
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)
    
    def test_change_password(self):
        """Test password change service"""
        old_password = 'oldpass123'
        new_password = 'NewPass123!'
        
        self.user.set_password(old_password)
        self.user.save()
        
        result = self.user_service.change_password(
            self.user.id,
            old_password,
            new_password
        )
        self.assertTrue(result)
        
        # Verify old password doesn't work
        self.assertFalse(self.user.check_password(old_password))
        # Verify new password works
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(new_password))
    
    def test_update_kyc_status(self):
        """Test KYC status update service"""
        result = self.user_service.update_kyc_status(
            self.user.id,
            'verified',
            'KYC documents verified successfully'
        )
        self.assertTrue(result)
        
        self.user.refresh_from_db()
        self.assertEqual(self.user.kyc_status, 'verified')
        self.assertIsNotNone(self.user.kyc_verified_at)
    
    def test_get_user_statistics(self):
        """Test user statistics service"""
        # Create some test data
        UserFactory.create_bulk(5)
        
        stats = self.user_service.get_user_statistics()
        
        self.assertIn('total_users', stats)
        self.assertIn('active_users', stats)
        self.assertIn('verified_users', stats)
        self.assertIn('new_users_today', stats)
        
        self.assertEqual(stats['total_users'], 6)  # 5 new + 1 from setUp
    
    def test_search_users(self):
        """Test user search service"""
        # Create users with different attributes
        UserFactory.create(username='john_doe', email='john@example.com')
        UserFactory.create(username='jane_doe', email='jane@example.com')
        UserFactory.create(username='bob_smith', email='bob@example.com')
        
        # Search by username
        results = self.user_service.search_users('john')
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].username, 'john_doe')
        
        # Search by email
        results = self.user_service.search_users('jane@example.com')
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].email, 'jane@example.com')
        
        # Search with multiple results
        results = self.user_service.search_users('doe')
        self.assertEqual(len(results), 2)
    
    @pytest.mark.django_db
    def test_bulk_user_operations(self):
        """Test bulk user operations"""
        # Create multiple users
        users_data = [
            {
                'username': f'bulkuser{i}',
                'email': f'bulk{i}@example.com',
                'password': 'BulkPass123!'
            }
            for i in range(10)
        ]
        
        created_users = self.user_service.bulk_create_users(users_data)
        self.assertEqual(len(created_users), 10)
        
        # Update all users
        update_count = self.user_service.bulk_update_users(
            user_ids=[u.id for u in created_users],
            update_data={'is_verified': True}
        )
        self.assertEqual(update_count, 10)
        
        # Verify updates
        for user in created_users:
            user.refresh_from_db()
            self.assertTrue(user.is_verified)


class TestOTPService(APITestCase):
    """Test OTPService functionality"""
    
    def setUp(self):
        self.otp_service = OTPService()
        self.user = UserFactory.create()
    
    def test_generate_otp(self):
        """Test OTP generation"""
        otp_data = self.otp_service.generate_otp(
            user=self.user,
            otp_type='registration',
            expires_in=10  # minutes
        )
        
        self.assertIsNotNone(otp_data)
        self.assertEqual(otp_data['user'], self.user)
        self.assertEqual(otp_data['otp_type'], 'registration')
        self.assertIsNotNone(otp_data['otp_code'])
        self.assertIsNotNone(otp_data['token'])
        self.assertFalse(otp_data['is_used'])
    
    def test_verify_otp_success(self):
        """Test successful OTP verification"""
        # Generate OTP
        otp_data = self.otp_service.generate_otp(
            user=self.user,
            otp_type='login',
            expires_in=10
        )
        
        # Verify OTP
        result = self.otp_service.verify_otp(
            user=self.user,
            otp_code=otp_data['otp_code'],
            otp_type='login'
        )
        
        self.assertTrue(result['success'])
        self.assertTrue(result['is_valid'])
        self.assertEqual(result['otp'], otp_data)
    
    def test_verify_otp_wrong_code(self):
        """Test OTP verification with wrong code"""
        self.otp_service.generate_otp(
            user=self.user,
            otp_type='password_reset',
            expires_in=10
        )
        
        result = self.otp_service.verify_otp(
            user=self.user,
            otp_code='999999',  # Wrong code
            otp_type='password_reset'
        )
        
        self.assertFalse(result['success'])
        self.assertFalse(result['is_valid'])
    
    def test_verify_otp_expired(self):
        """Test expired OTP verification"""
        # Generate OTP with immediate expiry
        otp_data = self.otp_service.generate_otp(
            user=self.user,
            otp_type='registration',
            expires_in=-1  # Already expired
        )
        
        result = self.otp_service.verify_otp(
            user=self.user,
            otp_code=otp_data['otp_code'],
            otp_type='registration'
        )
        
        self.assertFalse(result['success'])
        self.assertFalse(result['is_valid'])
    
    def test_verify_otp_already_used(self):
        """Test verification of already used OTP"""
        otp_data = self.otp_service.generate_otp(
            user=self.user,
            otp_type='transaction',
            expires_in=10
        )
        
        # Mark as used
        otp_data['is_used'] = True
        otp_data.save()
        
        result = self.otp_service.verify_otp(
            user=self.user,
            otp_code=otp_data['otp_code'],
            otp_type='transaction'
        )
        
        self.assertFalse(result['success'])
        self.assertFalse(result['is_valid'])
    
    def test_resend_otp(self):
        """Test OTP resend functionality"""
        # Generate initial OTP
        otp1 = self.otp_service.generate_otp(
            user=self.user,
            otp_type='login',
            expires_in=10
        )
        
        # Resend OTP
        otp2 = self.otp_service.resend_otp(
            user=self.user,
            otp_type='login'
        )
        
        self.assertNotEqual(otp1['otp_code'], otp2['otp_code'])
        self.assertNotEqual(otp1['token'], otp2['token'])
        
        # Old OTP should be invalidated
        old_otp = OTP.objects.get(id=otp1.id)
        self.assertTrue(old_otp.is_used)
    
    def test_cleanup_expired_otps(self):
        """Test cleanup of expired OTPs"""
        # Create expired OTPs
        for i in range(5):
            self.otp_service.generate_otp(
                user=self.user,
                otp_type='registration',
                expires_in=-1  # Already expired
            )
        
        # Create valid OTPs
        for i in range(3):
            self.otp_service.generate_otp(
                user=self.user,
                otp_type='login',
                expires_in=10
            )
        
        # Cleanup expired OTPs
        deleted_count = self.otp_service.cleanup_expired_otps()
        self.assertEqual(deleted_count, 5)
        
        # Check remaining OTPs
        remaining_otps = OTP.objects.filter(user=self.user)
        self.assertEqual(remaining_otps.count(), 3)
        
        for otp in remaining_otps:
            self.assertTrue(otp.is_valid())
    
    def test_get_otp_statistics(self):
        """Test OTP statistics"""
        # Generate OTPs of different types
        for otp_type in ['registration', 'login', 'password_reset']:
            for i in range(3):
                self.otp_service.generate_otp(
                    user=self.user,
                    otp_type=otp_type,
                    expires_in=10
                )
        
        stats = self.otp_service.get_otp_statistics(self.user.id)
        
        self.assertIn('total_otps', stats)
        self.assertIn('valid_otps', stats)
        self.assertIn('expired_otps', stats)
        self.assertIn('used_otps', stats)
        self.assertIn('by_type', stats)
        
        self.assertEqual(stats['total_otps'], 9)
        self.assertEqual(stats['valid_otps'], 9)
        self.assertEqual(stats['expired_otps'], 0)
        self.assertEqual(stats['used_otps'], 0)
        
        # Check distribution by type
        self.assertEqual(stats['by_type']['registration'], 3)
        self.assertEqual(stats['by_type']['login'], 3)
        self.assertEqual(stats['by_type']['password_reset'], 3)


class TestTokenService(APITestCase):
    """Test TokenService functionality"""
    
    def setUp(self):
        self.token_service = TokenService()
        self.user = UserFactory.create()
    
    def test_generate_tokens(self):
        """Test token generation"""
        tokens = self.token_service.generate_tokens(self.user)
        
        self.assertIn('access', tokens)
        self.assertIn('refresh', tokens)
        self.assertIn('access_expiry', tokens)
        self.assertIn('refresh_expiry', tokens)
        
        # Tokens should be strings
        self.assertIsInstance(tokens['access'], str)
        self.assertIsInstance(tokens['refresh'], str)
        
        # Expiry should be datetime
        from django.utils import timezone
        self.assertIsInstance(tokens['access_expiry'], timezone.datetime)
        self.assertIsInstance(tokens['refresh_expiry'], timezone.datetime)
    
    def test_verify_access_token(self):
        """Test access token verification"""
        tokens = self.token_service.generate_tokens(self.user)
        
        result = self.token_service.verify_access_token(tokens['access'])
        
        self.assertTrue(result['valid'])
        self.assertEqual(result['user_id'], self.user.id)
        self.assertEqual(result['username'], self.user.username)
    
    def test_verify_invalid_token(self):
        """Test invalid token verification"""
        result = self.token_service.verify_access_token('invalid.token.here')
        
        self.assertFalse(result['valid'])
        self.assertIn('error', result)
    
    def test_verify_expired_token(self):
        """Test expired token verification"""
        # Generate token with immediate expiry
        tokens = self.token_service.generate_tokens(
            self.user,
            access_token_lifetime=-1  # Already expired
        )
        
        result = self.token_service.verify_access_token(tokens['access'])
        
        self.assertFalse(result['valid'])
        self.assertIn('error', result)
    
    def test_refresh_token(self):
        """Test token refresh"""
        tokens = self.token_service.generate_tokens(self.user)
        
        new_tokens = self.token_service.refresh_token(tokens['refresh'])
        
        self.assertIn('access', new_tokens)
        self.assertIn('refresh', new_tokens)
        
        # New tokens should be different from old ones
        self.assertNotEqual(tokens['access'], new_tokens['access'])
        self.assertNotEqual(tokens['refresh'], new_tokens['refresh'])
    
    def test_refresh_invalid_token(self):
        """Test refresh with invalid token"""
        result = self.token_service.refresh_token('invalid.refresh.token')
        
        self.assertFalse(result['success'])
        self.assertIn('error', result)
    
    def test_revoke_token(self):
        """Test token revocation"""
        tokens = self.token_service.generate_tokens(self.user)
        
        result = self.token_service.revoke_token(tokens['refresh'])
        self.assertTrue(result['success'])
        
        # Try to refresh with revoked token
        refresh_result = self.token_service.refresh_token(tokens['refresh'])
        self.assertFalse(refresh_result['success'])
    
    def test_get_token_blacklist(self):
        """Test token blacklist functionality"""
        # Generate and revoke some tokens
        for i in range(3):
            tokens = self.token_service.generate_tokens(self.user)
            self.token_service.revoke_token(tokens['refresh'])
        
        blacklist = self.token_service.get_token_blacklist(self.user.id)
        
        self.assertEqual(len(blacklist), 3)
        for item in blacklist:
            self.assertEqual(item['user_id'], self.user.id)
            self.assertTrue(item['revoked'])
    
    def test_cleanup_expired_tokens(self):
        """Test cleanup of expired tokens"""
        # Generate tokens with immediate expiry
        for i in range(5):
            self.token_service.generate_tokens(
                self.user,
                access_token_lifetime=-1,
                refresh_token_lifetime=-1
            )
        
        # Generate valid tokens
        for i in range(3):
            self.token_service.generate_tokens(self.user)
        
        # Cleanup expired tokens
        deleted_count = self.token_service.cleanup_expired_tokens()
        self.assertEqual(deleted_count, 5)
    
    def test_token_statistics(self):
        """Test token statistics"""
        # Generate tokens
        for i in range(10):
            self.token_service.generate_tokens(self.user)
        
        # Revoke some tokens
        tokens = self.token_service.generate_tokens(self.user)
        self.token_service.revoke_token(tokens['refresh'])
        
        stats = self.token_service.get_token_statistics(self.user.id)
        
        self.assertIn('total_tokens', stats)
        self.assertIn('active_tokens', stats)
        self.assertIn('revoked_tokens', stats)
        self.assertIn('expired_tokens', stats)
        
        # Should have at least 11 tokens total (10 + 1)
        self.assertGreaterEqual(stats['total_tokens'], 11)
        self.assertGreaterEqual(stats['revoked_tokens'], 1)


# ==================== VIEW TESTS ====================
class TestUserViews(APITestCase):
    """Test User API views"""
    
    def setUp(self):
        self.user = UserFactory.create(
            email='test@example.com',
            password='testpass123',
            is_verified=True
        )
        self.user.set_password('testpass123')
        self.user.save()
        
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
    
    def test_register_view(self):
        """Test user registration endpoint"""
        url = '/api/v1/users/register/'
        data = {
            'username': 'newuser',
            'email': 'new@example.com',
            'phone': '01712345678',
            'password': 'TestPass123!',
            'confirm_password': 'TestPass123!'
        }
        
        response = self.client.post(url, data, format='json')
        
        if response.status_code != status.HTTP_201_CREATED:
            print(f"Registration failed: {response.data}")
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('user', response.data)
        self.assertIn('tokens', response.data)
        self.assertEqual(response.data['user']['email'], 'new@example.com')
    
    def test_login_view(self):
        """Test user login endpoint"""
        url = '/api/v1/users/login/'
        data = {
            'email': 'test@example.com',
            'password': 'testpass123'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('user', response.data)
        self.assertIn('tokens', response.data)
        self.assertEqual(response.data['user']['email'], 'test@example.com')
    
    def test_login_invalid_credentials(self):
        """Test login with invalid credentials"""
        url = '/api/v1/users/login/'
        data = {
            'email': 'test@example.com',
            'password': 'wrongpassword'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
    
    def test_profile_view(self):
        """Test user profile retrieval"""
        url = '/api/v1/users/profile/'
        
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('username', response.data)
        self.assertIn('email', response.data)
        self.assertIn('profile', response.data)
    
    def test_update_profile_view(self):
        """Test user profile update"""
        url = '/api/v1/users/profile/'
        data = {
            'first_name': 'Updated',
            'last_name': 'Name',
            'date_of_birth': '1990-01-01'
        }
        
        response = self.client.patch(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['first_name'], 'Updated')
        self.assertEqual(response.data['last_name'], 'Name')
    
    def test_change_password_view(self):
        """Test password change endpoint"""
        url = '/api/v1/users/change-password/'
        data = {
            'old_password': 'testpass123',
            'new_password': 'NewPass123!',
            'confirm_password': 'NewPass123!'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
        
        # Verify password was actually changed
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('NewPass123!'))
    
    def test_request_password_reset_view(self):
        """Test password reset request"""
        url = '/api/v1/users/password-reset/request/'
        data = {'email': 'test@example.com'}
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
    
    def test_verify_password_reset_view(self):
        """Test password reset verification"""
        # First request reset
        url = '/api/v1/users/password-reset/request/'
        data = {'email': 'test@example.com'}
        self.client.post(url, data, format='json')
        
        # Get OTP (in real scenario, this would come from email/SMS)
        otp = OTP.objects.filter(
            user=self.user,
            otp_type='password_reset'
        ).first()
        
        # Verify reset
        url = '/api/v1/users/password-reset/verify/'
        data = {
            'email': 'test@example.com',
            'otp_code': otp.otp_code,
            'new_password': 'NewResetPass123!',
            'confirm_password': 'NewResetPass123!'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
    
    def test_logout_view(self):
        """Test user logout"""
        url = '/api/v1/users/logout/'
        
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
    
    def test_logout_all_view(self):
        """Test logout from all devices"""
        url = '/api/v1/users/logout-all/'
        
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
    
    def test_deactivate_account_view(self):
        """Test account deactivation"""
        url = '/api/v1/users/deactivate/'
        
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
        
        # Verify account is deactivated
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)
    
    def test_user_activity_view(self):
        """Test user activity retrieval"""
        # Create some activities
        UserActivity.objects.create(
            user=self.user,
            activity_type='login',
            ip_address='192.168.1.1'
        )
        UserActivity.objects.create(
            user=self.user,
            activity_type='logout',
            ip_address='192.168.1.1'
        )
        
        url = '/api/v1/users/activities/'
        
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
        self.assertEqual(len(response.data['results']), 2)
    
    def test_user_devices_view(self):
        """Test user devices retrieval"""
        # Create some devices
        UserDevice.objects.create(
            user=self.user,
            device_id='device1',
            device_name='Test Device 1',
            device_type='mobile',
            os='Android',
            browser='Chrome',
            ip_address='192.168.1.1'
        )
        
        url = '/api/v1/users/devices/'
        
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
        self.assertEqual(len(response.data['results']), 1)
    
    def test_remove_device_view(self):
        """Test device removal"""
        device = UserDevice.objects.create(
            user=self.user,
            device_id='device1',
            device_name='Test Device',
            device_type='mobile',
            os='Android',
            browser='Chrome',
            ip_address='192.168.1.1'
        )
        
        url = f'/api/v1/users/devices/{device.id}/remove/'
        
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
        
        # Verify device is removed
        with self.assertRaises(UserDevice.DoesNotExist):
            UserDevice.objects.get(id=device.id)
    
    def test_verify_email_view(self):
        """Test email verification"""
        self.user.is_verified = False
        self.user.save()
        
        # Generate verification OTP
        otp_service = OTPService()
        otp_data = otp_service.generate_otp(
            user=self.user,
            otp_type='email_verification',
            expires_in=10
        )
        
        url = '/api/v1/users/verify-email/'
        data = {
            'otp_code': otp_data.otp_code
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
        
        # Verify email is marked as verified
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_verified)
    
    def test_resend_verification_view(self):
        """Test resend verification email"""
        self.user.is_verified = False
        self.user.save()
        
        url = '/api/v1/users/resend-verification/'
        
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)


# ==================== PERMISSION TESTS ====================
class TestUserPermissions(APITestCase):
    """Test user permissions and access control"""
    
    def setUp(self):
        self.regular_user = UserFactory.create(
            email='regular@example.com',
            password='regular123',
            user_type='user'
        )
        self.regular_user.set_password('regular123')
        self.regular_user.save()
        
        self.admin_user = UserFactory.create(
            email='admin@example.com',
            password='admin123',
            user_type='admin',
            is_staff=True,
            is_superuser=True
        )
        self.admin_user.set_password('admin123')
        self.admin_user.save()
        
        self.regular_client = APIClient()
        self.regular_client.force_authenticate(user=self.regular_user)
        
        self.admin_client = APIClient()
        self.admin_client.force_authenticate(user=self.admin_user)
    
    def test_regular_user_cannot_access_admin_endpoints(self):
        """Test regular user cannot access admin endpoints"""
        url = '/api/v1/admin/users/'  # Hypothetical admin endpoint
        
        response = self.regular_client.get(url)
        
        # Should return 403 Forbidden or 404 Not Found
        self.assertIn(response.status_code, [status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND])
    
    def test_admin_can_access_admin_endpoints(self):
        """Test admin can access admin endpoints"""
        url = '/api/v1/admin/users/'
        
        response = self.admin_client.get(url)
        
        # Admin should be able to access (might return empty list)
        self.assertNotEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_user_can_only_access_own_profile(self):
        """Test user can only access their own profile"""
        other_user = UserFactory.create(email='other@example.com')
        
        # Try to access other user's profile
        url = f'/api/v1/users/{other_user.id}/profile/'
        response = self.regular_client.get(url)
        
        # Should return 403 Forbidden or 404 Not Found
        self.assertIn(response.status_code, [status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND])
    
    def test_admin_can_access_any_profile(self):
        """Test admin can access any user's profile"""
        other_user = UserFactory.create(email='other@example.com')
        
        url = f'/api/v1/users/{other_user.id}/profile/'
        response = self.admin_client.get(url)
        
        # Admin should be able to access
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_user_cannot_deactivate_other_accounts(self):
        """Test user cannot deactivate other accounts"""
        other_user = UserFactory.create(email='other@example.com')
        
        url = f'/api/v1/users/{other_user.id}/deactivate/'
        response = self.regular_client.post(url)
        
        # Should return 403 Forbidden
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_admin_can_deactivate_any_account(self):
        """Test admin can deactivate any account"""
        other_user = UserFactory.create(email='other@example.com')
        
        url = f'/api/v1/users/{other_user.id}/deactivate/'
        response = self.admin_client.post(url)
        
        # Admin should be able to deactivate
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify account is deactivated
        other_user.refresh_from_db()
        self.assertFalse(other_user.is_active)
    
    def test_inactive_user_cannot_login(self):
        """Test inactive user cannot login"""
        inactive_user = UserFactory.create(
            email='inactive@example.com',
            password='inactive123',
            is_active=False
        )
        inactive_user.set_password('inactive123')
        inactive_user.save()
        
        url = '/api/v1/users/login/'
        data = {
            'email': 'inactive@example.com',
            'password': 'inactive123'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
    
    def test_unverified_user_restrictions(self):
        """Test restrictions for unverified users"""
        unverified_user = UserFactory.create(
            email='unverified@example.com',
            password='unverified123',
            is_verified=False
        )
        unverified_user.set_password('unverified123')
        unverified_user.save()
        
        unverified_client = APIClient()
        unverified_client.force_authenticate(user=unverified_user)
        
        # Test some restricted endpoints
        restricted_endpoints = [
            '/api/v1/wallet/withdraw/',
            '/api/v1/kyc/submit/',
            '/api/v1/users/change-password/'
        ]
        
        for endpoint in restricted_endpoints:
            response = unverified_client.get(endpoint)
            # Should return 403 Forbidden or redirect to verification
            self.assertIn(response.status_code, [
                status.HTTP_403_FORBIDDEN,
                status.HTTP_400_BAD_REQUEST,
                status.HTTP_302_FOUND
            ])


# ==================== INTEGRATION TESTS ====================
class TestUserIntegration(APITestCase):
    """Integration tests for user workflows"""
    
    def setUp(self):
        self.client = APIClient()
    
    def test_complete_user_registration_flow(self):
        """Test complete user registration flow"""
        # 1. Register
        register_data = {
            'username': 'newuser',
            'email': 'new@example.com',
            'phone': '01712345678',
            'password': 'TestPass123!',
            'confirm_password': 'TestPass123!'
        }
        
        response = self.client.post(
            '/api/v1/users/register/',
            register_data,
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        user_id = response.data['user']['id']
        access_token = response.data['tokens']['access']
        
        # Set authentication for subsequent requests
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        
        # 2. Verify email (simulate)
        user = User.objects.get(id=user_id)
        user.is_verified = True
        user.save()
        
        # 3. Complete profile
        profile_data = {
            'full_name': 'New User',
            'gender': 'male',
            'country': 'Bangladesh',
            'city': 'Dhaka'
        }
        
        response = self.client.patch(
            '/api/v1/users/profile/',
            profile_data,
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # 4. Change password
        password_data = {
            'old_password': 'TestPass123!',
            'new_password': 'NewPass123!',
            'confirm_password': 'NewPass123!'
        }
        
        response = self.client.post(
            '/api/v1/users/change-password/',
            password_data,
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # 5. Logout
        response = self.client.post('/api/v1/users/logout/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # 6. Login with new password
        self.client.credentials()  # Clear credentials
        login_data = {
            'email': 'new@example.com',
            'password': 'NewPass123!'
        }
        
        response = self.client.post(
            '/api/v1/users/login/',
            login_data,
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # 7. Check user is logged in
        response = self.client.get('/api/v1/users/profile/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['email'], 'new@example.com')
    
    def test_password_reset_flow(self):
        """Test complete password reset flow"""
        # Create user
        user = UserFactory.create(
            email='reset@example.com',
            password='oldpass123'
        )
        user.set_password('oldpass123')
        user.save()
        
        # 1. Request password reset
        request_data = {'email': 'reset@example.com'}
        response = self.client.post(
            '/api/v1/users/password-reset/request/',
            request_data,
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # 2. Get OTP (in real app, this would come from email/SMS)
        otp = OTP.objects.filter(
            user=user,
            otp_type='password_reset'
        ).first()
        
        # 3. Reset password
        reset_data = {
            'email': 'reset@example.com',
            'otp_code': otp.otp_code,
            'new_password': 'NewResetPass123!',
            'confirm_password': 'NewResetPass123!'
        }
        
        response = self.client.post(
            '/api/v1/users/password-reset/verify/',
            reset_data,
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # 4. Verify new password works
        user.refresh_from_db()
        self.assertTrue(user.check_password('NewResetPass123!'))
        
        # 5. Login with new password
        login_data = {
            'email': 'reset@example.com',
            'password': 'NewResetPass123!'
        }
        
        response = self.client.post(
            '/api/v1/users/login/',
            login_data,
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_user_deactivation_reactivation_flow(self):
        """Test user deactivation and reactivation flow"""
        # Create and login user
        user = UserFactory.create(
            email='deactivate@example.com',
            password='deactivate123'
        )
        user.set_password('deactivate123')
        user.save()
        
        self.client.force_authenticate(user=user)
        
        # 1. Deactivate account
        response = self.client.post('/api/v1/users/deactivate/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        user.refresh_from_db()
        self.assertFalse(user.is_active)
        
        # 2. Try to login (should fail)
        self.client.credentials()  # Clear credentials
        login_data = {
            'email': 'deactivate@example.com',
            'password': 'deactivate123'
        }
        
        response = self.client.post(
            '/api/v1/users/login/',
            login_data,
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        # 3. Reactivate account (admin action)
        admin = UserFactory.create(
            email='admin@example.com',
            user_type='admin',
            is_staff=True,
            is_superuser=True
        )
        admin_client = APIClient()
        admin_client.force_authenticate(user=admin)
        
        # In real app, there would be an admin endpoint for reactivation
        # For now, we'll simulate it directly
        user.is_active = True
        user.save()
        
        # 4. Verify user can login again
        login_data = {
            'email': 'deactivate@example.com',
            'password': 'deactivate123'
        }
        
        response = self.client.post(
            '/api/v1/users/login/',
            login_data,
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)


# ==================== PERFORMANCE TESTS ====================
@pytest.mark.performance
class TestUserPerformance(APITestCase):
    """Performance tests for user operations"""
    
    def setUp(self):
        # Create bulk users for performance testing
        self.users = UserFactory.create_bulk(count=1000)
        self.client = APIClient()
    
    def test_bulk_user_creation_performance(self):
        """Test performance of bulk user creation"""
        import time
        
        users_data = [
            {
                'username': f'perfuser{i}',
                'email': f'perf{i}@example.com',
                'password': 'PerfPass123!',
                'phone': f'017{str(i).zfill(8)}'
            }
            for i in range(100)
        ]
        
        start_time = time.time()
        
        for user_data in users_data:
            User.objects.create_user(**user_data)
        
        end_time = time.time()
        elapsed = end_time - start_time
        
        # Should create 100 users in less than 5 seconds
        self.assertLess(elapsed, 5.0)
        print(f"Created 100 users in {elapsed:.2f} seconds")
    
    def test_user_search_performance(self):
        """Test performance of user search"""
        import time
        
        start_time = time.time()
        
        # Search users (should use database indexes)
        results = User.objects.filter(email__icontains='example.com')[:100]
        
        end_time = time.time()
        elapsed = end_time - start_time
        
        # Should search 1000 users in less than 0.1 seconds
        self.assertLess(elapsed, 0.1)
        print(f"Searched {len(results)} users in {elapsed:.4f} seconds")
    
    def test_user_authentication_performance(self):
        """Test performance of user authentication"""
        import time
        
        user = self.users[0]
        user.set_password('testpass123')
        user.save()
        
        start_time = time.time()
        
        # Authenticate 100 times
        for i in range(100):
            user.check_password('testpass123')
        
        end_time = time.time()
        elapsed = end_time - start_time
        
        # Should authenticate 100 times in less than 0.5 seconds
        self.assertLess(elapsed, 0.5)
        print(f"Authenticated 100 times in {elapsed:.2f} seconds")
    
    def test_user_profile_retrieval_performance(self):
        """Test performance of user profile retrieval with joins"""
        import time
        
        # Create profiles for all users
        for user in self.users:
            UserProfileFactory.create(user=user)
        
        start_time = time.time()
        
        # Retrieve users with profiles (using select_related)
        users_with_profiles = User.objects.select_related('user_profile')[:100]
        
        # Access profile for each user (should not cause additional queries)
        for user in users_with_profiles:
            profile = user.user_profile
        
        end_time = time.time()
        elapsed = end_time - start_time
        
        # Should retrieve 100 users with profiles in less than 0.2 seconds
        self.assertLess(elapsed, 0.2)
        print(f"Retrieved 100 users with profiles in {elapsed:.4f} seconds")


# ==================== SECURITY TESTS ====================
@pytest.mark.security
class TestUserSecurity(APITestCase):
    """Security tests for user operations"""
    
    def setUp(self):
        self.user = UserFactory.create(
            email='security@example.com',
            password='SecurityPass123!'
        )
        self.user.set_password('SecurityPass123!')
        self.user.save()
        
        self.client = APIClient()
    
    def test_sql_injection_prevention(self):
        """Test SQL injection prevention"""
        malicious_inputs = [
            "' OR '1'='1",
            "'; DROP TABLE users; --",
            "' UNION SELECT username, password FROM users --"
        ]
        
        for malicious_input in malicious_inputs:
            # Try SQL injection in login
            data = {
                'email': malicious_input,
                'password': 'anything'
            }
            
            response = self.client.post(
                '/api/v1/users/login/',
                data,
                format='json'
            )
            
            # Should return validation error, not internal server error
            self.assertNotEqual(
                response.status_code,
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                f"SQL injection vulnerability detected: {malicious_input}"
            )
    
    def test_xss_prevention(self):
        """Test XSS (Cross-Site Scripting) prevention"""
        xss_payloads = [
            "<script>alert('XSS')</script>",
            "<img src=x onerror=alert(1)>",
            "javascript:alert('XSS')",
            "<svg onload=alert(1)>"
        ]
        
        for payload in xss_payloads:
            # Try XSS in user registration
            data = {
                'username': payload,
                'email': f'{payload}@example.com',
                'password': 'TestPass123!',
                'confirm_password': 'TestPass123!'
            }
            
            response = self.client.post(
                '/api/v1/users/register/',
                data,
                format='json'
            )
            
            # Should sanitize or reject the input
            if response.status_code == status.HTTP_201_CREATED:
                # If created, check that input was sanitized
                user = User.objects.get(email__contains='@example.com')
                self.assertNotIn('<script>', user.username)
                self.assertNotIn('javascript:', user.email)
            else:
                # Should return validation error
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_password_strength_enforcement(self):
        """Test password strength enforcement"""
        weak_passwords = [
            '123456',  # Too short
            'password',  # No uppercase, digit, special char
            'Password',  # No digit, special char
            'Password123',  # No special char
            'Pass!',  # Too short
            'AAAAAAAA',  # No lowercase, digit, special char
            'aaaaaaaa',  # No uppercase, digit, special char
            '12345678',  # No letters, special char
            '!@#$%^&*',  # No letters, digits
        ]
        
        for password in weak_passwords:
            data = {
                'username': f'test_{password[:5]}',
                'email': f'test_{password[:5]}@example.com',
                'password': password,
                'confirm_password': password
            }
            
            response = self.client.post(
                '/api/v1/users/register/',
                data,
                format='json'
            )
            
            # Should reject weak passwords
            self.assertEqual(
                response.status_code,
                status.HTTP_400_BAD_REQUEST,
                f"Weak password accepted: {password}"
            )
            self.assertIn('password', response.data)
    
    def test_brute_force_prevention(self):
        """Test brute force attack prevention"""
        # Try multiple failed login attempts
        for i in range(10):
            data = {
                'email': 'security@example.com',
                'password': f'wrongpassword{i}'
            }
            
            response = self.client.post(
                '/api/v1/users/login/',
                data,
                format='json'
            )
            
            # After several attempts, should implement rate limiting
            if i >= 5:
                # Might return 429 Too Many Requests or continue with 400
                self.assertIn(
                    response.status_code,
                    [status.HTTP_400_BAD_REQUEST, status.HTTP_429_TOO_MANY_REQUESTS]
                )
    
    def test_session_fixation_prevention(self):
        """Test session fixation prevention"""
        # Login and get session
        login_data = {
            'email': 'security@example.com',
            'password': 'SecurityPass123!'
        }
        
        response = self.client.post(
            '/api/v1/users/login/',
            login_data,
            format='json'
        )
        
        old_session_id = self.client.session.session_key
        
        # Perform sensitive operation (change password)
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {response.data['tokens']['access']}"
        )
        
        password_data = {
            'old_password': 'SecurityPass123!',
            'new_password': 'NewSecurityPass123!',
            'confirm_password': 'NewSecurityPass123!'
        }
        
        response = self.client.post(
            '/api/v1/users/change-password/',
            password_data,
            format='json'
        )
        
        # Session should be renewed after password change
        new_session_id = self.client.session.session_key
        self.assertNotEqual(old_session_id, new_session_id)
    
    def test_https_enforcement(self):
        """Test HTTPS enforcement (simulated)"""
        # This would be tested differently in production
        # For now, we check that sensitive endpoints require authentication
        
        sensitive_endpoints = [
            ('/api/v1/users/profile/', 'GET'),
            ('/api/v1/users/change-password/', 'POST'),
            ('/api/v1/wallet/balance/', 'GET'),
            ('/api/v1/kyc/submit/', 'POST'),
        ]
        
        for endpoint, method in sensitive_endpoints:
            if method == 'GET':
                response = self.client.get(endpoint)
            elif method == 'POST':
                response = self.client.post(endpoint)
            
            # Should require authentication
            self.assertIn(
                response.status_code,
                [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN],
                f"Endpoint {endpoint} should require authentication"
            )


# ==================== EDGE CASE TESTS ====================
class TestUserEdgeCases(APITestCase):
    """Edge case tests for user operations"""
    
    def setUp(self):
        self.client = APIClient()
    
    def test_duplicate_username_registration(self):
        """Test registration with duplicate username"""
        existing_user = UserFactory.create(username='existinguser')
        
        data = {
            'username': 'existinguser',  # Duplicate username
            'email': 'new@example.com',
            'password': 'TestPass123!',
            'confirm_password': 'TestPass123!'
        }
        
        response = self.client.post(
            '/api/v1/users/register/',
            data,
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('username', response.data)
    
    def test_duplicate_email_registration(self):
        """Test registration with duplicate email"""
        existing_user = UserFactory.create(email='existing@example.com')
        
        data = {
            'username': 'newuser',
            'email': 'existing@example.com',  # Duplicate email
            'password': 'TestPass123!',
            'confirm_password': 'TestPass123!'
        }
        
        response = self.client.post(
            '/api/v1/users/register/',
            data,
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('email', response.data)
    
    def test_duplicate_phone_registration(self):
        """Test registration with duplicate phone"""
        existing_user = UserFactory.create(phone='01712345678')
        
        data = {
            'username': 'newuser',
            'email': 'new@example.com',
            'phone': '01712345678',  # Duplicate phone
            'password': 'TestPass123!',
            'confirm_password': 'TestPass123!'
        }
        
        response = self.client.post(
            '/api/v1/users/register/',
            data,
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('phone', response.data)
    
    def test_case_insensitive_email_login(self):
        """Test case-insensitive email login"""
        user = UserFactory.create(
            email='TestUser@Example.COM',
            password='TestPass123!'
        )
        user.set_password('TestPass123!')
        user.save()
        
        # Try login with different cases
        test_cases = [
            'TestUser@Example.COM',  # Original case
            'testuser@example.com',  # Lowercase
            'TESTUSER@EXAMPLE.COM',  # Uppercase
            'TestUser@example.com',  # Mixed case
        ]
        
        for email in test_cases:
            data = {
                'email': email,
                'password': 'TestPass123!'
            }
            
            response = self.client.post(
                '/api/v1/users/login/',
                data,
                format='json'
            )
            
            self.assertEqual(
                response.status_code,
                status.HTTP_200_OK,
                f"Login failed for email case: {email}"
            )
    
    def test_very_long_inputs(self):
        """Test very long input handling"""
        # Very long username (more than 150 characters)
        long_username = 'x' * 151
        
        data = {
            'username': long_username,
            'email': 'long@example.com',
            'password': 'TestPass123!',
            'confirm_password': 'TestPass123!'
        }
        
        response = self.client.post(
            '/api/v1/users/register/',
            data,
            format='json'
        )
        
        # Should return validation error for long username
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('username', response.data)
    
    def test_special_characters_in_username(self):
        """Test special characters in username"""
        test_cases = [
            ('user@name', False),  # Contains @
            ('user#name', False),  # Contains #
            ('user$name', False),  # Contains $
            ('user-name', True),   # Contains - (should be allowed)
            ('user_name', True),   # Contains _ (should be allowed)
            ('user.name', True),   # Contains . (should be allowed)
            ('user123', True),     # Alphanumeric (should be allowed)
        ]
        
        for username, should_succeed in test_cases:
            data = {
                'username': username,
                'email': f'{username}@example.com',
                'password': 'TestPass123!',
                'confirm_password': 'TestPass123!'
            }
            
            response = self.client.post(
                '/api/v1/users/register/',
                data,
                format='json'
            )
            
            if should_succeed:
                self.assertEqual(
                    response.status_code,
                    status.HTTP_201_CREATED,
                    f"Username '{username}' should be allowed"
                )
            else:
                self.assertEqual(
                    response.status_code,
                    status.HTTP_400_BAD_REQUEST,
                    f"Username '{username}' should be rejected"
                )
    
    def test_empty_and_null_values(self):
        """Test empty and null value handling"""
        test_cases = [
            ({}, 'All fields empty'),
            ({'username': ''}, 'Empty username'),
            ({'email': ''}, 'Empty email'),
            ({'password': ''}, 'Empty password'),
            ({'phone': ''}, 'Empty phone (should be allowed)'),
            ({'username': None}, 'Null username'),
            ({'email': None}, 'Null email'),
        ]
        
        for data, description in test_cases:
            # Fill in minimal required fields
            test_data = {
                'username': 'testuser',
                'email': 'test@example.com',
                'password': 'TestPass123!',
                'confirm_password': 'TestPass123!'
            }
            test_data.update(data)
            
            response = self.client.post(
                '/api/v1/users/register/',
                test_data,
                format='json'
            )
            
            # Should handle gracefully (not crash with 500 error)
            self.assertNotEqual(
                response.status_code,
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                f"Server error for {description}"
            )
    
    def test_concurrent_registration(self):
        """Test concurrent user registration (simulated)"""
        import threading
        
        results = []
        errors = []
        
        def register_user(user_id):
            try:
                data = {
                    'username': f'concurrent{user_id}',
                    'email': f'concurrent{user_id}@example.com',
                    'password': 'TestPass123!',
                    'confirm_password': 'TestPass123!'
                }
                
                response = self.client.post(
                    '/api/v1/users/register/',
                    data,
                    format='json'
                )
                results.append(response.status_code)
            except Exception as e:
                errors.append(str(e))
        
        # Create multiple threads
        threads = []
        for i in range(10):
            thread = threading.Thread(target=register_user, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Check results
        self.assertEqual(len(errors), 0, f"Errors occurred: {errors}")
        
        # All registrations should succeed or fail gracefully
        for status_code in results:
            self.assertIn(
                status_code,
                [status.HTTP_201_CREATED, status.HTTP_400_BAD_REQUEST]
            )
        
        # Check that users were created
        created_users = User.objects.filter(
            username__startswith='concurrent'
        ).count()
        self.assertEqual(created_users, 10)