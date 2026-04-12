"""
api/ai_engine/INTEGRATIONS/vertex_ai_integration.py
====================================================
Google Vertex AI Integration — AutoML, custom training, prediction।
Managed ML platform on Google Cloud।
"""
import logging
from typing import Any, Dict, List, Optional
logger = logging.getLogger(__name__)

class VertexAIIntegration:
    """Google Vertex AI integration।"""

    def __init__(self, project_id: str = None, location: str = "us-central1"):
        self.project_id = project_id
        self.location   = location
        self._init()

    def _init(self):
        try:
            from google.cloud import aiplatform
            self.aiplatform = aiplatform
            aiplatform.init(project=self.project_id, location=self.location)
            logger.info(f"Vertex AI initialized: project={self.project_id}")
        except ImportError:
            logger.warning("google-cloud-aiplatform not installed. pip install google-cloud-aiplatform")
            self.aiplatform = None

    def create_dataset(self, display_name: str, gcs_source: str,
                        dataset_type: str = "tabular") -> dict:
        if not self.aiplatform: return {"error": "SDK not initialized"}
        try:
            if dataset_type == "tabular":
                dataset = self.aiplatform.TabularDataset.create(
                    display_name=display_name,
                    gcs_source=gcs_source,
                )
            else:
                return {"error": f"Unsupported dataset type: {dataset_type}"}
            return {"dataset_id": dataset.name, "display_name": display_name, "type": dataset_type}
        except Exception as e:
            logger.error(f"Vertex dataset create error: {e}")
            return {"error": str(e)}

    def train_automl(self, display_name: str, dataset_id: str,
                      target_column: str, budget_milli_hours: int = 1000) -> dict:
        if not self.aiplatform: return {"error": "SDK not initialized"}
        try:
            job = self.aiplatform.AutoMLTabularTrainingJob(
                display_name=display_name,
                optimization_prediction_type="classification",
            )
            model = job.run(
                dataset=self.aiplatform.TabularDataset(dataset_id),
                target_column=target_column,
                budget_milli_node_hours=budget_milli_hours,
            )
            return {"model_id": model.name, "display_name": display_name, "status": "trained"}
        except Exception as e:
            logger.error(f"Vertex AutoML train error: {e}")
            return {"error": str(e)}

    def deploy_model(self, model_id: str, endpoint_name: str,
                      machine_type: str = "n1-standard-4") -> dict:
        if not self.aiplatform: return {"error": "SDK not initialized"}
        try:
            model    = self.aiplatform.Model(model_id)
            endpoint = model.deploy(
                deployed_model_display_name=endpoint_name,
                machine_type=machine_type,
                min_replica_count=1,
                max_replica_count=3,
            )
            return {"endpoint_id": endpoint.name, "model_id": model_id, "status": "deployed"}
        except Exception as e:
            logger.error(f"Vertex deploy error: {e}")
            return {"error": str(e)}

    def predict(self, endpoint_id: str, instances: List[Dict]) -> dict:
        if not self.aiplatform: return {"error": "SDK not initialized"}
        try:
            endpoint = self.aiplatform.Endpoint(endpoint_id)
            response = endpoint.predict(instances=instances)
            return {
                "predictions":  response.predictions,
                "deployed_model": response.deployed_model_id,
            }
        except Exception as e:
            logger.error(f"Vertex predict error: {e}")
            return {"error": str(e)}

    def batch_predict(self, model_id: str, input_gcs: str,
                       output_gcs: str, machine_type: str = "n1-standard-4") -> dict:
        if not self.aiplatform: return {"error": "SDK not initialized"}
        try:
            model = self.aiplatform.Model(model_id)
            job   = model.batch_predict(
                job_display_name=f"batch_predict_{model_id[:8]}",
                gcs_source=input_gcs,
                gcs_destination_prefix=output_gcs,
                machine_type=machine_type,
            )
            return {"job_id": job.name, "status": "submitted"}
        except Exception as e:
            logger.error(f"Vertex batch predict error: {e}")
            return {"error": str(e)}

    def list_models(self) -> List[Dict]:
        if not self.aiplatform: return []
        try:
            models = self.aiplatform.Model.list()
            return [{"name": m.display_name, "id": m.name, "version": m.version_id}
                    for m in models]
        except Exception as e:
            logger.error(f"Vertex list models error: {e}")
            return []

    def get_model_evaluation(self, model_id: str) -> dict:
        if not self.aiplatform: return {}
        try:
            model = self.aiplatform.Model(model_id)
            evals = list(model.list_model_evaluations())
            if not evals: return {"evaluations": []}
            metrics = evals[0].metrics
            return {"metrics": dict(metrics), "evaluation_id": evals[0].name}
        except Exception as e:
            return {"error": str(e)}
