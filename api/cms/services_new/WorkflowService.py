# api/cms/services_new/WorkflowService.py
"""Content Approval Workflow Service — CMS owns this."""
import logging
from typing import Dict, Any, List, Optional
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType

logger = logging.getLogger(__name__)

VALID_TRANSITIONS = {
    'draft':     ['review'],
    'review':    ['approved', 'rejected', 'draft'],
    'approved':  ['published', 'draft'],
    'rejected':  ['draft'],
    'published': ['archived'],
    'archived':  ['draft'],
}


class WorkflowService:

    @staticmethod
    def get_or_create_state(content_obj) -> Any:
        from api.cms.models_new.workflow import WorkflowState
        ct = ContentType.objects.get_for_model(content_obj)
        state, created = WorkflowState.objects.get_or_create(
            content_type=ct, object_id=content_obj.pk,
            defaults={'state': 'draft'},
        )
        return state

    @staticmethod
    def submit_for_review(content_obj, by_user, note: str = '') -> Dict:
        """Author submits content for review."""
        state = WorkflowService.get_or_create_state(content_obj)
        if state.state != 'draft':
            return {'success': False, 'error': f"Cannot submit from state: {state.state}"}
        transition = state.transition('review', by_user, note)
        WorkflowService._notify('review', content_obj, by_user, state)
        return {'success': True, 'state': 'review', 'transition_id': transition.id}

    @staticmethod
    def approve(content_obj, by_user, note: str = '') -> Dict:
        """Reviewer approves content."""
        state = WorkflowService.get_or_create_state(content_obj)
        if state.state != 'review':
            return {'success': False, 'error': f"Cannot approve from state: {state.state}"}
        transition = state.transition('approved', by_user, note)
        # Check if auto-publish rule exists
        from api.cms.models_new.workflow import WorkflowRule
        ct = ContentType.objects.get_for_model(content_obj)
        rule = WorkflowRule.objects.filter(content_type=ct, is_active=True).first()
        if rule and rule.auto_publish:
            WorkflowService.publish(content_obj, by_user, "Auto-published after approval")
        WorkflowService._notify('approved', content_obj, by_user, state)
        return {'success': True, 'state': 'approved', 'transition_id': transition.id}

    @staticmethod
    def reject(content_obj, by_user, reason: str = '') -> Dict:
        """Reviewer rejects content with reason."""
        state = WorkflowService.get_or_create_state(content_obj)
        if state.state != 'review':
            return {'success': False, 'error': f"Cannot reject from state: {state.state}"}
        transition = state.transition('rejected', by_user, reason)
        WorkflowService._notify('rejected', content_obj, by_user, state)
        return {'success': True, 'state': 'rejected', 'reason': reason}

    @staticmethod
    def publish(content_obj, by_user, note: str = '') -> Dict:
        """Publish approved content."""
        state = WorkflowService.get_or_create_state(content_obj)
        if state.state not in ('approved', 'draft'):
            return {'success': False, 'error': f"Cannot publish from state: {state.state}"}
        transition = state.transition('published', by_user, note)
        # Actually publish the content object
        if hasattr(content_obj, 'status'):
            content_obj.status = 'published'
            content_obj.save(update_fields=['status'])
        elif hasattr(content_obj, 'is_published'):
            content_obj.is_published = True
            content_obj.save(update_fields=['is_published'])
        return {'success': True, 'state': 'published'}

    @staticmethod
    def get_pending_reviews(assigned_to=None) -> List:
        from api.cms.models_new.workflow import WorkflowState
        qs = WorkflowState.objects.filter(state='review').select_related('assigned_to', 'created_by')
        if assigned_to:
            qs = qs.filter(assigned_to=assigned_to)
        return list(qs.order_by('created_at'))

    @staticmethod
    def get_history(content_obj) -> List[Dict]:
        from api.cms.models_new.workflow import WorkflowState, WorkflowTransition
        ct = ContentType.objects.get_for_model(content_obj)
        try:
            state = WorkflowState.objects.get(content_type=ct, object_id=content_obj.pk)
        except WorkflowState.DoesNotExist:
            return []
        transitions = state.transitions.select_related('transitioned_by').order_by('-created_at')
        return [{
            'from_state': t.from_state, 'to_state': t.to_state,
            'by': t.transitioned_by.username if t.transitioned_by else '',
            'note': t.note, 'at': t.created_at.isoformat(),
        } for t in transitions]

    @staticmethod
    def _notify(event: str, content_obj, by_user, state):
        try:
            from api.cms.services_new.NotificationService import NotificationService
            ct = ContentType.objects.get_for_model(content_obj)
            title_map = {
                'review': "Content submitted for review",
                'approved': "Your content was approved",
                'rejected': "Content needs revision",
                'published': "Content is now live",
            }
            target = state.created_by or state.assigned_to
            if target:
                NotificationService.notify_user(
                    user=target,
                    notification_type=f'workflow_{event}',
                    title=title_map.get(event, f'Workflow: {event}'),
                    message=f"{ct.model} #{content_obj.pk} — {event} by {by_user.username}",
                )
        except Exception:
            pass
