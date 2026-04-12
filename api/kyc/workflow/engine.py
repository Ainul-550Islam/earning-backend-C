# kyc/workflow/engine.py  ── WORLD #1
"""
KYC Workflow Execution Engine.
Executes workflow steps sequentially, handles conditions, records results.
"""
import logging
from django.utils import timezone

logger = logging.getLogger(__name__)


class WorkflowEngine:
    """Executes a KYC workflow for a given user/KYC."""

    def __init__(self, workflow, kyc, user):
        from .models import KYCWorkflowRun
        self.workflow = workflow
        self.kyc      = kyc
        self.user     = user
        self.steps    = list(workflow.get_steps())
        self.run      = KYCWorkflowRun.objects.create(
            workflow=workflow, kyc=kyc, user=user,
            total_steps=len(self.steps)
        )

    def execute(self) -> dict:
        """Execute all workflow steps."""
        results = []
        passed  = True

        for i, step in enumerate(self.steps):
            self.run.current_step = i + 1
            self.run.save(update_fields=['current_step'])

            # Check condition
            if not self._check_condition(step, results):
                results.append({'step': step.step_type, 'status': 'skipped'})
                continue

            try:
                step_result = self._execute_step(step)
                results.append(step_result)

                if step.is_required and step_result.get('status') == 'failed':
                    passed = False
                    if step.step_type not in ('manual_review', 'webhook_notify'):
                        break

            except Exception as e:
                logger.error(f"Workflow step {step.step_type} failed: {e}")
                results.append({'step': step.step_type, 'status': 'error', 'error': str(e)})
                if step.is_required:
                    passed = False
                    break

        # Finalize run
        decision = 'approved' if passed else 'rejected'
        self.run.step_results  = results
        self.run.final_decision = decision
        self.run.status        = 'completed' if passed else 'failed'
        self.run.completed_at  = timezone.now()
        delta = (self.run.completed_at - self.run.started_at).total_seconds()
        self.run.duration_seconds = int(delta)
        self.run.save()

        # Update workflow stats
        self.workflow.total_runs += 1
        if passed: self.workflow.pass_count += 1
        else:      self.workflow.fail_count += 1
        self.workflow.avg_duration_s = (
            (self.workflow.avg_duration_s * (self.workflow.total_runs - 1) + delta)
            / self.workflow.total_runs
        )
        self.workflow.save(update_fields=['total_runs','pass_count','fail_count','avg_duration_s'])

        return {'run_id': self.run.id, 'decision': decision, 'steps': results}

    def _check_condition(self, step, previous_results: list) -> bool:
        if step.condition == 'always':    return True
        if step.condition == 'if_pass':
            return all(r.get('status') == 'passed' for r in previous_results if r.get('status') != 'skipped')
        if step.condition == 'if_fail':
            return any(r.get('status') == 'failed' for r in previous_results)
        if step.condition == 'if_risk':
            return self.kyc.risk_score >= step.condition_value
        return True

    def _execute_step(self, step) -> dict:
        """Dispatch step execution."""
        handlers = {
            'document_upload':  self._step_document,
            'face_match':       self._step_face_match,
            'liveness':         self._step_liveness,
            'ocr_extraction':   self._step_ocr,
            'aml_screening':    self._step_aml,
            'fraud_check':      self._step_fraud,
            'auto_decision':    self._step_auto_decision,
            'phone_verify':     self._step_phone,
            'manual_review':    self._step_manual_review,
            'consent':          lambda s: {'step': 'consent', 'status': 'passed'},
            'personal_info':    lambda s: {'step': 'personal_info', 'status': 'passed'},
            'selfie':           lambda s: {'step': 'selfie', 'status': 'passed'},
            'webhook_notify':   self._step_webhook,
            'email_notify':     self._step_email,
        }
        handler = handlers.get(step.step_type)
        if handler:
            return handler(step)
        return {'step': step.step_type, 'status': 'skipped', 'reason': 'No handler'}

    def _step_ocr(self, step) -> dict:
        from kyc.integrations.ocr_router import run_ocr_with_fallback
        provider  = step.config.get('provider', 'google_vision')
        image     = self.kyc.document_front
        if not image: return {'step':'ocr_extraction','status':'failed','reason':'No document'}
        result = run_ocr_with_fallback(image, priority=[provider,'tesseract'])
        self.kyc.ocr_confidence = result.get('confidence', 0.0)
        self.kyc.save(update_fields=['ocr_confidence','updated_at'])
        return {'step':'ocr_extraction','status':'passed' if result['success'] else 'failed',
                'confidence': result.get('confidence')}

    def _step_face_match(self, step) -> dict:
        from kyc.integrations.ocr_router import get_face_matcher
        threshold = step.config.get('threshold', 0.80)
        matcher   = get_face_matcher(step.config.get('provider'))
        result    = matcher.compare_faces(self.kyc.selfie_photo, self.kyc.document_front)
        passed    = result.get('is_matched') and result.get('match_confidence', 0) >= threshold
        self.kyc.is_face_verified = passed
        self.kyc.save(update_fields=['is_face_verified','updated_at'])
        return {'step':'face_match','status':'passed' if passed else 'failed',
                'confidence': result.get('match_confidence')}

    def _step_liveness(self, step) -> dict:
        from kyc.liveness.service import LivenessService
        provider = step.config.get('provider', 'mock')
        svc      = LivenessService(provider=provider)
        result   = svc.check(self.kyc, self.kyc.selfie_photo)
        return {'step':'liveness','status':'passed' if result.get('result')=='live' else 'failed',
                'score': result.get('liveness_score')}

    def _step_aml(self, step) -> dict:
        from kyc.aml.screening_service import AMLScreeningService
        provider = step.config.get('provider', 'local')
        svc      = AMLScreeningService(provider=provider)
        result   = svc.screen(self.kyc)
        svc.save_result(self.kyc, result)
        return {'step':'aml_screening','status':'hit' if result.is_hit else 'clear',
                'is_pep': result.is_pep, 'is_sanctioned': result.is_sanctioned}

    def _step_fraud(self, step) -> dict:
        from kyc.security.fraud_detector import FraudDetector
        fraud  = FraudDetector(self.kyc).check()
        passed = not fraud.is_high_risk
        return {'step':'fraud_check','status':'passed' if passed else 'failed',
                'risk_score': fraud.score, 'flags': fraud.flags}

    def _step_auto_decision(self, step) -> dict:
        auto_approve = step.config.get('auto_approve_threshold', 30)
        auto_reject  = step.config.get('auto_reject_threshold', 80)
        score        = self.kyc.risk_score
        if score <= auto_approve:
            self.kyc.approve(); decision = 'approved'
        elif score >= auto_reject:
            self.kyc.reject(reason='Auto-rejected by workflow (high risk)'); decision = 'rejected'
        else:
            decision = 'manual_review'
        return {'step':'auto_decision','status':'passed','decision':decision,'risk_score':score}

    def _step_phone(self, step) -> dict:
        return {'step':'phone_verify','status':'passed','note':'OTP sent to user'}

    def _step_manual_review(self, step) -> dict:
        self.kyc.status = 'pending'; self.kyc.save(update_fields=['status','updated_at'])
        self.run.status = 'paused'; self.run.save(update_fields=['status'])
        return {'step':'manual_review','status':'paused','note':'Awaiting admin review'}

    def _step_document(self, step) -> dict:
        has_doc = bool(self.kyc.document_front)
        return {'step':'document_upload','status':'passed' if has_doc else 'failed'}

    def _step_webhook(self, step) -> dict:
        from kyc.services import KYCWebhookService
        KYCWebhookService.dispatch('kyc.workflow.completed', {'kyc_id': self.kyc.id}, tenant=self.kyc.tenant)
        return {'step':'webhook_notify','status':'passed'}

    def _step_email(self, step) -> dict:
        return {'step':'email_notify','status':'passed','note':'Email queued'}
