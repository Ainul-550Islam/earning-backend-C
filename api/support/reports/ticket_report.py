"""
api/support/reports/ticket_report.py
FILE 48/70 — Full Ticket Analytics Report

Management-এর জন্য detailed ticket analytics।
CSV, PDF, Excel export support।
Scheduled + on-demand generation।
"""
import logging
import csv
from io import StringIO, BytesIO
from datetime import timedelta
from django.utils import timezone
from django.core.cache import cache

logger = logging.getLogger(__name__)


class TicketReport:
    """
    Comprehensive ticket analytics report।
    Period-based, category-based, agent-based breakdown।
    """

    CACHE_TTL = 1800  # 30 minutes

    # ──────────────────────────────────────────
    # MAIN REPORT
    # ──────────────────────────────────────────
    def generate(self, days: int = 30, filters: dict = None) -> dict:
        """
        Full ticket report generate করো।
        Returns: comprehensive metrics dict
        """
        cache_key = f'ticket_report:{days}:{hash(str(filters))}'
        cached    = cache.get(cache_key)
        if cached:
            return cached

        since = timezone.now() - timedelta(days=days)
        data  = {
            'period':               {'days': days, 'from': since.date().isoformat(), 'to': timezone.now().date().isoformat()},
            'summary':              self._summary(since, filters),
            'by_status':            self._by_status(since, filters),
            'by_priority':          self._by_priority(since, filters),
            'by_category':          self._by_category(since, filters),
            'by_channel':           self._by_channel(since, filters),
            'volume_trend':         self._volume_trend(since),
            'resolution_metrics':   self._resolution_metrics(since, filters),
            'response_time':        self._response_time_breakdown(since, filters),
            'top_users':            self._top_users(since),
            'hourly_distribution':  self._hourly_distribution(since),
            'day_of_week':          self._day_of_week(since),
            'first_contact_resolution': self._fcr_rate(since),
            'reopen_rate':          self._reopen_rate(since),
            'generated_at':         timezone.now().isoformat(),
        }

        cache.set(cache_key, data, timeout=self.CACHE_TTL)
        return data

    # ──────────────────────────────────────────
    # SUMMARY KPIs
    # ──────────────────────────────────────────
    def _summary(self, since, filters) -> dict:
        from api.support.models import SupportTicket, TicketRating
        from django.db.models import Avg, Count

        qs      = self._base_qs(since, filters)
        total   = qs.count()
        resolved= qs.filter(status='resolved').count()
        closed  = qs.filter(status='closed').count()
        open_ct = qs.filter(status__in=['open','in_progress','waiting_user']).count()
        spam    = qs.filter(status='spam').count()
        escalated = qs.filter(escalated=True).count()

        # Avg response
        responded = qs.filter(admin_responded_at__isnull=False)
        avg_resp  = 0
        if responded.exists():
            times    = [(t.admin_responded_at - t.created_at).total_seconds() / 60 for t in responded]
            avg_resp = round(sum(times) / len(times), 1)

        # Avg resolution
        res_tickets = qs.filter(resolved_at__isnull=False)
        avg_res     = 0
        if res_tickets.exists():
            times   = [(t.resolved_at - t.created_at).total_seconds() / 3600 for t in res_tickets]
            avg_res = round(sum(times) / len(times), 1)

        csat = TicketRating.objects.filter(
            ticket__created_at__gte=since
        ).aggregate(avg=Avg('rating'))['avg'] or 0

        return {
            'total':                total,
            'resolved':             resolved,
            'closed':               closed,
            'open':                 open_ct,
            'spam':                 spam,
            'escalated':            escalated,
            'resolution_rate_pct':  round((resolved + closed) / total * 100, 1) if total else 0,
            'escalation_rate_pct':  round(escalated / total * 100, 1) if total else 0,
            'avg_first_response_min':avg_resp,
            'avg_resolution_hrs':   avg_res,
            'csat_score':           round(csat, 2),
            'csat_pct':             round(csat / 5 * 100, 1),
        }

    # ──────────────────────────────────────────
    # BREAKDOWNS
    # ──────────────────────────────────────────
    def _by_status(self, since, filters) -> list:
        from api.support.models import SupportTicket
        from django.db.models import Count
        return list(
            self._base_qs(since, filters)
            .values('status')
            .annotate(count=Count('id'))
            .order_by('-count')
        )

    def _by_priority(self, since, filters) -> list:
        from django.db.models import Count, Avg
        result = []
        for p in ['urgent','high','medium','low']:
            qs_p = self._base_qs(since, filters).filter(priority=p)
            count= qs_p.count()
            if not count:
                continue
            responded = qs_p.filter(admin_responded_at__isnull=False)
            avg_resp  = 0
            if responded.exists():
                times    = [(t.admin_responded_at - t.created_at).total_seconds() / 60 for t in responded]
                avg_resp = round(sum(times) / len(times), 1)
            result.append({
                'priority':           p,
                'count':              count,
                'resolved':           qs_p.filter(status='resolved').count(),
                'avg_response_min':   avg_resp,
                'breach_count':       qs_p.filter(escalated=True).count(),
            })
        return result

    def _by_category(self, since, filters) -> list:
        from django.db.models import Count, Q
        return list(
            self._base_qs(since, filters)
            .values('category')
            .annotate(
                count   =Count('id'),
                resolved=Count('id', filter=Q(status='resolved')),
            )
            .order_by('-count')
        )

    def _by_channel(self, since, filters) -> list:
        from django.db.models import Count
        try:
            return list(
                self._base_qs(since, filters)
                .values('channel')
                .annotate(count=Count('id'))
                .order_by('-count')
            )
        except Exception:
            return []

    def _volume_trend(self, since) -> list:
        from api.support.models import SupportTicket
        from django.db.models import Count
        from django.db.models.functions import TruncDate
        return list(
            SupportTicket.objects.filter(created_at__gte=since)
            .annotate(date=TruncDate('created_at'))
            .values('date')
            .annotate(created=Count('id'))
            .order_by('date')
        )

    def _resolution_metrics(self, since, filters) -> dict:
        from api.support.models import SupportTicket

        qs          = self._base_qs(since, filters).filter(resolved_at__isnull=False)
        total       = qs.count()
        within_sla  = 0
        times       = []

        for t in qs:
            diff_hrs = (t.resolved_at - t.created_at).total_seconds() / 3600
            times.append(diff_hrs)
            from api.support.constants_extended import TicketPriority
            sla_hrs  = TicketPriority.SLA_HOURS.get(t.priority, 24)
            if diff_hrs <= sla_hrs:
                within_sla += 1

        return {
            'total_resolved':    total,
            'within_sla':        within_sla,
            'sla_compliance_pct':round(within_sla / total * 100, 1) if total else 0,
            'avg_hrs':           round(sum(times) / len(times), 1) if times else 0,
            'min_hrs':           round(min(times), 1) if times else 0,
            'max_hrs':           round(max(times), 1) if times else 0,
            'median_hrs':        round(sorted(times)[len(times)//2], 1) if times else 0,
        }

    def _response_time_breakdown(self, since, filters) -> dict:
        """First response time distribution"""
        qs      = self._base_qs(since, filters).filter(admin_responded_at__isnull=False)
        buckets = {'<1h': 0, '1-4h': 0, '4-8h': 0, '8-24h': 0, '>24h': 0}

        for t in qs:
            hrs = (t.admin_responded_at - t.created_at).total_seconds() / 3600
            if hrs < 1:      buckets['<1h']   += 1
            elif hrs < 4:    buckets['1-4h']  += 1
            elif hrs < 8:    buckets['4-8h']  += 1
            elif hrs < 24:   buckets['8-24h'] += 1
            else:            buckets['>24h']  += 1

        total = sum(buckets.values())
        return {
            'buckets':  buckets,
            'total':    total,
            'pct':      {k: round(v/total*100, 1) if total else 0 for k, v in buckets.items()},
        }

    def _top_users(self, since) -> list:
        from api.support.models import SupportTicket
        from django.db.models import Count
        return list(
            SupportTicket.objects.filter(created_at__gte=since)
            .values('user__username', 'user__email')
            .annotate(count=Count('id'))
            .order_by('-count')[:10]
        )

    def _hourly_distribution(self, since) -> list:
        from api.support.models import SupportTicket
        from django.db.models import Count
        from django.db.models.functions import ExtractHour
        return list(
            SupportTicket.objects.filter(created_at__gte=since)
            .annotate(hour=ExtractHour('created_at'))
            .values('hour')
            .annotate(count=Count('id'))
            .order_by('hour')
        )

    def _day_of_week(self, since) -> list:
        from api.support.models import SupportTicket
        from django.db.models import Count
        from django.db.models.functions import ExtractWeekDay
        days = ['Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday']
        data = list(
            SupportTicket.objects.filter(created_at__gte=since)
            .annotate(dow=ExtractWeekDay('created_at'))
            .values('dow')
            .annotate(count=Count('id'))
            .order_by('dow')
        )
        for item in data:
            item['day_name'] = days[item['dow'] - 1] if 1 <= item['dow'] <= 7 else str(item['dow'])
        return data

    def _fcr_rate(self, since) -> dict:
        """First Contact Resolution — one reply-এ resolved"""
        from api.support.models import SupportTicket, TicketMessage
        from django.db.models import Count

        resolved_qs = SupportTicket.objects.filter(
            status='resolved', created_at__gte=since
        )
        total      = resolved_qs.count()
        one_reply  = 0

        for t in resolved_qs:
            agent_msgs = TicketMessage.objects.filter(ticket=t, is_agent=True).count()
            if agent_msgs == 1:
                one_reply += 1

        return {
            'total_resolved': total,
            'fcr_count':      one_reply,
            'fcr_rate_pct':   round(one_reply / total * 100, 1) if total else 0,
        }

    def _reopen_rate(self, since) -> dict:
        from api.support.models import SupportTicket
        closed    = SupportTicket.objects.filter(status__in=['resolved','closed'], created_at__gte=since).count()
        reopened  = SupportTicket.objects.filter(status='open', resolved_at__isnull=False, created_at__gte=since).count()
        return {
            'total_closed':   closed,
            'reopened':       reopened,
            'reopen_rate_pct':round(reopened / closed * 100, 1) if closed else 0,
        }

    # ──────────────────────────────────────────
    # EXPORT
    # ──────────────────────────────────────────
    def export_csv(self, days: int = 30, filters: dict = None) -> tuple:
        """CSV export"""
        from api.support.models import SupportTicket
        since  = timezone.now() - timedelta(days=days)
        qs     = self._base_qs(since, filters).select_related('user','assigned_to')

        output = StringIO()
        writer = csv.writer(output)
        writer.writerow([
            'Ticket ID','User','Email','Category','Subject','Status','Priority',
            'Channel','Agent','Created At','First Response','Resolved At',
            'Wait Hours','Rating','Escalated'
        ])

        for t in qs:
            fr_min = ''
            if t.admin_responded_at:
                fr_min = round((t.admin_responded_at - t.created_at).total_seconds() / 60, 0)
            writer.writerow([
                t.ticket_id,
                t.user.username,
                t.user.email,
                t.category,
                t.subject,
                t.status,
                t.priority,
                getattr(t, 'channel', 'web'),
                t.assigned_to.username if t.assigned_to else '',
                t.created_at.strftime('%Y-%m-%d %H:%M'),
                fr_min,
                t.resolved_at.strftime('%Y-%m-%d %H:%M') if t.resolved_at else '',
                round((timezone.now() - t.created_at).total_seconds() / 3600, 1),
                t.satisfaction_rating or '',
                'Yes' if t.escalated else 'No',
            ])

        filename = f'ticket_report_{timezone.now().strftime("%Y%m%d_%H%M")}.csv'
        return filename, output.getvalue().encode('utf-8-sig')

    def _base_qs(self, since, filters):
        from api.support.models import SupportTicket
        qs = SupportTicket.objects.filter(created_at__gte=since)
        if filters:
            if filters.get('status'):
                qs = qs.filter(status=filters['status'])
            if filters.get('priority'):
                qs = qs.filter(priority=filters['priority'])
            if filters.get('category'):
                qs = qs.filter(category=filters['category'])
            if filters.get('agent_id'):
                qs = qs.filter(assigned_to_id=filters['agent_id'])
        return qs


ticket_report = TicketReport()