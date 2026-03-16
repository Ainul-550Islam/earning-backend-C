"""
Factory for creating Offer model instances and related models.
"""

import factory
from factory import Faker, LazyAttribute, SubFactory, post_generation
from factory.django import DjangoModelFactory
from django.utils import timezone
from decimal import Decimal
import random
import string
from datetime import datetime, timedelta


class OfferCategoryFactory(DjangoModelFactory):
    """Factory for creating OfferCategory instances"""
    
    class Meta:
        model = 'offerwall.OfferCategory'
        django_get_or_create = ['slug']
    
    name = factory.Iterator([
        'Mobile Apps', 'Surveys', 'Gaming', 'Financial',
        'Shopping', 'Entertainment', 'Utilities', 'Social Media'
    ])
    slug = factory.LazyAttribute(lambda x: x.name.lower().replace(' ', '-'))
    description = Faker('text', max_nb_chars=200)
    icon = factory.LazyFunction(
        lambda: f"categories/{random.choice(['mobile', 'survey', 'game', 'shopping', 'entertainment'])}.png"
    )
    is_active = True
    sort_order = factory.Sequence(lambda n: n)
    
    # Statistics
    total_offers = LazyAttribute(lambda x: random.randint(10, 1000))
    total_completions = LazyAttribute(lambda x: random.randint(100, 10000))
    total_payout = LazyAttribute(lambda x: Decimal(str(round(random.uniform(1000, 50000), 2))))
    
    # Metadata
    metadata = factory.LazyFunction(
        lambda: {
            'color': random.choice(['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7']),
            'requirements': random.choice(['Android', 'iOS', 'Web', 'All Platforms']),
            'avg_completion_time': f"{random.randint(1, 30)} minutes",
            'success_rate': f"{random.randint(60, 95)}%"
        }
    )
    
    @classmethod
    def create_popular_category(cls, **kwargs):
        """Create popular offer category"""
        return cls.create(
            name='Popular Offers',
            slug='popular',
            sort_order=1,
            total_offers=500,
            total_completions=10000,
            total_payout=Decimal('50000.00'),
            **kwargs
        )
    
    @classmethod
    def create_hight_paying_category(cls, **kwargs):
        """Create high paying category"""
        return cls.create(
            name='High Paying',
            slug='high-paying',
            description='High payout offers',
            sort_order=2,
            **kwargs
        )


class OfferProviderFactory(DjangoModelFactory):
    """Factory for creating OfferProvider instances"""
    
    class Meta:
        model = 'offerwall.OfferProvider'
        django_get_or_create = ['name']
    
    name = factory.Iterator([
        'OfferToro', 'AdGate', 'AdGem', 'Wannads', 'Persona.ly',
        'CPX Research', 'Ayet Studios', 'Adscend Media', 'RevenueHits'
    ])
    slug = factory.LazyAttribute(lambda x: x.name.lower().replace(' ', '-').replace('.', ''))
    api_key = factory.LazyFunction(
        lambda: ''.join(random.choices(string.ascii_letters + string.digits, k=32))
    )
    api_url = Faker('url')
    is_active = True
    rating = LazyAttribute(lambda x: round(random.uniform(3.5, 5.0), 1))
    
    # Payout information
    payout_rate = LazyAttribute(lambda x: Decimal(str(round(random.uniform(0.7, 0.9), 3))))  # 70-90%
    payment_cycle = factory.Iterator(['weekly', 'bi-weekly', 'monthly', 'daily'])
    min_payout = Decimal('50.00')
    
    # Statistics
    total_offers = LazyAttribute(lambda x: random.randint(50, 1000))
    successful_payments = LazyAttribute(lambda x: random.randint(100, 10000))
    total_paid = LazyAttribute(lambda x: Decimal(str(round(random.uniform(10000, 500000), 2))))
    
    # Settings
    auto_approve = random.choice([True, False])
    support_contact = Faker('email')
    
    # Metadata
    metadata = factory.LazyFunction(
        lambda: {
            'trust_score': random.randint(70, 100),
            'response_time': f"{random.randint(1, 48)} hours",
            'supported_countries': ['BD', 'US', 'UK', 'CA', 'AU'],
            'special_features': random.choice(['Instant Approvals', 'High Payouts', 'Mobile Offers', 'Global Offers'])
        }
    )
    
    @classmethod
    def create_premium_provider(cls, **kwargs):
        """Create premium offer provider"""
        return cls.create(
            name='Premium Network',
            rating=4.8,
            payout_rate=Decimal('0.85'),
            payment_cycle='weekly',
            total_paid=Decimal('100000.00'),
            auto_approve=True,
            **kwargs
        )


class OfferFactory(DjangoModelFactory):
    """Factory for creating Offer instances"""
    
    class Meta:
        model = 'offerwall.Offer'
    
    # Basic information
    title = factory.LazyFunction(
        lambda: random.choice([
            'Install and Run Mobile App',
            'Complete Survey About Shopping Habits',
            'Play Game and Reach Level 10',
            'Sign Up for Free Trial',
            'Watch Video and Answer Questions'
        ])
    )
    description = Faker('text', max_nb_chars=500)
    
    # Relationships
    category = SubFactory(OfferCategoryFactory)
    provider = SubFactory(OfferProviderFactory)
    
    # Payout information
    payout = LazyAttribute(lambda x: Decimal(str(round(random.uniform(10, 500), 2))))
    currency = factory.Iterator(['BDT', 'USD', 'EUR', 'INR'])
    payout_type = factory.Iterator(['fixed', 'cpi', 'cpa', 'cpe'])
    
    # Requirements
    required_action = factory.Iterator([
        'install', 'signup', 'purchase', 'survey', 'video', 'trial', 'game'
    ])
    platform = factory.Iterator(['android', 'ios', 'web', 'all'])
    device_requirements = factory.LazyFunction(
        lambda: {
            'min_android_version': random.choice(['4.4', '5.0', '6.0', '7.0', '8.0', '9.0', '10.0', '11.0']),
            'min_ram': f"{random.choice([1, 2, 3, 4])}GB",
            'storage_space': f"{random.choice([50, 100, 200, 500])}MB",
            'internet_required': random.choice([True, False])
        }
    )
    
    # Availability
    is_active = True
    is_featured = factory.LazyFunction(lambda: random.choice([True, False]))
    is_hot = factory.LazyFunction(lambda: random.choice([True, False]))
    is_new = factory.LazyFunction(lambda: random.choice([True, False]))
    
    start_date = factory.LazyFunction(
        lambda: timezone.now() - timedelta(days=random.randint(0, 30))
    )
    end_date = factory.LazyAttribute(
        lambda x: x.start_date + timedelta(days=random.randint(1, 90))
    )
    
    # Limits
    max_completions = LazyAttribute(lambda x: random.randint(100, 10000))
    available_completions = factory.LazyAttribute(
        lambda x: random.randint(0, x.max_completions)
    )
    daily_limit = LazyAttribute(lambda x: random.randint(10, 100))
    user_daily_limit = LazyAttribute(lambda x: random.randint(1, 5))
    
    # Difficulty and time
    difficulty = factory.Iterator(['very_easy', 'easy', 'medium', 'hard', 'very_hard'])
    estimated_time = factory.LazyFunction(
        lambda: f"{random.randint(1, 30)} minutes"
    )
    
    # Images and media
    thumbnail = factory.LazyFunction(
        lambda: f"offers/thumb_{random.randint(1, 10)}.jpg"
    )
    banner_image = factory.LazyFunction(
        lambda: f"offers/banner_{random.randint(1, 5)}.jpg"
    )
    screenshots = factory.LazyFunction(
        lambda: [
            f"offers/screenshot_{i}.jpg" 
            for i in range(1, random.randint(2, 5))
        ]
    )
    
    # Tracking
    tracking_url = Faker('url')
    conversion_url = Faker('url')
    postback_url = Faker('url')
    
    # Requirements for completion
    proof_required = random.choice([True, False])
    proof_type = factory.LazyFunction(
        lambda: random.choice(['screenshot', 'receipt', 'email', 'confirmation'])
    )
    
    # Instructions
    instructions = factory.LazyFunction(
        lambda: [
            f"Step {i}: {Faker('sentence').generate({})}"
            for i in range(1, random.randint(3, 7))
        ]
    )
    
    # Statistics
    total_completions = factory.LazyAttribute(
        lambda x: x.max_completions - x.available_completions
    )
    success_rate = LazyAttribute(lambda x: round(random.uniform(60, 95), 1))
    total_payout = LazyAttribute(
        lambda x: x.payout * Decimal(str(x.total_completions))
    )
    
    # Metadata
    tags = factory.LazyFunction(
        lambda: random.sample([
            'mobile', 'android', 'ios', 'game', 'survey', 'shopping',
            'entertainment', 'utility', 'social', 'finance'
        ], k=random.randint(2, 5))
    )
    
    metadata = factory.LazyFunction(
        lambda: {
            'requires_login': random.choice([True, False]),
            'age_restriction': random.choice(['13+', '16+', '18+', '21+']),
            'geoTargeting': random.choice(['BD Only', 'Global', 'US Only', 'Asia']),
            'device_id_required': random.choice([True, False]),
            'unique_install': random.choice([True, False])
        }
    )
    
    @classmethod
    def create_hot_offer(cls, **kwargs):
        """Create hot offer"""
        return cls.create(
            title='🔥 HOT OFFER: Earn 500 BDT in 5 Minutes',
            payout=Decimal('500.00'),
            is_hot=True,
            is_featured=True,
            difficulty='easy',
            estimated_time='5 minutes',
            **kwargs
        )
    
    @classmethod
    def create_new_offer(cls, **kwargs):
        """Create new offer"""
        return cls.create(
            title='🎁 NEW: Limited Time Offer',
            is_new=True,
            start_date=timezone.now() - timedelta(hours=1),
            end_date=timezone.now() + timedelta(days=7),
            **kwargs
        )
    
    @classmethod
    def create_high_paying_offer(cls, **kwargs):
        """Create high paying offer"""
        return cls.create(
            title='[MONEY] HIGH PAYING: Complete This Survey',
            payout=Decimal('1000.00'),
            difficulty='medium',
            estimated_time='20 minutes',
            max_completions=50,
            **kwargs
        )
    
    @classmethod
    def create_mobile_app_offer(cls, **kwargs):
        """Create mobile app installation offer"""
        return cls.create(
            title='📱 Install This App and Earn',
            required_action='install',
            platform='android',
            payout=Decimal('150.00'),
            estimated_time='3 minutes',
            device_requirements={
                'min_android_version': '5.0',
                'min_ram': '2GB',
                'storage_space': '100MB',
                'internet_required': True
            },
            **kwargs
        )
    
    @classmethod
    def create_survey_offer(cls, **kwargs):
        """Create survey offer"""
        return cls.create(
            title='[STATS] Survey: Share Your Opinion',
            required_action='survey',
            platform='web',
            payout=Decimal('200.00'),
            estimated_time='15 minutes',
            proof_required=True,
            proof_type='screenshot',
            **kwargs
        )
    
    @classmethod
    def create_expired_offer(cls, **kwargs):
        """Create expired offer"""
        return cls.create(
            title='⏰ EXPIRED: This Offer Has Ended',
            is_active=False,
            end_date=timezone.now() - timedelta(days=1),
            available_completions=0,
            **kwargs
        )
    
    @classmethod
    def create_limited_offer(cls, **kwargs):
        """Create limited availability offer"""
        return cls.create(
            title='🎯 LIMITED: Only 10 Spots Left',
            max_completions=100,
            available_completions=10,
            daily_limit=5,
            user_daily_limit=1,
            **kwargs
        )


class UserOfferCompletionFactory(DjangoModelFactory):
    """Factory for creating UserOfferCompletion instances"""
    
    class Meta:
        model = 'offerwall.UserOfferCompletion'
    
    user = SubFactory('api.tests.factories.UserFactory.UserFactory')
    offer = SubFactory(OfferFactory)
    
    # Completion details
    completion_id = factory.LazyFunction(
        lambda: f"COMP{''.join(random.choices(string.digits, k=12))}"
    )
    status = factory.Iterator([
        'pending', 'approved', 'rejected', 'pending_review', 'cancelled'
    ])
    
    # Payout
    earned_amount = factory.LazyAttribute(lambda x: x.offer.payout)
    currency = factory.LazyAttribute(lambda x: x.offer.currency)
    commission_rate = LazyAttribute(lambda x: Decimal(str(round(random.uniform(0.8, 1.0), 3))))  # 80-100%
    net_amount = factory.LazyAttribute(
        lambda x: x.earned_amount * x.commission_rate
    )
    
    # Timing
    started_at = factory.LazyFunction(
        lambda: timezone.now() - timedelta(minutes=random.randint(5, 60))
    )
    completed_at = factory.LazyAttribute(
        lambda x: x.started_at + timedelta(minutes=random.randint(1, 30))
        if x.status != 'pending' else None
    )
    approved_at = factory.LazyAttribute(
        lambda x: x.completed_at + timedelta(minutes=random.randint(5, 60))
        if x.status == 'approved' else None
    )
    
    # Proof and verification
    proof = factory.LazyFunction(
        lambda: f"proofs/{''.join(random.choices(string.digits, k=10))}.jpg"
        if random.choice([True, False]) else None
    )
    proof_type = factory.LazyAttribute(
        lambda x: random.choice(['screenshot', 'receipt', 'email', 'confirmation'])
        if x.proof else None
    )
    verification_notes = factory.LazyFunction(
        lambda: random.choice([
            'Proof verified successfully',
            'Manual review required',
            'Additional proof needed',
            'Auto-approved by system'
        ]) if random.choice([True, False]) else ''
    )
    
    # Tracking
    tracking_id = factory.LazyFunction(
        lambda: f"TRACK{''.join(random.choices(string.ascii_uppercase + string.digits, k=16))}"
    )
    click_id = factory.LazyFunction(
        lambda: f"CLICK{''.join(random.choices(string.ascii_letters + string.digits, k=20))}"
    )
    conversion_id = factory.LazyFunction(
        lambda: f"CONV{''.join(random.choices(string.digits, k=12))}"
    )
    
    # Device and location info
    ip_address = Faker('ipv4')
    user_agent = factory.LazyFunction(
        lambda: random.choice([
            'Mozilla/5.0 (Linux; Android 10; SM-G973F) AppleWebKit/537.36',
            'Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        ])
    )
    device_info = factory.LazyFunction(
        lambda: {
            'device_id': ''.join(random.choices(string.ascii_letters + string.digits, k=16)),
            'device_model': random.choice(['Samsung Galaxy S21', 'iPhone 13', 'OnePlus 9', 'Xiaomi Mi 11']),
            'os_version': random.choice(['Android 11', 'iOS 14', 'Windows 10']),
            'app_version': f"2.{random.randint(0, 5)}.{random.randint(0, 20)}"
        }
    )
    location_data = factory.LazyFunction(
        lambda: {
            'country': 'Bangladesh',
            'city': random.choice(['Dhaka', 'Chittagong', 'Sylhet', 'Khulna']),
            'latitude': round(random.uniform(20.0, 26.0), 6),
            'longitude': round(random.uniform(88.0, 92.0), 6)
        }
    )
    
    # Metadata
    metadata = factory.LazyFunction(
        lambda: {
            'session_id': ''.join(random.choices(string.ascii_letters + string.digits, k=32)),
            'referrer': random.choice(['direct', 'facebook', 'google', 'referral']),
            'campaign_id': random.randint(1000, 9999) if random.choice([True, False]) else None,
            'sub_id': random.randint(1, 10) if random.choice([True, False]) else None
        }
    )
    
    @classmethod
    def create_pending_completion(cls, **kwargs):
        """Create pending completion"""
        return cls.create(
            status='pending',
            completed_at=None,
            approved_at=None,
            **kwargs
        )
    
    @classmethod
    def create_approved_completion(cls, **kwargs):
        """Create approved completion"""
        return cls.create(
            status='approved',
            completed_at=timezone.now() - timedelta(minutes=30),
            approved_at=timezone.now() - timedelta(minutes=5),
            verification_notes='Auto-approved by system',
            **kwargs
        )
    
    @classmethod
    def create_rejected_completion(cls, **kwargs):
        """Create rejected completion"""
        return cls.create(
            status='rejected',
            completed_at=timezone.now() - timedelta(minutes=30),
            verification_notes='Proof verification failed',
            **kwargs
        )
    
    @classmethod
    def create_high_value_completion(cls, **kwargs):
        """Create high value completion"""
        return cls.create(
            earned_amount=Decimal('1000.00'),
            net_amount=Decimal('950.00'),
            status='approved',
            **kwargs
        )
    
    @classmethod
    def create_bulk_completions(cls, user, count=10, **kwargs):
        """Create multiple completions for a user"""
        completions = []
        for i in range(count):
            offer = OfferFactory.create()
            completion = cls.create(
                user=user,
                offer=offer,
                status=random.choice(['pending', 'approved', 'rejected']),
                started_at=timezone.now() - timedelta(days=random.randint(0, 30)),
                **kwargs
            )
            completions.append(completion)
        return completions


class OfferImpressionFactory(DjangoModelFactory):
    """Factory for creating OfferImpression instances"""
    
    class Meta:
        model = 'offerwall.OfferImpression'
    
    user = SubFactory('api.tests.factories.UserFactory.UserFactory')
    offer = SubFactory(OfferFactory)
    
    # Impression details
    impression_type = factory.Iterator(['view', 'click', 'conversion', 'lead'])
    session_id = factory.LazyFunction(
        lambda: ''.join(random.choices(string.ascii_letters + string.digits, k=32))
    )
    
    # Timing
    timestamp = factory.LazyFunction(
        lambda: timezone.now() - timedelta(minutes=random.randint(0, 1440))
    )
    
    # Source and medium
    source = factory.Iterator(['direct', 'organic', 'referral', 'email', 'push'])
    medium = factory.Iterator(['web', 'mobile_app', 'api', 'widget'])
    campaign = factory.LazyFunction(
        lambda: random.choice(['summer_sale', 'welcome_offer', 'referral_bonus', None])
    )
    
    # Device info
    ip_address = Faker('ipv4')
    user_agent = factory.LazyFunction(
        lambda: random.choice([
            'Mozilla/5.0 (Linux; Android 10; SM-G973F) AppleWebKit/537.36',
            'Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15'
        ])
    )
    device_type = factory.Iterator(['mobile', 'desktop', 'tablet'])
    os = factory.Iterator(['Android', 'iOS', 'Windows', 'macOS'])
    browser = factory.Iterator(['Chrome', 'Firefox', 'Safari', 'Edge'])
    
    # Location
    country = 'Bangladesh'
    city = factory.LazyFunction(
        lambda: random.choice(['Dhaka', 'Chittagong', 'Sylhet', 'Khulna', 'Rajshahi'])
    )
    latitude = LazyAttribute(lambda x: round(random.uniform(20.0, 26.0), 6))
    longitude = LazyAttribute(lambda x: round(random.uniform(88.0, 92.0), 6))
    
    # Referral info
    referrer_url = Faker('url')
    landing_page = Faker('url')
    
    # Metadata
    metadata = factory.LazyFunction(
        lambda: {
            'screen_resolution': f"{random.randint(800, 3840)}x{random.randint(600, 2160)}",
            'connection_type': random.choice(['wifi', 'mobile_data', 'ethernet']),
            'language': random.choice(['en', 'bn', 'ar']),
            'timezone': 'Asia/Dhaka',
            'is_returning': random.choice([True, False])
        }
    )
    
    @classmethod
    def create_view_impression(cls, **kwargs):
        """Create view impression"""
        return cls.create(
            impression_type='view',
            **kwargs
        )
    
    @classmethod
    def create_click_impression(cls, **kwargs):
        """Create click impression"""
        return cls.create(
            impression_type='click',
            **kwargs
        )
    
    @classmethod
    def create_conversion_impression(cls, **kwargs):
        """Create conversion impression"""
        return cls.create(
            impression_type='conversion',
            **kwargs
        )
    
    @classmethod
    def create_bulk_impressions(cls, user, offer, count=100, **kwargs):
        """Create multiple impressions"""
        impressions = []
        for i in range(count):
            impression = cls.create(
                user=user,
                offer=offer,
                impression_type=random.choice(['view', 'click']),
                timestamp=timezone.now() - timedelta(minutes=random.randint(0, 10080)),  # 7 days
                **kwargs
            )
            impressions.append(impression)
        return impressions