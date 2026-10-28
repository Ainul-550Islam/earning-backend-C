"""
tasks/services/WorkflowService.py
Create, run, and manage TaskWorkflow instances.
"""
import logging
from typing import Optional, Dict, Any, List
from django.utils import timezone
from django.db import transaction

logger = logging.getLogger(__name__)


class WorkflowService:
    """
    Manages the lifecycle of TaskWorkflow definitions and their executions.
    """

    # ─── Workflow CRUD ────────────────────────────────────────────────

    def create_workflow(
        self,
        name: str,
        description: str = '',
        trigger_type: str = 'manual',
        on_failure: str = 'stop',
        timeout_seconds: int = 3600,
        created_by=None,
    ) -> Dict[str, Any]:
        """Create a new TaskWorkflow definition."""
        try:
            from api.tasks.models.workflow import TaskWorkflow

            workflow = TaskWorkflow.objects.create(
                name=name,
                description=description,
                trigger_type=trigger_type,
                on_failure=on_failure,
                timeout_seconds=timeout_seconds,
                created_by=created_by,
                is_active=True,
            )
            logger.info(f"[OK] WorkflowService.create_workflow: '{name}' id={workflow.pk}")
            return {'success': True, 'workflow_id': workflow.pk, 'name': workflow.name}

        except Exception as e:
            logger.error(f"[ERROR] WorkflowService.create_workflow: {e}")
            return {'success': False, 'error': str(e)}

    def get_workflow(self, workflow_id: int) -> Optional[Dict]:
        """Return serialisable workflow info."""
        try:
            from api.tasks.models.workflow import TaskWorkflow

            wf = TaskWorkflow.objects.get(pk=workflow_id)
            return {
                'id': wf.pk,
                'name': wf.name,
                'description': wf.description,
                'is_active': wf.is_active,
                'trigger_type': wf.trigger_type,
                'on_failure': wf.on_failure,
                'timeout_seconds': wf.timeout_seconds,
                'step_count': wf.step_count,
                'created_at': wf.created_at.isoformat(),
            }
        except Exception as e:
            logger.error(f"[ERROR] WorkflowService.get_workflow {workflow_id}: {e}")
            return None

    def list_workflows(self, active_only: bool = True) -> List[Dict]:
        """Return list of workflow summaries."""
        try:
            from api.tasks.models.workflow import TaskWorkflow

            qs = TaskWorkflow.objects.all()
            if active_only:
                qs = qs.filter(is_active=True)

            return list(qs.values('id', 'name', 'description', 'is_active',
                                  'trigger_type', 'created_at'))
        except Exception as e:
            logger.error(f"[ERROR] WorkflowService.list_workflows: {e}")
            return []

    def update_workflow(self, workflow_id: int, **fields) -> Dict[str, Any]:
        """Update a workflow definition. Allowed fields passed as kwargs."""
        try:
            from api.tasks.models.workflow import TaskWorkflow

            allowed = {
                'name', 'description', 'trigger_type', 'on_failure',
                'timeout_seconds', 'is_active',
            }
            update_data = {k: v for k, v in fields.items() if k in allowed}
            if not update_data:
                return {'success': False, 'error': 'No valid fields to update'}

            updated = TaskWorkflow.objects.filter(pk=workflow_id).update(**update_data)
            if updated:
                logger.info(f"[OK] Workflow {workflow_id} updated: {update_data}")
                return {'success': True, 'workflow_id': workflow_id, 'updated': update_data}
            return {'success': False, 'error': 'Workflow not found'}

        except Exception as e:
            logger.error(f"[ERROR] WorkflowService.update_workflow {workflow_id}: {e}")
            return {'success': False, 'error': str(e)}

    def delete_workflow(self, workflow_id: int) -> Dict[str, Any]:
        """Soft-delete a workflow (mark inactive)."""
        return self.update_workflow(workflow_id, is_active=False)

    # ─── Step Management ──────────────────────────────────────────────

    def add_step(
        self,
        workflow_id: int,
        step_number: int,
        task_name: str,
        label: str = '',
        task_params: dict = None,
        on_failure: str = 'stop',
        timeout_seconds: int = 300,
        max_retries: int = 0,
        is_async: bool = False,
        condition: str = '',
    ) -> Dict[str, Any]:
        """Add a WorkflowStep to an existing workflow."""
        try:
            from api.tasks.models.workflow import TaskWorkflow, WorkflowStep

            workflow = TaskWorkflow.objects.get(pk=workflow_id)
            step = WorkflowStep.objects.create(
                workflow=workflow,
                step_number=step_number,
                task_name=task_name,
                label=label or task_name,
                task_params=task_params or {},
                on_failure=on_failure,
                timeout_seconds=timeout_seconds,
                max_retries=max_retries,
                is_async=is_async,
                condition=condition,
                is_active=True,
            )
            logger.info(f"[OK] Step {step_number} added to workflow {workflow_id}")
            return {'success': True, 'step_id': step.pk, 'workflow_id': workflow_id}

        except Exception as e:
            logger.error(f"[ERROR] WorkflowService.add_step: {e}")
            return {'success': False, 'error': str(e)}

    # ─── Execution ────────────────────────────────────────────────────

    def trigger_workflow(
        self,
        workflow_id: int,
        input_data: dict = None,
        triggered_by=None,
        trigger_type: str = 'manual',
        trigger_ref: str = '',
        async_execute: bool = True,
    ) -> Dict[str, Any]:
        """
        Create a WorkflowInstance and optionally dispatch it to Celery.
        Returns the instance ID so the caller can poll status.
        """
        try:
            from api.tasks.models.workflow import TaskWorkflow, WorkflowInstance

            workflow = TaskWorkflow.objects.get(pk=workflow_id, is_active=True)

            with transaction.atomic():
                instance = WorkflowInstance.objects.create(
                    workflow=workflow,
                    status='pending',
                    input_data=input_data or {},
                    triggered_by=triggered_by,
                    trigger_type=trigger_type,
                    trigger_ref=trigger_ref or '',
                )

            logger.info(f"[OK] WorkflowInstance #{instance.pk} created for workflow {workflow_id}")

            if async_execute:
                from api.tasks.celery_tasks import execute_workflow_instance
                execute_workflow_instance.apply_async(
                    kwargs={'instance_id': instance.pk},
                    countdown=1,
                )

            return {
                'success': True,
                'instance_id': instance.pk,
                'workflow_id': workflow_id,
                'status': instance.status,
            }

        except Exception as e:
            logger.error(f"[ERROR] WorkflowService.trigger_workflow {workflow_id}: {e}")
            return {'success': False, 'error': str(e)}

    def get_instance_status(self, instance_id: int) -> Optional[Dict]:
        """Return current status of a workflow instance."""
        try:
            from api.tasks.models.workflow import WorkflowInstance

            inst = WorkflowInstance.objects.get(pk=instance_id)
            return {
                'id': inst.pk,
                'workflow_name': inst.workflow.name,
                'status': inst.status,
                'current_step': inst.current_step,
                'started_at': inst.started_at.isoformat() if inst.started_at else None,
                'completed_at': inst.completed_at.isoformat() if inst.completed_at else None,
                'duration_seconds': inst.duration_seconds,
                'error': inst.error,
            }
        except Exception as e:
            logger.error(f"[ERROR] WorkflowService.get_instance_status {instance_id}: {e}")
            return None

    def list_instances(
        self,
        workflow_id: int = None,
        status: str = None,
        limit: int = 50,
    ) -> List[Dict]:
        """List workflow instances with optional filters."""
        try:
            from api.tasks.models.workflow import WorkflowInstance

            qs = WorkflowInstance.objects.select_related('workflow').order_by('-created_at')
            if workflow_id:
                qs = qs.filter(workflow_id=workflow_id)
            if status:
                qs = qs.filter(status=status)

            return list(
                qs[:limit].values(
                    'id', 'workflow__name', 'status',
                    'current_step', 'started_at', 'completed_at', 'error'
                )
            )
        except Exception as e:
            logger.error(f"[ERROR] WorkflowService.list_instances: {e}")
            return []

    def cancel_instance(self, instance_id: int, reason: str = '') -> Dict[str, Any]:
        """Cancel a running workflow instance."""
        try:
            from api.tasks.models.workflow import WorkflowInstance

            inst = WorkflowInstance.objects.get(pk=instance_id)
            if inst.status not in ('pending', 'running'):
                return {'success': False, 'error': f'Cannot cancel instance in {inst.status} state'}

            inst.cancel(reason=reason)
            logger.info(f"[OK] WorkflowInstance #{instance_id} cancelled")
            return {'success': True, 'instance_id': instance_id}

        except Exception as e:
            logger.error(f"[ERROR] WorkflowService.cancel_instance {instance_id}: {e}")
            return {'success': False, 'error': str(e)}

    def get_instance_logs(self, instance_id: int) -> List[Dict]:
        """Return step logs for a workflow instance."""
        try:
            from api.tasks.models.workflow import WorkflowLog

            return list(
                WorkflowLog.objects.filter(instance_id=instance_id)
                .order_by('step_number')
                .values(
                    'step_number', 'task_name', 'status',
                    'output', 'error', 'duration_seconds',
                    'started_at', 'completed_at',
                )
            )
        except Exception as e:
            logger.error(f"[ERROR] WorkflowService.get_instance_logs {instance_id}: {e}")
            return []
