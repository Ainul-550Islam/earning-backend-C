"""
Machine Learning Integration Service for Offer Routing System

This module provides comprehensive ML integration,
including model training, prediction, and optimization.
"""

import logging
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from django.core.cache import cache
from django.db.models import Q, Avg, Sum, Count, StdDev
from django.utils import timezone
from django.contrib.auth import get_user_model

from ..models import (
    OfferRoute, UserOfferHistory, RoutePerformanceStat,
    RoutingConfig, OfferQualityScore, RoutingInsight
)
from ..utils import get_client_ip, validate_ip_address

User = get_user_model()
logger = logging.getLogger(__name__)


class MLIntegrationService:
    """
    Comprehensive ML integration service for offer routing.
    
    Manages:
    - Feature engineering
    - Model training
    - Real-time prediction
    - Model evaluation
    - A/B testing integration
    - Continuous learning
    """
    
    def __init__(self):
        self.cache_timeout = 1800  # 30 minutes
        self.feature_window_days = 30
        self.model_retrain_interval = 7  # days
        self.prediction_confidence_threshold = 0.7
        self.feature_importance_threshold = 0.05
        
        # ML models registry
        self.models = {
            'conversion_prediction': None,
            'revenue_prediction': None,
            'fraud_detection': None,
            'user_segmentation': None,
            'offer_ranking': None,
            'price_optimization': None,
            'churn_prediction': None,
            'quality_scoring': None,
        }
        
        # Initialize models
        self._initialize_models()
    
    def train_conversion_prediction_model(self, tenant_id: int, training_days: int = 30) -> Dict[str, any]:
        """
        Train conversion prediction model.
        
        Args:
            tenant_id: Tenant ID to train for
            training_days: Number of days of training data
            
        Returns:
            Dictionary containing training results
        """
        try:
            # Get training data
            training_data = self._get_conversion_training_data(tenant_id, training_days)
            
            if len(training_data) < 1000:
                return {'error': 'Insufficient training data (minimum 1000 samples required)'}
            
            # Feature engineering
            X, y = self._engineer_conversion_features(training_data)
            
            # Split data
            X_train, X_test, y_train, y_test = self._split_data(X, y, test_size=0.2)
            
            # Train model
            model = self._train_conversion_model(X_train, y_train)
            
            # Evaluate model
            evaluation = self._evaluate_conversion_model(model, X_test, y_test)
            
            # Feature importance
            feature_importance = self._calculate_feature_importance(model, X.columns.tolist())
            
            # Save model
            model_metadata = {
                'model_type': 'conversion_prediction',
                'tenant_id': tenant_id,
                'training_data_size': len(training_data),
                'features': X.columns.tolist(),
                'feature_importance': feature_importance,
                'evaluation_metrics': evaluation,
                'training_date': timezone.now().isoformat(),
                'model_version': self._get_next_model_version('conversion_prediction')
            }
            
            self._save_model('conversion_prediction', model, model_metadata, tenant_id)
            
            # Build training results
            training_results = {
                'tenant_id': tenant_id,
                'model_type': 'conversion_prediction',
                'training_data_size': len(training_data),
                'feature_count': X.shape[1],
                'evaluation_metrics': evaluation,
                'feature_importance': feature_importance,
                'model_metadata': model_metadata,
                'training_time': timezone.now().isoformat(),
                'next_retrain_date': (timezone.now() + timedelta(days=self.model_retrain_interval)).isoformat()
            }
            
            # Cache training results
            cache_key = f"ml_training_conversion:{tenant_id}"
            cache.set(cache_key, training_results, self.cache_timeout)
            
            # Log training
            self._log_model_training(training_results)
            
            logger.info(f"Conversion prediction model trained for tenant {tenant_id}")
            
            return training_results
            
        except Exception as e:
            logger.error(f"Error training conversion prediction model for tenant {tenant_id}: {e}")
            return {'error': str(e)}
    
    def predict_conversion_probability(self, user_id: int, offer_id: int, context: Dict[str, any]) -> Dict[str, any]:
        """
        Predict conversion probability for user-offer pair.
        
        Args:
            user_id: User ID
            offer_id: Offer ID
            context: Prediction context
            
        Returns:
            Dictionary containing prediction results
        """
        try:
            # Get model
            model = self.models.get('conversion_prediction')
            if not model:
                return {'error': 'Conversion prediction model not available'}
            
            # Extract features
            features = self._extract_conversion_features(user_id, offer_id, context)
            
            # Make prediction
            prediction = model.predict_proba([features])[0]
            probability = prediction[1]  # Probability of conversion
            
            # Get prediction confidence
            confidence = self._calculate_prediction_confidence(model, [features])
            
            # Get similar cases
            similar_cases = self._find_similar_conversion_cases(user_id, offer_id, features)
            
            # Build prediction results
            prediction_results = {
                'user_id': user_id,
                'offer_id': offer_id,
                'conversion_probability': float(probability),
                'confidence': float(confidence),
                'prediction_class': 'high' if probability > 0.8 else 'medium' if probability > 0.5 else 'low',
                'features_used': features,
                'similar_cases': similar_cases,
                'model_metadata': self._get_model_metadata('conversion_prediction'),
                'prediction_time': timezone.now().isoformat(),
                'risk_assessment': self._assess_conversion_risk(probability, confidence),
                'recommendations': self._generate_conversion_recommendations(probability, confidence, similar_cases)
            }
            
            # Log prediction
            self._log_conversion_prediction(prediction_results)
            
            logger.info(f"Conversion prediction completed for user {user_id}, offer {offer_id}: {probability:.3f}")
            
            return prediction_results
            
        except Exception as e:
            logger.error(f"Error predicting conversion probability for user {user_id}, offer {offer_id}: {e}")
            return {'error': str(e)}
    
    def train_revenue_prediction_model(self, tenant_id: int, training_days: int = 30) -> Dict[str, any]:
        """
        Train revenue prediction model.
        
        Args:
            tenant_id: Tenant ID to train for
            training_days: Number of days of training data
            
        Returns:
            Dictionary containing training results
        """
        try:
            # Get training data
            training_data = self._get_revenue_training_data(tenant_id, training_days)
            
            if len(training_data) < 500:
                return {'error': 'Insufficient training data (minimum 500 samples required)'}
            
            # Feature engineering
            X, y = self._engineer_revenue_features(training_data)
            
            # Split data
            X_train, X_test, y_train, y_test = self._split_data(X, y, test_size=0.2)
            
            # Train model
            model = self._train_revenue_model(X_train, y_train)
            
            # Evaluate model
            evaluation = self._evaluate_revenue_model(model, X_test, y_test)
            
            # Feature importance
            feature_importance = self._calculate_feature_importance(model, X.columns.tolist())
            
            # Save model
            model_metadata = {
                'model_type': 'revenue_prediction',
                'tenant_id': tenant_id,
                'training_data_size': len(training_data),
                'features': X.columns.tolist(),
                'feature_importance': feature_importance,
                'evaluation_metrics': evaluation,
                'training_date': timezone.now().isoformat(),
                'model_version': self._get_next_model_version('revenue_prediction')
            }
            
            self._save_model('revenue_prediction', model, model_metadata, tenant_id)
            
            # Build training results
            training_results = {
                'tenant_id': tenant_id,
                'model_type': 'revenue_prediction',
                'training_data_size': len(training_data),
                'feature_count': X.shape[1],
                'evaluation_metrics': evaluation,
                'feature_importance': feature_importance,
                'model_metadata': model_metadata,
                'training_time': timezone.now().isoformat(),
                'next_retrain_date': (timezone.now() + timedelta(days=self.model_retrain_interval)).isoformat()
            }
            
            # Cache training results
            cache_key = f"ml_training_revenue:{tenant_id}"
            cache.set(cache_key, training_results, self.cache_timeout)
            
            # Log training
            self._log_model_training(training_results)
            
            logger.info(f"Revenue prediction model trained for tenant {tenant_id}")
            
            return training_results
            
        except Exception as e:
            logger.error(f"Error training revenue prediction model for tenant {tenant_id}: {e}")
            return {'error': str(e)}
    
    def predict_revenue(self, user_id: int, offer_id: int, context: Dict[str, any]) -> Dict[str, any]:
        """
        Predict revenue for user-offer pair.
        
        Args:
            user_id: User ID
            offer_id: Offer ID
            context: Prediction context
            
        Returns:
            Dictionary containing prediction results
        """
        try:
            # Get model
            model = self.models.get('revenue_prediction')
            if not model:
                return {'error': 'Revenue prediction model not available'}
            
            # Extract features
            features = self._extract_revenue_features(user_id, offer_id, context)
            
            # Make prediction
            prediction = model.predict([features])[0]
            
            # Get prediction confidence
            confidence = self._calculate_prediction_confidence(model, [features])
            
            # Get prediction interval
            prediction_interval = self._get_prediction_interval(model, [features], confidence=0.95)
            
            # Build prediction results
            prediction_results = {
                'user_id': user_id,
                'offer_id': offer_id,
                'predicted_revenue': float(prediction),
                'confidence': float(confidence),
                'prediction_interval': {
                    'lower': float(prediction_interval[0]),
                    'upper': float(prediction_interval[1]),
                    'confidence': 0.95
                },
                'features_used': features,
                'model_metadata': self._get_model_metadata('revenue_prediction'),
                'prediction_time': timezone.now().isoformat(),
                'risk_assessment': self._assess_revenue_risk(prediction, confidence),
                'recommendations': self._generate_revenue_recommendations(prediction, confidence)
            }
            
            # Log prediction
            self._log_revenue_prediction(prediction_results)
            
            logger.info(f"Revenue prediction completed for user {user_id}, offer {offer_id}: ${prediction:.2f}")
            
            return prediction_results
            
        except Exception as e:
            logger.error(f"Error predicting revenue for user {user_id}, offer {offer_id}: {e}")
            return {'error': str(e)}
    
    def train_fraud_detection_model(self, tenant_id: int, training_days: int = 30) -> Dict[str, any]:
        """
        Train fraud detection model.
        
        Args:
            tenant_id: Tenant ID to train for
            training_days: Number of days of training data
            
        Returns:
            Dictionary containing training results
        """
        try:
            # Get training data
            training_data = self._get_fraud_training_data(tenant_id, training_days)
            
            if len(training_data) < 1000:
                return {'error': 'Insufficient training data (minimum 1000 samples required)'}
            
            # Feature engineering
            X, y = self._engineer_fraud_features(training_data)
            
            # Split data
            X_train, X_test, y_train, y_test = self._split_data(X, y, test_size=0.2, stratify=y)
            
            # Train model
            model = self._train_fraud_model(X_train, y_train)
            
            # Evaluate model
            evaluation = self._evaluate_fraud_model(model, X_test, y_test)
            
            # Feature importance
            feature_importance = self._calculate_feature_importance(model, X.columns.tolist())
            
            # Save model
            model_metadata = {
                'model_type': 'fraud_detection',
                'tenant_id': tenant_id,
                'training_data_size': len(training_data),
                'features': X.columns.tolist(),
                'feature_importance': feature_importance,
                'evaluation_metrics': evaluation,
                'training_date': timezone.now().isoformat(),
                'model_version': self._get_next_model_version('fraud_detection')
            }
            
            self._save_model('fraud_detection', model, model_metadata, tenant_id)
            
            # Build training results
            training_results = {
                'tenant_id': tenant_id,
                'model_type': 'fraud_detection',
                'training_data_size': len(training_data),
                'feature_count': X.shape[1],
                'evaluation_metrics': evaluation,
                'feature_importance': feature_importance,
                'model_metadata': model_metadata,
                'training_time': timezone.now().isoformat(),
                'next_retrain_date': (timezone.now() + timedelta(days=self.model_retrain_interval)).isoformat()
            }
            
            # Cache training results
            cache_key = f"ml_training_fraud:{tenant_id}"
            cache.set(cache_key, training_results, self.cache_timeout)
            
            # Log training
            self._log_model_training(training_results)
            
            logger.info(f"Fraud detection model trained for tenant {tenant_id}")
            
            return training_results
            
        except Exception as e:
            logger.error(f"Error training fraud detection model for tenant {tenant_id}: {e}")
            return {'error': str(e)}
    
    def detect_fraud(self, user_id: int, context: Dict[str, any]) -> Dict[str, any]:
        """
        Detect fraud for user activity.
        
        Args:
            user_id: User ID
            context: Detection context
            
        Returns:
            Dictionary containing fraud detection results
        """
        try:
            # Get model
            model = self.models.get('fraud_detection')
            if not model:
                return {'error': 'Fraud detection model not available'}
            
            # Extract features
            features = self._extract_fraud_features(user_id, context)
            
            # Make prediction
            prediction = model.predict_proba([features])[0]
            fraud_probability = prediction[1]  # Probability of fraud
            
            # Get prediction confidence
            confidence = self._calculate_prediction_confidence(model, [features])
            
            # Get fraud indicators
            fraud_indicators = self._analyze_fraud_indicators(features)
            
            # Build detection results
            detection_results = {
                'user_id': user_id,
                'fraud_probability': float(fraud_probability),
                'confidence': float(confidence),
                'is_fraud': fraud_probability > 0.7,
                'risk_level': self._determine_fraud_risk_level(fraud_probability),
                'features_used': features,
                'fraud_indicators': fraud_indicators,
                'model_metadata': self._get_model_metadata('fraud_detection'),
                'detection_time': timezone.now().isoformat(),
                'recommended_action': self._recommend_fraud_action(fraud_probability, confidence, fraud_indicators),
                'similar_cases': self._find_similar_fraud_cases(user_id, features)
            }
            
            # Log detection
            self._log_fraud_detection(detection_results)
            
            logger.info(f"Fraud detection completed for user {user_id}: {fraud_probability:.3f}")
            
            return detection_results
            
        except Exception as e:
            logger.error(f"Error detecting fraud for user {user_id}: {e}")
            return {'error': str(e)}
    
    def get_ml_model_status(self, tenant_id: int) -> Dict[str, any]:
        """
        Get status of all ML models for tenant.
        
        Args:
            tenant_id: Tenant ID
            
        Returns:
            Dictionary containing model status
        """
        try:
            model_status = {}
            
            for model_type in self.models.keys():
                # Get model metadata
                metadata = self._get_model_metadata(model_type, tenant_id)
                
                if metadata:
                    # Get model performance
                    performance = self._get_model_performance(model_type, tenant_id)
                    
                    # Get training schedule
                    next_training = self._get_next_training_schedule(model_type, tenant_id)
                    
                    model_status[model_type] = {
                        'is_trained': True,
                        'metadata': metadata,
                        'performance': performance,
                        'next_training': next_training,
                        'health_status': self._check_model_health(model_type, tenant_id)
                    }
                else:
                    model_status[model_type] = {
                        'is_trained': False,
                        'status': 'not_trained',
                        'health_status': 'unavailable'
                    }
            
            # Get overall ML status
            overall_status = {
                'tenant_id': tenant_id,
                'models': model_status,
                'total_models': len(self.models),
                'trained_models': sum(1 for status in model_status.values() if status.get('is_trained', False)),
                'healthy_models': sum(1 for status in model_status.values() if status.get('health_status') == 'healthy'),
                'last_update': timezone.now().isoformat(),
                'ml_service_status': 'operational' if model_status else 'initializing'
            }
            
            return overall_status
            
        except Exception as e:
            logger.error(f"Error getting ML model status for tenant {tenant_id}: {e}")
            return {'error': str(e)}
    
    def retrain_all_models(self, tenant_id: int, force: bool = False) -> Dict[str, any]:
        """
        Retrain all ML models for tenant.
        
        Args:
            tenant_id: Tenant ID
            force: Force retrain even if not scheduled
            
        Returns:
            Dictionary containing retraining results
        """
        try:
            retraining_results = {
                'tenant_id': tenant_id,
                'force_retrain': force,
                'start_time': timezone.now().isoformat(),
                'results': {},
                'summary': {}
            }
            
            # Check if retraining is needed
            if not force:
                retraining_needed = self._check_retraining_needed(tenant_id)
                if not retraining_needed['needed']:
                    retraining_results['summary'] = {
                        'status': 'skipped',
                        'reason': 'retraining not needed',
                        'next_retrain_date': retraining_needed['next_retrain_date']
                    }
                    return retraining_results
            
            # Retrain each model
            for model_type in ['conversion_prediction', 'revenue_prediction', 'fraud_detection']:
                try:
                    if model_type == 'conversion_prediction':
                        result = self.train_conversion_prediction_model(tenant_id)
                    elif model_type == 'revenue_prediction':
                        result = self.train_revenue_prediction_model(tenant_id)
                    elif model_type == 'fraud_detection':
                        result = self.train_fraud_detection_model(tenant_id)
                    
                    retraining_results['results'][model_type] = result
                    
                except Exception as e:
                    retraining_results['results'][model_type] = {'error': str(e)}
            
            # Calculate summary
            successful_retrains = sum(1 for result in retraining_results['results'].values() if 'error' not in result)
            failed_retrains = len(retraining_results['results']) - successful_retrains
            
            retraining_results['summary'] = {
                'status': 'completed',
                'successful_retrains': successful_retrains,
                'failed_retrains': failed_retrains,
                'total_models': len(retraining_results['results']),
                'end_time': timezone.now().isoformat(),
                'duration_minutes': int((timezone.now() - timezone.parse(retraining_results['start_time'])).total_seconds() / 60)
            }
            
            # Log retraining
            self._log_model_retraining(retraining_results)
            
            logger.info(f"ML models retraining completed for tenant {tenant_id}")
            
            return retraining_results
            
        except Exception as e:
            logger.error(f"Error retraining ML models for tenant {tenant_id}: {e}")
            return {'error': str(e)}
    
    def _initialize_models(self):
        """Initialize ML models."""
        try:
            # Import ML libraries
            from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
            from sklearn.linear_model import LogisticRegression, LinearRegression
            from sklearn.svm import SVC, SVR
            from sklearn.neural_network import MLPClassifier, MLPRegressor
            from sklearn.preprocessing import StandardScaler
            from sklearn.pipeline import Pipeline
            
            # Initialize models with default parameters
            self.models = {
                'conversion_prediction': Pipeline([
                    ('scaler', StandardScaler()),
                    ('classifier', RandomForestClassifier(
                        n_estimators=100,
                        max_depth=10,
                        random_state=42,
                        n_jobs=-1
                    ))
                ]),
                'revenue_prediction': Pipeline([
                    ('scaler', StandardScaler()),
                    ('regressor', RandomForestRegressor(
                        n_estimators=100,
                        max_depth=10,
                        random_state=42,
                        n_jobs=-1
                    ))
                ]),
                'fraud_detection': Pipeline([
                    ('scaler', StandardScaler()),
                    ('classifier', RandomForestClassifier(
                        n_estimators=100,
                        max_depth=15,
                        random_state=42,
                        n_jobs=-1,
                        class_weight='balanced'
                    ))
                ]),
                'user_segmentation': Pipeline([
                    ('scaler', StandardScaler()),
                    ('classifier', LogisticRegression(
                        random_state=42,
                        max_iter=1000
                    ))
                ]),
                'offer_ranking': Pipeline([
                    ('scaler', StandardScaler()),
                    ('regressor', MLPRegressor(
                        hidden_layer_sizes=(100, 50),
                        random_state=42,
                        max_iter=500
                    ))
                ]),
                'price_optimization': Pipeline([
                    ('scaler', StandardScaler()),
                    ('regressor', SVR(
                        kernel='rbf',
                        C=1.0,
                        gamma='scale'
                    ))
                ]),
                'churn_prediction': Pipeline([
                    ('scaler', StandardScaler()),
                    ('classifier', MLPClassifier(
                        hidden_layer_sizes=(100, 50),
                        random_state=42,
                        max_iter=500
                    ))
                ]),
                'quality_scoring': Pipeline([
                    ('scaler', StandardScaler()),
                    ('regressor', LinearRegression(
                        n_jobs=-1
                    ))
                ])
            }
            
            logger.info("ML models initialized successfully")
            
        except Exception as e:
            logger.error(f"Error initializing ML models: {e}")
    
    def _get_conversion_training_data(self, tenant_id: int, days: int) -> List[Dict]:
        """Get conversion training data."""
        try:
            cutoff_date = timezone.now() - timedelta(days=days)
            
            # Get user offer history with conversions
            training_data = UserOfferHistory.objects.filter(
                user__tenant_id=tenant_id,
                completed_at__gte=cutoff_date,
                completed_at__isnull=False
            ).select_related('user', 'offer').values(
                'user_id',
                'offer_id',
                'revenue',
                'completed_at',
                'ip_address',
                'user_agent',
                'user__profile__conversion_count',
                'user__profile__total_revenue',
                'user__date_joined',
                'offer__base_price',
                'offer__expected_revenue',
                'offer__conversion_rate',
                'offer__priority',
                'offer__categories__name'
            )
            
            return list(training_data)
            
        except Exception as e:
            logger.error(f"Error getting conversion training data: {e}")
            return []
    
    def _engineer_conversion_features(self, training_data: List[Dict]) -> Tuple[pd.DataFrame, pd.Series]:
        """Engineer features for conversion prediction."""
        try:
            df = pd.DataFrame(training_data)
            
            # Time-based features
            df['hour_of_day'] = pd.to_datetime(df['completed_at']).dt.hour
            df['day_of_week'] = pd.to_datetime(df['completed_at']).dt.dayofweek
            df['days_since_join'] = (pd.to_datetime(df['completed_at']) - pd.to_datetime(df['user__date_joined'])).dt.days
            
            # User features
            df['user_conversion_count'] = df['user__profile__conversion_count'].fillna(0)
            df['user_total_revenue'] = df['user__profile__total_revenue'].fillna(0)
            df['user_avg_revenue'] = df['user_total_revenue'] / (df['user_conversion_count'] + 1)
            
            # Offer features
            df['offer_base_price'] = df['offer__base_price'].fillna(1.0)
            df['offer_expected_revenue'] = df['offer__expected_revenue'].fillna(0)
            df['offer_conversion_rate'] = df['offer__conversion_rate'].fillna(0)
            df['offer_priority'] = df['offer__priority'].fillna(0)
            
            # Interaction features
            df['price_revenue_ratio'] = df['offer_base_price'] / (df['revenue'] + 0.01)
            df['revenue_vs_expected'] = df['revenue'] / (df['offer_expected_revenue'] + 0.01)
            
            # Target variable (conversion success)
            y = (df['revenue'] > 0).astype(int)
            
            # Select features
            feature_columns = [
                'hour_of_day', 'day_of_week', 'days_since_join',
                'user_conversion_count', 'user_total_revenue', 'user_avg_revenue',
                'offer_base_price', 'offer_expected_revenue', 'offer_conversion_rate', 'offer_priority',
                'price_revenue_ratio', 'revenue_vs_expected'
            ]
            
            X = df[feature_columns].fillna(0)
            
            return X, y
            
        except Exception as e:
            logger.error(f"Error engineering conversion features: {e}")
            return pd.DataFrame(), pd.Series()
    
    def _train_conversion_model(self, X: pd.DataFrame, y: pd.Series):
        """Train conversion prediction model."""
        try:
            # Get the conversion model from initialized models
            model = self.models['conversion_prediction']
            
            # Train the model
            model.fit(X, y)
            
            return model
            
        except Exception as e:
            logger.error(f"Error training conversion model: {e}")
            return None
    
    def _evaluate_conversion_model(self, model, X_test: pd.DataFrame, y_test: pd.Series) -> Dict[str, float]:
        """Evaluate conversion prediction model."""
        try:
            from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score
            
            # Make predictions
            y_pred = model.predict(X_test)
            y_pred_proba = model.predict_proba(X_test)[:, 1]
            
            # Calculate metrics
            evaluation = {
                'accuracy': accuracy_score(y_test, y_pred),
                'precision': precision_score(y_test, y_pred),
                'recall': recall_score(y_test, y_pred),
                'f1_score': f1_score(y_test, y_pred),
                'roc_auc': roc_auc_score(y_test, y_pred_proba)
            }
            
            return evaluation
            
        except Exception as e:
            logger.error(f"Error evaluating conversion model: {e}")
            return {}
    
    def _save_model(self, model_type: str, model, metadata: Dict, tenant_id: int):
        """Save trained model to storage."""
        try:
            import pickle
            import os
            
            # Create models directory if it doesn't exist
            models_dir = f'ml_models/tenant_{tenant_id}'
            os.makedirs(models_dir, exist_ok=True)
            
            # Save model
            model_path = f'{models_dir}/{model_type}_model.pkl'
            with open(model_path, 'wb') as f:
                pickle.dump(model, f)
            
            # Save metadata
            metadata_path = f'{models_dir}/{model_type}_metadata.json'
            import json
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f)
            
            # Update in-memory model
            self.models[model_type] = model
            
            logger.info(f"Model saved: {model_type} for tenant {tenant_id}")
            
        except Exception as e:
            logger.error(f"Error saving model {model_type}: {e}")
    
    def _log_model_training(self, training_results: Dict):
        """Log model training for analytics."""
        try:
            RoutingInsight.objects.create(
                tenant_id=training_results['tenant_id'],
                insight_type='ml_training',
                title=f'ML Training: {training_results["model_type"]}',
                description=f'Model training completed for {training_results["model_type"]}',
                data=training_results
            )
            
        except Exception as e:
            logger.error(f"Error logging model training: {e}")
    
    def _get_next_model_version(self, model_type: str) -> str:
        """Get next model version."""
        try:
            # This would implement version tracking
            # For now, use timestamp-based version
            return f"v{timezone.now().strftime('%Y%m%d_%H%M%S')}"
            
        except Exception as e:
            logger.error(f"Error getting next model version: {e}")
            return "v1.0"
    
    def _extract_conversion_features(self, user_id: int, offer_id: int, context: Dict) -> List[float]:
        """Extract features for conversion prediction."""
        try:
            features = []
            
            # Time features
            current_time = timezone.now()
            features.append(current_time.hour)
            features.append(current_time.weekday())
            
            # User features
            user = User.objects.filter(id=user_id).first()
            if user and hasattr(user, 'profile'):
                features.append(user.profile.conversion_count or 0)
                features.append(float(user.profile.total_revenue or 0))
                features.append((timezone.now() - user.date_joined).days)
            else:
                features.extend([0, 0, 0])
            
            # Offer features
            offer = OfferRoute.objects.filter(id=offer_id).first()
            if offer:
                features.append(float(offer.base_price or 1.0))
                features.append(float(offer.expected_revenue or 0))
                features.append(float(offer.conversion_rate or 0))
                features.append(float(offer.priority or 0))
            else:
                features.extend([1.0, 0, 0, 0])
            
            # Context features
            features.append(float(context.get('device_type_score', 0)))
            features.append(float(context.get('geo_score', 0)))
            features.append(float(context.get('session_duration', 0)))
            
            return features
            
        except Exception as e:
            logger.error(f"Error extracting conversion features: {e}")
            return [0] * 15  # Return default features
    
    def _calculate_prediction_confidence(self, model, features: List) -> float:
        """Calculate prediction confidence."""
        try:
            # Get prediction probabilities
            if hasattr(model, 'predict_proba'):
                probabilities = model.predict_proba(features)[0]
                confidence = max(probabilities)
            else:
                # For models without predict_proba, use default confidence
                confidence = 0.7
            
            return float(confidence)
            
        except Exception as e:
            logger.error(f"Error calculating prediction confidence: {e}")
            return 0.5
    
    def _assess_conversion_risk(self, probability: float, confidence: float) -> str:
        """Assess conversion risk."""
        try:
            if confidence < 0.5:
                return 'high_risk'
            elif probability < 0.3:
                return 'low_probability'
            elif probability > 0.8:
                return 'high_probability'
            else:
                return 'medium_risk'
                
        except Exception as e:
            logger.error(f"Error assessing conversion risk: {e}")
            return 'unknown'
    
    def _generate_conversion_recommendations(self, probability: float, confidence: float, similar_cases: List) -> List[str]:
        """Generate conversion recommendations."""
        try:
            recommendations = []
            
            if probability < 0.3:
                recommendations.append("Consider showing higher-conversion offers")
            elif probability > 0.8:
                recommendations.append("This user has high conversion potential")
            
            if confidence < 0.6:
                recommendations.append("Prediction confidence is low - gather more user data")
            
            if similar_cases:
                recommendations.append("Based on similar user behavior patterns")
            
            return recommendations[:5]  # Top 5 recommendations
            
        except Exception as e:
            logger.error(f"Error generating conversion recommendations: {e}")
            return []
    
    def _log_conversion_prediction(self, prediction_results: Dict):
        """Log conversion prediction for analytics."""
        try:
            # This would log to analytics system
            # For now, just log to file
            logger.info(f"Conversion prediction logged: {prediction_results['user_id']} - {prediction_results['conversion_probability']:.3f}")
            
        except Exception as e:
            logger.error(f"Error logging conversion prediction: {e}")


# Global ML integration service instance
ml_integration_service = MLIntegrationService()
