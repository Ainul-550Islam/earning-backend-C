"""
api/ai_engine/INTEGRATIONS/pytorch_integration.py
==================================================
PyTorch Integration — deep learning model training ও inference।
MLP, LSTM, Transformer architectures।
Large-scale user behavior modeling, NLP tasks।
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class PyTorchIntegration:
    """PyTorch model training ও inference wrapper।"""

    def __init__(self, device: str = 'auto'):
        self.device = self._get_device(device)
        logger.info(f"PyTorch device: {self.device}")

    def _get_device(self, device: str) -> str:
        if device == 'auto':
            try:
                import torch
                return 'cuda' if torch.cuda.is_available() else 'cpu'
            except ImportError:
                return 'cpu'
        return device

    def build_mlp(self, input_dim: int, hidden_dims: List[int] = None,
                   output_dim: int = 1, dropout: float = 0.2,
                   task: str = 'classification') -> Any:
        """MLP (Multi-Layer Perceptron) তৈরি করো।"""
        try:
            import torch.nn as nn
            hidden_dims = hidden_dims or [256, 128, 64]

            layers  = []
            in_dim  = input_dim
            for h in hidden_dims:
                layers += [
                    nn.Linear(in_dim, h),
                    nn.BatchNorm1d(h),
                    nn.ReLU(),
                    nn.Dropout(dropout),
                ]
                in_dim = h

            layers.append(nn.Linear(in_dim, output_dim))
            if task == 'classification':
                layers.append(nn.Sigmoid() if output_dim == 1 else nn.Softmax(dim=1))

            return nn.Sequential(*layers)
        except ImportError:
            logger.warning("PyTorch not installed. pip install torch")
            return None

    def build_lstm(self, input_dim: int, hidden_dim: int = 128,
                    n_layers: int = 2, output_dim: int = 1) -> Any:
        """LSTM for sequential/time-series data।"""
        try:
            import torch
            import torch.nn as nn

            class LSTMModel(nn.Module):
                def __init__(self):
                    super().__init__()
                    self.lstm = nn.LSTM(input_dim, hidden_dim, n_layers,
                                        batch_first=True, dropout=0.2 if n_layers > 1 else 0)
                    self.fc   = nn.Linear(hidden_dim, output_dim)
                    self.sig  = nn.Sigmoid()

                def forward(self, x):
                    out, _ = self.lstm(x)
                    out    = self.fc(out[:, -1, :])
                    return self.sig(out) if output_dim == 1 else out

            return LSTMModel()
        except ImportError:
            logger.warning("PyTorch not installed")
            return None

    def train(self, model, X_train, y_train, X_val=None, y_val=None,
               epochs: int = 50, lr: float = 1e-3,
               batch_size: int = 256) -> dict:
        """PyTorch model train করো।"""
        if model is None:
            return {'error': 'No model provided'}
        try:
            import torch
            import torch.nn as nn
            from torch.utils.data import DataLoader, TensorDataset

            X_t = torch.FloatTensor(X_train).to(self.device)
            y_t = torch.FloatTensor(y_train).unsqueeze(1).to(self.device)
            model = model.to(self.device)

            dataset   = TensorDataset(X_t, y_t)
            loader    = DataLoader(dataset, batch_size=batch_size, shuffle=True)
            optimizer = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=1e-5)
            criterion = nn.BCELoss()
            scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, patience=5)

            history = {'train_loss': [], 'val_loss': []}

            for epoch in range(epochs):
                model.train()
                epoch_loss = 0.0
                for X_batch, y_batch in loader:
                    optimizer.zero_grad()
                    pred = model(X_batch)
                    loss = criterion(pred, y_batch)
                    loss.backward()
                    nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                    optimizer.step()
                    epoch_loss += loss.item()

                avg_loss = epoch_loss / len(loader)
                history['train_loss'].append(round(avg_loss, 6))

                if X_val is not None:
                    val_loss = self._compute_val_loss(model, X_val, y_val, criterion)
                    history['val_loss'].append(round(val_loss, 6))
                    scheduler.step(val_loss)

                if (epoch + 1) % 10 == 0:
                    logger.info(f"Epoch {epoch+1}/{epochs} — loss: {avg_loss:.4f}")

            return {'epochs': epochs, 'final_loss': history['train_loss'][-1],
                    'history': history}
        except Exception as e:
            logger.error(f"PyTorch train error: {e}")
            return {'error': str(e)}

    def _compute_val_loss(self, model, X_val, y_val, criterion) -> float:
        try:
            import torch
            model.eval()
            with torch.no_grad():
                X_t  = torch.FloatTensor(X_val).to(self.device)
                y_t  = torch.FloatTensor(y_val).unsqueeze(1).to(self.device)
                pred = model(X_t)
                return float(criterion(pred, y_t).item())
        except Exception:
            return 0.0

    def predict(self, model, X, threshold: float = 0.5) -> List:
        """Inference করো।"""
        if model is None:
            return [0] * len(X)
        try:
            import torch
            model.eval()
            with torch.no_grad():
                t    = torch.FloatTensor(X).to(self.device)
                preds = model(t).cpu().numpy().flatten()
            return [1 if p >= threshold else 0 for p in preds]
        except Exception as e:
            logger.error(f"PyTorch predict error: {e}")
            return [0] * len(X)

    def predict_proba(self, model, X) -> List[float]:
        """Probability predictions।"""
        if model is None:
            return [0.5] * len(X)
        try:
            import torch
            model.eval()
            with torch.no_grad():
                t     = torch.FloatTensor(X).to(self.device)
                probs = model(t).cpu().numpy().flatten()
            return [round(float(p), 6) for p in probs]
        except Exception as e:
            return [0.5] * len(X)

    def save_model(self, model, path: str) -> str:
        """Model checkpoint save করো।"""
        try:
            import torch
            torch.save(model.state_dict(), path)
            logger.info(f"PyTorch model saved: {path}")
            return path
        except Exception as e:
            logger.error(f"Save error: {e}")
            return ''

    def load_model(self, model_architecture, path: str) -> Any:
        """Model checkpoint load করো।"""
        try:
            import torch
            model_architecture.load_state_dict(torch.load(path, map_location=self.device))
            model_architecture.eval()
            return model_architecture
        except Exception as e:
            logger.error(f"Load error: {e}")
            return None

    def count_parameters(self, model) -> dict:
        """Model parameter count।"""
        try:
            total     = sum(p.numel() for p in model.parameters())
            trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
            return {
                'total_params':     total,
                'trainable_params': trainable,
                'frozen_params':    total - trainable,
                'size_mb':          round(total * 4 / 1024 / 1024, 3),  # float32
            }
        except Exception:
            return {}
