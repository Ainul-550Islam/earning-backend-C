# engagement/factories.py
"""
Factory classes for engagement system.
Provides factory methods for creating model instances and test data.
"""
import random
import string
from datetime import datetime, date, timedelta
from decimal import Decimal
from django.utils import timezone
from faker import Faker

from .models.checkin import DailyCheckIn
from .models.spinwheel import SpinWheel
from .models.quest import Quest, UserQuest
from .models.achievement import Achievement, UserAchievement
from .models.shop import ShopItem, ShopPurchase, UserInventory
from .models.leaderboard import Leaderboard, LeaderboardSeason, LeaderboardReward
from .models.notification import Notification
from .models.social import FeedItem, Friendship
from .models.referral import Referral, ReferralProgram
from .models.xp import UserXP
from .choices import (
    QUEST_STATUS_CHOICES, ACHIEVEMENT_DIFFICULTY_CHOICES,
    SHOP_ITEM_TYPE_CHOICES, SHOP_ITEM_RARITY_CHOICES
)

fake = Faker()


class UserFactory:
    """Factory for creating test users."""
    
    @staticmethod
    def create_user(username=None, email=None, **kwargs):
        """Create a test user."""
        from django.contrib.auth import get_user_model
        
        User = get_user_model()
        
        user_data = {
            'username': username or fake.user_name(),
            'email': email or fake.email(),
            'first_name': fake.first_name(),
            'last_name': fake.last_name(),
            'is_active': True,
            'date_joined': timezone.now(),
            'last_login': timezone.now(),
        }
        user_data.update(kwargs)
        
        return User.objects.create_user(**user_data)
    
    @staticmethod
    def create_premium_user(**kwargs):
        """Create a premium test user."""
        return UserFactory.create_user(
            has_premium=True,
            subscription_level='premium',
            **kwargs
        )
    
    @staticmethod
    def create_admin_user(**kwargs):
        """Create an admin test user."""
        return UserFactory.create_user(
            is_staff=True,
            is_superuser=False,
            **kwargs
        )
    
    @staticmethod
    def create_superadmin_user(**kwargs):
        """Create a superadmin test user."""
        return UserFactory.create_user(
            is_staff=True,
            is_superuser=True,
            **kwargs
        )


class TenantFactory:
    """Factory for creating test tenants."""
    
    @staticmethod
    def create_tenant(name=None, slug=None, **kwargs):
        """Create a test tenant."""
        from .models.base import TenantModel
        
        tenant_data = {
            'name': name or fake.company(),
            'slug': slug or fake.slug(),
            'is_active': True,
            'created_at': timezone.now(),
        }
        tenant_data.update(kwargs)
        
        return TenantModel.objects.create(**tenant_data)


class CheckInFactory:
    """Factory for creating check-in instances."""
    
    @staticmethod
    def create_checkin(user=None, checkin_date=None, **kwargs):
        """Create a test check-in."""
        checkin_data = {
            'user': user or UserFactory.create_user(),
            'date': checkin_date or date.today(),
            'coins_earned': Decimal(str(random.uniform(10, 100))),
            'xp_earned': random.randint(10, 50),
            'consecutive_days': random.randint(1, 30),
            'bonus_claimed': random.choice([True, False]),
            'reward_claimed': random.choice([True, False]),
            'streak_shield_used': random.choice([True, False]),
            'note': fake.sentence(),
            'created_at': timezone.now(),
        }
        checkin_data.update(kwargs)
        
        return DailyCheckIn.objects.create(**checkin_data)
    
    @staticmethod
    def create_checkin_streak(user, days):
        """Create a streak of check-ins."""
        checkins = []
        for i in range(days):
            checkin_date = date.today() - timedelta(days=i)
            checkin = CheckInFactory.create_checkin(
                user=user,
                date=checkin_date,
                consecutive_days=days - i
            )
            checkins.append(checkin)
        return checkins


class SpinWheelFactory:
    """Factory for creating spin wheel instances."""
    
    @staticmethod
    def create_spin(user=None, **kwargs):
        """Create a test spin."""
        spin_data = {
            'user': user or UserFactory.create_user(),
            'spun_at': timezone.now(),
            'coins_won': Decimal(str(random.uniform(0, 100))),
            'xp_earned': random.randint(0, 25),
            'outcome_idx': random.randint(0, 7),
            'is_boosted': random.choice([True, False]),
            'created_at': timezone.now(),
        }
        spin_data.update(kwargs)
        
        return SpinWheel.objects.create(**spin_data)
    
    @staticmethod
    def create_big_win_spin(user=None):
        """Create a spin with big win."""
        return SpinWheelFactory.create_spin(
            user=user,
            coins_won=Decimal(str(random.uniform(50, 100))),
            xp_earned=random.randint(20, 50)
        )


class QuestFactory:
    """Factory for creating quest instances."""
    
    @staticmethod
    def create_quest(**kwargs):
        """Create a test quest."""
        quest_data = {
            'name': fake.catch_phrase(),
            'description': fake.paragraph(),
            'type': random.choice(['daily', 'weekly', 'monthly', 'special']),
            'difficulty': random.choice(['easy', 'medium', 'hard', 'expert']),
            'required_progress': random.randint(1, 10),
            'coin_reward': Decimal(str(random.uniform(10, 100))),
            'xp_reward': random.randint(10, 50),
            'is_active': True,
            'expires_at': timezone.now() + timedelta(days=random.randint(1, 30)),
            'created_at': timezone.now(),
        }
        quest_data.update(kwargs)
        
        return Quest.objects.create(**quest_data)
    
    @staticmethod
    def create_user_quest(user=None, quest=None, **kwargs):
        """Create a test user quest."""
        quest_data = {
            'user': user or UserFactory.create_user(),
            'quest': quest or QuestFactory.create_quest(),
            'status': random.choice(['available', 'active', 'completed', 'expired']),
            'progress': random.randint(0, 10),
            'created_at': timezone.now(),
            'completed_at': timezone.now() if random.choice([True, False]) else None,
            'expires_at': timezone.now() + timedelta(days=random.randint(1, 30)),
        }
        quest_data.update(kwargs)
        
        return UserQuest.objects.create(**quest_data)


class AchievementFactory:
    """Factory for creating achievement instances."""
    
    @staticmethod
    def create_achievement(**kwargs):
        """Create a test achievement."""
        achievement_data = {
            'name': fake.catch_phrase(),
            'description': fake.paragraph(),
            'type': random.choice(['streak', 'total', 'level', 'social', 'earning']),
            'difficulty': random.choice(['easy', 'medium', 'hard', 'legendary']),
            'icon': random.choice(['🏆', '🌟', '🎯', '🔥', '💎', '👑']),
            'xp_reward': random.randint(10, 100),
            'coin_reward': Decimal(str(random.uniform(0, 50))),
            'badge': fake.word(),
            'is_active': True,
            'created_at': timezone.now(),
        }
        achievement_data.update(kwargs)
        
        return Achievement.objects.create(**achievement_data)
    
    @staticmethod
    def create_user_achievement(user=None, achievement=None, **kwargs):
        """Create a test user achievement."""
        achievement_data = {
            'user': user or UserFactory.create_user(),
            'achievement': achievement or AchievementFactory.create_achievement(),
            'progress': random.randint(0, 100),
            'unlocked_at': timezone.now() if random.choice([True, False]) else None,
        }
        achievement_data.update(kwargs)
        
        return UserAchievement.objects.create(**achievement_data)


class ShopFactory:
    """Factory for creating shop instances."""
    
    @staticmethod
    def create_shop_item(**kwargs):
        """Create a test shop item."""
        item_data = {
            'name': fake.catch_phrase(),
            'description': fake.paragraph(),
            'type': random.choice([choice[0] for choice in SHOP_ITEM_TYPE_CHOICES]),
            'price': Decimal(str(random.uniform(1, 100))),
            'quantity': random.randint(1, 10),
            'rarity': random.choice([choice[0] for choice in SHOP_ITEM_RARITY_CHOICES]),
            'icon': random.choice(['💰', '💎', '🎁', '⭐', '🔮']),
            'is_active': True,
            'stock': random.randint(0, 100),
            'max_purchase_per_user': random.randint(1, 10),
            'created_at': timezone.now(),
        }
        item_data.update(kwargs)
        
        return ShopItem.objects.create(**item_data)
    
    @staticmethod
    def create_shop_purchase(user=None, item=None, **kwargs):
        """Create a test shop purchase."""
        purchase_data = {
            'user': user or UserFactory.create_user(),
            'item': item or ShopFactory.create_shop_item(),
            'quantity': random.randint(1, 5),
            'coins_spent': Decimal(str(random.uniform(10, 100))),
            'status': 'completed',
            'purchased_at': timezone.now(),
        }
        purchase_data.update(kwargs)
        
        return ShopPurchase.objects.create(**purchase_data)
    
    @staticmethod
    def create_user_inventory(user=None, item=None, **kwargs):
        """Create a test user inventory item."""
        inventory_data = {
            'user': user or UserFactory.create_user(),
            'item': item or ShopFactory.create_shop_item(),
            'quantity': random.randint(1, 10),
            'expires_at': timezone.now() + timedelta(days=random.randint(1, 30)) if random.choice([True, False]) else None,
        }
        inventory_data.update(kwargs)
        
        return UserInventory.objects.create(**inventory_data)


class LeaderboardFactory:
    """Factory for creating leaderboard instances."""
    
    @staticmethod
    def create_leaderboard_season(**kwargs):
        """Create a test leaderboard season."""
        season_data = {
            'period': random.choice(['daily', 'weekly', 'monthly']),
            'start_date': date.today() - timedelta(days=random.randint(1, 30)),
            'end_date': date.today() + timedelta(days=random.randint(1, 30)),
            'is_active': True,
            'prize_pool': Decimal(str(random.uniform(1000, 10000))),
            'created_at': timezone.now(),
        }
        season_data.update(kwargs)
        
        return LeaderboardSeason.objects.create(**season_data)
    
    @staticmethod
    def create_leaderboard(user=None, **kwargs):
        """Create a test leaderboard entry."""
        user = user or UserFactory.create_user()
        
        leaderboard_data = {
            'user': user,
            'date': date.today(),
            'total_coins_earned': Decimal(str(random.uniform(0, 1000))),
            'total_xp_earned': random.randint(0, 500),
            'rank': random.randint(1, 1000),
            'reward_distributed': random.choice([True, False]),
            'created_at': timezone.now(),
        }
        leaderboard_data.update(kwargs)
        
        return Leaderboard.objects.create(**leaderboard_data)
    
    @staticmethod
    def create_leaderboard_reward(**kwargs):
        """Create a test leaderboard reward."""
        reward_data = {
            'rank': random.randint(1, 100),
            'season_type': random.choice(['daily', 'weekly', 'monthly']),
            'reward_coins': Decimal(str(random.uniform(10, 1000))),
            'reward_xp': random.randint(10, 500),
            'reward_badge': fake.word(),
            'created_at': timezone.now(),
        }
        reward_data.update(kwargs)
        
        return LeaderboardReward.objects.create(**reward_data)


class NotificationFactory:
    """Factory for creating notification instances."""
    
    @staticmethod
    def create_notification(user=None, **kwargs):
        """Create a test notification."""
        notification_data = {
            'user': user or UserFactory.create_user(),
            'type': random.choice(['achievement', 'quest', 'level_up', 'reward', 'social', 'system']),
            'title': fake.sentence(),
            'body': fake.paragraph(),
            'icon': random.choice(['🏆', '🎯', '⭐', '🎁', '📢']),
            'data': {'key': 'value'},
            'is_read': random.choice([True, False]),
            'read_at': timezone.now() if random.choice([True, False]) else None,
            'created_at': timezone.now(),
        }
        notification_data.update(kwargs)
        
        return Notification.objects.create(**notification_data)


class SocialFactory:
    """Factory for creating social instances."""
    
    @staticmethod
    def create_feed_item(user=None, **kwargs):
        """Create a test feed item."""
        feed_data = {
            'user': user or UserFactory.create_user(),
            'feed_type': random.choice(['achievement', 'level_up', 'streak_milestone', 'social']),
            'title': fake.sentence(),
            'body': fake.paragraph(),
            'image_url': fake.url() if random.choice([True, False]) else None,
            'likes_count': random.randint(0, 100),
            'comments_count': random.randint(0, 50),
            'created_at': timezone.now(),
        }
        feed_data.update(kwargs)
        
        return FeedItem.objects.create(**feed_data)
    
    @staticmethod
    def create_friendship(user1=None, user2=None, **kwargs):
        """Create a test friendship."""
        user1 = user1 or UserFactory.create_user()
        user2 = user2 or UserFactory.create_user()
        
        friendship_data = {
            'user': user1,
            'friend': user2,
            'status': random.choice(['pending', 'active']),
            'created_at': timezone.now(),
            'accepted_at': timezone.now() if random.choice([True, False]) else None,
        }
        friendship_data.update(kwargs)
        
        return Friendship.objects.create(**friendship_data)


class ReferralFactory:
    """Factory for creating referral instances."""
    
    @staticmethod
    def create_referral_program(**kwargs):
        """Create a test referral program."""
        program_data = {
            'name': fake.catch_phrase(),
            'description': fake.paragraph(),
            'reward_coins': Decimal(str(random.uniform(10, 100))),
            'reward_xp': random.randint(10, 50),
            'reward_type': random.choice(['coins', 'xp', 'item', 'badge']),
            'is_active': True,
            'created_at': timezone.now(),
        }
        program_data.update(kwargs)
        
        return ReferralProgram.objects.create(**program_data)
    
    @staticmethod
    def create_referral(referrer=None, referred=None, **kwargs):
        """Create a test referral."""
        referrer = referrer or UserFactory.create_user()
        referred = referred or UserFactory.create_user()
        
        referral_data = {
            'referrer': referrer,
            'referred': referred,
            'program': ReferralFactory.create_referral_program(),
            'referral_code': ''.join(random.choices(string.ascii_uppercase + string.digits, k=8)),
            'status': random.choice(['pending', 'confirmed', 'rewarded', 'expired']),
            'created_at': timezone.now(),
            'confirmed_at': timezone.now() if random.choice([True, False]) else None,
            'rewarded_at': timezone.now() if random.choice([True, False]) else None,
        }
        referral_data.update(kwargs)
        
        return Referral.objects.create(**referral_data)


class XPFactory:
    """Factory for creating XP instances."""
    
    @staticmethod
    def create_user_xp(user=None, **kwargs):
        """Create a test user XP."""
        xp_data = {
            'user': user or UserFactory.create_user(),
            'total_xp': random.randint(0, 10000),
            'level': random.randint(1, 100),
            'level_updated_at': timezone.now(),
            'created_at': timezone.now(),
        }
        xp_data.update(kwargs)
        
        return UserXP.objects.create(**xp_data)


# ── Bulk Factory Methods ─────────────────────────────────────────────────────

class BulkFactory:
    """Factory for creating bulk test data."""
    
    @staticmethod
    def create_users(count=10, **kwargs):
        """Create multiple users."""
        users = []
        for i in range(count):
            user = UserFactory.create_user(
                username=f"testuser_{i}",
                email=f"testuser_{i}@example.com",
                **kwargs
            )
            users.append(user)
        return users
    
    @staticmethod
    def create_checkins(user, days=30):
        """Create check-ins for a user over multiple days."""
        checkins = []
        for i in range(days):
            checkin_date = date.today() - timedelta(days=i)
            checkin = CheckInFactory.create_checkin(
                user=user,
                date=checkin_date,
                consecutive_days=days - i
            )
            checkins.append(checkin)
        return checkins
    
    @staticmethod
    def create_spins(user, count=10):
        """Create multiple spins for a user."""
        spins = []
        for i in range(count):
            spin = SpinWheelFactory.create_spin(
                user=user,
                spun_at=timezone.now() - timedelta(hours=i)
            )
            spins.append(spin)
        return spins
    
    @staticmethod
    def create_leaderboard(count=100, date=None):
        """Create a leaderboard with multiple entries."""
        if date is None:
            date = date.today()
        
        users = BulkFactory.create_users(count)
        leaderboard = []
        
        for i, user in enumerate(users):
            entry = LeaderboardFactory.create_leaderboard(
                user=user,
                date=date,
                rank=i + 1,
                total_coins_earned=Decimal(str(random.uniform(0, 1000))),
                total_xp_earned=random.randint(0, 500)
            )
            leaderboard.append(entry)
        
        return leaderboard
    
    @staticmethod
    def create_achievements(count=20):
        """Create multiple achievements."""
        achievements = []
        for i in range(count):
            achievement = AchievementFactory.create_achievement(
                name=f"Achievement {i + 1}",
                description=f"Description for achievement {i + 1}"
            )
            achievements.append(achievement)
        return achievements
    
    @staticmethod
    def create_shop_items(count=10):
        """Create multiple shop items."""
        items = []
        for i in range(count):
            item = ShopFactory.create_shop_item(
                name=f"Item {i + 1}",
                description=f"Description for item {i + 1}"
            )
            items.append(item)
        return items


# ── Test Data Scenarios ─────────────────────────────────────────────────────

class TestDataScenario:
    """Factory for creating complete test data scenarios."""
    
    @staticmethod
    def create_basic_user_scenario():
        """Create basic user scenario with check-ins and spins."""
        user = UserFactory.create_user()
        
        # Create check-ins
        checkins = BulkFactory.create_checkins(user, days=7)
        
        # Create spins
        spins = BulkFactory.create_spins(user, count=5)
        
        # Create XP
        xp = XPFactory.create_user_xp(user, total_xp=150, level=2)
        
        return {
            'user': user,
            'checkins': checkins,
            'spins': spins,
            'xp': xp
        }
    
    @staticmethod
    def create_achiever_scenario():
        """Create user scenario with achievements."""
        user = UserFactory.create_user()
        
        # Create achievements
        achievements = BulkFactory.create_achievements(10)
        
        # Unlock some achievements
        unlocked_achievements = []
        for i, achievement in enumerate(achievements[:5]):
            user_achievement = AchievementFactory.create_user_achievement(
                user=user,
                achievement=achievement,
                progress=100,
                unlocked_at=timezone.now()
            )
            unlocked_achievements.append(user_achievement)
        
        return {
            'user': user,
            'achievements': achievements,
            'unlocked_achievements': unlocked_achievements
        }
    
    @staticmethod
    def create_shopper_scenario():
        """Create user scenario with shop purchases."""
        user = UserFactory.create_user()
        
        # Create shop items
        items = BulkFactory.create_shop_items(5)
        
        # Create purchases
        purchases = []
        for item in items[:3]:
            purchase = ShopFactory.create_shop_purchase(user=user, item=item)
            purchases.append(purchase)
        
        # Create inventory
        inventory = []
        for item in items[:2]:
            inventory_item = ShopFactory.create_user_inventory(user=user, item=item)
            inventory.append(inventory_item)
        
        return {
            'user': user,
            'items': items,
            'purchases': purchases,
            'inventory': inventory
        }
    
    @staticmethod
    def create_social_scenario():
        """Create user scenario with social interactions."""
        users = BulkFactory.create_users(5)
        
        # Create friendships
        friendships = []
        for i in range(len(users) - 1):
            friendship = SocialFactory.create_friendship(
                user1=users[i],
                user2=users[i + 1],
                status='active'
            )
            friendships.append(friendship)
        
        # Create feed items
        feed_items = []
        for user in users:
            for i in range(3):
                feed_item = SocialFactory.create_feed_item(user=user)
                feed_items.append(feed_item)
        
        return {
            'users': users,
            'friendships': friendships,
            'feed_items': feed_items
        }
    
    @staticmethod
    def create_leaderboard_scenario():
        """Create complete leaderboard scenario."""
        # Create leaderboard
        leaderboard = BulkFactory.create_leaderboard(count=50)
        
        # Create season
        season = LeaderboardFactory.create_leaderboard_season()
        
        # Create rewards
        rewards = []
        for rank in [1, 2, 3, 10, 25, 50]:
            reward = LeaderboardFactory.create_leaderboard_reward(rank=rank)
            rewards.append(reward)
        
        return {
            'leaderboard': leaderboard,
            'season': season,
            'rewards': rewards
        }


# ── Factory Utilities ─────────────────────────────────────────────────────

class FactoryUtils:
    """Utility functions for factories."""
    
    @staticmethod
    def random_date(start_date=None, end_date=None):
        """Generate random date within range."""
        if start_date is None:
            start_date = date.today() - timedelta(days=365)
        if end_date is None:
            end_date = date.today()
        
        time_between = end_date - start_date
        days_between = time_between.days
        random_number_of_days = random.randrange(days_between)
        
        return start_date + timedelta(days=random_number_of_days)
    
    @staticmethod
    def random_datetime(start_date=None, end_date=None):
        """Generate random datetime within range."""
        if start_date is None:
            start_date = timezone.now() - timedelta(days=365)
        if end_date is None:
            end_date = timezone.now()
        
        time_between = end_date - start_date
        seconds_between = time_between.total_seconds()
        random_number_of_seconds = random.randrange(int(seconds_between))
        
        return start_date + timedelta(seconds=random_number_of_seconds)
    
    @staticmethod
    def random_choice(choices):
        """Random choice from list or tuple."""
        return random.choice(choices)
    
    @staticmethod
    def random_boolean():
        """Generate random boolean."""
        return random.choice([True, False])
    
    @staticmethod
    def random_decimal(min_val=0, max_val=100):
        """Generate random decimal."""
        return Decimal(str(random.uniform(min_val, max_val)))
    
    @staticmethod
    def random_int(min_val=0, max_val=100):
        """Generate random integer."""
        return random.randint(min_val, max_val)
    
    @staticmethod
    def random_string(length=10):
        """Generate random string."""
        return ''.join(random.choices(string.ascii_letters + string.digits, k=length))
    
    @staticmethod
    def create_test_image_url():
        """Create test image URL."""
        return f"https://picsum.photos/seed/{random_string(10)}/200/200.jpg"
    
    @staticmethod
    def create_test_avatar_url():
        """Create test avatar URL."""
        return f"https://picsum.photos/seed/avatar_{random_string(10)}/100/100.jpg"
