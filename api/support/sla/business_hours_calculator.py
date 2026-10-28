"""
api/support/sla/business_hours_calculator.py
FILE 13/70 — Business Hours Calculator

Exact business minutes calculation।
SLA compliance percentage-এর জন্য।
Agent productivity tracking-এর জন্য।

Features:
- Working minutes between two datetimes
- Multi-timezone support
- Holiday-aware
- Shift schedule integration
"""
import logging
from datetime import datetime, time, timedelta
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

DEFAULT_TZ             = getattr(settings, 'SLA_TIMEZONE', 'Asia/Dhaka')
DEFAULT_BUSINESS_START = time(9, 0)    # 9 AM
DEFAULT_BUSINESS_END   = time(18, 0)   # 6 PM
WORK_DAYS              = [0, 1, 2, 3, 4]  # Monday to Friday


class BusinessHoursCalculator:
    """
    Business hours calculator।
    Ticket response time accurately measure করো।
    """

    def __init__(
        self,
        timezone_name: str  = DEFAULT_TZ,
        business_start: time= DEFAULT_BUSINESS_START,
        business_end: time  = DEFAULT_BUSINESS_END,
        work_days: list     = None,
    ):
        self.timezone_name  = timezone_name
        self.business_start = business_start
        self.business_end   = business_end
        self.work_days      = work_days or WORK_DAYS

    # ──────────────────────────────────────────
    # MAIN: CALCULATE WORKING MINUTES
    # ──────────────────────────────────────────
    def working_minutes_between(self, start: datetime, end: datetime) -> float:
        """
        start থেকে end পর্যন্ত business minutes calculate করো।
        Weekends + holidays exclude করো।
        """
        if end <= start:
            return 0.0

        try:
            import pytz
            tz      = pytz.timezone(self.timezone_name)
            current = start.astimezone(tz)
            end_dt  = end.astimezone(tz)
            total   = 0.0

            while current < end_dt:
                day_end = self._get_day_end(current)

                # Skip non-working days
                if not self._is_working_day(current):
                    current = self._next_working_day_start(current)
                    continue

                # Before business hours
                if current.time() < self.business_start:
                    current = current.replace(
                        hour   = self.business_start.hour,
                        minute = self.business_start.minute,
                        second = 0, microsecond=0
                    )
                    continue

                # After business hours
                if current.time() >= self.business_end:
                    current = self._next_working_day_start(current)
                    continue

                # Calculate minutes for this segment
                segment_end = min(end_dt, day_end)
                minutes     = (segment_end - current).total_seconds() / 60
                total      += minutes

                current = day_end

            return round(total, 2)

        except ImportError:
            # Simple fallback without pytz
            diff    = (end - start).total_seconds() / 60
            # Rough estimate: 9 hours/day, 5 days/week
            business_ratio = (9 * 5) / (24 * 7)
            return round(diff * business_ratio, 2)

    def working_hours_between(self, start: datetime, end: datetime) -> float:
        """Working minutes → hours"""
        return round(self.working_minutes_between(start, end) / 60, 2)

    # ──────────────────────────────────────────
    # NEXT BUSINESS DATETIME
    # ──────────────────────────────────────────
    def next_business_datetime(self, dt: datetime) -> datetime:
        """
        দেওয়া datetime-এর পরের business time দাও।
        এখন business hours বাইরে থাকলে পরের business time দাও।
        """
        try:
            import pytz
            tz      = pytz.timezone(self.timezone_name)
            current = dt.astimezone(tz)

            # Already in business hours
            if self._is_working_day(current) and self._is_business_hour(current.time()):
                return dt

            # After business hours — next day
            if current.time() >= self.business_end:
                return self._next_working_day_start(current)

            # Before business hours — today's start
            if current.time() < self.business_start:
                return current.replace(
                    hour   = self.business_start.hour,
                    minute = self.business_start.minute,
                    second = 0, microsecond=0
                )

            return self._next_working_day_start(current)

        except ImportError:
            return dt

    # ──────────────────────────────────────────
    # TICKET METRICS
    # ──────────────────────────────────────────
    def calculate_first_response_time(self, ticket) -> float | None:
        """Ticket-এর actual first response business minutes"""
        if not ticket.admin_responded_at:
            return None
        return self.working_minutes_between(ticket.created_at, ticket.admin_responded_at)

    def calculate_resolution_time(self, ticket) -> float | None:
        """Ticket-এর actual resolution business minutes"""
        if not ticket.resolved_at:
            return None
        return self.working_minutes_between(ticket.created_at, ticket.resolved_at)

    def get_ticket_metrics(self, ticket) -> dict:
        """Complete ticket time metrics"""
        fr_minutes  = self.calculate_first_response_time(ticket)
        res_minutes = self.calculate_resolution_time(ticket)

        metrics = {
            'ticket_id': ticket.ticket_id,
        }

        if fr_minutes is not None:
            metrics['first_response'] = {
                'minutes': fr_minutes,
                'hours':   round(fr_minutes / 60, 2),
                'display': self._format_duration(fr_minutes),
            }

        if res_minutes is not None:
            metrics['resolution'] = {
                'minutes': res_minutes,
                'hours':   round(res_minutes / 60, 2),
                'display': self._format_duration(res_minutes),
            }

        # SLA compliance check
        try:
            sla        = ticket.sla
            fr_sla_min = sla.policy.first_response_hours * 60 if sla.policy else None
            res_sla_min= sla.policy.resolution_hours * 60 if sla.policy else None

            if fr_minutes is not None and fr_sla_min:
                metrics['first_response']['within_sla'] = fr_minutes <= fr_sla_min
                metrics['first_response']['sla_target_min'] = fr_sla_min

            if res_minutes is not None and res_sla_min:
                metrics['resolution']['within_sla'] = res_minutes <= res_sla_min
                metrics['resolution']['sla_target_min'] = res_sla_min
        except Exception:
            pass

        return metrics

    # ──────────────────────────────────────────
    # AGENT WORKING HOURS
    # ──────────────────────────────────────────
    def calculate_agent_online_time(self, agent_user, date) -> float:
        """Agent একদিনে কতক্ষণ online ছিল (minutes)"""
        try:
            from api.support.models import AgentStatus
            # This would need AgentStatusLog model for exact tracking
            # For now return shift-based estimate
            from api.support.models import SupportAgent
            agent  = SupportAgent.objects.get(user=agent_user)
            shifts = agent.shifts.filter(weekday=date.weekday(), is_active=True)
            if not shifts.exists():
                return 0.0

            shift      = shifts.first()
            start      = datetime.combine(date, shift.start_time)
            end        = datetime.combine(date, shift.end_time)
            return round((end - start).total_seconds() / 60, 1)
        except Exception:
            return 0.0

    # ──────────────────────────────────────────
    # DAILY / WEEKLY SUMMARIES
    # ──────────────────────────────────────────
    def get_business_hours_summary(self, date=None) -> dict:
        """আজকের business hours info"""
        if not date:
            date = timezone.now().date()

        dt = datetime.combine(date, time(12, 0))
        dt = dt.replace(tzinfo=timezone.utc)

        is_working = self._is_working_day_by_date(date)

        return {
            'date':           str(date),
            'is_working_day': is_working,
            'is_holiday':     self._check_holiday(date),
            'business_start': self.business_start.strftime('%H:%M'),
            'business_end':   self.business_end.strftime('%H:%M'),
            'timezone':       self.timezone_name,
            'total_hours':    (
                (self.business_end.hour * 60 + self.business_end.minute) -
                (self.business_start.hour * 60 + self.business_start.minute)
            ) / 60 if is_working else 0,
        }

    def get_remaining_business_minutes_today(self) -> float:
        """আজকে কতক্ষণ business time বাকি আছে (minutes)"""
        now = timezone.now()
        if not self._is_working_day(now):
            return 0.0

        try:
            import pytz
            tz      = pytz.timezone(self.timezone_name)
            local   = now.astimezone(tz)
            end_dt  = local.replace(
                hour   = self.business_end.hour,
                minute = self.business_end.minute,
                second = 0, microsecond=0
            )
            if local >= end_dt:
                return 0.0
            return round((end_dt - local).total_seconds() / 60, 1)
        except ImportError:
            return 0.0

    # ──────────────────────────────────────────
    # PRIVATE HELPERS
    # ──────────────────────────────────────────
    def _is_working_day(self, dt: datetime) -> bool:
        return dt.weekday() in self.work_days and not self._check_holiday(dt.date())

    def _is_working_day_by_date(self, date) -> bool:
        return date.weekday() in self.work_days and not self._check_holiday(date)

    def _is_business_hour(self, t: time) -> bool:
        return self.business_start <= t < self.business_end

    def _get_day_end(self, dt: datetime) -> datetime:
        return dt.replace(
            hour   = self.business_end.hour,
            minute = self.business_end.minute,
            second = 0, microsecond=0
        )

    def _next_working_day_start(self, dt: datetime) -> datetime:
        next_day = dt + timedelta(days=1)
        next_day = next_day.replace(
            hour   = self.business_start.hour,
            minute = self.business_start.minute,
            second = 0, microsecond=0
        )
        while not self._is_working_day(next_day):
            next_day += timedelta(days=1)
        return next_day

    def _check_holiday(self, date) -> bool:
        try:
            from api.support.models import Holiday
            return Holiday.objects.filter(date=date, affects_sla=True).exists()
        except Exception:
            return False

    def _format_duration(self, minutes: float) -> str:
        """Human readable duration"""
        if minutes < 60:
            return f'{int(minutes)}m'
        hours = int(minutes // 60)
        mins  = int(minutes % 60)
        if mins:
            return f'{hours}h {mins}m'
        return f'{hours}h'


# Default singleton (Asia/Dhaka timezone)
business_hours_calculator = BusinessHoursCalculator()