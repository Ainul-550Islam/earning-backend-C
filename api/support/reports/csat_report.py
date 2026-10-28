"""
api/support/reports/csat_report.py
FILE 50/70 — CSAT / NPS Detailed Report
"""
import logging
from datetime import timedelta
from django.utils import timezone
logger = logging.getLogger(__name__)

class CSATReport:
    def generate(self, days: int = 30) -> dict:
        from api.support.models import TicketRating, SupportTicket
        from django.db.models import Avg, Count
        since   = timezone.now() - timedelta(days=days)
        ratings = TicketRating.objects.filter(created_at__gte=since)
        total   = ratings.count()
        if not total:
            return {'total': 0, 'avg': 0, 'nps': 0, 'by_score': {}, 'by_category': []}

        avg     = ratings.aggregate(avg=Avg('rating'))['avg'] or 0
        by_score= {}
        for i in range(1, 6):
            cnt        = ratings.filter(rating=i).count()
            by_score[i]= {'count': cnt, 'pct': round(cnt/total*100, 1)}

        # NPS: Promoters (5) - Detractors (1-2) / total
        promoters  = by_score.get(5, {}).get('count', 0)
        detractors = (by_score.get(1, {}).get('count', 0) + by_score.get(2, {}).get('count', 0))
        nps        = round((promoters - detractors) / total * 100, 1)

        # By category
        by_cat = []
        for cat in SupportTicket.objects.values_list('category', flat=True).distinct():
            cat_ratings = ratings.filter(ticket__category=cat)
            if cat_ratings.exists():
                by_cat.append({
                    'category': cat,
                    'count':    cat_ratings.count(),
                    'avg':      round(cat_ratings.aggregate(avg=Avg('rating'))['avg'] or 0, 2),
                })

        # By agent
        by_agent = list(ratings.values('ticket__assigned_to__username').annotate(
            avg=Avg('rating'), count=Count('id')
        ).order_by('-avg')[:10])

        # Trend
        from django.db.models.functions import TruncDate
        trend = list(ratings.annotate(date=TruncDate('created_at')).values('date').annotate(
            avg=Avg('rating'), count=Count('id')
        ).order_by('date'))

        return {
            'period_days': days,
            'total':       total,
            'avg_score':   round(avg, 2),
            'nps_score':   nps,
            'satisfaction_pct': round((by_score.get(4,{}).get('count',0) + by_score.get(5,{}).get('count',0)) / total * 100, 1),
            'by_score':    by_score,
            'by_category': sorted(by_cat, key=lambda x: x['avg'], reverse=True),
            'by_agent':    by_agent,
            'trend':       trend,
            'comments':    list(ratings.exclude(comment='').order_by('-created_at').values('ticket__ticket_id','rating','comment','created_at')[:20]),
        }

csat_report = CSATReport()