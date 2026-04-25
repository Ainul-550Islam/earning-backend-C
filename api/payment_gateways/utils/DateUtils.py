# api/payment_gateways/utils/DateUtils.py
# Date and time utilities for payment processing

from datetime import date, datetime, timedelta
from typing import Optional, Tuple
from django.utils import timezone


class DateUtils:
    """Date/time utilities for payment gateway operations."""

    @staticmethod
    def now() -> datetime:
        """Return timezone-aware current datetime."""
        return timezone.now()

    @staticmethod
    def today() -> date:
        """Return current date in server timezone."""
        return timezone.localtime().date()

    @staticmethod
    def yesterday() -> date:
        return DateUtils.today() - timedelta(days=1)

    @staticmethod
    def start_of_month(d: date = None) -> date:
        """First day of the month."""
        d = d or DateUtils.today()
        return d.replace(day=1)

    @staticmethod
    def end_of_month(d: date = None) -> date:
        """Last day of the month."""
        import calendar
        d = d or DateUtils.today()
        last = calendar.monthrange(d.year, d.month)[1]
        return d.replace(day=last)

    @staticmethod
    def net_payment_date(days: int, from_date: date = None) -> date:
        """
        Calculate Net-N payment date (Net-15, Net-30, etc.).
        Skips weekends automatically.
        """
        d    = from_date or DateUtils.today()
        paid = d + timedelta(days=days)
        # If falls on weekend, push to Monday
        if paid.weekday() == 5:  # Saturday
            paid += timedelta(days=2)
        elif paid.weekday() == 6:  # Sunday
            paid += timedelta(days=1)
        return paid

    @staticmethod
    def next_payout_date(schedule_type: str) -> date:
        """
        Get next payout date based on schedule type.

        Args:
            schedule_type: 'daily' | 'weekly' | 'net15' | 'net30'

        Returns:
            date: Next scheduled payout date
        """
        today = DateUtils.today()
        if schedule_type == 'daily':
            return today + timedelta(days=1)
        elif schedule_type == 'weekly':
            # Next Monday
            days = (7 - today.weekday()) % 7 or 7
            return today + timedelta(days=days)
        elif schedule_type == 'net15':
            return DateUtils.net_payment_date(15, today)
        elif schedule_type == 'net30':
            return DateUtils.net_payment_date(30, today)
        return today + timedelta(days=30)

    @staticmethod
    def format_bd(dt: datetime) -> str:
        """Format datetime in Bangladesh style: 15 Jan 2025, 3:45 PM."""
        if not dt:
            return ''
        local = timezone.localtime(dt) if timezone.is_aware(dt) else dt
        return local.strftime('%d %b %Y, %I:%M %p')

    @staticmethod
    def age_in_days(dt: datetime) -> int:
        """How many days ago was this datetime."""
        if not dt:
            return 0
        delta = timezone.now() - dt
        return delta.days

    @staticmethod
    def get_date_range(period: str) -> Tuple[date, date]:
        """
        Parse period string to (start, end) date tuple.

        Supported:
            'today', 'yesterday', 'this_week', 'last_week',
            'this_month', 'last_month', 'last_7', 'last_30', 'last_90'
        """
        today = DateUtils.today()
        if period == 'today':
            return today, today
        elif period == 'yesterday':
            y = today - timedelta(days=1)
            return y, y
        elif period == 'this_week':
            start = today - timedelta(days=today.weekday())
            return start, today
        elif period == 'last_week':
            end   = today - timedelta(days=today.weekday() + 1)
            start = end - timedelta(days=6)
            return start, end
        elif period == 'this_month':
            return DateUtils.start_of_month(today), today
        elif period == 'last_month':
            last_month_end  = DateUtils.start_of_month(today) - timedelta(days=1)
            last_month_start= DateUtils.start_of_month(last_month_end)
            return last_month_start, last_month_end
        elif period.startswith('last_'):
            days = int(period.split('_')[1])
            return today - timedelta(days=days), today
        return today - timedelta(days=30), today

    @staticmethod
    def is_business_hours(hour: int = None, tz_offset: int = 6) -> bool:
        """
        Check if current time is within business hours (9AM–6PM BD time).
        Used for determining fast pay eligibility windows.
        """
        h = hour if hour is not None else (timezone.localtime().hour + tz_offset) % 24
        return 9 <= h <= 18
