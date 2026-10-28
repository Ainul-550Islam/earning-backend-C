"""
api/support/analytics/agent_heatmap.py
FILE 19/70 — Agent Performance Heatmap

Agent-এর hour-by-hour, day-by-day performance।
Supervisor dashboard-এ visual heatmap দেখাবে।

Metrics:
- Tickets resolved per hour/day
- Response time heatmap
- CSAT by agent by time
- Workload distribution heatmap
"""
import logging
from datetime import timedelta
from django.utils import timezone
from django.core.cache import cache

logger = logging.getLogger(__name__)


class AgentHeatmap:
    """
    Agent performance heatmap data generator।
    """

    CACHE_TTL  = 3600
    DAYS_SHORT = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun']
    HOURS      = list(range(0, 24))

    # ──────────────────────────────────────────
    # INDIVIDUAL AGENT HEATMAP
    # ──────────────────────────────────────────
    def get_agent_heatmap(self, agent_user, days: int = 30) -> dict:
        """
        Single agent-এর heatmap।
        Rows = Days of week, Cols = Hours of day।
        """
        cache_key = f'heatmap:agent:{agent_user.id}:{days}'
        cached    = cache.get(cache_key)
        if cached:
            return cached

        try:
            from api.support.models import SupportTicket
            from django.db.models import Count, Avg
            from django.db.models.functions import TruncHour

            since = timezone.now() - timedelta(days=days)

            # Resolved tickets by hour
            resolved = list(
                SupportTicket.objects.filter(
                    assigned_to     = agent_user,
                    resolved_at__gte= since,
                    resolved_at__isnull=False,
                ).annotate(hour=TruncHour('resolved_at'))
                .values('hour')
                .annotate(count=Count('id'))
                .order_by('hour')
            )

            # Build 7x24 matrix
            matrix = [[0] * 24 for _ in range(7)]
            max_val = 0

            for item in resolved:
                dow  = item['hour'].weekday()   # 0-6
                hr   = item['hour'].hour         # 0-23
                val  = item['count']
                matrix[dow][hr] += val
                max_val = max(max_val, matrix[dow][hr])

            # Normalize 0-1 for color coding
            normalized = []
            for dow in range(7):
                row = []
                for hr in range(24):
                    val  = matrix[dow][hr]
                    norm = val / max_val if max_val > 0 else 0
                    row.append({
                        'value':      val,
                        'normalized': round(norm, 3),
                        'color':      self._heatmap_color(norm),
                        'label':      f'{self.DAYS_SHORT[dow]} {hr:02d}:00 — {val} resolved',
                    })
                normalized.append({
                    'day':   self.DAYS_SHORT[dow],
                    'cells': row,
                })

            # Performance metrics
            metrics = self._get_agent_metrics(agent_user, since)

            result = {
                'agent':   agent_user.username,
                'days':    days,
                'matrix':  normalized,
                'metrics': metrics,
                'peak_day':  self._find_peak_day(matrix),
                'peak_hour': self._find_peak_hour(matrix),
            }

            cache.set(cache_key, result, timeout=self.CACHE_TTL)
            return result

        except Exception as e:
            logger.error(f'Agent heatmap failed: {e}')
            return {}

    # ──────────────────────────────────────────
    # TEAM HEATMAP
    # ──────────────────────────────────────────
    def get_team_heatmap(self, days: int = 30) -> dict:
        """
        Entire team-এর combined heatmap।
        কখন সবচেয়ে বেশি ticket আসে।
        """
        cache_key = f'heatmap:team:{days}'
        cached    = cache.get(cache_key)
        if cached:
            return cached

        try:
            from api.support.models import SupportTicket
            from django.db.models import Count
            from django.db.models.functions import TruncHour

            since = timezone.now() - timedelta(days=days)

            created = list(
                SupportTicket.objects.filter(created_at__gte=since)
                .annotate(hour=TruncHour('created_at'))
                .values('hour')
                .annotate(count=Count('id'))
                .order_by('hour')
            )

            # Build matrix
            matrix  = [[0] * 24 for _ in range(7)]
            max_val = 0
            for item in created:
                dow  = item['hour'].weekday()
                hr   = item['hour'].hour
                val  = item['count']
                matrix[dow][hr] += val
                max_val = max(max_val, matrix[dow][hr])

            # Format for frontend
            rows = []
            for dow in range(7):
                cells = []
                for hr in range(24):
                    val  = matrix[dow][hr]
                    norm = val / max_val if max_val > 0 else 0
                    cells.append({
                        'value':      val,
                        'normalized': round(norm, 3),
                        'color':      self._heatmap_color(norm),
                    })
                rows.append({'day': self.DAYS_SHORT[dow], 'cells': cells})

            result = {
                'type':      'team_volume',
                'title':     f'Ticket Volume Heatmap ({days}d)',
                'rows':      rows,
                'hours':     [f'{h:02d}' for h in self.HOURS],
                'peak_day':  self._find_peak_day(matrix),
                'peak_hour': self._find_peak_hour(matrix),
                'insights':  self._generate_insights(matrix, days),
            }

            cache.set(cache_key, result, timeout=self.CACHE_TTL)
            return result

        except Exception as e:
            logger.error(f'Team heatmap failed: {e}')
            return {}

    # ──────────────────────────────────────────
    # RESPONSE TIME HEATMAP
    # ──────────────────────────────────────────
    def get_response_time_heatmap(self, days: int = 30) -> dict:
        """
        Average response time by hour + day।
        কখন slowest response হয় সেটা দেখাবে।
        """
        try:
            from api.support.models import SupportTicket
            from django.db.models.functions import TruncHour

            since = timezone.now() - timedelta(days=days)
            tickets = SupportTicket.objects.filter(
                created_at__gte=since,
                admin_responded_at__isnull=False,
            ).annotate(hour=TruncHour('created_at')).values('hour', 'created_at', 'admin_responded_at')

            # Build matrix of avg response times (minutes)
            matrix_data = {}  # {(dow, hr): [times]}
            for t in tickets:
                dow  = t['hour'].weekday()
                hr   = t['hour'].hour
                resp = (t['admin_responded_at'] - t['created_at']).total_seconds() / 60
                key  = (dow, hr)
                if key not in matrix_data:
                    matrix_data[key] = []
                matrix_data[key].append(resp)

            matrix  = [[0.0] * 24 for _ in range(7)]
            max_val = 0.0
            for (dow, hr), times in matrix_data.items():
                avg          = sum(times) / len(times)
                matrix[dow][hr] = avg
                max_val      = max(max_val, avg)

            rows = []
            for dow in range(7):
                cells = []
                for hr in range(24):
                    val  = matrix[dow][hr]
                    norm = val / max_val if max_val > 0 else 0
                    # Inverted color — high response time = red (bad)
                    cells.append({
                        'value_min':  round(val, 1),
                        'normalized': round(norm, 3),
                        'color':      self._heatmap_color_inverted(norm),
                        'label':      f'{val:.0f}m avg response',
                    })
                rows.append({'day': self.DAYS_SHORT[dow], 'cells': cells})

            return {
                'type':  'response_time',
                'title': 'Avg Response Time Heatmap (minutes)',
                'rows':  rows,
                'hours': [f'{h:02d}' for h in self.HOURS],
                'note':  'Red = slow response, Green = fast response',
            }
        except Exception as e:
            logger.error(f'Response time heatmap failed: {e}')
            return {}

    # ──────────────────────────────────────────
    # LEADERBOARD
    # ──────────────────────────────────────────
    def get_leaderboard(self, days: int = 30) -> list:
        """Agent performance leaderboard"""
        try:
            from api.support.models import SupportAgent, SupportTicket, TicketRating
            from django.db.models import Count, Avg
            from datetime import timedelta

            since  = timezone.now() - timedelta(days=days)
            agents = SupportAgent.objects.filter(is_active=True).select_related('user')
            board  = []

            for agent in agents:
                resolved = SupportTicket.objects.filter(
                    assigned_to   = agent.user,
                    resolved_at__gte = since,
                ).count()

                csat = TicketRating.objects.filter(
                    ticket__assigned_to = agent.user,
                    created_at__gte     = since,
                ).aggregate(avg=Avg('rating'))['avg'] or 0

                # Response time avg
                responded = SupportTicket.objects.filter(
                    assigned_to         = agent.user,
                    created_at__gte     = since,
                    admin_responded_at__isnull=False,
                )
                avg_resp = 0
                if responded.exists():
                    times    = [(t.admin_responded_at - t.created_at).total_seconds() / 60
                                for t in responded]
                    avg_resp = round(sum(times) / len(times), 0)

                # Score formula
                score = (resolved * 2) + (csat * 10) + max(0, 50 - avg_resp * 0.1)

                board.append({
                    'rank':        0,  # Will be set after sorting
                    'username':    agent.user.username,
                    'role':        agent.role,
                    'resolved':    resolved,
                    'csat':        round(csat, 1),
                    'avg_resp_min':int(avg_resp),
                    'score':       round(score, 1),
                    'badge':       self._get_badge(resolved, csat),
                })

            board.sort(key=lambda x: x['score'], reverse=True)
            for i, agent in enumerate(board, 1):
                agent['rank']  = i
                agent['medal'] = '🥇' if i == 1 else '🥈' if i == 2 else '🥉' if i == 3 else ''

            return board

        except Exception as e:
            logger.error(f'Leaderboard failed: {e}')
            return []

    # ──────────────────────────────────────────
    # HELPERS
    # ──────────────────────────────────────────
    def _heatmap_color(self, normalized: float) -> str:
        """0=white/blue → 1=dark blue"""
        if normalized == 0:
            return '#f8fafc'
        if normalized < 0.25:
            return '#dbeafe'
        if normalized < 0.50:
            return '#93c5fd'
        if normalized < 0.75:
            return '#3b82f6'
        return '#1d4ed8'

    def _heatmap_color_inverted(self, normalized: float) -> str:
        """For response time: 0=green (fast) → 1=red (slow)"""
        if normalized == 0:
            return '#f0fdf4'
        if normalized < 0.25:
            return '#86efac'
        if normalized < 0.50:
            return '#facc15'
        if normalized < 0.75:
            return '#fb923c'
        return '#dc2626'

    def _find_peak_day(self, matrix: list) -> str:
        day_totals = [sum(matrix[d]) for d in range(7)]
        peak_idx   = day_totals.index(max(day_totals))
        return self.DAYS_SHORT[peak_idx]

    def _find_peak_hour(self, matrix: list) -> str:
        hour_totals = [sum(matrix[d][h] for d in range(7)) for h in range(24)]
        peak_hr     = hour_totals.index(max(hour_totals))
        return f'{peak_hr:02d}:00'

    def _generate_insights(self, matrix: list, days: int) -> list:
        insights = []
        peak_day = self._find_peak_day(matrix)
        peak_hr  = self._find_peak_hour(matrix)
        insights.append(f'Busiest day: {peak_day}')
        insights.append(f'Peak hour: {peak_hr}')

        # Weekend check
        weekend_total = sum(matrix[5]) + sum(matrix[6])
        weekday_total = sum(sum(matrix[d]) for d in range(5))
        if weekday_total > 0:
            weekend_pct = round(weekend_total / (weekday_total + weekend_total) * 100, 1)
            if weekend_pct > 15:
                insights.append(f'{weekend_pct}% tickets come on weekends — consider weekend coverage')

        return insights

    def _get_agent_metrics(self, agent_user, since) -> dict:
        try:
            from api.support.models import SupportTicket, TicketRating
            from django.db.models import Avg, Count

            tickets   = SupportTicket.objects.filter(assigned_to=agent_user, created_at__gte=since)
            resolved  = tickets.filter(status='resolved').count()
            csat      = TicketRating.objects.filter(
                ticket__assigned_to=agent_user,
                created_at__gte=since,
            ).aggregate(avg=Avg('rating'))['avg'] or 0

            return {
                'total_assigned': tickets.count(),
                'resolved':       resolved,
                'csat':           round(csat, 1),
            }
        except Exception:
            return {}

    def _get_badge(self, resolved: int, csat: float) -> str:
        if resolved >= 50 and csat >= 4.5:
            return '⭐ Elite Agent'
        if resolved >= 30 and csat >= 4.0:
            return '🌟 Star Agent'
        if resolved >= 15:
            return '💪 Active Agent'
        return ''


# Singleton
agent_heatmap = AgentHeatmap()