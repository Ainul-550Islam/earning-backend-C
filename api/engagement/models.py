# engagement/models.py
from django.db import models
from django.utils import timezone
from datetime import date
from django.conf import settings
from django.utils.translation import gettext_lazy as _


class DailyCheckIn(models.Model):

    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )
    # user = models.ForeignKey('api.User', on_delete=models.CASCADE, null=True, blank=True)
    user = models.ForeignKey(
    settings.AUTH_USER_MODEL, 
    on_delete=models.CASCADE,
    related_name='engagement_dailycheckin_user')
    date = models.DateField(default=date.today)
    coins_earned = models.DecimalField(max_digits=10, decimal_places=2, default=5, null=True, blank=True)
    consecutive_days = models.IntegerField(default=1)
    bonus_claimed = models.BooleanField(default=False)
    reward_claimed = models.BooleanField(default=False)


    
    class Meta:
        unique_together = ['user', 'date']
        ordering = ['-date']


class SpinWheel(models.Model):

    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )
    # user = models.ForeignKey('api.User', on_delete=models.CASCADE, null=True, blank=True)
    # ২. SpinWheel মডেলের জন্য
    user = models.ForeignKey(
    settings.AUTH_USER_MODEL, 
    on_delete=models.CASCADE,
    related_name='engagement_spinwheel_user'
    )
    coins_won = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    spun_at = models.DateTimeField(auto_now_add=True)
    total_spins = models.IntegerField(default=0)
    total_won = models.IntegerField(default=0)
    last_spin = models.DateTimeField(auto_now=True)


    
    @classmethod
    def can_spin(cls, user):
        """Check if user can spin today"""
        today = timezone.now().date()
        spins_today = cls.objects.filter(user=user, spun_at__date=today).count()
        return spins_today < 5  # Max 5 spins per day


class Leaderboard(models.Model):
    """Daily leaderboard cache"""
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )

    # user = models.ForeignKey('api.User', on_delete=models.CASCADE, null=True, blank=True)
    user = models.ForeignKey(
    settings.AUTH_USER_MODEL, 
    on_delete=models.CASCADE,
    related_name='engagement_leaderboard_user'
    )
    date = models.DateField(default=date.today)
    total_coins_earned = models.DecimalField(max_digits=10, decimal_places=2, default=0, null=True, blank=True)
    rank = models.IntegerField(default=0)
    
    class Meta:
        unique_together = ['user', 'date']
        ordering = ['date', 'rank']


class LeaderboardReward(models.Model):

    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )
    rank = models.IntegerField(unique=True)
    reward_coins = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    class Meta:
        ordering = ['rank']