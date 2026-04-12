"""
Tests for ML Model Pipeline  (PRODUCTION-READY — COMPLETE)
============================================================
Tests for MLPredictor, RiskScoringModel, and UnsupervisedAnomalyDetector.
"""
import pytest
from unittest.mock import patch, MagicMock


class TestMLPredictor:
    """Tests for the MLPredictor class."""

    def test_rule_based_fallback_no_model(self):
        """When no model is available, rule-based fallback should work."""
        from ..ai_ml_engines.ml_predictor import MLPredictor
        predictor = MLPredictor('risk_scoring')
        predictor._model = None  # Force fallback

        features = {
            'is_vpn': 1, 'is_tor': 0, 'is_proxy': 0,
            'is_datacenter': 0, 'risk_score': 75,
        }
        result = predictor.predict(features)
        assert 'fraud_probability' in result
        assert 'predicted_fraud' in result
        assert result['model_used'] == 'rule_based_fallback'

    def test_tor_flag_triggers_fraud(self):
        """Tor flag should push probability above 0.5."""
        from ..ai_ml_engines.ml_predictor import MLPredictor
        predictor = MLPredictor('risk_scoring')
        predictor._model = None

        features = {
            'is_vpn': 0, 'is_tor': 1, 'is_proxy': 0,
            'is_datacenter': 0, 'risk_score': 90,
        }
        result = predictor.predict(features)
        assert result['fraud_probability'] > 0.5
        assert result['predicted_fraud'] is True

    def test_clean_ip_not_fraud(self):
        """Clean IP should produce probability < 0.5."""
        from ..ai_ml_engines.ml_predictor import MLPredictor
        predictor = MLPredictor('risk_scoring')
        predictor._model = None

        features = {
            'is_vpn': 0, 'is_tor': 0, 'is_proxy': 0,
            'is_datacenter': 0, 'risk_score': 5,
        }
        result = predictor.predict(features)
        assert result['fraud_probability'] < 0.5
        assert result['predicted_fraud'] is False

    def test_multiple_flags_increase_probability(self):
        """Multiple flags should result in higher fraud probability."""
        from ..ai_ml_engines.ml_predictor import MLPredictor
        predictor = MLPredictor('risk_scoring')
        predictor._model = None

        single_flag = predictor.predict({'is_vpn': 1, 'is_tor': 0, 'risk_score': 30})
        multi_flag  = predictor.predict({'is_vpn': 1, 'is_tor': 1, 'risk_score': 80})
        assert multi_flag['fraud_probability'] > single_flag['fraud_probability']

    def test_vpn_flag_increases_probability(self):
        """VPN flag should increase probability over clean baseline."""
        from ..ai_ml_engines.ml_predictor import MLPredictor
        predictor = MLPredictor('risk_scoring')
        predictor._model = None

        clean = predictor.predict({'is_vpn': 0, 'is_tor': 0, 'risk_score': 5})
        vpn   = predictor.predict({'is_vpn': 1, 'is_tor': 0, 'risk_score': 35})
        assert vpn['fraud_probability'] > clean['fraud_probability']


class TestRiskScoringModel:
    """Tests for the feature engineering pipeline."""

    def test_feature_vector_length(self):
        """Feature vector must have the correct number of features."""
        from ..ai_ml_engines.risk_scoring_model import RiskScoringModel, FEATURE_NAMES

        data   = {'is_vpn': True, 'is_proxy': False, 'risk_score': 50}
        vector = RiskScoringModel.build_feature_vector(data)
        assert len(vector) == len(FEATURE_NAMES)

    def test_all_values_normalised(self):
        """All feature values must be in [0.0, 1.0]."""
        from ..ai_ml_engines.risk_scoring_model import RiskScoringModel

        data = {
            'is_vpn': True, 'is_proxy': True, 'is_tor': False,
            'is_datacenter': True, 'abuse_confidence_score': 100,
            'fraud_score': 80, 'risk_score': 100,
        }
        vector = RiskScoringModel.build_feature_vector(data)
        for v in vector:
            assert 0.0 <= v <= 1.0, f"Feature value {v} out of range [0.0, 1.0]"

    def test_tor_highest_contribution(self):
        """Tor should have higher weight than VPN alone."""
        from ..ai_ml_engines.risk_scoring_model import RiskScoringModel

        only_vpn = RiskScoringModel.predict({'is_vpn': 1, 'is_tor': 0, 'risk_score': 30})
        only_tor = RiskScoringModel.predict({'is_vpn': 0, 'is_tor': 1, 'risk_score': 45})
        assert only_tor['fraud_probability'] > only_vpn['fraud_probability']

    def test_feature_dict_has_all_names(self):
        """feature_dict should contain all FEATURE_NAMES as keys."""
        from ..ai_ml_engines.risk_scoring_model import RiskScoringModel, FEATURE_NAMES

        data   = {'is_vpn': True, 'risk_score': 50}
        fd     = RiskScoringModel.build_feature_dict(data)
        for name in FEATURE_NAMES:
            assert name in fd, f"Feature '{name}' missing from feature dict"

    def test_empty_data_returns_valid_vector(self):
        """Empty input should return a valid zero vector."""
        from ..ai_ml_engines.risk_scoring_model import RiskScoringModel, FEATURE_NAMES

        vector = RiskScoringModel.build_feature_vector({})
        assert len(vector) == len(FEATURE_NAMES)
        assert all(v == 0 for v in vector)

    def test_rule_based_score_zero_for_clean(self):
        """Rule-based score for a clean IP should be 0."""
        from ..ai_ml_engines.risk_scoring_model import RiskScoringModel

        result = RiskScoringModel._rule_based_score({}, [])
        assert result['fraud_probability'] == 0.0
        assert result['predicted_fraud'] is False

    def test_rule_based_score_caps_at_one(self):
        """Rule-based score should never exceed 1.0."""
        from ..ai_ml_engines.risk_scoring_model import RiskScoringModel

        data = {
            'is_tor': 1, 'is_vpn': 1, 'is_proxy': 1,
            'blacklisted': 1, 'multi_account_detected': 1,
            'device_spoofing': 1, 'velocity_exceeded': 1,
            'abuse_confidence_score': 100, 'fraud_score': 100,
            'risk_score': 100,
        }
        result = RiskScoringModel.predict(data)
        assert result['fraud_probability'] <= 1.0


class TestUnsupervisedAnomalyDetector:
    """Tests for the unsupervised anomaly detection model."""

    def test_unfitted_predict_returns_normal(self):
        """Unfitted model should return 'normal' for all inputs."""
        from ..ai_ml_engines.unsupervised_learning import UnsupervisedAnomalyDetector
        detector = UnsupervisedAnomalyDetector()
        result   = detector.predict([[0, 1, 0, 0, 0, 0, 0]])
        assert result == [1]  # 1 = normal

    def test_unfitted_predict_one_returns_not_anomaly(self):
        """Unfitted predict_one should return is_anomaly=False."""
        from ..ai_ml_engines.unsupervised_learning import UnsupervisedAnomalyDetector
        detector = UnsupervisedAnomalyDetector()
        result   = detector.predict_one([0, 1, 0, 0, 0.5, 0])
        assert result['is_anomaly'] is False
        assert result['model_ready'] is False

    def test_is_ready_false_before_fit(self):
        """is_ready should be False before fitting."""
        from ..ai_ml_engines.unsupervised_learning import UnsupervisedAnomalyDetector
        detector = UnsupervisedAnomalyDetector()
        assert detector.is_ready is False

    def test_insufficient_data_returns_error(self):
        """Less than 10 samples should return an error."""
        from ..ai_ml_engines.unsupervised_learning import UnsupervisedAnomalyDetector
        try:
            from sklearn.ensemble import IsolationForest
        except ImportError:
            pytest.skip('scikit-learn not installed')

        detector = UnsupervisedAnomalyDetector()
        result   = detector.fit([[0, 1, 0]] * 5)  # Only 5 samples
        assert 'error' in result

    def test_fit_with_sufficient_data(self):
        """Should successfully train with ≥10 samples."""
        try:
            from sklearn.ensemble import IsolationForest
        except ImportError:
            pytest.skip('scikit-learn not installed')

        from ..ai_ml_engines.unsupervised_learning import UnsupervisedAnomalyDetector
        X = [[float(i % 2), float((i+1) % 3), 0.5] for i in range(20)]
        detector = UnsupervisedAnomalyDetector(contamination=0.1)
        result   = detector.fit(X)

        assert 'error' not in result
        assert result['status'] == 'trained'
        assert result['training_samples'] == 20
        assert detector.is_ready is True

    def test_supported_algorithms(self):
        """Test that all supported algorithm names are accepted."""
        from ..ai_ml_engines.unsupervised_learning import UnsupervisedAnomalyDetector
        for algo in UnsupervisedAnomalyDetector.SUPPORTED_ALGORITHMS:
            det = UnsupervisedAnomalyDetector(algorithm=algo)
            assert det.algorithm == algo

    def test_unsupported_algorithm_raises(self):
        """Unsupported algorithm name should raise ValueError."""
        from ..ai_ml_engines.unsupervised_learning import UnsupervisedAnomalyDetector
        with pytest.raises(ValueError):
            UnsupervisedAnomalyDetector(algorithm='fake_algorithm_xyz')
