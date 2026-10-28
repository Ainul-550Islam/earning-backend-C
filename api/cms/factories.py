# api/cms/factories.py
"""Model factories for testing and data generation."""
import logging
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, Any, Optional, List, Type
from django.utils import timezone
from django.contrib.auth import get_user_model
from faker import Faker
import factory
from factory import fuzzy

logger = logging.getLogger(__name__)

# ── models_new imports for factories ────────────────────────────────────────
def _get_model(name):
    """Lazy model getter to avoid circular imports."""
    mapping = {
        'SurveyCategory':    ('api.cms.models_new.profile_surveys', 'SurveyCategory'),
        'SurveyTemplate':    ('api.cms.models_new.profile_surveys', 'SurveyTemplate'),
        'SurveyCompletion':  ('api.cms.models_new.profile_surveys', 'SurveyCompletion'),
        'RewardPool':        ('api.cms.models_new.survey_rewards',  'RewardPool'),
        'RewardTransaction': ('api.cms.models_new.survey_rewards',  'RewardTransaction'),
        'UserProfile':       ('api.cms.models_new.user_profile',    'UserProfile'),
        'UserSegment':       ('api.cms.models_new.user_profile',    'UserSegment'),
        'TaskSchedule':      ('api.cms.models_new.task_management', 'TaskSchedule'),
        'TaskExecution':     ('api.cms.models_new.task_management', 'TaskExecution'),
    }
    mod_path, cls_name = mapping[name]
    import importlib
    mod = importlib.import_module(mod_path)
    return getattr(mod, cls_name)
# ─────────────────────────────────────────────────────────────────────────────


# Get faker instance
fake = Faker()


# ── Original Factories (Enhanced) ─────────────────────────────────────

class UserFactory:
    @staticmethod
    def create(username=None, email=None, is_staff=False, **kwargs):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        username = username or f"user_{uuid.uuid4().hex[:8]}"
        email = email or f"{username}@test.com"
        # Always active unless caller explicitly overrides
        kwargs.setdefault('is_active', True)
        user = User.objects.create_user(
            username=username, email=email, password='testpass123',
            is_staff=is_staff, **kwargs
        )
        return user

    @staticmethod
    def create_admin(username=None):
        return UserFactory.create(username=username, is_staff=True, is_superuser=True)


class VirtualCurrencyFactory:
    @staticmethod
    def create(name='Test Coins', usd_ratio=100, **kwargs):
        from api.cms.models_new.cpalead import VirtualCurrency
        return VirtualCurrency.objects.create(
            name=name, symbol='🪙', usd_ratio=usd_ratio,
            daily_earn_cap=5000, is_active=True, **kwargs
        )


class UserVirtualBalanceFactory:
    @staticmethod
    def create(user, currency=None, balance=0):
        from api.cms.models_new.cpalead import UserVirtualBalance, VirtualCurrency
        if not currency:
            currency = VirtualCurrencyFactory.create()
        bal, _ = UserVirtualBalance.objects.get_or_create(
            user=user,
            currency=currency,  # filter by currency so each user can have multiple currency balances
            defaults={'balance': Decimal(str(balance))}
        )
        return bal


# ── Enhanced Factory Classes ─────────────────────────────────────

class CMSFactory(factory.django.DjangoModelFactory):
    """Base factory for CMS models."""
    
    class Meta:
        abstract = True
    
    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        """Override create to handle UUID fields."""
        if hasattr(model_class, 'uuid') and 'uuid' not in kwargs:
            kwargs['uuid'] = uuid.uuid4()
        
        return super()._create(model_class, *args, **kwargs)


class TimestampedFactory(CMSFactory):
    """Factory for models with timestamp fields."""
    
    created_at = factory.LazyAttribute(lambda o: timezone.now() - timedelta(days=fake.random_int(1, 365)))
    updated_at = factory.LazyAttribute(lambda o: timezone.now() - timedelta(hours=fake.random_int(1, 24)))


class SoftDeleteFactory(CMSFactory):
    """Factory for models with soft delete functionality."""
    
    is_deleted = False
    deleted_at = None


# ── Survey Factories ─────────────────────────────────────────────

class SurveyCategoryFactory(CMSFactory):
    """Factory for SurveyCategory model."""
    
    class Meta:
        model = _get_model('SurveyCategory')
    
    name = factory.Faker('word')
    description = factory.Faker('text', max_nb_chars=200)
    is_active = True
    created_by = factory.SubFactory('cms.factories.UserFactory')


class SurveyFactory(CMSFactory):
    """Factory for Survey model."""
    
    class Meta:
        model = _get_model('SurveyTemplate')
    
    uuid = factory.LazyAttribute(lambda o: uuid.uuid4())
    title = factory.Faker('sentence', nb_words=4)
    description = factory.Faker('text', max_nb_chars=500)
    category = factory.SubFactory(SurveyCategoryFactory)
    difficulty = factory.Iterator(['easy', 'medium', 'hard'])
    status = factory.Iterator(['draft', 'active', 'paused', 'completed'])
    is_public = True
    min_reward = fuzzy.FuzzyDecimal(0.10, 1.00, 2)
    max_reward = fuzzy.FuzzyDecimal(1.00, 10.00, 2)
    estimated_time = fuzzy.FuzzyInteger(5, 60)  # minutes
    max_participants = fuzzy.FuzzyInteger(100, 1000)
    current_participants = 0
    created_by = factory.SubFactory('cms.factories.UserFactory')
    created_at = factory.LazyAttribute(lambda o: timezone.now() - timedelta(days=fake.random_int(1, 30)))
    updated_at = factory.LazyAttribute(lambda o: timezone.now() - timedelta(hours=fake.random_int(1, 24)))


class SurveyCompletionFactory(CMSFactory):
    """Factory for SurveyCompletion model."""
    
    class Meta:
        model = _get_model('SurveyCompletion')
    
    uuid = factory.LazyAttribute(lambda o: uuid.uuid4())
    user = factory.SubFactory('cms.factories.UserFactory')
    survey = factory.SubFactory(SurveyFactory)
    status = factory.Iterator(['in_progress', 'completed', 'abandoned'])
    responses = factory.LazyAttribute(lambda o: {
        'answers': [
            {'question_id': str(uuid.uuid4()), 'answer': fake.word()}
            for _ in range(fake.random_int(1, 10))
        ]
    })
    quality_score = fuzzy.FuzzyFloat(0.0, 1.0, 2)
    started_at = factory.LazyAttribute(lambda o: timezone.now() - timedelta(minutes=fake.random_int(5, 60)))
    completed_at = factory.LazyAttribute(lambda o: 
        timezone.now() if o.status == 'completed' else None
    )
    time_spent = fuzzy.FuzzyInteger(60, 3600)  # seconds


# ── Reward Factories ─────────────────────────────────────────────

class RewardPoolFactory(CMSFactory):
    """Factory for RewardPool model."""
    
    class Meta:
        model = _get_model('RewardPool')
    
    uuid = factory.LazyAttribute(lambda o: uuid.uuid4())
    name = factory.Faker('word')
    description = factory.Faker('text', max_nb_chars=200)
    total_allocated = fuzzy.FuzzyDecimal(1000.00, 10000.00, 2)
    current_balance = factory.LazyAttribute(lambda o: o.total_allocated * fuzzy.FuzzyFloat(0.3, 0.9, 2))
    is_active = True
    created_by = factory.SubFactory('cms.factories.UserFactory')


class RewardTransactionFactory(CMSFactory):
    """Factory for RewardTransaction model."""
    
    class Meta:
        model = _get_model('RewardTransaction')
    
    uuid = factory.LazyAttribute(lambda o: uuid.uuid4())
    user = factory.SubFactory('cms.factories.UserFactory')
    reward_pool = factory.SubFactory(RewardPoolFactory)
    amount = fuzzy.FuzzyDecimal(0.10, 100.00, 2)
    transaction_type = factory.Iterator(['earned', 'payout', 'bonus', 'penalty'])
    status = factory.Iterator(['pending', 'completed', 'failed', 'cancelled'])
    description = factory.Faker('sentence')
    data = factory.LazyAttribute(lambda o: {
        'source': 'survey_completion',
        'survey_id': str(uuid.uuid4())
    })
    created_at = factory.LazyAttribute(lambda o: timezone.now() - timedelta(hours=fake.random_int(1, 168)))


# ── User Profile Factories ─────────────────────────────────────

class UserProfileFactory(CMSFactory):
    """Factory for UserProfile model."""
    
    class Meta:
        model = _get_model('UserProfile')
    
    uuid = factory.LazyAttribute(lambda o: uuid.uuid4())
    user = factory.SubFactory('cms.factories.UserFactory')
    first_name = factory.Faker('first_name')
    last_name = factory.Faker('last_name')
    email = factory.LazyAttribute(lambda o: f"{o.user.username}@example.com")
    phone_number = factory.Faker('phone_number')
    date_of_birth = factory.Faker('date_of_birth', minimum_age=18, maximum_age=80)
    address = factory.Faker('address')
    country = factory.Faker('country')
    city = factory.Faker('city')
    postal_code = factory.Faker('postalcode')
    avatar_url = factory.Faker('image_url')
    bio = factory.Faker('text', max_nb_chars=300)
    preferences = factory.LazyAttribute(lambda o: {
        'notifications': True,
        'email_updates': False,
        'language': 'en'
    })
    completeness_percentage = fuzzy.FuzzyFloat(0.0, 100.0, 1)
    created_at = factory.LazyAttribute(lambda o: timezone.now() - timedelta(days=fake.random_int(1, 365)))
    updated_at = factory.LazyAttribute(lambda o: timezone.now() - timedelta(hours=fake.random_int(1, 24)))


class UserSegmentFactory(CMSFactory):
    """Factory for UserSegment model."""
    
    class Meta:
        model = _get_model('UserSegment')
    
    uuid = factory.LazyAttribute(lambda o: uuid.uuid4())
    user = factory.SubFactory('cms.factories.UserFactory')
    name = factory.Iterator(['new_user', 'active_user', 'high_value', 'inactive', 'vip'])
    segment_type = factory.Iterator(['demographic', 'behavioral', 'custom'])
    criteria = factory.LazyAttribute(lambda o: {
        'age_range': [18, 65],
        'activity_level': 'high'
    })
    is_active = True
    created_at = factory.LazyAttribute(lambda o: timezone.now() - timedelta(days=fake.random_int(1, 30)))


# ── Task Management Factories ─────────────────────────────────────

class TaskScheduleFactory(CMSFactory):
    """Factory for TaskSchedule model."""
    
    class Meta:
        model = _get_model('TaskSchedule')
    
    uuid = factory.LazyAttribute(lambda o: uuid.uuid4())
    task_name = factory.Faker('word')
    task_type = factory.Iterator(['cleanup', 'analytics', 'notification', 'backup', 'sync'])
    description = factory.Faker('text', max_nb_chars=200)
    schedule_type = factory.Iterator(['once', 'recurring', 'cron'])
    schedule_config = factory.LazyAttribute(lambda o: {
        'interval': 'daily',
        'time': '02:00'
    } if o.schedule_type == 'recurring' else {
        'run_at': timezone.now() + timedelta(hours=1)
    })
    priority = fuzzy.FuzzyInteger(1, 10)
    max_retries = fuzzy.FuzzyInteger(1, 5)
    timeout_seconds = fuzzy.FuzzyInteger(300, 3600)
    status = factory.Iterator(['active', 'paused', 'disabled'])
    last_run_at = factory.LazyAttribute(lambda o: timezone.now() - timedelta(hours=fake.random_int(1, 24)))
    next_run_at = factory.LazyAttribute(lambda o: timezone.now() + timedelta(hours=fake.random_int(1, 24)))
    created_by = factory.SubFactory('cms.factories.UserFactory')


class TaskExecutionFactory(CMSFactory):
    """Factory for TaskExecution model."""
    
    class Meta:
        model = _get_model('TaskExecution')
    
    uuid = factory.LazyAttribute(lambda o: uuid.uuid4())
    schedule = factory.SubFactory(TaskScheduleFactory)
    status = factory.Iterator(['pending', 'running', 'success', 'failure', 'retry'])
    worker_id = factory.Faker('uuid4')
    started_at = factory.LazyAttribute(lambda o: timezone.now() - timedelta(minutes=fake.random_int(1, 60)))
    completed_at = factory.LazyAttribute(lambda o: 
        timezone.now() if o.status in ['success', 'failure'] else None
    )
    duration_seconds = fuzzy.FuzzyInteger(10, 3600)
    retry_count = fuzzy.FuzzyInteger(0, 3)
    error_message = factory.LazyAttribute(lambda o: 
        fake.sentence() if o.status == 'failure' else None
    )
    result_data = factory.LazyAttribute(lambda o: {
        'processed_items': fake.random_int(10, 100),
        'success_rate': fuzzy.FuzzyFloat(0.8, 1.0, 2)
    } if o.status == 'success' else None)


# ── Factory Utilities ─────────────────────────────────────

class FactoryManager:
    """Manager for organizing and using factories."""
    
    def __init__(self):
        self.factories = self._load_factories()
    
    def _load_factories(self) -> Dict[str, Type]:
        """Load all available factories."""
        return {
            'user': UserFactory,
            'survey_category': SurveyCategoryFactory,
            'survey': SurveyFactory,
            'survey_completion': SurveyCompletionFactory,
            'reward_pool': RewardPoolFactory,
            'reward_transaction': RewardTransactionFactory,
            'user_profile': UserProfileFactory,
            'user_segment': UserSegmentFactory,
            'task_schedule': TaskScheduleFactory,
            'task_execution': TaskExecutionFactory,
            'virtual_currency': VirtualCurrencyFactory,
            'user_virtual_balance': UserVirtualBalanceFactory,
        }
    
    def get_factory(self, name: str) -> Optional[Type]:
        """Get factory by name."""
        return self.factories.get(name)
    
    def create(self, factory_name: str, **kwargs) -> Any:
        """Create instance using factory."""
        factory_class = self.get_factory(factory_name)
        if not factory_class:
            raise ValueError(f"Factory '{factory_name}' not found")
        
        return factory_class.create(**kwargs)
    
    def create_batch(self, factory_name: str, count: int, **kwargs) -> List[Any]:
        """Create multiple instances using factory."""
        factory_class = self.get_factory(factory_name)
        if not factory_class:
            raise ValueError(f"Factory '{factory_name}' not found")
        
        return [factory_class.create(**kwargs) for _ in range(count)]
    
    def list_factories(self) -> List[str]:
        """List all available factory names."""
        return list(self.factories.keys())


# Global factory manager
factory_manager = FactoryManager()


# ── Test Data Builders ─────────────────────────────────────

class TestDataBuilder:
    """Builder for creating complex test data scenarios."""
    
    def __init__(self):
        self.users = []
        self.surveys = []
        self.completions = []
        self.rewards = []
        self.profiles = []
    
    def with_users(self, count: int = 5, admin: bool = False) -> 'TestDataBuilder':
        """Add users to test data."""
        if admin:
            self.users.extend([UserFactory.create_admin() for _ in range(count)])
        else:
            self.users.extend([UserFactory.create() for _ in range(count)])
        return self
    
    def with_surveys(self, count: int = 10) -> 'TestDataBuilder':
        """Add surveys to test data."""
        self.surveys.extend([SurveyFactory() for _ in range(count)])
        return self
    
    def with_completions(self, count: int = 20) -> 'TestDataBuilder':
        """Add survey completions to test data."""
        if not self.users:
            self.with_users(5)
        
        user = fake.choice(self.users)
        survey = fake.choice(self.surveys) if self.surveys else SurveyFactory()
        
        for _ in range(count):
            completion = SurveyCompletionFactory(user=user, survey=survey)
            self.completions.append(completion)
        
        return self
    
    def with_rewards(self, count: int = 15) -> 'TestDataBuilder':
        """Add reward transactions to test data."""
        if not self.users:
            self.with_users(5)
        
        user = fake.choice(self.users)
        
        for _ in range(count):
            transaction = RewardTransactionFactory(user=user)
            self.rewards.append(transaction)
        
        return self
    
    def with_profiles(self, count: int = 8) -> 'TestDataBuilder':
        """Add user profiles to test data."""
        if not self.users:
            self.with_users(count)
        
        for user in self.users[:count]:
            profile = UserProfileFactory(user=user)
            self.profiles.append(profile)
        
        return self
    
    def build(self) -> Dict[str, Any]:
        """Build the test data structure."""
        return {
            'users': self.users,
            'surveys': self.surveys,
            'completions': self.completions,
            'rewards': self.rewards,
            'profiles': self.profiles
        }
    
    def reset(self) -> 'TestDataBuilder':
        """Reset the builder."""
        self.users = []
        self.surveys = []
        self.completions = []
        self.rewards = []
        self.profiles = []
        return self


# ── Seeding Utilities ─────────────────────────────────────

def seed_database(scale: str = 'small') -> Dict[str, int]:
    """Seed database with test data."""
    scale_configs = {
        'small': {
            'users': 10,
            'surveys': 5,
            'completions': 25,
            'rewards': 30,
            'profiles': 10
        },
        'medium': {
            'users': 50,
            'surveys': 20,
            'completions': 200,
            'rewards': 250,
            'profiles': 50
        },
        'large': {
            'users': 200,
            'surveys': 100,
            'completions': 1000,
            'rewards': 1200,
            'profiles': 200
        }
    }
    
    config = scale_configs.get(scale, scale_configs['small'])
    
    logger.info(f"Seeding database with {scale} scale configuration")
    
    # Create data
    users = [UserFactory.create() for _ in range(config['users'])]
    surveys = [SurveyFactory() for _ in range(config['surveys'])]
    
    # Create completions
    completions = []
    for _ in range(config['completions']):
        user = fake.choice(users)
        survey = fake.choice(surveys)
        completion = SurveyCompletionFactory(user=user, survey=survey)
        completions.append(completion)
    
    # Create rewards
    rewards = [RewardTransactionFactory(user=fake.choice(users)) for _ in range(config['rewards'])]
    
    # Create profiles
    profiles = []
    for user in users[:config['profiles']]:
        profile = UserProfileFactory(user=user)
        profiles.append(profile)
    
    result = {
        'users_created': len(users),
        'surveys_created': len(surveys),
        'completions_created': len(completions),
        'rewards_created': len(rewards),
        'profiles_created': len(profiles)
    }
    
    logger.info(f"Database seeding completed: {result}")
    return result


def clear_test_data():
    """Clear all test data from database."""
    from django.core.management import call_command
    call_command('flush', interactive=False)
    logger.info("Test data cleared from database")


class ConversionLogFactory:
    @staticmethod
    def create(user=None, payout_usd=0.50, status='approved', lead_id=None, **kwargs):
        from api.cms.models_new.cpalead import ConversionLog
        lead_id = lead_id or f"TEST_{uuid.uuid4().hex[:12]}"
        return ConversionLog.objects.create(
            subid=str(user.id) if user else 'anon',
            lead_id=lead_id,
            payout_usd=Decimal(str(payout_usd)),
            user=user,
            status=status,
            raw_postback_data={},
            **kwargs
        )


class OfferWallConfigFactory:
    @staticmethod
    def create(name='Test Offerwall', publisher_id='test123', currency=None):
        from api.cms.models_new.cpalead import OfferWallConfig
        if not currency:
            currency = VirtualCurrencyFactory.create()
        return OfferWallConfig.objects.create(
            name=name,
            publisher_id=publisher_id,
            currency=currency
        )
        return OfferWallConfig.objects.create(
            name=name, offerwall_title='Earn Coins',
            publisher_id=publisher_id, currency=currency, is_active=True,
        )


class ContentLockerFactory:
    @staticmethod
    def create(name='Test Locker', locker_type='content',
                zero_hours_mode=False, unlock_mode='24h'):
        from api.cms.models_new.cpalead import ContentLocker
        return ContentLocker.objects.create(
            name=name, locker_type=locker_type,
            title='Complete an offer to unlock',
            locked_content='SECRET CONTENT HERE',
            preview_content='Blurred preview...',
            zero_hours_mode=zero_hours_mode,
            unlock_mode=unlock_mode,
            is_active=True,
        )


class ReferralCodeFactory:
    @staticmethod
    def create(user):
        from api.cms.models_new.referral import ReferralCode
        return ReferralCode.get_or_create_for_user(user)


class QuizFactory:
    @staticmethod
    def create(title='Test Quiz', num_questions=3):
        from api.cms.models_new.quiz import QuizTemplate, QuizQuestion, QuizAnswer, QuizResult
        import re
        slug = re.sub(r'[^a-z0-9\-]', '-', title.lower())[:80]
        base = slug
        i = 1
        while QuizTemplate.objects.filter(slug=slug).exists():
            slug = f"{base}-{i}"; i += 1
        quiz = QuizTemplate.objects.create(
            title=title, slug=slug, quiz_type='personality',
            payout_usd=Decimal('0.10'), is_active=True,
        )
        for j in range(num_questions):
            q = QuizQuestion.objects.create(
                quiz=quiz, text=f"Question {j+1}?", order=j, is_required=True
            )
            for k, tag in enumerate(['a', 'b', 'c', 'd']):
                QuizAnswer.objects.create(
                    question=q, text=f"Answer {tag.upper()}",
                    personality_tag=tag, score_weight=k+1, order=k
                )
        for tag in ['a', 'b', 'c']:
            QuizResult.objects.create(
                quiz=quiz, title=f"Result {tag.upper()}",
                description=f"You are type {tag.upper()}!",
                personality_tag=tag,
            )
        return quiz


class SmartLinkFactory:
    @staticmethod
    def create(name='Test SmartLink', offers=None):
        from api.cms.models_new.smartlink import SmartLink, SmartLinkRule
        import re
        slug = re.sub(r'[^a-z0-9\-]', '-', name.lower())[:80]
        sl = SmartLink.objects.create(
            name=name, slug=slug, rotation_mode='best_payout', is_active=True
        )
        for offer in (offers or [{'url': 'https://example.com/offer', 'payout': 0.50}]):
            SmartLinkRule.objects.create(
                smartlink=sl, offer_url=offer.get('url', ''),
                payout_usd=offer.get('payout', 0), is_active=True,
            )
        return sl


class WithdrawalRequestFactory:
    @staticmethod
    def create(user, coins=1000, method='paypal', status='pending'):
        from api.cms.models_new.withdrawal import WithdrawalRequest
        return WithdrawalRequest.objects.create(
            user=user, method=method,
            account_id='test@paypal.com',
            requested_coins=Decimal(str(coins)),
            requested_usd=Decimal(str(coins / 100)),
            fee_usd=Decimal('0.02'),
            net_usd=Decimal(str(coins / 100)) - Decimal('0.02'),
            status=status,
        )


class UserProfileFactory:
    @staticmethod
    def create(user, level=1, **kwargs):
        from api.cms.models_new.withdrawal import UserProfile
        profile, _ = UserProfile.objects.get_or_create(
            user=user,
            defaults={'level': level, **kwargs}
        )
        return profile


class SiteConfigFactory:
    @staticmethod
    def create(**kwargs):
        from api.cms.models_new.site_config import SiteConfig
        return SiteConfig.objects.create(
            site_name=kwargs.get('site_name', 'Test Site'),
            is_active=True,
            **{k: v for k, v in kwargs.items() if k != 'site_name'}
        )


class DynamicFormFactory:
    @staticmethod
    def create(name='Test Form', num_fields=3):
        from api.cms.models_new.forms import DynamicForm, FormField
        import re
        slug = re.sub(r'[^a-z0-9\-]', '-', name.lower())[:80]
        form = DynamicForm.objects.create(
            name=name, slug=slug, title=name,
            submit_text='Submit', is_active=True,
        )
        field_types = ['text', 'email', 'textarea']
        for i in range(num_fields):
            ft = field_types[i % len(field_types)]
            FormField.objects.create(
                form=form, label=f"Field {i+1}", name=f"field_{i+1}",
                field_type=ft, order=i, is_required=(i == 0),
            )
        return form
