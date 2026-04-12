"""
api/ai_engine/exceptions.py
============================
AI Engine — Custom Exceptions।
"""

from rest_framework.exceptions import APIException
from rest_framework import status


class ModelNotFoundError(APIException):
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = 'AI Model পাওয়া যায়নি।'
    default_code = 'model_not_found'


class ModelNotDeployedError(APIException):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = 'AI Model এখনো deployed নয়।'
    default_code = 'model_not_deployed'


class TrainingInProgressError(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = 'Model training চলছে, পরে আবার চেষ্টা করুন।'
    default_code = 'training_in_progress'


class InsufficientDataError(APIException):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_detail = 'Prediction এর জন্য পর্যাপ্ত ডেটা নেই।'
    default_code = 'insufficient_data'


class FeatureExtractionError(APIException):
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_detail = 'Feature extraction ব্যর্থ হয়েছে।'
    default_code = 'feature_extraction_failed'


class PredictionError(APIException):
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_detail = 'Prediction করা সম্ভব হয়নি।'
    default_code = 'prediction_failed'


class ModelVersionError(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'Invalid model version।'
    default_code = 'invalid_model_version'


class EmbeddingError(APIException):
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_detail = 'Embedding generation ব্যর্থ হয়েছে।'
    default_code = 'embedding_failed'


class RecommendationError(APIException):
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_detail = 'Recommendation generate করা সম্ভব হয়নি।'
    default_code = 'recommendation_failed'


class AnomalyDetectionError(APIException):
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_detail = 'Anomaly detection ব্যর্থ হয়েছে।'
    default_code = 'anomaly_detection_failed'


class NLPProcessingError(APIException):
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_detail = 'NLP processing ব্যর্থ হয়েছে।'
    default_code = 'nlp_failed'


class CVProcessingError(APIException):
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_detail = 'Image processing ব্যর্থ হয়েছে।'
    default_code = 'cv_failed'


class ABTestError(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'A/B Test সংক্রান্ত ত্রুটি।'
    default_code = 'ab_test_error'


class DataDriftError(APIException):
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_detail = 'Data drift detection ব্যর্থ হয়েছে।'
    default_code = 'drift_detection_failed'


class StorageError(APIException):
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_detail = 'Model storage সংক্রান্ত ত্রুটি।'
    default_code = 'storage_error'
