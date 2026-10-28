# engagement/tests/test_quests.py
import pytest
from datetime import date, timedelta
from decimal import Decimal

from ..services.quest_service import QuestService
from ..models.quest import Quest, UserQuest
from .factories import UserFactory, QuestFactory, UserQuestFactory


@pytest.mark.django_db
class TestQuestService:

    def test_init_daily_creates_user_quests(self):
        user  = UserFactory(coin_balance=Decimal("0"))
        QuestFactory(type="daily", action="checkin", is_active=True)
        QuestFactory(type="daily", action="spin",    is_active=True)
        created = QuestService.init_daily(user)
        assert len(created) == 2
        assert UserQuest.objects.filter(user=user, period_date=date.today()).count() == 2

    def test_init_daily_idempotent(self):
        """Calling init_daily twice should not create duplicate rows."""
        user  = UserFactory(coin_balance=Decimal("0"))
        QuestFactory(type="daily", action="checkin", is_active=True)
        QuestService.init_daily(user)
        QuestService.init_daily(user)
        assert UserQuest.objects.filter(user=user, period_date=date.today()).count() == 1

    def test_init_weekly_creates_for_monday(self):
        user   = UserFactory(coin_balance=Decimal("0"))
        monday = date.today() - timedelta(days=date.today().weekday())
        QuestFactory(type="weekly", action="spin", is_active=True)
        created = QuestService.init_weekly(user)
        assert len(created) == 1
        assert UserQuest.objects.filter(user=user, period_date=monday).exists()

    def test_record_action_advances_progress(self):
        user  = UserFactory(coin_balance=Decimal("0"))
        quest = QuestFactory(type="daily", action="checkin", target=3, is_active=True)
        uq    = UserQuestFactory(user=user, quest=quest, period_date=date.today(), status="active", progress=0)
        QuestService.record_action(user, "checkin", increment=1)
        uq.refresh_from_db()
        assert uq.progress == 1

    def test_record_action_completes_quest(self):
        user  = UserFactory(coin_balance=Decimal("0"))
        quest = QuestFactory(type="daily", action="spin", target=2,
                              coin_reward=Decimal("20"), xp_reward=50, is_active=True)
        uq    = UserQuestFactory(user=user, quest=quest, period_date=date.today(),
                                 status="active", progress=1)
        completed = QuestService.record_action(user, "spin", increment=1)
        assert len(completed) == 1
        uq.refresh_from_db()
        assert uq.status == "completed"
        assert uq.reward_claimed is True

    def test_completed_quest_grants_coins(self):
        user  = UserFactory(coin_balance=Decimal("0"))
        quest = QuestFactory(type="daily", action="checkin", target=1,
                              coin_reward=Decimal("30"), xp_reward=0, is_active=True)
        UserQuestFactory(user=user, quest=quest, period_date=date.today(),
                         status="active", progress=0)
        QuestService.record_action(user, "checkin", increment=1)
        user.refresh_from_db()
        assert user.coin_balance == Decimal("30")

    def test_active_for_user_returns_daily_and_weekly(self):
        user = UserFactory(coin_balance=Decimal("0"))
        daily_q  = QuestFactory(type="daily",  action="spin",    is_active=True)
        weekly_q = QuestFactory(type="weekly", action="checkin", is_active=True)
        monday   = date.today() - timedelta(days=date.today().weekday())
        UserQuestFactory(user=user, quest=daily_q,  period_date=date.today())
        UserQuestFactory(user=user, quest=weekly_q, period_date=monday)
        data = QuestService.active_for_user(user)
        assert len(data["daily"])  == 1
        assert len(data["weekly"]) == 1

    def test_record_action_does_not_exceed_target(self):
        user  = UserFactory(coin_balance=Decimal("0"))
        quest = QuestFactory(type="daily", action="checkin", target=3, is_active=True)
        uq    = UserQuestFactory(user=user, quest=quest, period_date=date.today(),
                                 status="active", progress=2)
        QuestService.record_action(user, "checkin", increment=10)
        uq.refresh_from_db()
        assert uq.progress == 3  # capped at target
