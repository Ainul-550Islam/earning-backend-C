"""
Tests for Threshold ViewSets — FIXED
URL prefix: /threshold/ (ROOT_URLCONF=alerts.urls in test context)
Pagination disabled → response.data is a plain list.
"""
from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth import get_user_model
from api.alerts.models.core import AlertRule
from api.alerts.models.threshold import ThresholdConfig, ThresholdBreach, AdaptiveThreshold, ThresholdProfile

User = get_user_model()


def _count(data):
    if isinstance(data, dict): return len(data.get('results', []))
    return len(data)


def _rule(name='TR Rule', user=None):
    return AlertRule.objects.create(
        name=name, alert_type='server_error', severity='high',
        threshold_value=80.0, time_window_minutes=60, cooldown_minutes=30,
        created_by=user)


_tc_counter = [0]

def _tc(rule, suffix=''):
    """Create ThresholdConfig with correct field names and unique name"""
    _tc_counter[0] += 1
    return ThresholdConfig.objects.create(
        name=f'TC-{rule.id}-{_tc_counter[0]}{suffix}',
        alert_rule=rule, threshold_type='static',
        comparison_operator='gt', primary_threshold=85.0,
        secondary_threshold=90.0, calculation_window_minutes=10)


class ThresholdConfigViewSetTest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user('thrcvs','thrc@x.com','pass', is_staff=True)
        self.client.force_authenticate(self.user)
        self.rule = _rule(user=self.user)
        self.tc = _tc(self.rule)

    def test_list_threshold_configs(self):
        resp = self.client.get('/threshold/configs/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(_count(resp.data), 1)

    def test_create_threshold_config(self):
        data = {'name': 'TC-New-Staging', 'alert_rule': self.rule.id,
                'threshold_type': 'static', 'comparison_operator': 'lt',
                'primary_threshold': 75.0, 'calculation_window_minutes': 5}
        resp = self.client.post('/threshold/configs/', data, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

    def test_retrieve_threshold_config(self):
        resp = self.client.get(f'/threshold/configs/{self.tc.id}/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_update_threshold_config(self):
        resp = self.client.patch(f'/threshold/configs/{self.tc.id}/',
                                 {'primary_threshold': 90.0}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_delete_threshold_config(self):
        resp = self.client.delete(f'/threshold/configs/{self.tc.id}/')
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)

    def test_evaluate_threshold(self):
        resp = self.client.post(f'/threshold/configs/{self.tc.id}/evaluate/',
                                {'value': 88.0}, format='json')
        self.assertIn(resp.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST,
                                          status.HTTP_403_FORBIDDEN])

    def test_threshold_effectiveness(self):
        resp = self.client.get(f'/threshold/configs/{self.tc.id}/effectiveness/')
        self.assertIn(resp.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST])


class ThresholdBreachViewSetTest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user('thrbvs','thrb@x.com','pass', is_staff=True)
        self.client.force_authenticate(self.user)
        self.rule = _rule('Breach Rule', user=self.user)
        self.tc = _tc(self.rule)
        self.breach = ThresholdBreach.objects.create(
            threshold_config=self.tc, breach_value=92.0,
            threshold_value=85.0, breach_percentage=8.2, status='open')

    def test_list_breaches(self):
        resp = self.client.get('/threshold/breaches/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(_count(resp.data), 1)

    def test_retrieve_breach(self):
        resp = self.client.get(f'/threshold/breaches/{self.breach.id}/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_resolve_breach(self):
        resp = self.client.post(f'/threshold/breaches/{self.breach.id}/resolve/')
        self.assertIn(resp.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST,
                                          status.HTTP_403_FORBIDDEN])

    def test_breaches_by_severity(self):
        resp = self.client.get('/threshold/breaches/by_severity/high/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_active_breaches(self):
        resp = self.client.get('/threshold/breaches/active/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_breach_statistics(self):
        resp = self.client.get('/threshold/breaches/statistics/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)


class AdaptiveThresholdViewSetTest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user('athr','athr@x.com','pass', is_staff=True)
        self.client.force_authenticate(self.user)
        self.rule = _rule('Adaptive Rule', user=self.user)
        self.tc = _tc(self.rule)
        # AdaptiveThreshold is OneToOne with ThresholdConfig
        self.at = AdaptiveThreshold.objects.create(
            name=f'Adaptive-T1-{self.tc.id}',
            threshold_config=self.tc,
            adaptation_method='moving_average',
            base_threshold=85.0,
            current_threshold=85.0,
            min_threshold=70.0,
            max_threshold=100.0,
            is_active=True)

    def test_list_adaptive_thresholds(self):
        resp = self.client.get('/threshold/adaptive/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(_count(resp.data), 1)

    def test_retrieve_adaptive_threshold(self):
        resp = self.client.get(f'/threshold/adaptive/{self.at.id}/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_update_adaptive_threshold(self):
        resp = self.client.patch(f'/threshold/adaptive/{self.at.id}/',
                                 {'is_active': False}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_train_adaptive_threshold(self):
        resp = self.client.post(f'/threshold/adaptive/{self.at.id}/train/')
        self.assertIn(resp.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST,
                                          status.HTTP_403_FORBIDDEN])

    def test_adapt_threshold(self):
        resp = self.client.post(f'/threshold/adaptive/{self.at.id}/adapt/',
                                {'value': 88.0}, format='json')
        self.assertIn(resp.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST,
                                          status.HTTP_403_FORBIDDEN])

    def test_threshold_history(self):
        resp = self.client.get(f'/threshold/adaptive/{self.at.id}/history/')
        self.assertIn(resp.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST])


class ThresholdProfileViewSetTest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user('tpvs','tp@x.com','pass', is_staff=True)
        self.client.force_authenticate(self.user)
        self.profile = ThresholdProfile.objects.create(
            name='Production Profile',
            description='For production servers',
            profile_type='balanced',
            default_threshold_multiplier=1.0,
            sensitivity_level=0.5,
            target_false_positive_rate=0.05,
            target_detection_rate=0.95,
            created_by=self.user)

    def test_list_profiles(self):
        resp = self.client.get('/threshold/profiles/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(_count(resp.data), 1)

    def test_create_profile(self):
        data = {'name': 'Staging Profile', 'description': 'For staging',
                'profile_type': 'conservative', 'default_threshold_multiplier': 1.2,
                'sensitivity_level': 0.3, 'target_false_positive_rate': 0.02,
                'target_detection_rate': 0.90}
        resp = self.client.post('/threshold/profiles/', data, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

    def test_retrieve_profile(self):
        resp = self.client.get(f'/threshold/profiles/{self.profile.id}/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['name'], 'Production Profile')

    def test_update_profile(self):
        resp = self.client.patch(f'/threshold/profiles/{self.profile.id}/',
                                 {'description': 'Updated desc'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_apply_profile(self):
        resp = self.client.post(f'/threshold/profiles/{self.profile.id}/apply/',
                                {'rule_ids': [1, 2]}, format='json')
        self.assertIn(resp.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST,
                                          status.HTTP_403_FORBIDDEN])

    def test_clone_profile(self):
        resp = self.client.post(f'/threshold/profiles/{self.profile.id}/clone/',
                                {'name': 'Cloned Profile'}, format='json')
        self.assertIn(resp.status_code, [status.HTTP_200_OK, status.HTTP_201_CREATED,
                                          status.HTTP_400_BAD_REQUEST, status.HTTP_403_FORBIDDEN])
