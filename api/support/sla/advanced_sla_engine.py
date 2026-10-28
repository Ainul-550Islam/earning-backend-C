"""
api/support/sla/advanced_sla_engine.py
FILE 11/70 — Advanced SLA Engine

Business hours + timezone + holiday aware SLA calculation।
Zendesk-এর মতো exact minute tracking।

Features:
- Business hours only calculation (9AM-6PM)
- Timezone support (Asia/Dhaka, UTC, etc.)
- Holiday exclusion (Eid, national holidays)
- Per-category SLA policies
- Real-time breach detection
- SLA pause (when waiting for user reply)

Settings:
    SLA_TIMEZONE = 'Asia/Dhaka'
    SLA_BUSINESS_HOURS_ONLY = True
"""
import logging
from datetime import datetime, timedelta, time
from django.utils import timezone
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

SLA_TIMEZONE           = getattr(settings, 'SLA_TIMEZONE',            'Asia/Dhaka')
SLA_BUSINESS_HOURS_ONLY= getattr(settings, 'SLA_BUSINESS_HOURS_ONLY', True)


class AdvancedSLAEngine:
    """
    World-class SLA engine।
    Exact business minute calculation।
    """

    # Default SLA policies per priority (hours)
    DEFAULT_POLICIES = {
        'urgent': {'first_response': 1,   'resolution': 4,   'name': 'Urgent SLA'},
        'high':   {'first_response': 4,   'resolution': 24,  'name': 'High SLA'},
        'medium': {'first_response': 8,   'resolution': 48,  'name': 'Medium SLA'},
        'low':    {'first_response': 24,  'resolution': 72,  'name': 'Low SLA'},
    }

    # Per-category overrides
    CATEGORY_POLICIES = {
        'fraud':      {'priority': 'urgent', 'first_response': 0.5, 'resolution': 2},
        'payment':    {'priority': 'high',   'first_response': 2,   'resolution': 12},
        'withdrawal': {'priority': 'high',   'first_response': 2,   'resolution': 12},
        'kyc':        {'priority': 'medium', 'first_response': 8,   'resolution': 48},
        'coins':      {'priority': 'medium', 'first_response': 12,  'resolution': 48},
        'account':    {'priority': 'medium', 'first_response': 8,   'resolution': 24},
        'technical':  {'priority': 'medium', 'first_response': 8,   'resolution': 48},
        'referral':   {'priority': 'low',    'first_response': 24,  'resolution': 72},
        'offer':      {'priority': 'low',    'first_response': 24,  'resolution': 72},
        'other':      {'priority': 'low',    'first_response': 24,  'resolution': 72},
    }

    # ──────────────────────────────────────────
    # SETUP SLA FOR NEW TICKET
    # ──────────────────────────────────────────
    def setup_ticket_sla(self, ticket) -> object:
        """
        New ticket create হলে SLA setup করো।
        Business hours ধরে deadline calculate করো।
        """
        from api.support.models import TicketSLA, SLAPolicy

        policy_data   = self._get_policy(ticket)
        now           = timezone.now()

        # Calculate deadlines
        first_response_due = self._add_sla_time(now, policy_data['first_response'])
        resolution_due     = self._add_sla_time(now, policy_data['resolution'])

        # Get or create policy
        db_policy = self._get_or_create_db_policy(ticket.priority, policy_data)

        sla, created = TicketSLA.objects.get_or_create(
            ticket   = ticket,
            defaults = {
                'policy':               db_policy,
                'first_response_due':   first_response_due,
                'resolution_due':       resolution_due,
                'first_response_breached': False,
                'resolution_breached':     False,
            }
        )

        if created:
            # Update ticket sla_policy
            ticket.sla_policy = db_policy
            ticket.save(update_fields=['sla_policy'])
            logger.info(
                f'SLA setup: {ticket.ticket_id} | '
                f'FR due: {first_response_due.strftime("%Y-%m-%d %H:%M")} | '
                f'Res due: {resolution_due.strftime("%Y-%m-%d %H:%M")}'
            )

        return sla

    # ──────────────────────────────────────────
    # REAL-TIME SLA STATUS
    # ──────────────────────────────────────────
    def get_sla_status(self, ticket) -> dict:
        """
        Ticket-এর real-time SLA status।
        Agent dashboard-এ live দেখাবে।
        """
        try:
            sla = ticket.sla
            now = timezone.now()

            # First response remaining
            fr_remaining = None
            fr_breached  = sla.first_response_breached
            if sla.first_response_due and not sla.first_response_at:
                diff        = (sla.first_response_due - now).total_seconds() / 60
                fr_remaining= round(diff, 1)
                if diff < 0 and not fr_breached:
                    fr_breached = True

            # Resolution remaining
            res_remaining = None
            res_breached  = sla.resolution_breached
            if sla.resolution_due and not sla.resolution_at:
                diff          = (sla.resolution_due - now).total_seconds() / 60
                res_remaining = round(diff, 1)
                if diff < 0 and not res_breached:
                    res_breached = True

            # Health status
            health = self._calculate_health(fr_remaining, res_remaining, fr_breached, res_breached)

            return {
                'ticket_id':                    ticket.ticket_id,
                'priority':                     ticket.priority,
                'sla_policy':                   sla.policy.name if sla.policy else 'Unknown',

                # First response
                'first_response_due':           sla.first_response_due,
                'first_response_at':            sla.first_response_at,
                'first_response_remaining_min': fr_remaining,
                'first_response_breached':      fr_breached,

                # Resolution
                'resolution_due':               sla.resolution_due,
                'resolution_at':                sla.resolution_at,
                'resolution_remaining_min':     res_remaining,
                'resolution_breached':          res_breached,

                # Overall
                'is_breached':                  fr_breached or res_breached,
                'health':                       health,
                'health_color':                 self._health_color(health),
            }
        except Exception as e:
            logger.error(f'SLA status failed for {ticket.ticket_id}: {e}')
            return {'ticket_id': ticket.ticket_id, 'error': str(e)}

    # ──────────────────────────────────────────
    # PAUSE / RESUME SLA (waiting for user)
    # ──────────────────────────────────────────
    def pause_sla(self, ticket) -> bool:
        """
        Ticket 'waiting_user' status হলে SLA pause।
        User reply না দেওয়া পর্যন্ত SLA time বাড়বে না।
        """
        try:
            sla = ticket.sla
            pause_key = f'sla_pause:{ticket.ticket_id}'

            if cache.get(pause_key):
                return True  # Already paused

            cache.set(pause_key, timezone.now().isoformat(), timeout=86400 * 7)
            logger.info(f'SLA paused: {ticket.ticket_id}')
            return True
        except Exception as e:
            logger.warning(f'SLA pause failed: {e}')
            return False

    def resume_sla(self, ticket) -> bool:
        """
        User reply দিলে SLA resume।
        Paused সময় deadline-এ যোগ করো।
        """
        try:
            sla       = ticket.sla
            pause_key = f'sla_pause:{ticket.ticket_id}'
            paused_at = cache.get(pause_key)

            if not paused_at:
                return True  # Not paused

            # Calculate pause duration
            from django.utils.timezone import make_aware
            import datetime as dt
            if isinstance(paused_at, str):
                paused_at_dt   = dt.datetime.fromisoformat(paused_at)
                if paused_at_dt.tzinfo is None:
                    paused_at_dt = make_aware(paused_at_dt)
            else:
                paused_at_dt = paused_at
            pause_duration = timezone.now() - paused_at_dt

            # Extend deadlines
            update_fields = []
            if sla.first_response_due and not sla.first_response_at:
                sla.first_response_due += pause_duration
                update_fields.append('first_response_due')
            if sla.resolution_due and not sla.resolution_at:
                sla.resolution_due += pause_duration
                update_fields.append('resolution_due')

            if update_fields:
                sla.save(update_fields=update_fields)

            cache.delete(pause_key)
            logger.info(f'SLA resumed: {ticket.ticket_id}, pause duration: {pause_duration}')
            return True
        except Exception as e:
            logger.warning(f'SLA resume failed: {e}')
            return False

    # ──────────────────────────────────────────
    # BREACH DETECTION & HANDLING
    # ──────────────────────────────────────────
    def check_and_handle_breach(self, ticket) -> dict:
        """
        SLA breach check করো এবং handle করো।
        Celery task এটা call করবে।
        """
        result = {
            'ticket_id':   ticket.ticket_id,
            'fr_breached': False,
            'res_breached':False,
            'actions':     [],
        }

        try:
            sla = ticket.sla
            now = timezone.now()

            # First response breach
            if (sla.first_response_due and
                not sla.first_response_at and
                not sla.first_response_breached and
                now > sla.first_response_due):

                self._handle_first_response_breach(ticket, sla)
                result['fr_breached'] = True
                result['actions'].append('first_response_breach_handled')

            # Resolution breach
            if (sla.resolution_due and
                not sla.resolution_at and
                not sla.resolution_breached and
                now > sla.resolution_due):

                self._handle_resolution_breach(ticket, sla)
                result['res_breached'] = True
                result['actions'].append('resolution_breach_handled')

            # Warning — 1 hour before breach
            if sla.first_response_due and not sla.first_response_at and not sla.warning_sent:
                warning_at = sla.first_response_due - timedelta(hours=1)
                if now >= warning_at:
                    self._send_sla_warning(ticket, 'first_response')
                    sla.warning_sent = True
                    sla.save(update_fields=['warning_sent'])
                    result['actions'].append('warning_sent')

        except Exception as e:
            logger.error(f'SLA breach check failed for {ticket.ticket_id}: {e}')

        return result

    def run_global_breach_check(self) -> dict:
        """
        সব active tickets-এর SLA check।
        Celery beat: প্রতি 15 মিনিটে।
        """
        from api.support.models import SupportTicket, TicketSLA
        stats = {'checked': 0, 'fr_breached': 0, 'res_breached': 0, 'warnings': 0}

        active_tickets = SupportTicket.objects.filter(
            status__in=['open', 'in_progress', 'waiting_user'],
        ).select_related('sla', 'assigned_to', 'user')

        for ticket in active_tickets:
            try:
                result = self.check_and_handle_breach(ticket)
                stats['checked'] += 1
                if result['fr_breached']:
                    stats['fr_breached'] += 1
                if result['res_breached']:
                    stats['res_breached'] += 1
                if 'warning_sent' in result['actions']:
                    stats['warnings'] += 1
            except Exception as e:
                logger.error(f'Global SLA check error on {ticket.ticket_id}: {e}')

        logger.info(f'Global SLA check: {stats}')
        return stats

    # ──────────────────────────────────────────
    # FIRST RESPONSE RECORDING
    # ──────────────────────────────────────────
    def record_first_response(self, ticket) -> bool:
        """Agent প্রথম reply দিলে first_response_at set করো"""
        try:
            sla = ticket.sla
            if not sla.first_response_at:
                sla.first_response_at = timezone.now()
                sla.save(update_fields=['first_response_at'])
                logger.info(f'First response recorded: {ticket.ticket_id}')
            return True
        except Exception as e:
            logger.warning(f'Record first response failed: {e}')
            return False

    def record_resolution(self, ticket) -> bool:
        """Ticket resolve হলে resolution_at set করো"""
        try:
            sla = ticket.sla
            if not sla.resolution_at:
                sla.resolution_at = timezone.now()
                sla.save(update_fields=['resolution_at'])
            return True
        except Exception as e:
            logger.warning(f'Record resolution failed: {e}')
            return False

    # ──────────────────────────────────────────
    # COMPLIANCE REPORT
    # ──────────────────────────────────────────
    def get_compliance_report(self, days: int = 30) -> dict:
        """SLA compliance report"""
        from api.support.models import TicketSLA
        from django.utils import timezone
        since   = timezone.now() - timedelta(days=days)
        slas    = TicketSLA.objects.filter(created_at__gte=since)
        total   = slas.count()

        if not total:
            return {'total': 0, 'compliance_rate': 100.0, 'period_days': days}

        fr_breached  = slas.filter(first_response_breached=True).count()
        res_breached = slas.filter(resolution_breached=True).count()
        any_breached = slas.filter(
            first_response_breached=True
        ).count() + slas.filter(
            resolution_breached=True,
            first_response_breached=False,
        ).count()

        # By priority
        by_priority = {}
        for priority in ['urgent', 'high', 'medium', 'low']:
            p_slas   = slas.filter(ticket__priority=priority)
            p_total  = p_slas.count()
            p_breach = p_slas.filter(
                first_response_breached=True
            ).count() + p_slas.filter(
                resolution_breached=True,
                first_response_breached=False
            ).count()
            if p_total:
                by_priority[priority] = {
                    'total':           p_total,
                    'breached':        p_breach,
                    'compliance_rate': round((p_total - p_breach) / p_total * 100, 1),
                    'sla_hours':       self.DEFAULT_POLICIES.get(priority, {}).get('resolution', 24),
                }

        return {
            'period_days':          days,
            'total':                total,
            'first_response_breached': fr_breached,
            'resolution_breached':  res_breached,
            'any_breached':         any_breached,
            'compliance_rate':      round((total - any_breached) / total * 100, 1),
            'by_priority':          by_priority,
        }

    # ──────────────────────────────────────────
    # BUSINESS HOURS CALCULATION
    # ──────────────────────────────────────────
    def _add_sla_time(self, start: datetime, hours: float) -> datetime:
        """
        Business hours ধরে SLA deadline calculate করো।
        Non-business hours এবং holidays skip করো।
        """
        if not SLA_BUSINESS_HOURS_ONLY:
            return start + timedelta(hours=hours)

        return self._add_business_hours(start, hours)

    def _add_business_hours(self, start: datetime, hours: float) -> datetime:
        """Exact business hours calculation"""
        try:
            import pytz
            tz       = pytz.timezone(SLA_TIMEZONE)
            current  = start.astimezone(tz)
            remaining= hours * 60  # Convert to minutes

            business_start = time(9, 0)   # 9 AM
            business_end   = time(18, 0)  # 6 PM

            while remaining > 0:
                current_time = current.time()
                weekday      = current.weekday()

                # Skip weekends (5=Saturday, 6=Sunday)
                if weekday >= 5:
                    # Move to Monday 9 AM
                    days_until_monday = (7 - weekday) % 7 or 7
                    current = current.replace(
                        hour=9, minute=0, second=0, microsecond=0
                    ) + timedelta(days=days_until_monday)
                    continue

                # Skip holidays
                if self._is_holiday(current.date()):
                    current = current.replace(
                        hour=9, minute=0, second=0, microsecond=0
                    ) + timedelta(days=1)
                    continue

                # Before business hours
                if current_time < business_start:
                    current = current.replace(
                        hour=business_start.hour,
                        minute=business_start.minute,
                        second=0, microsecond=0
                    )
                    continue

                # After business hours
                if current_time >= business_end:
                    current = (current + timedelta(days=1)).replace(
                        hour=business_start.hour,
                        minute=business_start.minute,
                        second=0, microsecond=0
                    )
                    continue

                # Calculate minutes available today
                end_today = current.replace(
                    hour=business_end.hour,
                    minute=business_end.minute,
                    second=0, microsecond=0
                )
                available = (end_today - current).total_seconds() / 60

                if remaining <= available:
                    current = current + timedelta(minutes=remaining)
                    remaining = 0
                else:
                    remaining -= available
                    current = (current + timedelta(days=1)).replace(
                        hour=business_start.hour,
                        minute=business_start.minute,
                        second=0, microsecond=0
                    )

            return current.astimezone(timezone.utc).replace(tzinfo=timezone.utc)

        except ImportError:
            # pytz not installed — simple calculation
            logger.warning('pytz not installed. Using simple SLA calculation. pip install pytz')
            return start + timedelta(hours=hours)
        except Exception as e:
            logger.error(f'Business hours calculation failed: {e}')
            return start + timedelta(hours=hours)

    def _is_holiday(self, date) -> bool:
        """Holiday check"""
        try:
            from api.support.models import Holiday
            return Holiday.objects.filter(date=date, affects_sla=True).exists()
        except Exception:
            return False

    def _get_policy(self, ticket) -> dict:
        """Ticket-এর SLA policy determine করো"""
        # Category-specific override
        cat_policy = self.CATEGORY_POLICIES.get(ticket.category)
        if cat_policy:
            return cat_policy

        # Priority-based default
        return self.DEFAULT_POLICIES.get(ticket.priority, self.DEFAULT_POLICIES['medium'])

    def _get_or_create_db_policy(self, priority: str, policy_data: dict):
        """DB-তে SLA policy get or create"""
        try:
            from api.support.models import SLAPolicy
            policy, _ = SLAPolicy.objects.get_or_create(
                priority  = priority,
                defaults  = {
                    'name':                  policy_data.get('name', f'{priority.title()} SLA'),
                    'first_response_hours':  policy_data['first_response'],
                    'resolution_hours':      policy_data['resolution'],
                    'business_hours_only':   SLA_BUSINESS_HOURS_ONLY,
                    'is_active':             True,
                }
            )
            return policy
        except Exception:
            return None

    def _handle_first_response_breach(self, ticket, sla) -> None:
        """First response breach handle"""
        from api.support.models import SLABreach
        now           = timezone.now()
        overdue_hours = (now - sla.first_response_due).total_seconds() / 3600

        SLABreach.objects.get_or_create(
            ticket      = ticket,
            breach_type = 'first_response',
            defaults    = {
                'policy':       sla.policy,
                'due_at':       sla.first_response_due,
                'overdue_hours':round(overdue_hours, 2),
            }
        )

        sla.first_response_breached = True
        sla.save(update_fields=['first_response_breached'])

        # Escalate ticket
        if not ticket.escalated:
            ticket.escalated    = True
            ticket.escalated_at = now
            priority_map = {'low': 'medium', 'medium': 'high', 'high': 'urgent'}
            ticket.priority = priority_map.get(ticket.priority, ticket.priority)
            ticket.save(update_fields=['escalated', 'escalated_at', 'priority'])

        logger.warning(f'SLA BREACH (first_response): {ticket.ticket_id}, overdue: {overdue_hours:.1f}h')

        # Notify
        self._notify_breach(ticket, 'first_response', overdue_hours)

    def _handle_resolution_breach(self, ticket, sla) -> None:
        """Resolution breach handle"""
        from api.support.models import SLABreach
        now           = timezone.now()
        overdue_hours = (now - sla.resolution_due).total_seconds() / 3600

        SLABreach.objects.get_or_create(
            ticket      = ticket,
            breach_type = 'resolution',
            defaults    = {
                'policy':       sla.policy,
                'due_at':       sla.resolution_due,
                'overdue_hours':round(overdue_hours, 2),
            }
        )

        sla.resolution_breached = True
        sla.save(update_fields=['resolution_breached'])

        logger.warning(f'SLA BREACH (resolution): {ticket.ticket_id}, overdue: {overdue_hours:.1f}h')
        self._notify_breach(ticket, 'resolution', overdue_hours)

    def _notify_breach(self, ticket, breach_type: str, overdue_hours: float) -> None:
        try:
            from api.support.sla.sla_breach_notifier import sla_notifier
            sla_notifier.notify_breach(ticket, breach_type, overdue_hours)
        except Exception as e:
            logger.warning(f'SLA breach notification failed: {e}')

    def _send_sla_warning(self, ticket, breach_type: str) -> None:
        try:
            from api.support.sla.sla_breach_notifier import sla_notifier
            sla_notifier.notify_warning(ticket, breach_type)
        except Exception as e:
            logger.warning(f'SLA warning failed: {e}')

    def _calculate_health(self, fr_remaining, res_remaining, fr_breached, res_breached) -> str:
        if fr_breached or res_breached:
            return 'breached'
        mins = min(
            fr_remaining  if fr_remaining  is not None else float('inf'),
            res_remaining if res_remaining is not None else float('inf'),
        )
        if mins < 0:
            return 'breached'
        if mins < 60:
            return 'critical'   # Less than 1 hour
        if mins < 240:
            return 'warning'    # Less than 4 hours
        return 'ok'

    def _health_color(self, health: str) -> str:
        return {
            'ok':      '#16a34a',
            'warning': '#ca8a04',
            'critical':'#ea580c',
            'breached':'#dc2626',
        }.get(health, '#6b7280')


# Singleton
advanced_sla_engine = AdvancedSLAEngine()