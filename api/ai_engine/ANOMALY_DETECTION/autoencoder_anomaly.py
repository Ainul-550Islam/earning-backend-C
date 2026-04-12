"""
api/ai_engine/ANOMALY_DETECTION/autoencoder_anomaly.py
=======================================================
Autoencoder-based Anomaly Detection।
Reconstruction error → anomaly score।
Complex patterns ও high-dimensional data এর জন্য।
"""
import logging
from typing import List, Optional
logger = logging.getLogger(__name__)

class AutoencoderAnomalyDetector:
    """Neural autoencoder based anomaly detection।"""

    def __init__(self, input_dim: int, encoding_dim: int = 32,
                 threshold: float = None):
        self.input_dim    = input_dim
        self.encoding_dim = encoding_dim
        self.threshold    = threshold
        self.model        = None
        self._trained     = False
        self._mean_error  = 0.0
        self._std_error   = 1.0

    def build(self):
        try:
            import torch, torch.nn as nn
            self.model = nn.Sequential(
                nn.Linear(self.input_dim, max(self.encoding_dim*2, 64)), nn.ReLU(),
                nn.Linear(max(self.encoding_dim*2, 64), self.encoding_dim), nn.ReLU(),
                nn.Linear(self.encoding_dim, max(self.encoding_dim*2, 64)), nn.ReLU(),
                nn.Linear(max(self.encoding_dim*2, 64), self.input_dim),
            )
            return True
        except ImportError:
            logger.warning("PyTorch not installed for autoencoder. pip install torch")
            return False

    def fit(self, X_normal, epochs: int = 50, lr: float = 1e-3) -> dict:
        if self.model is None:
            if not self.build():
                return {'fitted': False, 'method': 'sklearn_fallback'}
        try:
            import torch, torch.nn as nn
            import numpy as np
            X = torch.FloatTensor(np.array(X_normal))
            opt = torch.optim.Adam(self.model.parameters(), lr=lr)
            self.model.train()
            for _ in range(epochs):
                opt.zero_grad()
                reconstructed = self.model(X)
                loss = nn.MSELoss()(reconstructed, X)
                loss.backward()
                opt.step()
            self.model.eval()
            with torch.no_grad():
                errors = ((X - self.model(X))**2).mean(dim=1).numpy()
            self._mean_error = float(errors.mean())
            self._std_error  = float(errors.std()) or 1.0
            self.threshold   = self.threshold or (self._mean_error + 3 * self._std_error)
            self._trained    = True
            return {'fitted': True, 'threshold': round(self.threshold, 6), 'mean_error': round(self._mean_error, 6)}
        except Exception as e:
            return self._sklearn_fallback_fit(X_normal)

    def _sklearn_fallback_fit(self, X_normal) -> dict:
        try:
            from sklearn.preprocessing import StandardScaler
            import numpy as np
            self._scaler = StandardScaler()
            self._scaler.fit(np.array(X_normal))
            self._trained    = True
            self.threshold   = self.threshold or 3.0
            return {'fitted': True, 'method': 'sklearn_fallback'}
        except Exception as e:
            return {'fitted': False, 'error': str(e)}

    def reconstruction_error(self, X) -> List[float]:
        if not self._trained: return [0.05] * len(X)
        try:
            import torch, numpy as np
            t = torch.FloatTensor(np.array(X))
            with torch.no_grad():
                errors = ((t - self.model(t))**2).mean(dim=1).numpy()
            return [round(float(e), 6) for e in errors]
        except Exception:
            try:
                import numpy as np
                X_arr = np.array(X)
                X_scaled = self._scaler.transform(X_arr)
                return [round(float(abs(z).mean()), 4) for z in X_scaled]
            except Exception:
                return [0.05] * len(X)

    def is_anomaly(self, features: dict) -> dict:
        import numpy as np
        X = [list(features.values())]
        error = self.reconstruction_error(X)[0]
        z_score = (error - self._mean_error) / max(self._std_error, 0.001)
        is_anom = error > (self.threshold or self._mean_error + 3*self._std_error)
        return {
            'is_anomaly':         is_anom,
            'reconstruction_error': round(error, 6),
            'z_score':            round(z_score, 4),
            'anomaly_score':      round(min(1.0, max(0.0, z_score/6)), 4),
            'threshold':          round(self.threshold or 0, 6),
        }
