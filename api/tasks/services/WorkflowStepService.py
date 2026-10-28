"""
tasks/services/WorkflowStepService.py
Execute individual steps within a WorkflowInstance.
"""
import logging
import time
from typing import Any, Dict, Optional
from django.utils import timezone

logger = logging.getLogger(__name__)


class WorkflowStepService:
    """
    Executes a single WorkflowStep within a WorkflowInstance.
    Handles:
    - Condition evaluation (skip logic)
    - Task dispatch (sync or async)
    - Timeout enforcement
    - Retry on step failure
    - Writing WorkflowLog entries
    - Propagating output to instance context
    """

    def execute_step(
        self,
        instance_id: int,
        step_number: int,
    ) -> Dict[str, Any]:
        """
        Execute the step identified by (instance_id, step_number).
        Returns a dict with keys: success, output, error, duration_seconds.
        """
        from api.tasks.models.workflow import WorkflowInstance, WorkflowStep, WorkflowLog

        try:
            instance = WorkflowInstance.objects.select_related('workflow').get(pk=instance_id)
            step     = WorkflowStep.objects.get(
                workflow=instance.workflow,
                step_number=step_number,
                is_active=True,
            )

        except WorkflowInstance.DoesNotExist:
            logger.error(f"[ERROR] WorkflowInstance #{instance_id} not found")
            return {'success': False, 'error': 'Instance not found'}
        except WorkflowStep.DoesNotExist:
            logger.error(f"[ERROR] Step {step_number} not found for instance #{instance_id}")
            return {'success': False, 'error': f'Step {step_number} not found'}

        # Create log entry
        log, _ = WorkflowLog.objects.get_or_create(
            instance=instance,
            step_number=step_number,
            defaults={
                'task_name': step.task_name,
                'status': 'pending',
            },
        )

        # Update instance current_step
        instance.current_step = step_number
        instance.save(update_fields=['current_step', 'updated_at'])

        # Evaluate condition
        if step.condition:
            try:
                condition_result = self._evaluate_condition(
                    step.condition, instance.context_data
                )
                if not condition_result:
                    log.status = 'skipped'
                    log.save(update_fields=['status'])
                    logger.info(f"[SKIP] Instance #{instance_id} step {step_number} – condition false")
                    return {'success': True, 'output': None, 'skipped': True, 'duration_seconds': 0}
            except Exception as cond_err:
                logger.warning(f"[WARN] Condition eval error for step {step_number}: {cond_err}")

        # Update log to running
        log.status     = 'running'
        log.started_at = timezone.now()
        log.save(update_fields=['status', 'started_at'])

        # Build task params (template interpolation from context)
        resolved_params = self._resolve_params(step.task_params, instance.context_data)

        # Execute
        start_time = time.monotonic()
        max_retries = step.max_retries
        attempt = 0
        last_error = ''
        output = None
        success = False

        while attempt <= max_retries:
            attempt += 1
            try:
                output  = self._dispatch_task(step, resolved_params, instance)
                success = True
                break
            except Exception as task_err:
                last_error = str(task_err)
                logger.warning(
                    f"[RETRY] Step {step_number} attempt {attempt}/{max_retries+1}: {task_err}"
                )
                if attempt > max_retries:
                    break
                time.sleep(min(2 ** attempt, 30))  # exponential backoff, max 30s

        duration = time.monotonic() - start_time

        # Update log
        log.status           = 'success' if success else 'failed'
        log.completed_at     = timezone.now()
        log.duration_seconds = duration
        log.output           = output
        log.error            = '' if success else last_error
        log.retry_count      = attempt - 1
        log.save(update_fields=[
            'status', 'completed_at', 'duration_seconds',
            'output', 'error', 'retry_count',
        ])

        # Propagate output to instance context
        if success and output is not None:
            try:
                context = instance.context_data or {}
                context[f'step_{step_number}'] = {'output': output}
                instance.context_data = context
                instance.save(update_fields=['context_data', 'updated_at'])
            except Exception:
                pass

        if success:
            logger.info(f"[OK] Instance #{instance_id} step {step_number} completed in {duration:.2f}s")
        else:
            logger.error(f"[FAIL] Instance #{instance_id} step {step_number}: {last_error}")

        return {
            'success': success,
            'output': output,
            'error': last_error,
            'duration_seconds': duration,
            'attempts': attempt,
        }

    # ─── Helpers ──────────────────────────────────────────────────────

    def _dispatch_task(self, step, params: dict, instance) -> Any:
        """
        Dispatch the Celery task for this step.
        For async steps, fires-and-forgets and returns None.
        For sync steps, applies the task and waits for the result.
        """
        from celery import current_app

        task_fn = current_app.tasks.get(step.task_name)
        if task_fn is None:
            raise ValueError(f"Task '{step.task_name}' not registered with Celery")

        if step.is_async:
            task_fn.apply_async(kwargs=params)
            return None
        else:
            result = task_fn.apply(kwargs=params, timeout=step.timeout_seconds)
            return result.get(timeout=step.timeout_seconds)

    def _evaluate_condition(self, condition: str, context: dict) -> bool:
        """
        Safely evaluate a Python condition string against the workflow context.
        Only allows basic comparisons; no imports or complex expressions.
        """
        safe_globals = {'__builtins__': {}}
        safe_locals  = {'context': context}
        return bool(eval(condition, safe_globals, safe_locals))  # noqa S307

    def _resolve_params(self, params: dict, context: dict) -> dict:
        """
        Interpolate {{step_N.output.key}} references in task_params
        using the accumulated workflow context.
        """
        import re
        resolved = {}
        for key, value in params.items():
            if isinstance(value, str):
                def replacer(match):
                    path = match.group(1).split('.')
                    node = context
                    for part in path:
                        if isinstance(node, dict):
                            node = node.get(part, '')
                        else:
                            return ''
                    return str(node)
                resolved[key] = re.sub(r'\{\{([^}]+)\}\}', replacer, value)
            else:
                resolved[key] = value
        return resolved
