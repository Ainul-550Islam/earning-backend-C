"""Workflow Engine — Executes multi-step DR workflows with dependencies."""
import logging
from datetime import datetime
from typing import Callable, List
logger = logging.getLogger(__name__)

class WorkflowStep:
    def __init__(self, name: str, fn: Callable, rollback_fn: Callable = None, required: bool = True):
        self.name = name
        self.fn = fn
        self.rollback_fn = rollback_fn
        self.required = required

class WorkflowEngine:
    def __init__(self, workflow_name: str):
        self.name = workflow_name
        self.steps: List[WorkflowStep] = []
        self.completed_steps = []

    def add_step(self, step: WorkflowStep):
        self.steps.append(step)

    def execute(self, context: dict) -> dict:
        results = []
        logger.info(f"Workflow '{self.name}' started with {len(self.steps)} steps")
        for step in self.steps:
            logger.info(f"  Step: {step.name}")
            try:
                result = step.fn(context)
                self.completed_steps.append(step)
                results.append({"step": step.name, "status": "success", "result": result})
            except Exception as e:
                logger.error(f"  Step FAILED: {step.name}: {e}")
                results.append({"step": step.name, "status": "failed", "error": str(e)})
                if step.required:
                    self._rollback(context)
                    return {"workflow": self.name, "status": "failed", "failed_step": step.name, "steps": results}
        return {"workflow": self.name, "status": "completed", "steps": results,
                "completed_at": datetime.utcnow().isoformat()}

    def _rollback(self, context: dict):
        logger.warning(f"Rolling back workflow '{self.name}'")
        for step in reversed(self.completed_steps):
            if step.rollback_fn:
                try:
                    step.rollback_fn(context)
                    logger.info(f"  Rolled back: {step.name}")
                except Exception as e:
                    logger.error(f"  Rollback failed for {step.name}: {e}")
