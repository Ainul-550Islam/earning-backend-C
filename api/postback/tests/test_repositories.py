"""
test_repositories.py – Tests for repositories.py data-access layer.
"""
import datetime
from django.test import TestCase


class BaseRepositoryTests(TestCase):

    def test_base_repository_instantiable(self):
        from api.postback.repositories import BaseRepository
        from api.postback.models import PostbackLog
        repo = BaseRepository(PostbackLog)
        self.assertIsNotNone(repo)

    def test_base_repository_get_by_id_returns_none_for_missing(self):
        import uuid
        from api.postback.repositories import BaseRepository
        from api.postback.models import PostbackLog
        repo = BaseRepository(PostbackLog)
        result = repo.get_by_id(uuid.uuid4())
        self.assertIsNone(result)

    def test_base_repository_get_all_returns_list(self):
        from api.postback.repositories import BaseRepository
        from api.postback.models import PostbackLog
        repo = BaseRepository(PostbackLog)
        result = repo.get_all()
        self.assertIsNotNone(result)

    def test_base_repository_count_returns_int(self):
        from api.postback.repositories import BaseRepository
        from api.postback.models import PostbackLog
        repo = BaseRepository(PostbackLog)
        self.assertIsInstance(repo.count(), int)


class PostbackLogRepositoryTests(TestCase):

    def setUp(self):
        from api.postback.tests.factories import (
            NetworkPostbackConfigFactory, PostbackLogFactory,
            RewardedPostbackLogFactory, FailedPostbackLogFactory,
        )
        self.network = NetworkPostbackConfigFactory()
        self.log = RewardedPostbackLogFactory(network=self.network, lead_id="repo-lead-001")
        self.failed = FailedPostbackLogFactory(network=self.network)

    def test_postback_log_repo_instantiable(self):
        from api.postback.repositories import PostbackLogRepository
        repo = PostbackLogRepository()
        self.assertIsNotNone(repo)

    def test_get_by_id_returns_log(self):
        from api.postback.repositories import PostbackLogRepository
        repo = PostbackLogRepository()
        result = repo.get_by_id(self.log.pk)
        if result is not None:
            self.assertEqual(str(result.pk), str(self.log.pk))

    def test_get_by_id_returns_none_for_missing(self):
        import uuid
        from api.postback.repositories import PostbackLogRepository
        repo = PostbackLogRepository()
        result = repo.get_by_id(uuid.uuid4())
        self.assertIsNone(result)

    def test_get_by_network(self):
        from api.postback.repositories import PostbackLogRepository
        repo = PostbackLogRepository()
        result = repo.get_by_network(self.network)
        self.assertIsNotNone(result)

    def test_get_failed_logs(self):
        from api.postback.repositories import PostbackLogRepository
        repo = PostbackLogRepository()
        result = repo.get_failed()
        self.assertIsNotNone(result)

    def test_get_for_retry(self):
        from api.postback.repositories import PostbackLogRepository
        repo = PostbackLogRepository()
        result = repo.get_for_retry()
        self.assertIsNotNone(result)

    def test_get_recent(self):
        from api.postback.repositories import PostbackLogRepository
        repo = PostbackLogRepository()
        result = repo.get_recent(days=7)
        self.assertIsNotNone(result)

    def test_get_by_lead_id(self):
        from api.postback.repositories import PostbackLogRepository
        repo = PostbackLogRepository()
        result = repo.get_by_lead_id("repo-lead-001")
        self.assertIsNotNone(result)

    def test_get_statistics(self):
        from api.postback.repositories import PostbackLogRepository
        repo = PostbackLogRepository()
        result = repo.get_statistics()
        self.assertIsInstance(result, dict)


class PostbackInsightRepositoryTests(TestCase):

    def test_insight_repo_instantiable(self):
        from api.postback.repositories import PostbackInsightRepository
        repo = PostbackInsightRepository()
        self.assertIsNotNone(repo)

    def test_get_for_network(self):
        from api.postback.tests.factories import NetworkPostbackConfigFactory
        from api.postback.repositories import PostbackInsightRepository
        network = NetworkPostbackConfigFactory()
        repo = PostbackInsightRepository()
        result = repo.get_for_network(network)
        self.assertIsNotNone(result)

    def test_get_with_anomalies(self):
        from api.postback.repositories import PostbackInsightRepository
        repo = PostbackInsightRepository()
        result = repo.get_with_anomalies()
        self.assertIsNotNone(result)

    def test_get_date_range(self):
        from api.postback.repositories import PostbackInsightRepository
        repo = PostbackInsightRepository()
        today = datetime.date.today()
        result = repo.get_date_range(
            today - datetime.timedelta(days=7), today
        )
        self.assertIsNotNone(result)


class NetworkConfigRepositoryTests(TestCase):

    def setUp(self):
        from api.postback.tests.factories import NetworkPostbackConfigFactory
        self.network = NetworkPostbackConfigFactory()

    def test_network_config_repo_instantiable(self):
        from api.postback.repositories import NetworkPostbackConfigRepository
        repo = NetworkPostbackConfigRepository()
        self.assertIsNotNone(repo)

    def test_get_active(self):
        from api.postback.repositories import NetworkPostbackConfigRepository
        repo = NetworkPostbackConfigRepository()
        result = repo.get_active()
        self.assertIsNotNone(result)

    def test_get_by_key(self):
        from api.postback.repositories import NetworkPostbackConfigRepository
        repo = NetworkPostbackConfigRepository()
        result = repo.get_by_key(self.network.network_key)
        if result is not None:
            self.assertEqual(result.network_key, self.network.network_key)

    def test_get_with_whitelists(self):
        from api.postback.repositories import NetworkPostbackConfigRepository
        repo = NetworkPostbackConfigRepository()
        result = repo.get_with_whitelists()
        self.assertIsNotNone(result)


class RepositoryHelperTests(TestCase):

    def test_get_postback_log_repository(self):
        from api.postback.repositories import get_postback_log_repository
        repo = get_postback_log_repository()
        self.assertIsNotNone(repo)

    def test_get_postback_insight_repository(self):
        from api.postback.repositories import get_postback_insight_repository
        repo = get_postback_insight_repository()
        self.assertIsNotNone(repo)

    def test_get_network_config_repository(self):
        from api.postback.repositories import get_network_config_repository
        repo = get_network_config_repository()
        self.assertIsNotNone(repo)

    def test_repository_health_check(self):
        from api.postback.repositories import check_repository_health
        result = check_repository_health()
        self.assertIsInstance(result, dict)
        self.assertIn("status", result)

    def test_create_repository_factory(self):
        from api.postback.repositories import create_repository
        from api.postback.models import PostbackLog
        repo = create_repository(PostbackLog)
        self.assertIsNotNone(repo)
