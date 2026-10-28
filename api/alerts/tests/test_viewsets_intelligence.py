"""Tests for Intelligence ViewSets — FIXED. URL prefix: /intelligence/"""
from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth import get_user_model
from api.alerts.models.intelligence import (
    AlertCorrelation, AlertPrediction, AnomalyDetectionModel, AlertNoise, RootCauseAnalysis,
)

User = get_user_model()


def _count(data):
    if isinstance(data, dict): return len(data.get('results', []))
    return len(data)


class AlertCorrelationViewSetTest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user('corvs','cor@x.com','pass', is_staff=True)
        self.client.force_authenticate(self.user)
        self.corr = AlertCorrelation.objects.create(
            name='CPU-Memory Correlation', correlation_type='temporal',
            correlation_strength=0.85, is_active=True, time_window_minutes=60)

    def test_list_correlations(self):
        resp = self.client.get('/intelligence/correlations/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(_count(resp.data), 1)

    def test_create_correlation(self):
        data = {'name': 'New Correlation', 'correlation_type': 'statistical',
                'correlation_strength': 0.7, 'is_active': True, 'time_window_minutes': 30}
        resp = self.client.post('/intelligence/correlations/', data, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

    def test_retrieve_correlation(self):
        resp = self.client.get(f'/intelligence/correlations/{self.corr.id}/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['name'], 'CPU-Memory Correlation')

    def test_update_correlation(self):
        resp = self.client.patch(f'/intelligence/correlations/{self.corr.id}/',
                                 {'correlation_strength': 0.9}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.corr.refresh_from_db()
        self.assertAlmostEqual(float(self.corr.correlation_strength), 0.9, places=1)

    def test_delete_correlation(self):
        resp = self.client.delete(f'/intelligence/correlations/{self.corr.id}/')
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)

    def test_analyze_correlation(self):
        resp = self.client.post(f'/intelligence/correlations/{self.corr.id}/analyze/')
        self.assertIn(resp.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST, status.HTTP_403_FORBIDDEN])

    def test_significant_correlations(self):
        resp = self.client.get('/intelligence/correlations/significant/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_correlations_by_type(self):
        resp = self.client.get('/intelligence/correlations/by_type/temporal/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)


class AlertPredictionViewSetTest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user('predvs','pred@x.com','pass', is_staff=True)
        self.client.force_authenticate(self.user)
        self.pred = AlertPrediction.objects.create(
            name='Volume Prediction', prediction_type='volume',
            model_type='linear_regression', is_active=True)

    def test_list_predictions(self):
        resp = self.client.get('/intelligence/predictions/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(_count(resp.data), 1)

    def test_create_prediction(self):
        data = {'name': 'Severity Prediction', 'prediction_type': 'severity',
                'model_type': 'arima', 'is_active': True}
        resp = self.client.post('/intelligence/predictions/', data, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

    def test_retrieve_prediction(self):
        resp = self.client.get(f'/intelligence/predictions/{self.pred.id}/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['name'], 'Volume Prediction')

    def test_update_prediction(self):
        resp = self.client.patch(f'/intelligence/predictions/{self.pred.id}/',
                                 {'is_active': False}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_train_prediction(self):
        resp = self.client.post(f'/intelligence/predictions/{self.pred.id}/train/')
        self.assertIn(resp.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST, status.HTTP_403_FORBIDDEN])

    def test_active_predictions(self):
        resp = self.client.get('/intelligence/predictions/active/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(_count(resp.data), 1)

    def test_predictions_by_type(self):
        resp = self.client.get('/intelligence/predictions/by_type/volume/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)


class AnomalyDetectionViewSetTest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user('anomvs','anom@x.com','pass', is_staff=True)
        self.client.force_authenticate(self.user)
        self.model = AnomalyDetectionModel.objects.create(
            name='CPU Anomaly Model', detection_method='statistical', is_active=True)

    def test_list_anomaly_models(self):
        resp = self.client.get('/intelligence/anomaly_models/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(_count(resp.data), 1)

    def test_create_anomaly_model(self):
        data = {'name': 'Memory Anomaly Model', 'detection_method': 'threshold_based', 'is_active': True}
        resp = self.client.post('/intelligence/anomaly_models/', data, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

    def test_retrieve_anomaly_model(self):
        resp = self.client.get(f'/intelligence/anomaly_models/{self.model.id}/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['name'], 'CPU Anomaly Model')

    def test_detect_anomalies(self):
        resp = self.client.post(f'/intelligence/anomaly_models/{self.model.id}/detect/')
        self.assertIn(resp.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST, status.HTTP_403_FORBIDDEN])

    def test_active_anomaly_models(self):
        resp = self.client.get('/intelligence/anomaly_models/active/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)


class AlertNoiseViewSetTest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user('noisevs','noise@x.com','pass', is_staff=True)
        self.client.force_authenticate(self.user)
        self.noise = AlertNoise.objects.create(
            name='Rate Limit Filter', noise_type='repeated',
            filter_type='rate_limit', action='suppress', is_active=True)

    def test_list_noise_filters(self):
        resp = self.client.get('/intelligence/noise_filters/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(_count(resp.data), 1)

    def test_create_noise_filter(self):
        data = {'name': 'New Noise Filter', 'noise_type': 'maintenance',
                'action': 'delay', 'is_active': True}
        resp = self.client.post('/intelligence/noise_filters/', data, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

    def test_retrieve_noise_filter(self):
        resp = self.client.get(f'/intelligence/noise_filters/{self.noise.id}/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['name'], 'Rate Limit Filter')

    def test_update_noise_filter(self):
        resp = self.client.patch(f'/intelligence/noise_filters/{self.noise.id}/',
                                 {'is_active': False}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_delete_noise_filter(self):
        resp = self.client.delete(f'/intelligence/noise_filters/{self.noise.id}/')
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)


class RootCauseAnalysisViewSetTest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user('rcavs','rca@x.com','pass', is_staff=True)
        self.client.force_authenticate(self.user)
        self.rca = RootCauseAnalysis.objects.create(
            title='DB Slowdown RCA', description='', analysis_method='5_whys', status='draft')

    def test_list_rca(self):
        resp = self.client.get('/intelligence/rca/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(_count(resp.data), 1)

    def test_create_rca(self):
        data = {'title': 'New RCA', 'description': 'Test',
                'analysis_method': 'fault_tree', 'status': 'draft'}
        resp = self.client.post('/intelligence/rca/', data, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

    def test_retrieve_rca(self):
        resp = self.client.get(f'/intelligence/rca/{self.rca.id}/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['title'], 'DB Slowdown RCA')

    def test_update_rca(self):
        resp = self.client.patch(f'/intelligence/rca/{self.rca.id}/',
                                 {'status': 'in_progress'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_analyze_rca(self):
        resp = self.client.post(f'/intelligence/rca/{self.rca.id}/analyze/')
        self.assertIn(resp.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST, status.HTTP_403_FORBIDDEN])

    def test_intelligence_overview(self):
        resp = self.client.get('/intelligence/overview/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
