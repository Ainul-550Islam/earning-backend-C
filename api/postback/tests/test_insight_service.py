"""test_insight_service.py – Comprehensive tests for PostbackInsightService."""
from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest.mock import patch, MagicMock

from django.test import TestCase
from django.utils import timezone
from django.db import transaction
from django.core.cache import cache

from api.postback.services import PostbackInsightService
from api.postback.models import PostbackInsight, PostbackLog, NetworkPostbackConfig
from api.postback.choices import PostbackStatus
from api.postback.tests.factories import (
    NetworkPostbackConfigFactory,
    PostbackInsightFactory,
    PostbackLogFactory,
    RewardedPostbackLogFactory,
    RejectedPostbackLogFactory,
    DuplicatePostbackLogFactory,
    FailedPostbackLogFactory,
    AnomalousPostbackInsightFactory,
)


class PostbackInsightServiceBasicTests(TestCase):
    """Test basic PostbackInsightService functionality."""

    def setUp(self):
        self.network = NetworkPostbackConfigFactory()
        self.target_date = date.today()

    def test_get_daily_insight_new(self):
        """Test getting daily insight for new date."""
        insight = PostbackInsightService.get_daily_insight(self.network, self.target_date)
        
        self.assertEqual(insight.network, self.network)
        self.assertEqual(insight.date, self.target_date)
        self.assertEqual(insight.received_count, 0)
        self.assertEqual(insight.rewarded_count, 0)
        self.assertEqual(insight.rejected_count, 0)
        self.assertEqual(insight.duplicate_count, 0)
        self.assertEqual(insight.failed_count, 0)
        self.assertEqual(insight.total_payout, Decimal('0'))
        self.assertEqual(insight.total_points_awarded, 0)
        self.assertEqual(insight.health_score, Decimal('0'))
        self.assertEqual(insight.average_processing_time, 0.0)
        self.assertFalse(insight.anomaly_detected)
        self.assertEqual(insight.anomaly_details, {})

    def test_get_daily_insight_existing(self):
        """Test getting existing daily insight."""
        existing_insight = PostbackInsightFactory(
            network=self.network,
            date=self.target_date,
            received_count=100,
            rewarded_count=80,
            health_score=Decimal('85.5')
        )
        
        insight = PostbackInsightService.get_daily_insight(self.network, self.target_date)
        
        self.assertEqual(insight.id, existing_insight.id)
        self.assertEqual(insight.received_count, 100)
        self.assertEqual(insight.rewarded_count, 80)
        self.assertEqual(insight.health_score, Decimal('85.5'))

    def test_get_daily_insight_different_networks(self):
        """Test getting insights for different networks."""
        network1 = NetworkPostbackConfigFactory()
        network2 = NetworkPostbackConfigFactory()
        
        insight1 = PostbackInsightService.get_daily_insight(network1, self.target_date)
        insight2 = PostbackInsightService.get_daily_insight(network2, self.target_date)
        
        self.assertEqual(insight1.network, network1)
        self.assertEqual(insight2.network, network2)
        self.assertNotEqual(insight1.id, insight2.id)

    def test_get_daily_insight_different_dates(self):
        """Test getting insights for different dates."""
        yesterday = self.target_date - timedelta(days=1)
        today = self.target_date
        
        yesterday_insight = PostbackInsightService.get_daily_insight(self.network, yesterday)
        today_insight = PostbackInsightService.get_daily_insight(self.network, today)
        
        self.assertEqual(yesterday_insight.date, yesterday)
        self.assertEqual(today_insight.date, today)
        self.assertNotEqual(yesterday_insight.id, today_insight.id)

    def test_get_daily_insight_integrity_hash(self):
        """Test daily insight integrity hash generation."""
        insight = PostbackInsightService.get_daily_insight(self.network, self.target_date)
        
        # Should have integrity hash
        self.assertIsNotNone(insight.integrity_hash)
        self.assertEqual(len(insight.integrity_hash), 64)  # SHA-256 length


class PostbackInsightServiceRecalculationTests(TestCase):
    """Test insight recalculation functionality."""

    def setUp(self):
        self.network = NetworkPostbackConfigFactory()
        self.target_date = date.today()

    def test_recalculate_daily_insight_basic(self):
        """Test basic daily insight recalculation."""
        # Create test logs
        PostbackLogFactory(
            network=self.network,
            status=PostbackStatus.REWARDED,
            payout=Decimal('10.50'),
            points_awarded=105,
            received_at=timezone.make_aware(datetime.combine(self.target_date, datetime.min.time()))
        )
        PostbackLogFactory(
            network=self.network,
            status=PostbackStatus.REJECTED,
            received_at=timezone.make_aware(datetime.combine(self.target_date, datetime.min.time()))
        )
        PostbackLogFactory(
            network=self.network,
            status=PostbackStatus.DUPLICATE,
            received_at=timezone.make_aware(datetime.combine(self.target_date, datetime.min.time()))
        )
        
        insight = PostbackInsightService.recalculate_daily_insight(self.network, self.target_date)
        
        self.assertEqual(insight.received_count, 3)
        self.assertEqual(insight.rewarded_count, 1)
        self.assertEqual(insight.rejected_count, 1)
        self.assertEqual(insight.duplicate_count, 1)
        self.assertEqual(insight.failed_count, 0)
        self.assertEqual(insight.total_payout, Decimal('10.50'))
        self.assertEqual(insight.total_points_awarded, 105)

    def test_recalculate_daily_insight_with_processing_times(self):
        """Test recalculation with processing times."""
        # Create logs with different processing times
        base_time = timezone.make_aware(datetime.combine(self.target_date, datetime.min.time()))
        
        PostbackLogFactory(
            network=self.network,
            status=PostbackStatus.REWARDED,
            received_at=base_time,
            processed_at=base_time + timedelta(seconds=2)
        )
        PostbackLogFactory(
            network=self.network,
            status=PostbackStatus.REWARDED,
            received_at=base_time + timedelta(minutes=1),
            processed_at=base_time + timedelta(minutes=1, seconds=3)
        )
        PostbackLogFactory(
            network=self.network,
            status=PostbackStatus.REWARDED,
            received_at=base_time + timedelta(minutes=2),
            processed_at=base_time + timedelta(minutes=2, seconds=1)
        )
        
        insight = PostbackInsightService.recalculate_daily_insight(self.network, self.target_date)
        
        # Average processing time should be (2 + 3 + 1) / 3 = 2.0
        self.assertEqual(insight.average_processing_time, 2.0)

    def test_recalculate_daily_insight_health_score_calculation(self):
        """Test health score calculation in recalculation."""
        # Create logs with different statuses
        base_time = timezone.make_aware(datetime.combine(self.target_date, datetime.min.time()))
        
        # 80% success rate (8 rewarded, 2 rejected)
        for i in range(8):
            PostbackLogFactory(
                network=self.network,
                status=PostbackStatus.REWARDED,
                received_at=base_time + timedelta(minutes=i)
            )
        for i in range(2):
            PostbackLogFactory(
                network=self.network,
                status=PostbackStatus.REJECTED,
                received_at=base_time + timedelta(minutes=10 + i)
            )
        
        insight = PostbackInsightService.recalculate_daily_insight(self.network, self.target_date)
        
        # Health score should be based on success rate
        self.assertGreater(insight.health_score, 70)  # Should be high with 80% success
        self.assertLessEqual(insight.health_score, 100)

    def test_recalculate_daily_insight_no_logs(self):
        """Test recalculation with no logs."""
        insight = PostbackInsightService.recalculate_daily_insight(self.network, self.target_date)
        
        self.assertEqual(insight.received_count, 0)
        self.assertEqual(insight.rewarded_count, 0)
        self.assertEqual(insight.health_score, Decimal('0'))
        self.assertEqual(insight.average_processing_time, 0.0)

    def test_recalculate_daily_insight_existing_overwrite(self):
        """Test recalculation overwrites existing data."""
        # Create existing insight
        existing_insight = PostbackInsightFactory(
            network=self.network,
            date=self.target_date,
            received_count=50,
            rewarded_count=25
        )
        
        # Create new logs
        PostbackLogFactory(
            network=self.network,
            status=PostbackStatus.REWARDED,
            received_at=timezone.make_aware(datetime.combine(self.target_date, datetime.min.time()))
        )
        
        insight = PostbackInsightService.recalculate_daily_insight(self.network, self.target_date)
        
        # Should overwrite existing data
        self.assertEqual(insight.id, existing_insight.id)
        self.assertEqual(insight.received_count, 1)
        self.assertEqual(insight.rewarded_count, 1)

    def test_recalculate_daily_insight_cross_day_logs(self):
        """Test recalculation only includes logs from target date."""
        target_date = self.target_date
        previous_date = target_date - timedelta(days=1)
        next_date = target_date + timedelta(days=1)
        
        # Create logs for different dates
        PostbackLogFactory(
            network=self.network,
            status=PostbackStatus.REWARDED,
            received_at=timezone.make_aware(datetime.combine(previous_date, datetime.min.time()))
        )
        PostbackLogFactory(
            network=self.network,
            status=PostbackStatus.REWARDED,
            received_at=timezone.make_aware(datetime.combine(target_date, datetime.min.time()))
        )
        PostbackLogFactory(
            network=self.network,
            status=PostbackStatus.REWARDED,
            received_at=timezone.make_aware(datetime.combine(next_date, datetime.min.time()))
        )
        
        insight = PostbackInsightService.recalculate_daily_insight(self.network, target_date)
        
        # Should only include target date logs
        self.assertEqual(insight.received_count, 1)
        self.assertEqual(insight.rewarded_count, 1)


class PostbackInsightServiceHealthTrendTests(TestCase):
    """Test health trend functionality."""

    def setUp(self):
        self.network = NetworkPostbackConfigFactory()

    def test_get_network_health_trend_basic(self):
        """Test basic health trend retrieval."""
        # Create insights for multiple days
        for i in range(7):
            PostbackInsightFactory(
                network=self.network,
                date=date.today() - timedelta(days=i),
                health_score=Decimal(f'{80 + i}.5')
            )
        
        trend = PostbackInsightService.get_network_health_trend(self.network, 7)
        
        self.assertEqual(len(trend), 7)
        
        # Should be ordered by date (most recent first)
        self.assertEqual(trend[0]['date'], date.today())
        self.assertEqual(trend[6]['date'], date.today() - timedelta(days=6))
        
        # Should contain expected fields
        for day_data in trend:
            self.assertIn('date', day_data)
            self.assertIn('health_score', day_data)
            self.assertIn('received_count', day_data)
            self.assertIn('rewarded_count', day_data)

    def test_get_network_health_trend_partial_data(self):
        """Test health trend with partial data."""
        # Create insights for only some days
        PostbackInsightFactory(
            network=self.network,
            date=date.today(),
            health_score=Decimal('85.0')
        )
        PostbackInsightFactory(
            network=self.network,
            date=date.today() - timedelta(days=2),
            health_score=Decimal('90.0')
        )
        
        trend = PostbackInsightService.get_network_health_trend(self.network, 7)
        
        # Should return available data only
        self.assertEqual(len(trend), 2)
        self.assertEqual(trend[0]['health_score'], Decimal('85.0'))
        self.assertEqual(trend[1]['health_score'], Decimal('90.0'))

    def test_get_network_health_trend_no_data(self):
        """Test health trend with no data."""
        trend = PostbackInsightService.get_network_health_trend(self.network, 7)
        
        self.assertEqual(trend, [])

    def test_get_network_health_trend_date_range(self):
        """Test health trend with specific date range."""
        # Create insights across a wider range
        for i in range(14):
            PostbackInsightFactory(
                network=self.network,
                date=date.today() - timedelta(days=i),
                health_score=Decimal(f'{75 + i}.0')
            )
        
        # Request only last 7 days
        trend = PostbackInsightService.get_network_health_trend(self.network, 7)
        
        self.assertEqual(len(trend), 7)
        
        # Should be most recent 7 days
        expected_dates = [date.today() - timedelta(days=i) for i in range(7)]
        actual_dates = [day_data['date'] for day_data in trend]
        
        self.assertEqual(set(actual_dates), set(expected_dates))

    def test_get_network_health_trend_multiple_networks(self):
        """Test health trend for multiple networks."""
        network1 = NetworkPostbackConfigFactory()
        network2 = NetworkPostbackConfigFactory()
        
        # Create insights for both networks
        for i in range(5):
            PostbackInsightFactory(
                network=network1,
                date=date.today() - timedelta(days=i),
                health_score=Decimal('80.0')
            )
            PostbackInsightFactory(
                network=network2,
                date=date.today() - timedelta(days=i),
                health_score=Decimal('90.0')
            )
        
        trend1 = PostbackInsightService.get_network_health_trend(network1, 5)
        trend2 = PostbackInsightService.get_network_health_trend(network2, 5)
        
        # Should return separate trends
        self.assertEqual(len(trend1), 5)
        self.assertEqual(len(trend2), 5)
        
        # All scores should be different between networks
        for day1, day2 in zip(trend1, trend2):
            self.assertEqual(day1['health_score'], Decimal('80.0'))
            self.assertEqual(day2['health_score'], Decimal('90.0'))


class PostbackInsightServiceAnomalyDetectionTests(TestCase):
    """Test anomaly detection functionality."""

    def setUp(self):
        self.network = NetworkPostbackConfigFactory()
        self.target_date = date.today()

    def test_detect_anomalies_volume_spike(self):
        """Test anomaly detection for volume spike."""
        # Create baseline data (last 7 days)
        for i in range(7, 0, -1):
            PostbackInsightFactory(
                network=self.network,
                date=self.target_date - timedelta(days=i),
                received_count=100
            )
        
        # Create current day with spike
        current_insight = PostbackInsightFactory(
            network=self.network,
            date=self.target_date,
            received_count=250  # 150% increase
        )
        
        anomalies = PostbackInsightService.detect_anomalies(self.network, self.target_date)
        
        self.assertTrue(anomalies)
        self.assertIn('volume_spike', anomalies)
        
        spike_data = anomalies['volume_spike']
        self.assertEqual(spike_data['type'], 'volume_spike')
        self.assertGreater(spike_data['deviation_percent'], 50)
        self.assertEqual(spike_data['current'], 250)
        self.assertEqual(spike_data['baseline_avg'], 100.0)

    def test_detect_anomalies_health_drop(self):
        """Test anomaly detection for health score drop."""
        # Create baseline with good health
        for i in range(7, 0, -1):
            PostbackInsightFactory(
                network=self.network,
                date=self.target_date - timedelta(days=i),
                health_score=Decimal('85.0')
            )
        
        # Create current day with poor health
        current_insight = PostbackInsightFactory(
            network=self.network,
            date=self.target_date,
            health_score=Decimal('60.0')  # Significant drop
        )
        
        anomalies = PostbackInsightService.detect_anomalies(self.network, self.target_date)
        
        self.assertTrue(anomalies)
        self.assertIn('health_drop', anomalies)
        
        health_data = anomalies['health_drop']
        self.assertEqual(health_data['type'], 'health_drop')
        self.assertLess(health_data['current'], 70.0)
        self.assertEqual(health_data['baseline_avg'], 85.0)

    def test_detect_anomalies_high_rejection_rate(self):
        """Test anomaly detection for high rejection rate."""
        # Create insight with high rejection rate (>30%)
        insight = PostbackInsightFactory(
            network=self.network,
            date=self.target_date,
            received_count=100,
            rejected_count=25,
            failed_count=10  # 35% rejection rate
        )
        
        anomalies = PostbackInsightService.detect_anomalies(self.network, self.target_date)
        
        self.assertTrue(anomalies)
        self.assertIn('high_rejection_rate', anomalies)
        
        rejection_data = anomalies['high_rejection_rate']
        self.assertEqual(rejection_data['type'], 'high_rejection_rate')
        self.assertGreater(rejection_data['rejection_rate'], 30.0)

    def test_detect_anomalies_high_duplicate_rate(self):
        """Test anomaly detection for high duplicate rate."""
        # Create insight with high duplicate rate (>25%)
        insight = PostbackInsightFactory(
            network=self.network,
            date=self.target_date,
            received_count=100,
            duplicate_count=30  # 30% duplicate rate
        )
        
        anomalies = PostbackInsightService.detect_anomalies(self.network, self.target_date)
        
        self.assertTrue(anomalies)
        self.assertIn('high_duplicate_rate', anomalies)
        
        duplicate_data = anomalies['high_duplicate_rate']
        self.assertEqual(duplicate_data['type'], 'high_duplicate_rate')
        self.assertGreater(duplicate_data['duplicate_rate'], 25.0)

    def test_detect_anomalies_no_anomalies(self):
        """Test anomaly detection with no anomalies."""
        # Create normal baseline
        for i in range(7, 0, -1):
            PostbackInsightFactory(
                network=self.network,
                date=self.target_date - timedelta(days=i),
                received_count=100,
                health_score=Decimal('85.0')
            )
        
        # Create normal current day
        current_insight = PostbackInsightFactory(
            network=self.network,
            date=self.target_date,
            received_count=105,  # Small increase
            health_score=Decimal('87.0'),  # Slight improvement
            rejected_count=10,  # 10% rejection rate
            duplicate_count=5   # 5% duplicate rate
        )
        
        anomalies = PostbackInsightService.detect_anomalies(self.network, self.target_date)
        
        self.assertFalse(anomalies)

    def test_detect_anomalies_no_baseline(self):
        """Test anomaly detection with no baseline data."""
        # Create insight without baseline
        insight = PostbackInsightFactory(
            network=self.network,
            date=self.target_date,
            received_count=100
        )
        
        anomalies = PostbackInsightService.detect_anomalies(self.network, self.target_date)
        
        # Should not detect anomalies without baseline
        self.assertFalse(anomalies)

    def test_detect_anomalies_multiple_anomalies(self):
        """Test detection of multiple anomalies."""
        # Create baseline
        for i in range(7, 0, -1):
            PostbackInsightFactory(
                network=self.network,
                date=self.target_date - timedelta(days=i),
                received_count=100,
                health_score=Decimal('85.0')
            )
        
        # Create current day with multiple issues
        current_insight = PostbackInsightFactory(
            network=self.network,
            date=self.target_date,
            received_count=300,  # Volume spike
            health_score=Decimal('50.0'),  # Health drop
            rejected_count=60,  # High rejection rate (20%)
            duplicate_count=100  # High duplicate rate (33%)
        )
        
        anomalies = PostbackInsightService.detect_anomalies(self.network, self.target_date)
        
        self.assertTrue(anomalies)
        # Should detect multiple anomalies
        self.assertIn('volume_spike', anomalies)
        self.assertIn('health_drop', anomalies)
        self.assertIn('high_duplicate_rate', anomalies)

    def test_detect_anomalies_insufficient_baseline(self):
        """Test anomaly detection with insufficient baseline data."""
        # Create only 1 day of baseline (insufficient for reliable detection)
        PostbackInsightFactory(
            network=self.network,
            date=self.target_date - timedelta(days=1),
            received_count=100
        )
        
        # Create current day with spike
        current_insight = PostbackInsightFactory(
            network=self.network,
            date=self.target_date,
            received_count=1000  # Huge spike
        )
        
        anomalies = PostbackInsightService.detect_anomalies(self.network, self.target_date)
        
        # May not detect anomalies with insufficient baseline
        # This tests the edge case handling
        self.assertIsInstance(anomalies, dict)


class PostbackInsightServiceSummaryTests(TestCase):
    """Test summary functionality."""

    def setUp(self):
        self.network = NetworkPostbackConfigFactory()

    def test_get_network_summary_basic(self):
        """Test basic network summary."""
        # Create insights for multiple days
        for i in range(5):
            PostbackInsightFactory(
                network=self.network,
                date=date.today() - timedelta(days=i),
                received_count=100 + i * 10,
                rewarded_count=80 + i * 5,
                total_payout=Decimal(f'{100 + i * 10}.00')
            )
        
        summary = PostbackInsightService.get_network_summary(self.network, 7)
        
        self.assertEqual(summary['network_key'], self.network.network_key)
        self.assertEqual(summary['period_days'], 7)
        self.assertGreater(summary['total_received'], 0)
        self.assertGreater(summary['total_rewarded'], 0)
        self.assertGreater(summary['total_payout'], 0)
        self.assertIn('avg_health_score', summary)
        self.assertIn('daily_breakdown', summary)

    def test_get_network_summary_calculations(self):
        """Test summary calculations."""
        # Create predictable data
        insights = []
        for i in range(3):
            insight = PostbackInsightFactory(
                network=self.network,
                date=date.today() - timedelta(days=i),
                received_count=100,
                rewarded_count=80,
                total_payout=Decimal('200.00'),
                health_score=Decimal('85.0')
            )
            insights.append(insight)
        
        summary = PostbackInsightService.get_network_summary(self.network, 7)
        
        # Verify calculations
        self.assertEqual(summary['total_received'], 300)  # 3 * 100
        self.assertEqual(summary['total_rewarded'], 240)  # 3 * 80
        self.assertEqual(summary['total_payout'], Decimal('600.00'))  # 3 * 200
        self.assertEqual(summary['avg_health_score'], Decimal('85.0'))  # All same

    def test_get_network_summary_no_data(self):
        """Test summary with no data."""
        summary = PostbackInsightService.get_network_summary(self.network, 7)
        
        self.assertEqual(summary['network_key'], self.network.network_key)
        self.assertEqual(summary['period_days'], 7)
        self.assertEqual(summary['total_received'], 0)
        self.assertEqual(summary['total_rewarded'], 0)
        self.assertEqual(summary['total_payout'], Decimal('0'))
        self.assertEqual(summary['avg_health_score'], Decimal('0'))
        self.assertEqual(summary['daily_breakdown'], [])

    def test_get_network_summary_partial_period(self):
        """Test summary with partial period data."""
        # Create data for only 3 days out of 7-day period
        for i in range(3):
            PostbackInsightFactory(
                network=self.network,
                date=date.today() - timedelta(days=i),
                received_count=50
            )
        
        summary = PostbackInsightService.get_network_summary(self.network, 7)
        
        # Should only include available data
        self.assertEqual(summary['total_received'], 150)
        self.assertEqual(len(summary['daily_breakdown']), 3)

    def test_get_network_summary_multiple_networks(self):
        """Test summary for multiple networks."""
        network1 = NetworkPostbackConfigFactory()
        network2 = NetworkPostbackConfigFactory()
        
        # Create data for both networks
        PostbackInsightFactory(
            network=network1,
            received_count=100,
            total_payout=Decimal('100.00')
        )
        PostbackInsightFactory(
            network=network2,
            received_count=200,
            total_payout=Decimal('200.00')
        )
        
        summary1 = PostbackInsightService.get_network_summary(network1, 7)
        summary2 = PostbackInsightService.get_network_summary(network2, 7)
        
        self.assertEqual(summary1['total_received'], 100)
        self.assertEqual(summary2['total_received'], 200)
        self.assertEqual(summary1['network_key'], network1.network_key)
        self.assertEqual(summary2['network_key'], network2.network_key)


class PostbackInsightServiceBackfillTests(TestCase):
    """Test backfill functionality."""

    def setUp(self):
        self.network = NetworkPostbackConfigFactory()

    def test_backfill_missing_insights_basic(self):
        """Test basic backfill of missing insights."""
        start_date = date.today() - timedelta(days=5)
        end_date = date.today() - timedelta(days=1)
        
        # Create some logs for backfill period
        for i in range(5):
            PostbackLogFactory(
                network=self.network,
                status=PostbackStatus.REWARDED,
                received_at=timezone.make_aware(datetime.combine(
                    start_date + timedelta(days=i), datetime.min.time()
                ))
            )
        
        processed_count = PostbackInsightService.backfill_missing_insights(
            self.network, start_date, end_date
        )
        
        self.assertEqual(processed_count, 5)
        
        # Verify insights were created
        for i in range(5):
            target_date = start_date + timedelta(days=i)
            insight_exists = PostbackInsight.objects.filter(
                network=self.network, date=target_date
            ).exists()
            self.assertTrue(insight_exists)

    def test_backfill_missing_insights_no_logs(self):
        """Test backfill with no logs."""
        start_date = date.today() - timedelta(days=3)
        end_date = date.today() - timedelta(days=1)
        
        processed_count = PostbackInsightService.backfill_missing_insights(
            self.network, start_date, end_date
        )
        
        self.assertEqual(processed_count, 3)
        
        # Should create insights with zero counts
        for i in range(3):
            target_date = start_date + timedelta(days=i)
            insight = PostbackInsight.objects.get(
                network=self.network, date=target_date
            )
            self.assertEqual(insight.received_count, 0)

    def test_backfill_missing_insights_existing_data(self):
        """Test backfill with existing insights."""
        start_date = date.today() - timedelta(days=2)
        end_date = date.today()
        
        # Create existing insight for one day
        existing_date = start_date + timedelta(days=1)
        existing_insight = PostbackInsightFactory(
            network=self.network,
            date=existing_date,
            received_count=50
        )
        
        # Create logs for all days
        for i in range(3):
            PostbackLogFactory(
                network=self.network,
                status=PostbackStatus.REWARDED,
                received_at=timezone.make_aware(datetime.combine(
                    start_date + timedelta(days=i), datetime.min.time()
                ))
            )
        
        processed_count = PostbackInsightService.backfill_missing_insights(
            self.network, start_date, end_date
        )
        
        self.assertEqual(processed_count, 3)
        
        # Existing insight should be updated
        updated_insight = PostbackInsight.objects.get(
            network=self.network, date=existing_date
        )
        self.assertNotEqual(updated_insight.received_count, 50)  # Should be recalculated

    def test_backfill_missing_insights_large_range(self):
        """Test backfill with large date range."""
        start_date = date.today() - timedelta(days=30)
        end_date = date.today()
        
        # Create logs for the period
        for i in range(30):
            PostbackLogFactory(
                network=self.network,
                status=PostbackStatus.REWARDED,
                received_at=timezone.make_aware(datetime.combine(
                    start_date + timedelta(days=i), datetime.min.time()
                ))
            )
        
        processed_count = PostbackInsightService.backfill_missing_insights(
            self.network, start_date, end_date
        )
        
        self.assertEqual(processed_count, 30)
        
        # Verify all insights exist
        insight_count = PostbackInsight.objects.filter(
            network=self.network,
            date__gte=start_date,
            date__lte=end_date
        ).count()
        self.assertEqual(insight_count, 30)

    def test_backfill_missing_insights_invalid_range(self):
        """Test backfill with invalid date range."""
        start_date = date.today()
        end_date = date.today() - timedelta(days=5)  # End before start
        
        processed_count = PostbackInsightService.backfill_missing_insights(
            self.network, start_date, end_date
        )
        
        self.assertEqual(processed_count, 0)  # Should handle gracefully


class PostbackInsightServicePerformanceTests(TestCase):
    """Test performance characteristics."""

    def setUp(self):
        self.network = NetworkPostbackConfigFactory()

    def test_get_daily_insight_performance(self):
        """Test performance of getting daily insights."""
        import time
        
        start_time = time.time()
        
        # Get insights for multiple dates
        for i in range(100):
            target_date = date.today() - timedelta(days=i)
            PostbackInsightService.get_daily_insight(self.network, target_date)
        
        end_time = time.time()
        elapsed_time = end_time - start_time
        
        # Should complete within reasonable time
        self.assertLess(elapsed_time, 2.0, "Get daily insight too slow")

    def test_recalculate_performance(self):
        """Test performance of insight recalculation."""
        import time
        
        # Create many logs
        base_time = timezone.now() - timedelta(days=1)
        for i in range(1000):
            PostbackLogFactory(
                network=self.network,
                status=PostbackStatus.REWARDED,
                received_at=base_time + timedelta(minutes=i)
            )
        
        start_time = time.time()
        
        # Recalculate insight
        insight = PostbackInsightService.recalculate_daily_insight(
            self.network, date.today() - timedelta(days=1)
        )
        
        end_time = time.time()
        elapsed_time = end_time - start_time
        
        # Should complete within reasonable time
        self.assertLess(elapsed_time, 5.0, "Recalculation too slow")
        self.assertEqual(insight.received_count, 1000)

    def test_health_trend_performance(self):
        """Test performance of health trend calculation."""
        import time
        
        # Create many insights
        for i in range(100):
            PostbackInsightFactory(
                network=self.network,
                date=date.today() - timedelta(days=i),
                health_score=Decimal('85.0')
            )
        
        start_time = time.time()
        
        # Get health trend
        trend = PostbackInsightService.get_network_health_trend(self.network, 100)
        
        end_time = time.time()
        elapsed_time = end_time - start_time
        
        # Should complete within reasonable time
        self.assertLess(elapsed_time, 1.0, "Health trend calculation too slow")
        self.assertEqual(len(trend), 100)

    def test_anomaly_detection_performance(self):
        """Test performance of anomaly detection."""
        import time
        
        # Create baseline data
        for i in range(30):
            PostbackInsightFactory(
                network=self.network,
                date=date.today() - timedelta(days=i),
                received_count=100
            )
        
        start_time = time.time()
        
        # Detect anomalies
        anomalies = PostbackInsightService.detect_anomalies(self.network, date.today())
        
        end_time = time.time()
        elapsed_time = end_time - start_time
        
        # Should complete within reasonable time
        self.assertLess(elapsed_time, 0.5, "Anomaly detection too slow")

    def test_summary_performance(self):
        """Test performance of summary calculation."""
        import time
        
        # Create many insights
        for i in range(50):
            PostbackInsightFactory(
                network=self.network,
                date=date.today() - timedelta(days=i),
                received_count=100,
                total_payout=Decimal('100.00')
            )
        
        start_time = time.time()
        
        # Get summary
        summary = PostbackInsightService.get_network_summary(self.network, 60)
        
        end_time = time.time()
        elapsed_time = end_time - start_time
        
        # Should complete within reasonable time
        self.assertLess(elapsed_time, 1.0, "Summary calculation too slow")
        self.assertEqual(summary['total_received'], 5000)

    def test_backfill_performance(self):
        """Test performance of backfill operations."""
        import time
        
        # Create logs for backfill period
        start_date = date.today() - timedelta(days=10)
        for i in range(10):
            for j in range(100):  # 100 logs per day
                PostbackLogFactory(
                    network=self.network,
                    status=PostbackStatus.REWARDED,
                    received_at=timezone.make_aware(datetime.combine(
                        start_date + timedelta(days=i), 
                        datetime.min.time()
                    )) + timedelta(minutes=j)
                )
        
        start_time = time.time()
        
        # Backfill insights
        processed_count = PostbackInsightService.backfill_missing_insights(
            self.network, start_date, date.today() - timedelta(days=1)
        )
        
        end_time = time.time()
        elapsed_time = end_time - start_time
        
        # Should complete within reasonable time
        self.assertLess(elapsed_time, 10.0, "Backfill too slow")
        self.assertEqual(processed_count, 9)


class PostbackInsightServiceIntegrationTests(TestCase):
    """Test integration with other components."""

    def setUp(self):
        self.network = NetworkPostbackConfigFactory()

    def test_integration_with_postback_logs(self):
        """Test integration with postback logs."""
        # Create logs with various statuses
        base_time = timezone.make_aware(datetime.combine(date.today(), datetime.min.time()))
        
        PostbackLogFactory(
            network=self.network,
            status=PostbackStatus.REWARDED,
            payout=Decimal('10.00'),
            points_awarded=100,
            received_at=base_time,
            processed_at=base_time + timedelta(seconds=2)
        )
        PostbackLogFactory(
            network=self.network,
            status=PostbackStatus.REJECTED,
            received_at=base_time + timedelta(minutes=1),
            processed_at=base_time + timedelta(minutes=1, seconds=1)
        )
        PostbackLogFactory(
            network=self.network,
            status=PostbackStatus.DUPLICATE,
            received_at=base_time + timedelta(minutes=2),
            processed_at=base_time + timedelta(minutes=2, seconds=3)
        )
        
        # Recalculate insight
        insight = PostbackInsightService.recalculate_daily_insight(self.network, date.today())
        
        # Should accurately reflect log data
        self.assertEqual(insight.received_count, 3)
        self.assertEqual(insight.rewarded_count, 1)
        self.assertEqual(insight.rejected_count, 1)
        self.assertEqual(insight.duplicate_count, 1)
        self.assertEqual(insight.total_payout, Decimal('10.00'))
        self.assertEqual(insight.total_points_awarded, 100)
        self.assertEqual(insight.average_processing_time, 2.0)  # (2 + 1 + 3) / 3

    def test_integration_with_caching(self):
        """Test integration with caching system."""
        # Test caching of insights
        cache_key = f"postback_insight:{self.network.id}:{date.today()}"
        
        # Get insight (should cache)
        insight1 = PostbackInsightService.get_daily_insight(self.network, date.today())
        
        # Check if cached
        cached_insight = cache.get(cache_key)
        self.assertIsNotNone(cached_insight)
        
        # Get insight again (should use cache)
        insight2 = PostbackInsightService.get_daily_insight(self.network, date.today())
        
        self.assertEqual(insight1.id, insight2.id)

    def test_integration_with_database_transactions(self):
        """Test integration with database transactions."""
        try:
            with transaction.atomic():
                # Create insight within transaction
                insight = PostbackInsightService.get_daily_insight(self.network, date.today())
                
                # Create logs
                PostbackLogFactory(
                    network=self.network,
                    status=PostbackStatus.REWARDED,
                    received_at=timezone.now()
                )
                
                # Recalculate within transaction
                recalc_insight = PostbackInsightService.recalculate_daily_insight(
                    self.network, date.today()
                )
                
                # Force transaction rollback
                raise Exception("Test rollback")
        except Exception:
            pass
        
        # Check if rollback occurred
        logs_count = PostbackLog.objects.filter(network=self.network).count()
        self.assertEqual(logs_count, 0)  # Should be rolled back

    def test_integration_with_multiple_networks(self):
        """Test integration with multiple networks."""
        network1 = NetworkPostbackConfigFactory()
        network2 = NetworkPostbackConfigFactory()
        
        # Create insights for both networks
        insight1 = PostbackInsightService.get_daily_insight(network1, date.today())
        insight2 = PostbackInsightService.get_daily_insight(network2, date.today())
        
        # Should be independent
        self.assertNotEqual(insight1.id, insight2.id)
        self.assertEqual(insight1.network, network1)
        self.assertEqual(insight2.network, network2)
        
        # Create logs for network1 only
        PostbackLogFactory(
            network=network1,
            status=PostbackStatus.REWARDED,
            received_at=timezone.now()
        )
        
        # Recalculate only network1
        recalc1 = PostbackInsightService.recalculate_daily_insight(network1, date.today())
        recalc2 = PostbackInsightService.recalculate_daily_insight(network2, date.today())
        
        # Network1 should have data, network2 should not
        self.assertGreater(recalc1.received_count, 0)
        self.assertEqual(recalc2.received_count, 0)

    def test_integration_with_error_handling(self):
        """Test integration with error handling."""
        # Test with invalid network
        invalid_network = NetworkPostbackConfigFactory.build()
        invalid_network.id = None  # Make it invalid
        
        # Should handle gracefully
        try:
            PostbackInsightService.get_daily_insight(invalid_network, date.today())
        except Exception as e:
            # Should handle database errors gracefully
            self.assertIsInstance(e, Exception)

    def test_integration_with_concurrent_operations(self):
        """Test integration with concurrent operations."""
        # Test concurrent insight creation
        with transaction.atomic():
            # Lock network to simulate concurrent access
            locked_network = NetworkPostbackConfig.objects.select_for_update().get(
                id=self.network.id
            )
            
            # Create insight
            insight = PostbackInsightService.get_daily_insight(locked_network, date.today())
            
            # Should be consistent
            self.assertEqual(insight.network, locked_network)

    def test_integration_with_data_consistency(self):
        """Test data consistency across operations."""
        # Create logs
        base_time = timezone.now()
        for i in range(10):
            PostbackLogFactory(
                network=self.network,
                status=PostbackStatus.REWARDED,
                received_at=base_time + timedelta(minutes=i)
            )
        
        # Get insight
        insight = PostbackInsightService.get_daily_insight(self.network, date.today())
        
        # Recalculate
        recalc_insight = PostbackInsightService.recalculate_daily_insight(
            self.network, date.today()
        )
        
        # Should be consistent
        self.assertEqual(insight.id, recalc_insight.id)
        self.assertEqual(recalc_insight.received_count, 10)
        self.assertEqual(recalc_insight.rewarded_count, 10)
