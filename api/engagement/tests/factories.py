# engagement/tests/factories.py
import factory
import factory.fuzzy
from datetime import date, timedelta
from django.contrib.auth import get_user_model
from factory.django import DjangoModelFactory

from ..models.checkin import DailyCheckIn
from ..models.spinwheel import SpinWheel
from ..models.leaderboard import Leaderboard, LeaderboardReward, LeaderboardSeason
from ..models.achievement import Achievement, UserAchievement, AchievementProgress
from ..models.xp import UserXP, XPTransaction
from ..models.quest import Quest, UserQuest
from ..models.challenge import Challenge, ChallengeParticipant
from ..models.shop import ShopItem, ShopPurchase, UserInventory
from ..models.referral import ReferralProgram, Referral
from ..models.notification import Notification, UserPushToken
from ..constants import ACHIEVEMENT_TYPES, QUEST_TYPES, SHOP_ITEM_TYPES

User = get_user_model()


class UserFactory(DjangoModelFactory):
    class Meta:
        model = User

    username   = factory.Sequence(lambda n: f"user_{n}")
    email      = factory.LazyAttribute(lambda o: f"{o.username}@example.com")
    password   = factory.PostGenerationMethodCall("set_password", "testpass123")
    is_active  = True
    coin_balance = factory.fuzzy.FuzzyDecimal(0, 500, precision=2)


class DailyCheckInFactory(DjangoModelFactory):
    class Meta:
        model = DailyCheckIn

    user             = factory.SubFactory(UserFactory)
    date             = factory.LazyFunction(date.today)
    coins_earned     = factory.fuzzy.FuzzyDecimal(5, 35, precision=2)
    xp_earned        = factory.fuzzy.FuzzyInteger(10, 70)
    consecutive_days = factory.fuzzy.FuzzyInteger(1, 30)
    bonus_claimed    = False
    reward_claimed   = False
    streak_shield_used = False
    note             = factory.LazyAttribute(lambda o: f"Day {o.consecutive_days} bonus!")


class SpinWheelFactory(DjangoModelFactory):
    class Meta:
        model = SpinWheel

    user        = factory.SubFactory(UserFactory)
    coins_won   = factory.fuzzy.FuzzyDecimal(1, 50, precision=2)
    xp_earned   = 5
    outcome_idx = factory.fuzzy.FuzzyInteger(0, 4)
    is_boosted  = False


class LeaderboardSeasonFactory(DjangoModelFactory):
    class Meta:
        model = LeaderboardSeason

    period     = "daily"
    start_date = factory.LazyFunction(date.today)
    end_date   = factory.LazyAttribute(lambda o: o.start_date + timedelta(days=1))
    is_active  = True
    prize_pool = factory.fuzzy.FuzzyDecimal(100, 1000, precision=2)


class LeaderboardFactory(DjangoModelFactory):
    class Meta:
        model = Leaderboard

    user               = factory.SubFactory(UserFactory)
    date               = factory.LazyFunction(date.today)
    total_coins_earned = factory.fuzzy.FuzzyDecimal(10, 500, precision=2)
    total_xp_earned    = factory.fuzzy.FuzzyInteger(10, 500)
    rank               = factory.Sequence(lambda n: n + 1)
    reward_distributed = False


class LeaderboardRewardFactory(DjangoModelFactory):
    class Meta:
        model = LeaderboardReward

    rank         = factory.Sequence(lambda n: n + 1)
    season_type  = "daily"
    reward_coins = factory.fuzzy.FuzzyDecimal(10, 100, precision=2)
    reward_xp    = factory.fuzzy.FuzzyInteger(10, 100)
    reward_badge = ""


class AchievementFactory(DjangoModelFactory):
    class Meta:
        model = Achievement

    slug        = factory.Sequence(lambda n: f"achievement-{n}")
    name        = factory.Sequence(lambda n: f"Achievement {n}")
    description = factory.Faker("sentence")
    icon        = "🏅"
    badge_color = "#FFD700"
    type        = factory.fuzzy.FuzzyChoice([t[0] for t in ACHIEVEMENT_TYPES])
    threshold   = factory.fuzzy.FuzzyInteger(1, 100)
    xp_reward   = factory.fuzzy.FuzzyInteger(10, 200)
    coin_reward = factory.fuzzy.FuzzyDecimal(0, 50, precision=2)
    is_secret   = False
    is_active   = True
    order       = factory.Sequence(lambda n: n)


class UserAchievementFactory(DjangoModelFactory):
    class Meta:
        model = UserAchievement

    user        = factory.SubFactory(UserFactory)
    achievement = factory.SubFactory(AchievementFactory)
    notified    = False
    reward_claimed = False


class AchievementProgressFactory(DjangoModelFactory):
    class Meta:
        model = AchievementProgress

    user        = factory.SubFactory(UserFactory)
    achievement = factory.SubFactory(AchievementFactory)
    current     = factory.fuzzy.FuzzyInteger(0, 50)


class UserXPFactory(DjangoModelFactory):
    class Meta:
        model = UserXP

    user     = factory.SubFactory(UserFactory)
    total_xp = factory.fuzzy.FuzzyInteger(0, 5000)
    level    = factory.fuzzy.FuzzyInteger(1, 20)


class XPTransactionFactory(DjangoModelFactory):
    class Meta:
        model = XPTransaction

    user   = factory.SubFactory(UserFactory)
    source = factory.fuzzy.FuzzyChoice(["checkin", "spin", "quest", "achievement", "admin"])
    amount = factory.fuzzy.FuzzyInteger(5, 200)
    note   = factory.Faker("sentence", nb_words=4)
    ref_id = factory.Sequence(lambda n: str(n))


class QuestFactory(DjangoModelFactory):
    class Meta:
        model = Quest

    slug        = factory.Sequence(lambda n: f"quest-{n}")
    title       = factory.Sequence(lambda n: f"Quest {n}")
    description = factory.Faker("sentence")
    type        = factory.fuzzy.FuzzyChoice([t[0] for t in QUEST_TYPES])
    icon        = "📋"
    target      = factory.fuzzy.FuzzyInteger(1, 10)
    action      = factory.fuzzy.FuzzyChoice(["checkin", "spin", "buy_item"])
    coin_reward = factory.fuzzy.FuzzyDecimal(5, 50, precision=2)
    xp_reward   = factory.fuzzy.FuzzyInteger(10, 100)
    is_active   = True
    order       = factory.Sequence(lambda n: n)


class UserQuestFactory(DjangoModelFactory):
    class Meta:
        model = UserQuest

    user        = factory.SubFactory(UserFactory)
    quest       = factory.SubFactory(QuestFactory)
    period_date = factory.LazyFunction(date.today)
    status      = "active"
    progress    = 0
    reward_claimed = False


class ChallengeFactory(DjangoModelFactory):
    class Meta:
        model = Challenge

    title       = factory.Sequence(lambda n: f"Challenge {n}")
    description = factory.Faker("sentence")
    type        = "solo"
    metric      = "total_coins"
    target      = factory.fuzzy.FuzzyInteger(50, 500)
    starts_at   = factory.LazyFunction(lambda: __import__("django.utils.timezone", fromlist=["now"]).now())
    ends_at     = factory.LazyAttribute(
        lambda o: o.starts_at + __import__("datetime").timedelta(days=7)
    )
    coin_reward = factory.fuzzy.FuzzyDecimal(20, 200, precision=2)
    xp_reward   = factory.fuzzy.FuzzyInteger(50, 500)
    is_public   = True


class ChallengeParticipantFactory(DjangoModelFactory):
    class Meta:
        model = ChallengeParticipant

    user      = factory.SubFactory(UserFactory)
    challenge = factory.SubFactory(ChallengeFactory)
    status    = "active"
    score     = factory.fuzzy.FuzzyDecimal(0, 200, precision=2)
    rank      = factory.Sequence(lambda n: n + 1)


class ShopItemFactory(DjangoModelFactory):
    class Meta:
        model = ShopItem

    slug         = factory.Sequence(lambda n: f"item-{n}")
    name         = factory.Sequence(lambda n: f"Item {n}")
    description  = factory.Faker("sentence")
    type         = factory.fuzzy.FuzzyChoice([t[0] for t in SHOP_ITEM_TYPES])
    icon         = "🛍️"
    price_coins  = factory.fuzzy.FuzzyDecimal(10, 200, precision=2)
    stock        = -1
    max_per_user = -1
    effect_days  = 1
    is_active    = True
    order        = factory.Sequence(lambda n: n)


class ShopPurchaseFactory(DjangoModelFactory):
    class Meta:
        model = ShopPurchase

    user        = factory.SubFactory(UserFactory)
    item        = factory.SubFactory(ShopItemFactory)
    quantity    = 1
    coins_spent = factory.fuzzy.FuzzyDecimal(10, 200, precision=2)
    is_active   = True


class UserInventoryFactory(DjangoModelFactory):
    class Meta:
        model = UserInventory

    user     = factory.SubFactory(UserFactory)
    item     = factory.SubFactory(ShopItemFactory)
    quantity = factory.fuzzy.FuzzyInteger(1, 5)


class ReferralProgramFactory(DjangoModelFactory):
    class Meta:
        model = ReferralProgram

    name            = factory.Sequence(lambda n: f"Program {n}")
    referrer_reward = 50
    referee_reward  = 25
    referrer_xp     = 100
    referee_xp      = 50
    max_referrals   = 0
    is_active       = True


class ReferralFactory(DjangoModelFactory):
    class Meta:
        model = Referral

    referrer = factory.SubFactory(UserFactory)
    referee  = factory.SubFactory(UserFactory)
    code     = factory.Sequence(lambda n: f"CODE{n:06X}")
    status   = "pending"


class NotificationFactory(DjangoModelFactory):
    class Meta:
        model = Notification

    user    = factory.SubFactory(UserFactory)
    type    = "reward"
    title   = factory.Faker("sentence", nb_words=5)
    body    = factory.Faker("sentence")
    icon    = "🎉"
    is_read = False


class UserPushTokenFactory(DjangoModelFactory):
    class Meta:
        model = UserPushToken

    user      = factory.SubFactory(UserFactory)
    platform  = "fcm"
    token     = factory.Sequence(lambda n: f"fcm-token-{n:08x}")
    device_id = factory.Sequence(lambda n: f"device-{n}")
    is_active = True
