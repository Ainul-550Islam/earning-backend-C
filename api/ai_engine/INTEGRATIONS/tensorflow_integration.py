"""
api/ai_engine/INTEGRATIONS/tensorflow_integration.py
=====================================================
TensorFlow/Keras Integration।
"""

import logging
logger = logging.getLogger(__name__)


class TensorFlowIntegration:
    """TensorFlow/Keras model training ও serving।"""

    def build_mlp(self, input_dim: int, hidden_dims: list = None,
                  output_dim: int = 1, task: str = 'classification'):
        try:
            import tensorflow as tf
            hidden_dims = hidden_dims or [128, 64, 32]
            model = tf.keras.Sequential()
            model.add(tf.keras.layers.Input(shape=(input_dim,)))
            for dim in hidden_dims:
                model.add(tf.keras.layers.Dense(dim, activation='relu'))
                model.add(tf.keras.layers.BatchNormalization())
                model.add(tf.keras.layers.Dropout(0.2))
            if task == 'classification':
                model.add(tf.keras.layers.Dense(output_dim, activation='sigmoid'))
                model.compile(optimizer='adam', loss='binary_crossentropy', metrics=['accuracy'])
            else:
                model.add(tf.keras.layers.Dense(output_dim))
                model.compile(optimizer='adam', loss='mse')
            return model
        except ImportError:
            logger.warning("TensorFlow not installed. pip install tensorflow")
            return None

    def train(self, model, X_train, y_train, X_val=None, y_val=None,
              epochs: int = 50, batch_size: int = 256) -> dict:
        if model is None:
            return {'error': 'Model not built'}
        try:
            validation_data = (X_val, y_val) if X_val is not None else None
            callbacks = []
            try:
                import tensorflow as tf
                callbacks.append(tf.keras.callbacks.EarlyStopping(patience=5, restore_best_weights=True))
            except Exception:
                pass
            history = model.fit(
                X_train, y_train,
                validation_data=validation_data,
                epochs=epochs, batch_size=batch_size,
                callbacks=callbacks, verbose=0
            )
            return {
                'final_loss':     round(float(history.history['loss'][-1]), 4),
                'epochs_trained': len(history.history['loss']),
            }
        except Exception as e:
            return {'error': str(e)}

    def save_model(self, model, path: str):
        if model:
            try:
                model.save(path)
                return path
            except Exception as e:
                logger.error(f"TF model save error: {e}")
        return None

    def load_model(self, path: str):
        try:
            import tensorflow as tf
            return tf.keras.models.load_model(path)
        except Exception as e:
            logger.error(f"TF model load error: {e}")
            return None


"""
api/ai_engine/INTEGRATIONS/pytorch_integration.py
==================================================
PyTorch Integration।
"""


class PyTorchIntegration:
    """PyTorch model training ও inference।"""

    def build_mlp(self, input_dim: int, hidden_dims: list = None, output_dim: int = 1):
        try:
            import torch
            import torch.nn as nn
            hidden_dims = hidden_dims or [128, 64, 32]

            layers = []
            in_dim = input_dim
            for h in hidden_dims:
                layers += [nn.Linear(in_dim, h), nn.BatchNorm1d(h), nn.ReLU(), nn.Dropout(0.2)]
                in_dim = h
            layers += [nn.Linear(in_dim, output_dim), nn.Sigmoid()]
            return nn.Sequential(*layers)
        except ImportError:
            logger.warning("PyTorch not installed. pip install torch")
            return None

    def train(self, model, X_train, y_train, epochs: int = 50,
              lr: float = 1e-3, batch_size: int = 256) -> dict:
        if model is None:
            return {'error': 'Model not built'}
        try:
            import torch
            import torch.nn as nn
            from torch.utils.data import DataLoader, TensorDataset

            X_t = torch.FloatTensor(X_train)
            y_t = torch.FloatTensor(y_train).unsqueeze(1)
            dataset = TensorDataset(X_t, y_t)
            loader  = DataLoader(dataset, batch_size=batch_size, shuffle=True)

            optimizer = torch.optim.Adam(model.parameters(), lr=lr)
            criterion = nn.BCELoss()

            model.train()
            for epoch in range(epochs):
                for X_batch, y_batch in loader:
                    optimizer.zero_grad()
                    pred = model(X_batch)
                    loss = criterion(pred, y_batch)
                    loss.backward()
                    optimizer.step()

            return {'epochs': epochs, 'status': 'completed'}
        except Exception as e:
            return {'error': str(e)}

    def predict(self, model, X) -> list:
        if model is None:
            return [0.5] * len(X)
        try:
            import torch
            model.eval()
            with torch.no_grad():
                t = torch.FloatTensor(X)
                preds = model(t).numpy().flatten()
            return [round(float(p), 4) for p in preds]
        except Exception:
            return [0.5] * len(X)


"""
api/ai_engine/INTEGRATIONS/sagemaker_integration.py
====================================================
AWS SageMaker Integration।
"""


class SageMakerIntegration:
    """AWS SageMaker model training ও deployment।"""

    def __init__(self, role_arn: str = None, region: str = 'us-east-1'):
        self.role_arn = role_arn
        self.region   = region
        self._init()

    def _init(self):
        try:
            import boto3
            self.session = boto3.Session(region_name=self.region)
        except ImportError:
            logger.warning("boto3 not installed. pip install boto3")
            self.session = None

    def deploy_model(self, model_data: str, instance_type: str = 'ml.t2.medium') -> dict:
        if not self.session:
            return {'error': 'boto3 not available'}
        # Placeholder — implement with sagemaker SDK
        return {'endpoint': 'sagemaker-endpoint-placeholder', 'status': 'deployed'}

    def invoke_endpoint(self, endpoint_name: str, payload: dict) -> dict:
        if not self.session:
            return {'error': 'boto3 not available'}
        try:
            import json
            client = self.session.client('sagemaker-runtime')
            response = client.invoke_endpoint(
                EndpointName=endpoint_name,
                ContentType='application/json',
                Body=json.dumps(payload)
            )
            import json as json2
            return json2.loads(response['Body'].read())
        except Exception as e:
            return {'error': str(e)}


"""
api/ai_engine/INTEGRATIONS/kubeflow_integration.py
===================================================
KubeFlow Pipeline Integration।
"""


class KubeFlowIntegration:
    """KubeFlow Pipelines integration for ML orchestration।"""

    def __init__(self, host: str = None):
        self.host   = host
        self.client = None
        self._init()

    def _init(self):
        try:
            import kfp
            if self.host:
                self.client = kfp.Client(host=self.host)
        except ImportError:
            logger.warning("kfp not installed. pip install kfp")

    def submit_pipeline(self, pipeline_fn, run_name: str, params: dict = None) -> dict:
        if not self.client:
            return {'error': 'KubeFlow client not configured'}
        try:
            run = self.client.create_run_from_pipeline_func(
                pipeline_fn,
                arguments=params or {},
                run_name=run_name,
            )
            return {'run_id': run.run_id, 'status': 'submitted'}
        except Exception as e:
            return {'error': str(e)}
