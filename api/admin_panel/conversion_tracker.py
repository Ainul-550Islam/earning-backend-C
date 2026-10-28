# api/admin_panel/conversion_tracker.py
"""
Conversion & Postback Tracking Debug Console.
Admin interface to trace, debug, and manually fire conversions.
Calls api.postback and api.promotions — admin_panel only observes and controls.
"""
from __future__ import annotations
import logging
from typing import Any, Dict, List, Optional
from django.utils import timezone
from django.core.cache import cache
from datetime import timedelta

logger = logging.getLogger(__name__)


class ConversionTracker:
    """Debug console for conversion tracking."""

    @classmethod
    def trace_conversion(cls, submission_id: Any) -> Dict:
        """Full trace of a conversion: submission → approval → payout → postback."""
        trace = {'submission_id': submission_id, 'steps': []}
        try:
            from api.promotions.models import TaskSubmission
            sub = TaskSubmission.objects.select_related('campaign', 'worker').get(pk=submission_id)
            trace['steps'].append({
                'step': 1, 'name': 'Submission Received',
                'status': 'ok', 'time': sub.created_at.isoformat(),
                'data': {'user': sub.worker.username if sub.worker else '', 'campaign': sub.campaign.title if sub.campaign else ''},
            })
            trace['steps'].append({
                'step': 2, 'name': 'Fraud Check',
                'status': 'ok' if sub.status != 'rejected' else 'failed',
                'data': {'status': sub.status},
            })
        except Exception as e:
            trace['error'] = str(e)
        return trace

    @classmethod
    def get_real_time_conversions(cls, minutes: int = 10) -> List[Dict]:
        """Get conversions from the last N minutes."""
        cutoff = timezone.now() - timedelta(minutes=minutes)
        try:
            from api.promotions.models import TaskSubmission
            return list(
                TaskSubmission.objects.filter(created_at__gte=cutoff)
                .select_related('campaign', 'worker')
                .values('id', 'campaign__title', 'worker__username',
                        'status', 'reward_usd', 'created_at')
                .order_by('-created_at')[:200]
            )
        except Exception:
            return []

    @classmethod
    def get_conversion_funnel(cls, offer_id: Any, days: int = 7) -> Dict:
        """Conversion funnel: clicks → submissions → approvals → payouts."""
        cutoff = timezone.now() - timedelta(days=days)
        funnel = {'offer_id': offer_id, 'period_days': days}
        try:
            from api.smartlink.models.click import Click
            funnel['clicks'] = Click.objects.filter(
                smartlink__campaign_id=offer_id, created_at__gte=cutoff
            ).count()
        except Exception:
            funnel['clicks'] = 0
        try:
            from api.promotions.models import TaskSubmission
            from django.db.models import Count, Q
            stats = TaskSubmission.objects.filter(
                campaign_id=offer_id, created_at__gte=cutoff
            ).aggregate(
                total=Count('id'),
                approved=Count('id', filter=Q(status='approved')),
                rejected=Count('id', filter=Q(status='rejected')),
            )
            funnel.update(stats)
        except Exception:
            pass
        return funnel

    @classmethod
    def manual_approve_conversion(cls, submission_id: Any, actor) -> Dict:
        """Manually approve a conversion (admin override)."""
        try:
            from api.promotions.models import TaskSubmission
            sub = TaskSubmission.objects.get(pk=submission_id)
            old_status = sub.status
            sub.status = 'approved'
            sub.reviewed_at = timezone.now()
            sub.reviewer = actor
            sub.save()
            from api.admin_panel.models.activity import AdminActivity
            AdminActivity.log(actor=actor, action='manual_approve_conversion',
                              model_name='TaskSubmission', object_id=str(submission_id),
                              changes={'old_status': old_status, 'new_status': 'approved'})
            return {'success': True, 'submission_id': submission_id, 'old_status': old_status}
        except Exception as e:
            return {'success': False, 'error': str(e)}


class PostbackDebugger:
    """Real-time postback fire/retry debug panel."""

    @classmethod
    def get_recent_postbacks(cls, limit: int = 100, status: str = '') -> List[Dict]:
        """Get recent postback logs."""
        try:
            from api.postback.models import PostbackLog
            qs = PostbackLog.objects.all()
            if status:
                qs = qs.filter(status=status)
            return list(qs.values(
                'id', 'network', 'url', 'status_code', 'status',
                'response_body', 'attempt_count', 'created_at'
            ).order_by('-created_at')[:limit])
        except Exception as e:
            return []

    @classmethod
    def retry_failed_postback(cls, postback_id: Any, actor) -> Dict:
        """Manually retry a failed postback."""
        try:
            from api.postback.models import PostbackLog
            postback = PostbackLog.objects.get(pk=postback_id)
            # Fire via Celery
            from celery import current_app
            current_app.send_task('api.postback.tasks.fire_postback',
                                   args=[postback.url, postback.parameters])
            from api.admin_panel.models.activity import AdminActivity
            AdminActivity.log(actor=actor, action='retry_postback',
                              model_name='PostbackLog', object_id=str(postback_id))
            return {'success': True, 'postback_id': postback_id, 'queued': True}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    @classmethod
    def test_postback_url(cls, url: str, params: Dict, actor) -> Dict:
        """Send a test postback to a URL."""
        try:
            import requests
            resp = requests.get(url, params=params, timeout=10)
            result = {
                'success': resp.status_code < 400,
                'status_code': resp.status_code,
                'response': resp.text[:500],
                'url': url,
            }
            from api.admin_panel.models.activity import AdminActivity
            AdminActivity.log(actor=actor, action='test_postback',
                              changes={'url': url, 'params': params, 'status': resp.status_code})
            return result
        except Exception as e:
            return {'success': False, 'error': str(e), 'url': url}

    @classmethod
    def get_postback_stats(cls, days: int = 7) -> Dict:
        """Postback delivery statistics."""
        cutoff = timezone.now() - timedelta(days=days)
        try:
            from api.postback.models import PostbackLog
            from django.db.models import Count
            qs = PostbackLog.objects.filter(created_at__gte=cutoff)
            return {
                'total': qs.count(),
                'success': qs.filter(status='success').count(),
                'failed': qs.filter(status='failed').count(),
                'retry_queue': qs.filter(status='retry').count(),
                'by_network': list(qs.values('network').annotate(c=Count('id')).order_by('-c')[:10]),
            }
        except Exception:
            return {}


conversion_tracker = ConversionTracker()
postback_debugger  = PostbackDebugger()