"""api/tasks/tests/test_tasks.py — Celery task unit tests."""
import pytest
from decimal import Decimal
from unittest.mock import patch, MagicMock
from django.utils import timezone


@pytest.mark.django_db
class TestOfferTasks:
    def test_offer_quality_score_runs(self, db):
        from api.tasks.offer_tasks import offer_quality_score
        result = offer_quality_score.apply().get()
        assert result['status'] == 'success'
        assert 'scored' in result

    def test_refresh_offer_feed_returns_dict(self, db):
        from api.tasks.offer_tasks import refresh_offer_feed
        result = refresh_offer_feed.apply(kwargs={'country': 'US', 'device': 'desktop'}).get()
        assert result['status'] == 'success'
        assert 'offers_in_feed' in result


@pytest.mark.django_db
class TestGamificationTasks:
    def test_award_xp_points(self, db, user):
        from api.tasks.gamification_tasks import award_xp_points
        result = award_xp_points.apply(kwargs={
            'user_id': user.pk, 'xp': 50, 'reason': 'test'
        }).get()
        assert result['status'] == 'success'
        assert result['xp_awarded'] == 50

    def test_update_global_leaderboard(self, db):
        from api.tasks.gamification_tasks import update_global_leaderboard
        result = update_global_leaderboard.apply(
            kwargs={'periods': ['daily']}
        ).get()
        assert result['status'] == 'success'

    def test_update_streak_status_no_completion(self, db, user):
        from api.tasks.gamification_tasks import update_streak_status
        result = update_streak_status.apply(kwargs={'user_id': user.pk}).get()
        # Should skip since no completions today
        assert result['status'] in ('no_completion_today', 'success', 'already_counted')


@pytest.mark.django_db
class TestCommunityTasks:
    def test_award_community_points(self, db, user):
        from api.tasks.community_tasks import award_community_points
        result = award_community_points.apply(kwargs={
            'user_id':    user.pk,
            'amount_usd': '1.00',
            'source':     'test',
        }).get()
        assert result['status'] in ('success', 'skipped')

    def test_update_community_leaderboard(self, db):
        from api.tasks.community_tasks import update_community_leaderboard
        result = update_community_leaderboard.apply().get()
        assert result['status'] == 'success'
        assert 'entries' in result


@pytest.mark.django_db
class TestComplianceTasks:
    def test_check_data_retention(self, db):
        from api.tasks.compliance_tasks import check_data_retention_policies
        result = check_data_retention_policies.apply().get()
        assert result['status'] == 'success'
        assert 'deleted' in result


@pytest.mark.django_db
class TestAnalyticsTasks:
    def test_compute_platform_kpis(self, db):
        from api.tasks.analytics_tasks import compute_platform_kpis
        result = compute_platform_kpis.apply().get()
        assert result['status'] == 'success'

    def test_refresh_analytics_cache(self, db):
        from api.tasks.analytics_tasks import refresh_analytics_cache
        result = refresh_analytics_cache.apply().get()
        assert result['status'] == 'success'


@pytest.mark.django_db
class TestIPManagementTasks:
    def test_sync_ip_blacklist(self, db):
        from api.tasks.ip_management_tasks import sync_ip_blacklist
        result = sync_ip_blacklist.apply().get()
        assert result['status'] == 'success'
        assert 'synced' in result

    def test_update_geo_routing(self, db):
        from api.tasks.ip_management_tasks import update_geo_routing_table
        result = update_geo_routing_table.apply().get()
        assert result['status'] == 'success'


@pytest.mark.django_db
class TestCAPTasks:
    def test_check_all_offer_caps(self, db):
        from api.tasks.tasks_cap import check_all_offer_caps
        result = check_all_offer_caps.apply().get()
        assert result['status'] == 'success'
        assert 'capped' in result

    def test_reset_daily_caps(self, db):
        from api.tasks.tasks_cap import reset_daily_caps
        result = reset_daily_caps.apply().get()
        assert result['status'] == 'success'


@pytest.mark.django_db
class TestDataPipelineTasks:
    def test_sync_offer_data_bridge(self, db):
        from api.tasks.data_pipeline_tasks import sync_offer_data_bridge
        result = sync_offer_data_bridge.apply().get()
        assert result['status'] == 'success'

    def test_warm_all_caches(self, db):
        from api.tasks.data_pipeline_tasks import warm_all_caches
        result = warm_all_caches.apply().get()
        assert result['status'] == 'success'
        assert 'warmed' in result


@pytest.mark.django_db
class TestRTBTasks:
    def test_refresh_bid_cache(self, db):
        from api.tasks.rtb_tasks import refresh_bid_cache
        result = refresh_bid_cache.apply().get()
        assert result['status'] == 'success'

    def test_update_bid_floor_prices(self, db):
        from api.tasks.rtb_tasks import update_bid_floor_prices
        result = update_bid_floor_prices.apply().get()
        assert result['status'] == 'success'


@pytest.mark.django_db
class TestClickTrackingTasks:
    def test_process_click_event(self, db, user):
        from api.tasks.click_tracking_tasks import process_click_event
        result = process_click_event.apply(kwargs={
            'user_id':    user.pk,
            'offer_id':   'OFFER_001',
            'ip_address': '1.2.3.4',
            'user_agent': 'TestAgent/1.0',
            'country':    'US',
            'device':     'desktop',
        }).get()
        assert result['status'] in ('success', 'duplicate', 'blocked')
        if result['status'] == 'success':
            assert 'click_id' in result

    def test_cleanup_old_clicks(self, db):
        from api.tasks.click_tracking_tasks import cleanup_old_clicks
        result = cleanup_old_clicks.apply(kwargs={'days_to_keep': 90}).get()
        assert result['status'] == 'success'
        assert 'deleted' in result
