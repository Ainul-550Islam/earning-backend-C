# api/djoyalty/models/gamification.py
"""
Djoyalty Gamification Models -- World-class loyalty gamification।
SpinWheel, ScratchCard, Lottery/Raffle, QuizReward, LeaderboardSeason।

World reference: Open Loyalty, Voucherify, Smile.io, Starbucks Rewards।
"""
import logging
from decimal import Decimal
from django.db import models
from django.utils import timezone
from ..managers import ActiveManager

logger = logging.getLogger(__name__)


class SpinWheelConfig(models.Model):
    """
    Spin-the-Wheel configuration।
    Customer purchase/action এর পরে spin করতে পারে।
    World: Voucherify spin-wheel, WooCommerce gamification।
    """
    tenant = models.ForeignKey(
        'djoyalty.Tenant', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='spin_wheel_configs',
    )
    name = models.CharField(max_length=200, verbose_name='Wheel Name')
    description = models.TextField(null=True, blank=True)
    trigger = models.CharField(
        max_length=30,
        choices=[
            ('purchase', 'After Purchase'),
            ('login', 'Daily Login'),
            ('birthday', 'Birthday'),
            ('manual', 'Admin Manual'),
            ('campaign', 'Campaign'),
        ],
        default='purchase',
        verbose_name='Trigger',
    )
    min_spend_to_unlock = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Minimum Spend to Unlock Spin',
    )
    spins_per_day = models.PositiveIntegerField(default=1, verbose_name='Spins per Day')
    is_active = models.BooleanField(default=True)
    valid_from = models.DateTimeField(null=True, blank=True)
    valid_until = models.DateTimeField(null=True, blank=True)
    image = models.URLField(null=True, blank=True, verbose_name='Wheel Image URL')

    objects = models.Manager()
    active = ActiveManager()

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'djoyalty'
        verbose_name = 'Spin Wheel Config'
        verbose_name_plural = 'Spin Wheel Configs'
        # AUDIT FIX (4): (tenant, is_active) for active wheel listing;
        # (is_active, trigger) for trigger-based wheel lookup.
        indexes = [
            models.Index(fields=['tenant', 'is_active'],
                         name='spinwheel_tenant_active_idx'),
            models.Index(fields=['is_active', 'trigger'],
                         name='spinwheel_active_trigger_idx'),
        ]

    def __str__(self):
        return f'SpinWheel({self.name})'


class SpinWheelSlice(models.Model):
    """
    Individual slice on the spin wheel -- each slice = one prize।
    """
    wheel = models.ForeignKey(
        SpinWheelConfig, on_delete=models.CASCADE,
        related_name='slices', verbose_name='Wheel',
    )
    label = models.CharField(max_length=100, verbose_name='Slice Label')
    prize_type = models.CharField(
        max_length=20,
        choices=[
            ('points', 'Points'),
            ('voucher', 'Voucher'),
            ('gift_card', 'Gift Card'),
            ('multiplier', 'Points Multiplier'),
            ('nothing', 'No Prize (Try Again)'),
        ],
        default='points',
        verbose_name='Prize Type',
    )
    points_value = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Points Value',
    )
    voucher_discount = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Voucher Discount %',
    )
    multiplier_value = models.DecimalField(
        max_digits=6, decimal_places=2, default=Decimal('1'),
        verbose_name='Multiplier Value',
    )
    multiplier_hours = models.PositiveIntegerField(default=0, verbose_name='Multiplier Duration (hours)')
    probability = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('10.00'),
        verbose_name='Probability %',
        help_text='All slices probabilities must sum to 100',
    )
    color = models.CharField(max_length=20, default='#3b82f6', verbose_name='Slice Color')
    icon = models.CharField(max_length=100, null=True, blank=True, verbose_name='Icon')
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        app_label = 'djoyalty'
        verbose_name = 'Spin Wheel Slice'
        verbose_name_plural = 'Spin Wheel Slices'
        ordering = ['sort_order']
        # AUDIT FIX (4): (wheel,) for loading all slices for a wheel;
        # (wheel, sort_order) covers ordered slice fetch.
        indexes = [
            models.Index(fields=['wheel', 'sort_order'],
                         name='spinslice_wheel_order_idx'),
        ]

    def __str__(self):
        return f'Slice({self.wheel.name}: {self.label} -- {self.probability}%)'


class SpinWheelResult(models.Model):
    """
    Customer এর spin result record।
    """
    customer = models.ForeignKey(
        'djoyalty.Customer', on_delete=models.CASCADE,
        related_name='spin_results', verbose_name='Customer',
    )
    wheel = models.ForeignKey(
        SpinWheelConfig, on_delete=models.CASCADE,
        related_name='results', verbose_name='Wheel',
    )
    slice_won = models.ForeignKey(
        SpinWheelSlice, null=True, on_delete=models.SET_NULL,
        related_name='results', verbose_name='Slice Won',
    )
    points_awarded = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
    )
    prize_claimed = models.BooleanField(default=False)
    claimed_at = models.DateTimeField(null=True, blank=True)
    reference_txn = models.ForeignKey(
        'djoyalty.Txn', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='spin_results',
    )
    spun_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'djoyalty'
        verbose_name = 'Spin Wheel Result'
        verbose_name_plural = 'Spin Wheel Results'
        ordering = ['-spun_at']
        indexes = [
            models.Index(fields=['customer', 'wheel', 'spun_at']),
        ]

    def __str__(self):
        prize = self.slice_won.label if self.slice_won else 'No Prize'
        return f'SpinResult({self.customer.code}: {prize})'


class ScratchCard(models.Model):
    """
    Scratch card model -- customer scratches to reveal prize।
    World: WooCommerce gamification, Open Loyalty coupons।
    """
    tenant = models.ForeignKey(
        'djoyalty.Tenant', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='scratch_cards',
    )
    customer = models.ForeignKey(
        'djoyalty.Customer', on_delete=models.CASCADE,
        related_name='scratch_cards', verbose_name='Customer',
    )
    code = models.CharField(max_length=30, unique=True, verbose_name='Card Code')
    prize_type = models.CharField(
        max_length=20,
        choices=[
            ('points', 'Points'),
            ('voucher', 'Voucher Discount'),
            ('gift_card', 'Gift Card'),
            ('nothing', 'No Prize'),
        ],
        default='points',
    )
    points_value = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Points Value (hidden until scratch)',
    )
    voucher_discount = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
    )
    status = models.CharField(
        max_length=20,
        choices=[
            ('unscratched', 'Unscratched'),
            ('scratched', 'Scratched'),
            ('claimed', 'Claimed'),
            ('expired', 'Expired'),
        ],
        default='unscratched',
    )
    issued_for = models.CharField(max_length=100, null=True, blank=True, verbose_name='Issued For (purchase/campaign)')
    expires_at = models.DateTimeField(null=True, blank=True)
    scratched_at = models.DateTimeField(null=True, blank=True)
    claimed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = models.Manager()
    active = ActiveManager()

    class Meta:
        app_label = 'djoyalty'
        verbose_name = 'Scratch Card'
        verbose_name_plural = 'Scratch Cards'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['code']),
            models.Index(fields=['customer', 'status']),
        ]

    def __str__(self):
        return f'ScratchCard({self.code}: {self.customer.code} [{self.status}])'

    def save(self, *args, **kwargs):
        if self.code:
            self.code = self.code.upper()
        super().save(*args, **kwargs)


class LotteryDraw(models.Model):
    """
    Lottery/Raffle draw -- customers buy tickets with points।
    World: Capital One, airline miles lotteries।
    """
    tenant = models.ForeignKey(
        'djoyalty.Tenant', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='lottery_draws',
    )
    name = models.CharField(max_length=200, verbose_name='Lottery Name')
    description = models.TextField(null=True, blank=True)
    ticket_cost_points = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('50'),
        verbose_name='Points per Ticket',
    )
    max_tickets_per_customer = models.PositiveIntegerField(
        default=10, verbose_name='Max Tickets per Customer',
    )
    prize_description = models.TextField(verbose_name='Prize Description')
    prize_points_value = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Prize Points Value',
    )
    status = models.CharField(
        max_length=20,
        choices=[
            ('upcoming', 'Upcoming'),
            ('open', 'Open for Entries'),
            ('closed', 'Closed'),
            ('drawn', 'Drawn'),
        ],
        default='upcoming',
    )
    draw_date = models.DateTimeField(verbose_name='Draw Date')
    start_date = models.DateTimeField(default=timezone.now)
    winner = models.ForeignKey(
        'djoyalty.Customer', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='lottery_wins',
        verbose_name='Winner',
    )
    total_tickets_sold = models.PositiveIntegerField(default=0)
    image = models.URLField(null=True, blank=True)

    objects = models.Manager()
    active = ActiveManager()

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'djoyalty'
        verbose_name = 'Lottery Draw'
        verbose_name_plural = 'Lottery Draws'
        ordering = ['-draw_date']
        # AUDIT FIX (4): (tenant, status) for status-filtered listing;
        # (status, draw_date) for upcoming draw scheduling.
        indexes = [
            models.Index(fields=['tenant', 'status'],
                         name='lottery_tenant_status_idx'),
            models.Index(fields=['status', 'draw_date'],
                         name='lottery_status_date_idx'),
        ]

    def __str__(self):
        return f'Lottery({self.name} [{self.status}])'


class LotteryTicket(models.Model):
    """
    Customer এর lottery ticket।
    """
    lottery = models.ForeignKey(
        LotteryDraw, on_delete=models.CASCADE,
        related_name='tickets', verbose_name='Lottery',
    )
    customer = models.ForeignKey(
        'djoyalty.Customer', on_delete=models.CASCADE,
        related_name='lottery_tickets', verbose_name='Customer',
    )
    ticket_number = models.CharField(max_length=20, unique=True, verbose_name='Ticket Number')
    points_spent = models.DecimalField(max_digits=14, decimal_places=2)
    is_winner = models.BooleanField(default=False)
    purchased_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'djoyalty'
        verbose_name = 'Lottery Ticket'
        verbose_name_plural = 'Lottery Tickets'
        ordering = ['-purchased_at']
        indexes = [
            models.Index(fields=['lottery', 'customer']),
            models.Index(fields=['ticket_number']),
        ]

    def __str__(self):
        return f'Ticket({self.ticket_number}: {self.customer.code} -> {self.lottery.name})'


class LeaderboardSeason(models.Model):
    """
    Seasonal leaderboard -- quarterly/monthly competitions।
    World: Fitbit challenges, Xbox Rewards Hub।
    """
    tenant = models.ForeignKey(
        'djoyalty.Tenant', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='leaderboard_seasons',
    )
    name = models.CharField(max_length=200, verbose_name='Season Name')
    description = models.TextField(null=True, blank=True)
    season_type = models.CharField(
        max_length=20,
        choices=[
            ('monthly', 'Monthly'),
            ('quarterly', 'Quarterly'),
            ('annual', 'Annual'),
            ('custom', 'Custom'),
        ],
        default='monthly',
    )
    start_date = models.DateTimeField(verbose_name='Start Date')
    end_date = models.DateTimeField(verbose_name='End Date')
    status = models.CharField(
        max_length=20,
        choices=[('upcoming', 'Upcoming'), ('active', 'Active'), ('ended', 'Ended')],
        default='upcoming',
    )
    # Prizes for top positions
    first_prize_points = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('5000'),
    )
    second_prize_points = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('2000'),
    )
    third_prize_points = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('1000'),
    )
    participation_prize_points = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('100'),
        verbose_name='Participation Consolation Prize',
    )
    metric = models.CharField(
        max_length=30,
        choices=[
            ('lifetime_earned', 'Total Points Earned'),
            ('total_spend', 'Total Spend'),
            ('transaction_count', 'Transaction Count'),
            ('streak_days', 'Streak Days'),
            ('referral_count', 'Referral Count'),
        ],
        default='lifetime_earned',
        verbose_name='Ranking Metric',
    )
    prizes_distributed = models.BooleanField(default=False)

    objects = models.Manager()
    active = ActiveManager()

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'djoyalty'
        verbose_name = 'Leaderboard Season'
        verbose_name_plural = 'Leaderboard Seasons'
        ordering = ['-start_date']
        # AUDIT FIX (4): (tenant, status) for active season lookup;
        # (status, start_date, end_date) for time-window season queries.
        indexes = [
            models.Index(fields=['tenant', 'status'],
                         name='lbseason_tenant_status_idx'),
            models.Index(fields=['status', 'start_date', 'end_date'],
                         name='lbseason_status_dates_idx'),
        ]

    def __str__(self):
        return f'Season({self.name}: {self.start_date.strftime("%Y-%m")} [{self.status}])'


class QuizReward(models.Model):
    """
    Quiz/Survey -> points reward।
    World: Voucherify challenges, engagement mechanics।
    """
    tenant = models.ForeignKey(
        'djoyalty.Tenant', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='quiz_rewards',
    )
    title = models.CharField(max_length=200, verbose_name='Quiz Title')
    description = models.TextField(null=True, blank=True)
    points_reward = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('50'),
        verbose_name='Points Reward on Completion',
    )
    pass_score = models.PositiveIntegerField(default=80, verbose_name='Pass Score %')
    max_attempts = models.PositiveIntegerField(default=1, verbose_name='Max Attempts')
    time_limit_minutes = models.PositiveIntegerField(default=10, verbose_name='Time Limit (minutes)')
    is_active = models.BooleanField(default=True)
    valid_from = models.DateTimeField(null=True, blank=True)
    valid_until = models.DateTimeField(null=True, blank=True)

    objects = models.Manager()
    active = ActiveManager()

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'djoyalty'
        verbose_name = 'Quiz Reward'
        verbose_name_plural = 'Quiz Rewards'
        # AUDIT FIX (4): (tenant, is_active) for active quiz listing;
        # (is_active, valid_from, valid_until) for time-window availability.
        indexes = [
            models.Index(fields=['tenant', 'is_active'],
                         name='quizreward_tenant_active_idx'),
            models.Index(fields=['is_active', 'valid_from', 'valid_until'],
                         name='quizreward_active_dates_idx'),
        ]

    def __str__(self):
        return f'Quiz({self.title}: {self.points_reward} pts)'


class CustomerQuizAttempt(models.Model):
    """
    Customer এর quiz attempt record।
    """
    customer = models.ForeignKey(
        'djoyalty.Customer', on_delete=models.CASCADE,
        related_name='quiz_attempts',
    )
    quiz = models.ForeignKey(
        QuizReward, on_delete=models.CASCADE,
        related_name='attempts',
    )
    score = models.PositiveIntegerField(default=0, verbose_name='Score %')
    passed = models.BooleanField(default=False)
    points_awarded = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
    )
    attempt_number = models.PositiveIntegerField(default=1)
    started_at = models.DateTimeField(default=timezone.now)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'djoyalty'
        verbose_name = 'Customer Quiz Attempt'
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['customer', 'quiz']),
        ]

    def __str__(self):
        return f'QuizAttempt({self.customer.code}: {self.quiz.title} score={self.score}%)'
