# api/support/tasks/insight_tasks.py  — WORLD #1 COMPLETE
"""Analytics and insight generation tasks."""
import logging
from celery import shared_task
from django.utils import timezone
from datetime import timedelta
logger = logging.getLogger(__name__)

@shared_task(name="support.tasks.insight_tasks.generate_daily_insight")
def generate_daily_insight():
    """Daily — generate support insights for dashboard."""
    try:
        from api.support.reports.ticket_report import ticket_report
        stats = ticket_report.generate(days=1)
        logger.info(f"Daily insight generated: {stats.get('summary',{}).get('total',0)} tickets")
        return stats
    except Exception as e:
        logger.error(f"Daily insight failed: {e}")
        return {"error": str(e)}

@shared_task(name="support.tasks.insight_tasks.save_agent_snapshots")
def save_agent_snapshots():
    """Daily — save agent performance snapshot + run churn scan."""
    from api.support.models import SupportAgent, SupportTicket
    from django.db.models import Count, Q
    snapshots = []
    for agent in SupportAgent.objects.filter(is_active=True).select_related("user"):
        today = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        tickets = SupportTicket.objects.filter(assigned_to=agent.user, created_at__gte=today)
        snapshots.append({
            "agent":    agent.user.username,
            "assigned": tickets.count(),
            "resolved": tickets.filter(status="resolved").count(),
        })
    # Run AI churn scan
    try:
        from api.support.ai.ai_churn_predictor import churn_predictor
        churn_result = churn_predictor.run_daily_scan()
    except Exception as e:
        churn_result = {"error": str(e)}
    return {"snapshots": len(snapshots), "churn": churn_result}

@shared_task(name="support.tasks.insight_tasks.generate_topic_clusters")
def generate_topic_clusters():
    """Weekly — cluster tickets into topics using AI."""
    try:
        from api.support.analytics.topic_clustering import topic_clusterer
        result = topic_clusterer.run(days=7)
        return result
    except Exception as e:
        logger.error(f"Topic clustering failed: {e}")
        return {"error": str(e)}