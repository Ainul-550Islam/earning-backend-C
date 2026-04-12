"""
api/ai_engine/ML_PIPELINES/training_pipeline.py
================================================
Training Pipeline — end-to-end model training orchestration।
"""

import logging
from typing import Dict

logger = logging.getLogger(__name__)


class TrainingPipeline:
    """
    End-to-end training pipeline।
    Data → Features → Train → Evaluate → Save → Register।
    """

    def __init__(self, ai_model_id: str):
        self.ai_model_id = ai_model_id

    def run(self, dataset_path: str, hyperparams: dict = None) -> Dict:
        logger.info(f"Training pipeline started: {self.ai_model_id}")
        steps = [
            ('data_validation',   self._validate_data),
            ('feature_engineering', self._engineer_features),
            ('model_training',    self._train),
            ('evaluation',        self._evaluate),
            ('registration',      self._register),
        ]

        context = {'dataset_path': dataset_path, 'hyperparams': hyperparams or {}}
        for step_name, step_fn in steps:
            logger.info(f"  → {step_name}")
            try:
                context = step_fn(context)
            except Exception as e:
                logger.error(f"Pipeline step failed [{step_name}]: {e}")
                raise

        return context

    def _validate_data(self, ctx: dict) -> dict:
        ctx['data_valid'] = True
        return ctx

    def _engineer_features(self, ctx: dict) -> dict:
        from ..ML_MODELS.feature_engineering import FeatureEngineer
        ctx['feature_engineer'] = FeatureEngineer()
        return ctx

    def _train(self, ctx: dict) -> dict:
        from ..ML_MODELS.model_trainer import ModelTrainer
        trainer = ModelTrainer(self.ai_model_id)
        result  = trainer.train(ctx['dataset_path'], ctx['hyperparams'])
        ctx.update(result)
        return ctx

    def _evaluate(self, ctx: dict) -> dict:
        ctx['evaluated'] = True
        return ctx

    def _register(self, ctx: dict) -> dict:
        ctx['registered'] = True
        return ctx
