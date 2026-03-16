"""
Factory for creating User model instances for testing.
Uses Factory Boy for flexible test data generation.
"""

import factory
from factory import Faker, LazyAttribute, SubFactory, post_generation
from factory.django import DjangoModelFactory
from django.contrib.auth import get_user_model
from django.utils import timezone
from decimal import Decimal
import random
import string

User = get_user_model()


class UserFactory(DjangoModelFactory):
    """Factory for creating User instances"""
    
    class Meta:
        model = User
        django_get_or_create = ['username']
    
    # Basic information
    username = Faker('user_name')
    email = Faker('email')
    first_name = Faker('first_name')
    last_name = Faker('last_name')
    password = factory.PostGenerationMethodCall('set_password', 'testpass123')
    
    # Custom fields
    phone = Faker('phone_number')
    user_type = factory.Iterator(['user', 'agent', 'merchant'])
    is_verified = True
    is_active = True
    is_staff = False
    is_superuser = False
    date_of_birth = Faker('date_of_birth', minimum_age=18, maximum_age=65)
    
    # Financial fields
    balance = LazyAttribute(lambda x: Decimal(str(round(random.uniform(0, 10000), 2))))
    total_earned = LazyAttribute(lambda x: Decimal(str(round(random.uniform(100, 50000), 2))))
    total_withdrawn = LazyAttribute(lambda x: Decimal(str(round(random.uniform(0, 10000), 2))))
    
    # KYC fields
    kyc_status = factory.Iterator(['pending', 'verified', 'rejected'])
    kyc_verified_at = factory.LazyFunction(timezone.now)
    
    # Referral fields
    referral_code = factory.LazyFunction(
        lambda: ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
    )
    
    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        """Override to handle referral code generation"""
        manager = cls._get_manager(model_class)
        
        # Generate unique referral code if not provided
        if 'referral_code' not in kwargs or not kwargs['referral_code']:
            while True:
                code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
                if not User.objects.filter(referral_code=code).exists():
                    kwargs['referral_code'] = code
                    break
        
        return manager.create(*args, **kwargs)
    
    @post_generation
    def groups(self, create, extracted, **kwargs):
        """Add groups to user"""
        if not create:
            return
        
        if extracted:
            for group in extracted:
                self.groups.add(group)
    
    @post_generation
    def user_permissions(self, create, extracted, **kwargs):
        """Add permissions to user"""
        if not create:
            return
        
        if extracted:
            for permission in extracted:
                self.user_permissions.add(permission)
    
    # Alternative constructors for specific user types
    @classmethod
    def create_admin(cls, **kwargs):
        """Create an admin user"""
        return cls.create(
            username='admin',
            email='admin@example.com',
            user_type='admin',
            is_staff=True,
            is_superuser=True,
            **kwargs
        )
    
    @classmethod
    def create_inactive(cls, **kwargs):
        """Create an inactive user"""
        return cls.create(
            is_active=False,
            is_verified=False,
            **kwargs
        )
    
    @classmethod
    def create_with_balance(cls, balance_amount, **kwargs):
        """Create user with specific balance"""
        return cls.create(
            balance=Decimal(str(balance_amount)),
            total_earned=Decimal(str(balance_amount * 5)),
            **kwargs
        )
    
    @classmethod
    def create_verified_kyc(cls, **kwargs):
        """Create user with verified KYC"""
        return cls.create(
            kyc_status='verified',
            kyc_verified_at=timezone.now(),
            **kwargs
        )
    
    @classmethod
    def create_bulk(cls, count=10, **kwargs):
        """Create multiple users at once"""
        users = []
        for i in range(count):
            user = cls.create(
                username=f'user_{i}_{random.randint(1000, 9999)}',
                email=f'user{i}@example.com',
                **kwargs
            )
            users.append(user)
        return users


class UserProfileFactory(DjangoModelFactory):
    """Factory for creating UserProfile instances"""
    
    class Meta:
        model = 'users.UserProfile'
        django_get_or_create = ['user']
    
    user = SubFactory(UserFactory)
    full_name = Faker('name')
    gender = factory.Iterator(['male', 'female', 'other'])
    address = Faker('address')
    city = Faker('city')
    state = Faker('state')
    country = 'Bangladesh'
    postal_code = Faker('postcode')
    
    # Social links
    facebook = Faker('url')
    twitter = Faker('url')
    linkedin = Faker('url')
    
    # Additional info
    occupation = factory.Iterator(['Student', 'Developer', 'Business', 'Freelancer', 'Other'])
    education = factory.Iterator(['High School', 'Bachelor', 'Master', 'PhD', 'Other'])
    bio = Faker('text', max_nb_chars=200)
    
    # Preferences
    language = factory.Iterator(['en', 'bn', 'ar', 'es'])
    timezone = factory.Iterator(['Asia/Dhaka', 'UTC', 'America/New_York'])
    currency = factory.Iterator(['BDT', 'USD', 'EUR', 'INR'])
    
    # Email preferences
    email_notifications = True
    promotional_emails = False
    security_alerts = True


class OTPFactory(DjangoModelFactory):
    """Factory for creating OTP instances"""
    
    class Meta:
        model = 'users.OTP'
    
    user = SubFactory(UserFactory)
    otp_type = factory.Iterator(['registration', 'login', 'password_reset', 'transaction'])
    otp_code = factory.LazyFunction(lambda: str(random.randint(100000, 999999)))
    token = factory.LazyFunction(lambda: ''.join(random.choices(string.ascii_letters + string.digits, k=32)))
    is_used = False
    expires_at = factory.LazyFunction(
        lambda: timezone.now() + timezone.timedelta(minutes=10)
    )


class UserActivityFactory(DjangoModelFactory):
    """Factory for creating UserActivity instances"""
    
    class Meta:
        model = 'users.UserActivity'
    
    user = SubFactory(UserFactory)
    activity_type = factory.Iterator([
        'login', 'logout', 'password_change', 'profile_update',
        'transaction', 'withdrawal', 'deposit', 'kyc_submission'
    ])
    ip_address = Faker('ipv4')
    user_agent = factory.LazyFunction(
        lambda: random.choice([
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15',
            'Mozilla/5.0 (Linux; Android 10; SM-G973F) AppleWebKit/537.36'
        ])
    )
    device_info = factory.LazyFunction(
        lambda: {
            'device': random.choice(['mobile', 'tablet', 'desktop']),
            'os': random.choice(['Android', 'iOS', 'Windows', 'macOS']),
            'browser': random.choice(['Chrome', 'Firefox', 'Safari', 'Edge']),
            'screen_resolution': f'{random.randint(800, 3840)}x{random.randint(600, 2160)}'
        }
    )
    location = factory.LazyFunction(
        lambda: {
            'country': 'Bangladesh',
            'city': random.choice(['Dhaka', 'Chittagong', 'Sylhet', 'Khulna']),
            'latitude': round(random.uniform(20.0, 26.0), 6),
            'longitude': round(random.uniform(88.0, 92.0), 6)
        }
    )
    metadata = factory.LazyFunction(
        lambda: {
            'success': random.choice([True, False]),
            'duration': round(random.uniform(0.1, 5.0), 2)
        }
    )


class UserDeviceFactory(DjangoModelFactory):
    """Factory for creating UserDevice instances"""
    
    class Meta:
        model = 'users.UserDevice'
    
    user = SubFactory(UserFactory)
    device_id = factory.LazyFunction(
        lambda: ''.join(random.choices(string.ascii_letters + string.digits, k=32))
    )
    device_name = factory.Iterator(['Samsung Galaxy S21', 'iPhone 13', 'OnePlus 9', 'Xiaomi Mi 11'])
    device_type = factory.Iterator(['mobile', 'tablet', 'desktop'])
    os = factory.Iterator(['Android 12', 'iOS 15', 'Windows 11', 'macOS Monterey'])
    browser = factory.Iterator(['Chrome 96', 'Firefox 95', 'Safari 15', 'Edge 96'])
    ip_address = Faker('ipv4')
    is_trusted = True
    last_login = factory.LazyFunction(timezone.now)