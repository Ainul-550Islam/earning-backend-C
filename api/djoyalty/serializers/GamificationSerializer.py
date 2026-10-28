# api/djoyalty/serializers/GamificationSerializer.py
"""
Djoyalty Gamification Serializers -- NEW।
SpinWheel, ScratchCard, Lottery, Quiz, LeaderboardSeason --
all fully modelled but had ZERO serializers।

AUDIT FIX (2.3): LeaderboardSeasonSerializer.get_my_rank() previously
called LeaderboardService directly inside a SerializerMethodField —
business logic in the serializer layer (violation of "এক কাজের জন্য
একটাই মালিক").  The service call is now the sole responsibility of
LeaderboardSeasonViewSet (list/retrieve overrides), which annotates
each LeaderboardSeason instance with .customer_rank before handing off
to the serializer.  The serializer reads the pre-computed value only.
"""
from rest_framework import serializers
from ..models.gamification import (
    SpinWheelConfig, SpinWheelSlice, SpinWheelResult,
    ScratchCard, LotteryDraw, LotteryTicket,
    LeaderboardSeason, QuizReward, CustomerQuizAttempt,
)


# ─── Spin Wheel ────────────────────────────────────────────────────────────────

class SpinWheelSliceSerializer(serializers.ModelSerializer):
    class Meta:
        model = SpinWheelSlice
        fields = [
            'id', 'label', 'prize_type',
            'points_value', 'voucher_discount',
            'multiplier_value', 'multiplier_hours',
            'probability', 'color', 'icon', 'sort_order',
        ]
        read_only_fields = ['id']

    def validate_probability(self, value):
        if value < 0 or value > 100:
            raise serializers.ValidationError('Probability must be 0-100.')
        return value


class SpinWheelConfigSerializer(serializers.ModelSerializer):
    slices             = SpinWheelSliceSerializer(many=True, read_only=True)
    total_probability  = serializers.SerializerMethodField()
    is_currently_valid = serializers.SerializerMethodField()

    class Meta:
        model = SpinWheelConfig
        fields = [
            'id', 'name', 'description', 'trigger',
            'min_spend_to_unlock', 'spins_per_day',
            'is_active', 'valid_from', 'valid_until', 'image',
            'total_probability', 'is_currently_valid',
            'slices',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'total_probability', 'is_currently_valid',
                            'created_at', 'updated_at']

    def get_total_probability(self, obj) -> str:
        total = sum(s.probability for s in obj.slices.all())
        return str(total)

    def get_is_currently_valid(self, obj) -> bool:
        from django.utils import timezone
        now = timezone.now()
        if not obj.is_active:
            return False
        if obj.valid_from and obj.valid_from > now:
            return False
        if obj.valid_until and obj.valid_until < now:
            return False
        return True


class SpinWheelResultSerializer(serializers.ModelSerializer):
    customer_code = serializers.SerializerMethodField()
    slice_label   = serializers.SerializerMethodField()
    prize_type    = serializers.SerializerMethodField()

    class Meta:
        model = SpinWheelResult
        fields = [
            'id', 'customer', 'customer_code',
            'wheel', 'slice_won', 'slice_label', 'prize_type',
            'points_awarded', 'prize_claimed', 'claimed_at',
            'spun_at', 'created_at',
        ]
        read_only_fields = fields

    def get_customer_code(self, obj) -> str:
        return obj.customer.code if obj.customer else ''

    def get_slice_label(self, obj) -> str:
        return obj.slice_won.label if obj.slice_won else 'No Prize'

    def get_prize_type(self, obj) -> str:
        return obj.slice_won.prize_type if obj.slice_won else 'nothing'


class SpinWheelResultPublicSerializer(serializers.ModelSerializer):
    """Returned to customer after spin -- shows their prize only."""
    slice_label  = serializers.SerializerMethodField()
    prize_type   = serializers.SerializerMethodField()
    prize_value  = serializers.SerializerMethodField()

    class Meta:
        model = SpinWheelResult
        fields = [
            'id', 'slice_label', 'prize_type', 'prize_value',
            'points_awarded', 'prize_claimed', 'spun_at',
        ]
        read_only_fields = fields

    def get_slice_label(self, obj) -> str:
        return obj.slice_won.label if obj.slice_won else 'No Prize'

    def get_prize_type(self, obj) -> str:
        return obj.slice_won.prize_type if obj.slice_won else 'nothing'

    def get_prize_value(self, obj) -> dict:
        s = obj.slice_won
        if not s:
            return {}
        return {
            'points': str(s.points_value),
            'voucher_discount': str(s.voucher_discount),
            'multiplier': str(s.multiplier_value),
            'multiplier_hours': s.multiplier_hours,
        }


# ─── Scratch Card ──────────────────────────────────────────────────────────────

class ScratchCardSerializer(serializers.ModelSerializer):
    customer_code = serializers.SerializerMethodField()
    is_expired    = serializers.SerializerMethodField()
    # prize fields hidden until scratched
    prize_revealed = serializers.SerializerMethodField()

    class Meta:
        model = ScratchCard
        fields = [
            'id', 'customer', 'customer_code',
            'code', 'status', 'issued_for',
            'expires_at', 'is_expired',
            'scratched_at', 'claimed_at',
            'prize_revealed',
            'created_at',
        ]
        read_only_fields = fields

    def get_customer_code(self, obj) -> str:
        return obj.customer.code if obj.customer else ''

    def get_is_expired(self, obj) -> bool:
        if obj.status == 'expired':
            return True
        from django.utils import timezone
        if obj.expires_at and obj.expires_at < timezone.now():
            return True
        return False

    def get_prize_revealed(self, obj) -> dict:
        """Only reveal prize after scratching."""
        if obj.status in ('scratched', 'claimed'):
            return {
                'prize_type': obj.prize_type,
                'points_value': str(obj.points_value),
                'voucher_discount': str(obj.voucher_discount),
            }
        return {'prize_type': 'hidden'}


# ─── Lottery ───────────────────────────────────────────────────────────────────

class LotteryTicketSerializer(serializers.ModelSerializer):
    customer_code = serializers.SerializerMethodField()

    class Meta:
        model = LotteryTicket
        fields = [
            'id', 'lottery', 'customer', 'customer_code',
            'ticket_number', 'points_spent',
            'is_winner', 'purchased_at',
        ]
        read_only_fields = fields

    def get_customer_code(self, obj) -> str:
        return obj.customer.code if obj.customer else ''


class LotteryDrawSerializer(serializers.ModelSerializer):
    tickets_purchased_by_me = serializers.SerializerMethodField()
    is_open                 = serializers.SerializerMethodField()

    class Meta:
        model = LotteryDraw
        fields = [
            'id', 'name', 'description',
            'ticket_cost_points', 'max_tickets_per_customer',
            'prize_description', 'prize_points_value',
            'status', 'draw_date', 'start_date',
            'winner', 'total_tickets_sold',
            'image', 'is_open',
            'tickets_purchased_by_me',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'winner', 'total_tickets_sold',
                            'is_open', 'tickets_purchased_by_me',
                            'created_at', 'updated_at']

    def get_is_open(self, obj) -> bool:
        return obj.status == 'open'

    def get_tickets_purchased_by_me(self, obj) -> int:
        request = self.context.get('request')
        if request and hasattr(request, 'loyalty_customer'):
            return obj.tickets.filter(customer=request.loyalty_customer).count()
        return 0


class LotteryTicketPurchaseSerializer(serializers.Serializer):
    """POST /lottery/<id>/buy-tickets/"""
    quantity = serializers.IntegerField(min_value=1, max_value=50)


# ─── Leaderboard Season ────────────────────────────────────────────────────────

class LeaderboardSeasonSerializer(serializers.ModelSerializer):
    """
    Leaderboard season representation.

    AUDIT FIX (2.3 — serializer side):
    get_my_rank() no longer imports or calls LeaderboardService.
    The service call was the architecture violation: serializer layer
    must not own business logic.

    The viewset (LeaderboardSeasonViewSet) now annotates each
    LeaderboardSeason instance with `.customer_rank` before this
    serializer runs (via list() / retrieve() overrides).  The
    serializer simply reads the pre-computed attribute.

    Fallback to 0 so existing API contract is preserved when the
    serializer is used outside the viewset context (e.g. tests).
    """
    is_active_now  = serializers.SerializerMethodField()
    my_rank        = serializers.SerializerMethodField()
    days_remaining = serializers.SerializerMethodField()

    class Meta:
        model = LeaderboardSeason
        fields = [
            'id', 'name', 'description', 'season_type',
            'start_date', 'end_date', 'status',
            'first_prize_points', 'second_prize_points', 'third_prize_points',
            'participation_prize_points', 'metric',
            'prizes_distributed',
            'is_active_now', 'days_remaining', 'my_rank',
            'created_at',
        ]
        read_only_fields = ['id', 'prizes_distributed', 'is_active_now',
                            'days_remaining', 'my_rank', 'created_at']

    def get_is_active_now(self, obj) -> bool:
        return obj.status == 'active'

    def get_days_remaining(self, obj) -> int:
        from django.utils import timezone
        if obj.status == 'active' and obj.end_date:
            delta = obj.end_date.date() - timezone.now().date()
            return max(delta.days, 0)
        return 0

    def get_my_rank(self, obj) -> int:
        """
        AUDIT FIX (2.3): Service call removed from serializer.
        Rank is pre-annotated by LeaderboardSeasonViewSet onto obj.customer_rank.
        Serializer reads the value — it does NOT compute it.
        """
        return getattr(obj, 'customer_rank', 0)


# ─── Quiz ──────────────────────────────────────────────────────────────────────

class QuizRewardSerializer(serializers.ModelSerializer):
    is_currently_valid = serializers.SerializerMethodField()
    my_attempts        = serializers.SerializerMethodField()
    can_attempt        = serializers.SerializerMethodField()

    class Meta:
        model = QuizReward
        fields = [
            'id', 'title', 'description',
            'points_reward', 'pass_score',
            'max_attempts', 'time_limit_minutes',
            'is_active', 'valid_from', 'valid_until',
            'is_currently_valid', 'my_attempts', 'can_attempt',
            'created_at',
        ]
        read_only_fields = ['id', 'is_currently_valid', 'my_attempts',
                            'can_attempt', 'created_at']

    def get_is_currently_valid(self, obj) -> bool:
        from django.utils import timezone
        now = timezone.now()
        if not obj.is_active:
            return False
        if obj.valid_from and obj.valid_from > now:
            return False
        if obj.valid_until and obj.valid_until < now:
            return False
        return True

    def get_my_attempts(self, obj) -> int:
        request = self.context.get('request')
        if request and hasattr(request, 'loyalty_customer'):
            return obj.attempts.filter(customer=request.loyalty_customer).count()
        return 0

    def get_can_attempt(self, obj) -> bool:
        attempts = self.get_my_attempts(obj)
        return attempts < obj.max_attempts


class CustomerQuizAttemptSerializer(serializers.ModelSerializer):
    customer_code = serializers.SerializerMethodField()
    quiz_title    = serializers.SerializerMethodField()

    class Meta:
        model = CustomerQuizAttempt
        fields = [
            'id', 'customer', 'customer_code',
            'quiz', 'quiz_title',
            'score', 'passed', 'points_awarded',
            'attempt_number', 'started_at', 'completed_at',
        ]
        read_only_fields = fields

    def get_customer_code(self, obj) -> str:
        return obj.customer.code if obj.customer else ''

    def get_quiz_title(self, obj) -> str:
        return obj.quiz.title if obj.quiz else ''


class QuizSubmitSerializer(serializers.Serializer):
    """POST /quiz/<id>/submit/ -- submit quiz answers."""
    answers = serializers.DictField(
        child=serializers.CharField(),
        help_text='{"question_id": "answer_value", ...}',
    )
    time_taken_seconds = serializers.IntegerField(min_value=0, required=False)
