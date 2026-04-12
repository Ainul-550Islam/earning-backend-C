"""
api/ai_engine/INTEGRATIONS/mlflow_integration.py
=================================================
MLflow Integration — experiment tracking।
"""

import logging
from ..config import ai_config

logger = logging.getLogger(__name__)


class MLflowIntegration:
    """MLflow experiment tracking integration।"""

    def __init__(self):
        self.tracking_uri = ai_config.mlflow_tracking_uri
        self._setup()

    def _setup(self):
        if not self.tracking_uri:
            return
        try:
            import mlflow
            mlflow.set_tracking_uri(self.tracking_uri)
        except ImportError:
            logger.warning("mlflow not installed. pip install mlflow")

    def start_run(self, experiment_name: str, run_name: str = None) -> str:
        try:
            import mlflow
            mlflow.set_experiment(experiment_name)
            run = mlflow.start_run(run_name=run_name)
            return run.info.run_id
        except Exception as e:
            logger.error(f"MLflow start_run error: {e}")
            return ''

    def log_params(self, params: dict):
        try:
            import mlflow
            mlflow.log_params(params)
        except Exception as e:
            logger.debug(f"MLflow log_params: {e}")

    def log_metrics(self, metrics: dict, step: int = None):
        try:
            import mlflow
            mlflow.log_metrics(metrics, step=step)
        except Exception as e:
            logger.debug(f"MLflow log_metrics: {e}")

    def log_model(self, model, artifact_path: str = 'model'):
        try:
            import mlflow.sklearn
            mlflow.sklearn.log_model(model, artifact_path)
        except Exception as e:
            logger.debug(f"MLflow log_model: {e}")

    def end_run(self, status: str = 'FINISHED'):
        try:
            import mlflow
            mlflow.end_run(status=status)
        except Exception as e:
            logger.debug(f"MLflow end_run: {e}")


"""
api/ai_engine/INTEGRATIONS/vertex_ai_integration.py
====================================================
Google Vertex AI Integration।
"""


class VertexAIIntegration:
    """Google Cloud Vertex AI integration।"""

    def __init__(self, project_id: str = None, location: str = 'us-central1'):
        self.project_id = project_id
        self.location   = location
        self._init()

    def _init(self):
        try:
            from google.cloud import aiplatform
            aiplatform.init(project=self.project_id, location=self.location)
            self.client = aiplatform
        except ImportError:
            logger.warning("google-cloud-aiplatform not installed.")
            self.client = None

    def predict(self, endpoint_id: str, instances: list) -> list:
        if not self.client:
            return []
        try:
            endpoint = self.client.Endpoint(endpoint_id)
            response = endpoint.predict(instances=instances)
            return response.predictions
        except Exception as e:
            logger.error(f"Vertex AI predict error: {e}")
            return []
