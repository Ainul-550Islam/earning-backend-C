"""
api/ai_engine/ML_PIPELINES/deployment_pipeline.py
==================================================
Deployment Pipeline — model production deployment।
Safety checks → version promotion → endpoint activation → health verify।
Blue-green deployment support।
"""
import logging
from typing import Optional
logger = logging.getLogger(__name__)

class DeploymentPipeline:
    """Safe model deployment to production।"""

    def deploy(self, ai_model_id: str, version_id: Optional[str] = None,
               skip_checks: bool = False) -> dict:
        steps = []
        try:
            # Step 1: Validate model exists
            from ..models import AIModel
            model = AIModel.objects.get(id=ai_model_id)
            steps.append({'step': 'model_validation', 'status': 'passed'})

            # Step 2: Evaluation check
            if not skip_checks:
                eval_result = self._run_evaluation(ai_model_id)
                steps.append({'step': 'evaluation', 'status': 'passed' if eval_result['passed'] else 'failed', 'metrics': eval_result.get('metrics', {})})
                if not eval_result['passed']:
                    return self._fail('Evaluation failed — model metrics below threshold', steps)

            # Step 3: Version promotion
            if version_id:
                ver_result = self._promote_version(version_id)
                steps.append({'step': 'version_promotion', 'status': 'passed', 'version': ver_result.get('version')})

            # Step 4: Deploy
            from ..services import ModelManagementService
            deployed = ModelManagementService.deploy_model(ai_model_id)
            steps.append({'step': 'deployment', 'status': 'passed'})

            # Step 5: Health check
            health = self._post_deploy_health(ai_model_id)
            steps.append({'step': 'health_check', 'status': 'passed' if health['healthy'] else 'warning', 'details': health})

            logger.info(f"Model deployed successfully: {ai_model_id}")
            return {
                'success':    True,
                'model_id':   ai_model_id,
                'model_name': deployed.name,
                'status':     deployed.status,
                'steps':      steps,
            }
        except Exception as e:
            logger.error(f"Deployment failed [{ai_model_id}]: {e}")
            steps.append({'step': 'error', 'status': 'failed', 'error': str(e)})
            return self._fail(str(e), steps)

    def _run_evaluation(self, ai_model_id: str) -> dict:
        from .evaluation_pipeline import EvaluationPipeline
        return EvaluationPipeline().run(ai_model_id)

    def _promote_version(self, version_id: str) -> dict:
        from ..repository import ModelVersionRepository
        version = ModelVersionRepository.promote_to_production(version_id)
        return {'version': version.version, 'stage': version.stage}

    def _post_deploy_health(self, ai_model_id: str) -> dict:
        from ..models import AIModel
        model = AIModel.objects.get(id=ai_model_id)
        return {'healthy': model.status == 'deployed', 'status': model.status}

    def _fail(self, reason: str, steps: list) -> dict:
        return {'success': False, 'error': reason, 'steps': steps}

    def rollback(self, ai_model_id: str, previous_version_id: str) -> dict:
        try:
            self._promote_version(previous_version_id)
            from ..services import ModelManagementService
            ModelManagementService.deploy_model(ai_model_id)
            logger.info(f"Rollback complete: {ai_model_id} → {previous_version_id}")
            return {'success': True, 'rolled_back_to': previous_version_id}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def blue_green_deploy(self, ai_model_id: str,
                           new_version_id: str, traffic_pct: float = 0.10) -> dict:
        return {
            'strategy':     'blue_green',
            'new_traffic':  traffic_pct,
            'old_traffic':  1.0 - traffic_pct,
            'status':       'in_progress',
            'next_step':    'Monitor for 24h then increase traffic',
            'ai_model_id':  ai_model_id,
        }
