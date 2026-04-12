"""
api/ai_engine/INTEGRATIONS/kubeflow_integration.py
===================================================
KubeFlow Pipelines Integration — ML orchestration on Kubernetes।
Training, evaluation, deployment pipeline orchestration।
"""
import logging
from typing import Any, Dict, List, Optional
logger = logging.getLogger(__name__)

class KubeFlowIntegration:
    """KubeFlow Pipelines integration for ML workflow orchestration।"""

    def __init__(self, host: str = None, namespace: str = "kubeflow"):
        self.host      = host
        self.namespace = namespace
        self.client    = None
        self._init()

    def _init(self):
        try:
            import kfp
            if self.host:
                self.client = kfp.Client(host=self.host)
                logger.info(f"KubeFlow client initialized: {self.host}")
            else:
                logger.warning("KubeFlow host not configured — using in-cluster discovery")
                self.client = kfp.Client()
        except ImportError:
            logger.warning("kfp not installed. pip install kfp")
        except Exception as e:
            logger.warning(f"KubeFlow init error: {e}")

    def submit_pipeline(self, pipeline_fn, run_name: str,
                         params: dict = None, experiment_name: str = "default") -> dict:
        if not self.client:
            return {"error": "KubeFlow client not configured"}
        try:
            experiment = self.client.create_experiment(name=experiment_name)
            run = self.client.create_run_from_pipeline_func(
                pipeline_fn,
                arguments=params or {},
                run_name=run_name,
                experiment_name=experiment_name,
            )
            return {
                "run_id":          run.run_id,
                "experiment_id":   experiment.id,
                "status":          "submitted",
                "run_name":        run_name,
            }
        except Exception as e:
            logger.error(f"Pipeline submit error: {e}")
            return {"error": str(e)}

    def get_run_status(self, run_id: str) -> dict:
        if not self.client: return {"error": "not_configured"}
        try:
            run = self.client.get_run(run_id=run_id)
            return {
                "run_id":      run_id,
                "status":      run.run.status,
                "name":        run.run.name,
                "created_at":  str(run.run.created_at),
            }
        except Exception as e:
            return {"error": str(e)}

    def list_runs(self, experiment_name: str = None) -> List[Dict]:
        if not self.client: return []
        try:
            runs = self.client.list_runs(experiment_id=None if not experiment_name else
                                          self.client.get_experiment(experiment_name=experiment_name).id)
            return [{"run_id": r.id, "name": r.name, "status": r.status}
                    for r in (runs.runs or [])]
        except Exception as e:
            logger.error(f"List runs error: {e}")
            return []

    def create_training_pipeline(self, model_id: str, dataset_path: str,
                                   hyperparams: dict = None):
        """Standard ML training pipeline create করো।"""
        try:
            import kfp.dsl as dsl

            @dsl.component
            def train_op(model_id: str, dataset_path: str) -> str:
                from api.ai_engine.ML_PIPELINES.training_pipeline import TrainingPipeline
                result = TrainingPipeline(model_id).run(dataset_path)
                return str(result)

            @dsl.pipeline(name=f"Training Pipeline — {model_id}")
            def training_pipeline():
                train_task = train_op(model_id=model_id, dataset_path=dataset_path)
                return train_task

            return training_pipeline
        except ImportError:
            logger.warning("kfp not installed for pipeline creation")
            return None

    def delete_run(self, run_id: str) -> dict:
        if not self.client: return {"error": "not_configured"}
        try:
            self.client.delete_run(run_id=run_id)
            return {"deleted": run_id, "status": "ok"}
        except Exception as e:
            return {"error": str(e)}
