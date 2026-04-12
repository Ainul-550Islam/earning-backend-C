"""
api/ai_engine/INTEGRATIONS/sagemaker_integration.py
====================================================
AWS SageMaker Integration — cloud ML training ও deployment।
Managed training jobs, model hosting, batch transforms।
Production-scale model serving on AWS infrastructure।
"""

import logging
import json
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class SageMakerIntegration:
    """
    AWS SageMaker full integration।
    Training jobs, endpoints, batch predictions।
    """

    def __init__(self, role_arn: str = None,
                 region: str = 'us-east-1',
                 s3_bucket: str = None):
        self.role_arn  = role_arn
        self.region    = region
        self.s3_bucket = s3_bucket
        self.session   = None
        self.sm_client = None
        self._init()

    def _init(self):
        try:
            import boto3
            self.session   = boto3.Session(region_name=self.region)
            self.sm_client = self.session.client('sagemaker')
            logger.info(f"SageMaker client initialized — region: {self.region}")
        except ImportError:
            logger.warning("boto3 not installed. pip install boto3 sagemaker")
        except Exception as e:
            logger.error(f"SageMaker init error: {e}")

    def create_training_job(self, job_name: str, algorithm_image: str,
                             training_data_s3: str, output_s3: str,
                             hyperparams: dict = None,
                             instance_type: str = 'ml.m5.xlarge',
                             instance_count: int = 1) -> dict:
        """SageMaker training job শুরু করো।"""
        if not self.sm_client:
            return {'error': 'SageMaker client not initialized'}

        config = {
            'TrainingJobName':     job_name,
            'RoleArn':             self.role_arn or '',
            'AlgorithmSpecification': {
                'TrainingImage':    algorithm_image,
                'TrainingInputMode': 'File',
            },
            'HyperParameters':     {k: str(v) for k, v in (hyperparams or {}).items()},
            'InputDataConfig':     [{
                'ChannelName':  'training',
                'DataSource':   {
                    'S3DataSource': {
                        'S3DataType': 'S3Prefix',
                        'S3Uri':      training_data_s3,
                    }
                },
            }],
            'OutputDataConfig':    {'S3OutputPath': output_s3},
            'ResourceConfig': {
                'InstanceType':  instance_type,
                'InstanceCount': instance_count,
                'VolumeSizeInGB': 30,
            },
            'StoppingCondition': {'MaxRuntimeInSeconds': 86400},
        }

        try:
            response = self.sm_client.create_training_job(**config)
            return {
                'job_name':  job_name,
                'status':    'created',
                'arn':       response.get('TrainingJobArn', ''),
            }
        except Exception as e:
            logger.error(f"Training job error: {e}")
            return {'error': str(e)}

    def get_training_job_status(self, job_name: str) -> dict:
        """Training job status check করো।"""
        if not self.sm_client:
            return {'error': 'Not initialized'}
        try:
            response = self.sm_client.describe_training_job(TrainingJobName=job_name)
            return {
                'job_name':    job_name,
                'status':      response.get('TrainingJobStatus'),
                'secondary':   response.get('SecondaryStatus'),
                'failure_reason': response.get('FailureReason', ''),
            }
        except Exception as e:
            return {'error': str(e)}

    def deploy_model(self, model_data: str,
                      endpoint_name: str,
                      image_uri: str,
                      instance_type: str = 'ml.t2.medium',
                      instance_count: int = 1) -> dict:
        """Model endpoint deploy করো।"""
        if not self.sm_client:
            return {'error': 'Not initialized'}

        model_name = f"{endpoint_name}-model"
        try:
            # Create model
            self.sm_client.create_model(
                ModelName=model_name,
                PrimaryContainer={
                    'Image':        image_uri,
                    'ModelDataUrl': model_data,
                },
                ExecutionRoleArn=self.role_arn or '',
            )

            # Create endpoint config
            self.sm_client.create_endpoint_config(
                EndpointConfigName=f"{endpoint_name}-config",
                ProductionVariants=[{
                    'VariantName':     'default',
                    'ModelName':       model_name,
                    'InstanceType':    instance_type,
                    'InitialInstanceCount': instance_count,
                }],
            )

            # Create endpoint
            self.sm_client.create_endpoint(
                EndpointName=endpoint_name,
                EndpointConfigName=f"{endpoint_name}-config",
            )

            return {
                'endpoint_name': endpoint_name,
                'status':        'creating',
                'instance_type': instance_type,
            }
        except Exception as e:
            logger.error(f"Deploy error: {e}")
            return {'error': str(e)}

    def invoke_endpoint(self, endpoint_name: str,
                         payload: dict,
                         content_type: str = 'application/json') -> dict:
        """Deployed endpoint এ prediction request পাঠাও।"""
        if not self.session:
            return {'error': 'Not initialized'}
        try:
            runtime = self.session.client('sagemaker-runtime')
            response = runtime.invoke_endpoint(
                EndpointName=endpoint_name,
                ContentType=content_type,
                Body=json.dumps(payload),
            )
            result = json.loads(response['Body'].read().decode())
            return {'prediction': result, 'status': 'ok'}
        except Exception as e:
            logger.error(f"Invoke error: {e}")
            return {'error': str(e)}

    def batch_transform(self, job_name: str,
                          model_name: str,
                          input_s3: str,
                          output_s3: str,
                          instance_type: str = 'ml.m5.xlarge') -> dict:
        """Batch prediction job চালাও।"""
        if not self.sm_client:
            return {'error': 'Not initialized'}
        try:
            response = self.sm_client.create_transform_job(
                TransformJobName=job_name,
                ModelName=model_name,
                TransformInput={
                    'DataSource': {'S3DataSource': {'S3DataType': 'S3Prefix', 'S3Uri': input_s3}},
                    'ContentType': 'application/json',
                },
                TransformOutput={'S3OutputPath': output_s3},
                TransformResources={'InstanceType': instance_type, 'InstanceCount': 1},
            )
            return {'job_name': job_name, 'status': 'created'}
        except Exception as e:
            return {'error': str(e)}

    def delete_endpoint(self, endpoint_name: str) -> dict:
        """Endpoint delete করো (cost saving)।"""
        if not self.sm_client:
            return {'error': 'Not initialized'}
        try:
            self.sm_client.delete_endpoint(EndpointName=endpoint_name)
            return {'deleted': endpoint_name, 'status': 'ok'}
        except Exception as e:
            return {'error': str(e)}

    def list_endpoints(self) -> List[Dict]:
        """Active endpoints list করো।"""
        if not self.sm_client:
            return []
        try:
            response = self.sm_client.list_endpoints()
            return [
                {
                    'name':     e['EndpointName'],
                    'status':   e['EndpointStatus'],
                    'created':  str(e.get('CreationTime', '')),
                }
                for e in response.get('Endpoints', [])
            ]
        except Exception as e:
            logger.error(f"List endpoints error: {e}")
            return []

    def upload_to_s3(self, local_path: str, s3_key: str) -> str:
        """Model artifact S3 তে upload করো।"""
        if not self.session or not self.s3_bucket:
            return ''
        try:
            s3 = self.session.client('s3')
            s3.upload_file(local_path, self.s3_bucket, s3_key)
            s3_uri = f"s3://{self.s3_bucket}/{s3_key}"
            logger.info(f"Uploaded to: {s3_uri}")
            return s3_uri
        except Exception as e:
            logger.error(f"S3 upload error: {e}")
            return ''
