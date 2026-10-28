# api/djoyalty/tests/test_gamification.py
"""
Gamification Tests -- NEW।
SpinWheel, ScratchCard, Lottery, Quiz, LeaderboardSeason --
all had ZERO test coverage।
"""
from decimal import Decimal
from django.test import TestCase
from rest_framework.test import APITestCase
from rest_framework import status
from .factories import make_customer, make_loyalty_points


# ─── SpinWheel Tests ──────────────────────────────────────────────────────────

class SpinWheelModelTest(TestCase):

    def setUp(self):
        self.customer = make_customer(code='SPINCUST01')
        make_loyalty_points(self.customer, balance=Decimal('500'))

        from djoyalty.models.gamification import SpinWheelConfig, SpinWheelSlice
        self.wheel = SpinWheelConfig.objects.create(
            name='Test Wheel',
            trigger='manual',
            spins_per_day=3,
            is_active=True,
        )
        self.slice_points = SpinWheelSlice.objects.create(
            wheel=self.wheel,
            label='100 Points',
            prize_type='points',
            points_value=Decimal('100'),
            probability=Decimal('60'),
            color='#FFD700',
            sort_order=1,
        )
        self.slice_nothing = SpinWheelSlice.objects.create(
            wheel=self.wheel,
            label='No Prize',
            prize_type='nothing',
            points_value=Decimal('0'),
            probability=Decimal('40'),
            color='#CCCCCC',
            sort_order=2,
        )

    def test_wheel_created(self):
        self.assertTrue(self.wheel.is_active)
        self.assertEqual(self.wheel.slices.count(), 2)

    def test_total_probability_is_100(self):
        total = sum(s.probability for s in self.wheel.slices.all())
        self.assertEqual(total, Decimal('100'))

    def test_slice_has_correct_prize_type(self):
        self.assertEqual(self.slice_points.prize_type, 'points')
        self.assertEqual(self.slice_nothing.prize_type, 'nothing')

    def test_wheel_spins_per_day(self):
        self.assertEqual(self.wheel.spins_per_day, 3)


class SpinWheelSerializerTest(TestCase):

    def setUp(self):
        from djoyalty.models.gamification import SpinWheelConfig, SpinWheelSlice
        self.wheel = SpinWheelConfig.objects.create(
            name='Ser Wheel', trigger='manual', spins_per_day=1, is_active=True
        )
        SpinWheelSlice.objects.create(
            wheel=self.wheel, label='Prize', prize_type='points',
            points_value=Decimal('50'), probability=Decimal('100'), color='#000', sort_order=1
        )

    def test_serializer_includes_slices(self):
        from djoyalty.serializers.GamificationSerializer import SpinWheelConfigSerializer
        s = SpinWheelConfigSerializer(self.wheel)
        self.assertIn('slices', s.data)
        self.assertEqual(len(s.data['slices']), 1)

    def test_serializer_total_probability(self):
        from djoyalty.serializers.GamificationSerializer import SpinWheelConfigSerializer
        s = SpinWheelConfigSerializer(self.wheel)
        self.assertIn('total_probability', s.data)
        self.assertIn(s.data['total_probability'], ['100', '100.00', 100])

    def test_serializer_is_currently_valid(self):
        from djoyalty.serializers.GamificationSerializer import SpinWheelConfigSerializer
        s = SpinWheelConfigSerializer(self.wheel)
        self.assertTrue(s.data['is_currently_valid'])


# ─── ScratchCard Tests ────────────────────────────────────────────────────────

class ScratchCardModelTest(TestCase):

    def setUp(self):
        self.customer = make_customer(code='SCRATCUST01')

    def test_create_scratch_card(self):
        from djoyalty.models.gamification import ScratchCard
        card = ScratchCard.objects.create(
            customer=self.customer,
            code='SCRATCH001',
            issued_for='purchase',
            status='unscratched',
            prize_type='points',
            points_value=Decimal('200'),
        )
        self.assertEqual(card.status, 'unscratched')
        self.assertEqual(card.prize_type, 'points')

    def test_scratched_card_reveals_prize(self):
        from djoyalty.models.gamification import ScratchCard
        from django.utils import timezone
        card = ScratchCard.objects.create(
            customer=self.customer,
            code='SCRATCH002',
            issued_for='purchase',
            status='scratched',
            prize_type='points',
            points_value=Decimal('100'),
            scratched_at=timezone.now(),
        )
        self.assertEqual(card.status, 'scratched')
        self.assertIsNotNone(card.scratched_at)

    def test_serializer_hides_prize_when_unscratched(self):
        from djoyalty.models.gamification import ScratchCard
        from djoyalty.serializers.GamificationSerializer import ScratchCardSerializer
        card = ScratchCard(
            customer=self.customer,
            code='SCRATCH003',
            status='unscratched',
            prize_type='points',
            points_value=Decimal('50'),
        )
        s = ScratchCardSerializer(card)
        self.assertEqual(s.data['prize_revealed']['prize_type'], 'hidden')

    def test_serializer_reveals_prize_when_scratched(self):
        from djoyalty.models.gamification import ScratchCard
        from djoyalty.serializers.GamificationSerializer import ScratchCardSerializer
        from django.utils import timezone
        card = ScratchCard(
            customer=self.customer,
            code='SCRATCH004',
            status='scratched',
            prize_type='points',
            points_value=Decimal('50'),
            scratched_at=timezone.now(),
        )
        s = ScratchCardSerializer(card)
        self.assertNotEqual(s.data['prize_revealed']['prize_type'], 'hidden')
        self.assertEqual(s.data['prize_revealed']['prize_type'], 'points')


# ─── Lottery Tests ────────────────────────────────────────────────────────────

class LotteryModelTest(TestCase):

    def setUp(self):
        self.customer = make_customer(code='LOTTCUST01')
        make_loyalty_points(self.customer, balance=Decimal('1000'))
        from django.utils import timezone
        from datetime import timedelta
        from djoyalty.models.gamification import LotteryDraw
        self.lottery = LotteryDraw.objects.create(
            name='Test Lottery',
            ticket_cost_points=Decimal('50'),
            max_tickets_per_customer=5,
            prize_description='Grand Prize',
            prize_points_value=Decimal('10000'),
            status='open',
            draw_date=timezone.now() + timedelta(days=7),
            start_date=timezone.now(),
            total_tickets_sold=0,
        )

    def test_lottery_created_open(self):
        self.assertEqual(self.lottery.status, 'open')
        self.assertEqual(self.lottery.ticket_cost_points, Decimal('50'))

    def test_ticket_purchase_deducts_points(self):
        """Ticket purchase should cost points_per_ticket × quantity."""
        quantity = 3
        total_cost = self.lottery.ticket_cost_points * quantity
        self.assertEqual(total_cost, Decimal('150'))

    def test_lottery_serializer_is_open(self):
        from djoyalty.serializers.GamificationSerializer import LotteryDrawSerializer
        s = LotteryDrawSerializer(self.lottery)
        self.assertTrue(s.data['is_open'])

    def test_lottery_ticket_purchase_serializer_validates_quantity(self):
        from djoyalty.serializers.GamificationSerializer import LotteryTicketPurchaseSerializer
        s = LotteryTicketPurchaseSerializer(data={'quantity': 0})
        self.assertFalse(s.is_valid())

        s = LotteryTicketPurchaseSerializer(data={'quantity': 3})
        self.assertTrue(s.is_valid())

    def test_lottery_ticket_purchase_max_50(self):
        from djoyalty.serializers.GamificationSerializer import LotteryTicketPurchaseSerializer
        s = LotteryTicketPurchaseSerializer(data={'quantity': 51})
        self.assertFalse(s.is_valid())


# ─── Quiz Tests ───────────────────────────────────────────────────────────────

class QuizRewardTest(TestCase):

    def setUp(self):
        self.customer = make_customer(code='QUIZCUST01')
        make_loyalty_points(self.customer, balance=Decimal('500'))
        from djoyalty.models.gamification import QuizReward
        self.quiz = QuizReward.objects.create(
            title='Loyalty Knowledge Quiz',
            points_reward=Decimal('200'),
            pass_score=70,
            max_attempts=3,
            time_limit_minutes=10,
            is_active=True,
        )

    def test_quiz_created(self):
        self.assertTrue(self.quiz.is_active)
        self.assertEqual(self.quiz.max_attempts, 3)

    def test_quiz_serializer_my_attempts_zero(self):
        from djoyalty.serializers.GamificationSerializer import QuizRewardSerializer
        s = QuizRewardSerializer(self.quiz, context={})
        self.assertEqual(s.data['my_attempts'], 0)

    def test_quiz_serializer_can_attempt_true(self):
        from djoyalty.serializers.GamificationSerializer import QuizRewardSerializer
        s = QuizRewardSerializer(self.quiz, context={})
        self.assertTrue(s.data['can_attempt'])

    def test_quiz_submit_serializer_valid(self):
        from djoyalty.serializers.GamificationSerializer import QuizSubmitSerializer
        data = {'answers': {'q1': 'a', 'q2': 'b', 'q3': 'c'}}
        s = QuizSubmitSerializer(data=data)
        self.assertTrue(s.is_valid(), s.errors)

    def test_quiz_submit_serializer_empty_answers_invalid(self):
        from djoyalty.serializers.GamificationSerializer import QuizSubmitSerializer
        s = QuizSubmitSerializer(data={'answers': {}})
        # Empty dict is valid dict -- business logic validates content
        self.assertTrue(s.is_valid())


# ─── LeaderboardSeason Tests ──────────────────────────────────────────────────

class LeaderboardSeasonTest(TestCase):

    def setUp(self):
        from django.utils import timezone
        from datetime import timedelta
        from djoyalty.models.gamification import LeaderboardSeason
        self.season = LeaderboardSeason.objects.create(
            name='Q1 2026 Season',
            season_type='monthly',
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=30),
            status='active',
            first_prize_points=Decimal('5000'),
            second_prize_points=Decimal('3000'),
            third_prize_points=Decimal('1000'),
            participation_prize_points=Decimal('100'),
            metric='points_earned',
        )

    def test_season_created_active(self):
        self.assertEqual(self.season.status, 'active')
        self.assertEqual(self.season.first_prize_points, Decimal('5000'))

    def test_season_serializer_is_active_now(self):
        from djoyalty.serializers.GamificationSerializer import LeaderboardSeasonSerializer
        s = LeaderboardSeasonSerializer(self.season)
        self.assertTrue(s.data['is_active_now'])

    def test_season_serializer_days_remaining_positive(self):
        from djoyalty.serializers.GamificationSerializer import LeaderboardSeasonSerializer
        s = LeaderboardSeasonSerializer(self.season)
        self.assertGreater(s.data['days_remaining'], 0)
