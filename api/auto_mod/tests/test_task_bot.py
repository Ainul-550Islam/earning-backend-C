# =============================================================================
# auto_mod/tests/test_task_bot.py
# =============================================================================

"""
Tests for task bot functionality.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status
from django.core.management import call_command

from ..choices import BotStatus, TaskType, SubmissionType, ModerationStatus
from ..models import TaskBot, SuspiciousSubmission
from api.auto_mod.services import BotService
from ..exceptions import BotAlreadyRunningError, BotNotReadyError

User = get_user_model()


class TaskBotModelTest(TestCase):
    """Test TaskBot model functionality."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123"
        )
        
        self.bot = TaskBot.objects.create(
            name="Test Bot",
            bot_type=TaskType.IMAGE_SCANNER,
            status=BotStatus.IDLE,
            max_retries=3,
            created_by=self.user
        )
    
    def test_bot_creation(self):
        """Test basic bot creation."""
        self.assertEqual(self.bot.name, "Test Bot")
        self.assertEqual(self.bot.bot_type, TaskType.IMAGE_SCANNER)
        self.assertEqual(self.bot.status, BotStatus.IDLE)
        self.assertEqual(self.bot.max_retries, 3)
        self.assertEqual(self.bot.current_retry, 0)
        self.assertEqual(self.bot.created_by, self.user)
        self.assertIsNotNone(self.bot.created_at)
        self.assertIsNone(self.bot.last_heartbeat)
        self.assertIsNone(self.bot.last_run_at)
    
    def test_bot_str_representation(self):
        """Test bot string representation."""
        expected = f"{self.bot.name} ({self.bot.get_bot_type_display()})"
        self.assertEqual(str(self.bot), expected)
    
    def test_start_bot(self):
        """Test starting a bot."""
        self.bot.start()
        
        self.assertEqual(self.bot.status, BotStatus.RUNNING)
        self.assertIsNotNone(self.bot.last_run_at)
        self.assertEqual(self.bot.current_retry, 0)
    
    def test_stop_bot(self):
        """Test stopping a bot."""
        self.bot.start()
        self.bot.stop()
        
        self.assertEqual(self.bot.status, BotStatus.STOPPED)
    
    def test_pause_bot(self):
        """Test pausing a bot."""
        self.bot.start()
        self.bot.pause()
        
        self.assertEqual(self.bot.status, BotStatus.PAUSED)
    
    def test_restart_bot(self):
        """Test restarting a bot."""
        self.bot.start()
        self.bot.pause()
        self.bot.restart()
        
        self.assertEqual(self.bot.status, BotStatus.RUNNING)
        self.assertEqual(self.bot.current_retry, 0)
    
    def test_increment_retry(self):
        """Test incrementing retry count."""
        self.bot.increment_retry()
        
        self.assertEqual(self.bot.current_retry, 1)
        
        # Test max retries reached
        self.bot.current_retry = self.bot.max_retries
        self.bot.increment_retry()
        
        self.assertEqual(self.bot.status, BotStatus.FAILED)
    
    def test_update_heartbeat(self):
        """Test updating heartbeat."""
        old_heartbeat = self.bot.last_heartbeat
        self.bot.update_heartbeat()
        
        self.assertNotEqual(self.bot.last_heartbeat, old_heartbeat)
    
    def test_is_healthy(self):
        """Test bot health check."""
        # Idle bot should be healthy
        self.assertTrue(self.bot.is_healthy())
        
        # Running bot with recent heartbeat should be healthy
        self.bot.start()
        self.bot.update_heartbeat()
        self.assertTrue(self.bot.is_healthy())
        
        # Bot without heartbeat should be unhealthy
        self.bot.last_heartbeat = None
        self.assertFalse(self.bot.is_healthy())
    
    def test_can_run(self):
        """Test bot run eligibility."""
        # Idle bot can run
        self.assertTrue(self.bot.can_run())
        
        # Running bot cannot run
        self.bot.start()
        self.assertFalse(self.bot.can_run())
        
        # Failed bot cannot run
        self.bot.status = BotStatus.FAILED
        self.assertFalse(self.bot.can_run())
        
        # Bot at max retries cannot run
        self.bot.status = BotStatus.IDLE
        self.bot.current_retry = self.bot.max_retries
        self.assertFalse(self.bot.can_run())
    
    def test_get_runtime_stats(self):
        """Test runtime statistics."""
        self.bot.start()
        self.bot.update_heartbeat()
        
        stats = self.bot.get_runtime_stats()
        
        self.assertIn("status", stats)
        self.assertIn("last_run_at", stats)
        self.assertIn("last_heartbeat", stats)
        self.assertIn("current_retry", stats)
        self.assertIn("max_retries", stats)
        self.assertIn("is_healthy", stats)
    
    def test_by_status_queryset(self):
        """Test by_status queryset method."""
        qs = TaskBot.objects.by_status(BotStatus.IDLE)
        self.assertIn(self.bot, qs)
        
        self.bot.start()
        qs = TaskBot.objects.by_status(BotStatus.RUNNING)
        self.assertIn(self.bot, qs)
        
        qs = TaskBot.objects.by_status(BotStatus.IDLE)
        self.assertNotIn(self.bot, qs)
    
    def test_by_type_queryset(self):
        """Test by_type queryset method."""
        qs = TaskBot.objects.by_type(TaskType.IMAGE_SCANNER)
        self.assertIn(self.bot, qs)
        
        qs = TaskBot.objects.by_type(TaskType.TEXT_SCANNER)
        self.assertNotIn(self.bot, qs)
    
    def test_active_queryset(self):
        """Test active queryset method."""
        # Idle bot should be in active queryset
        qs = TaskBot.objects.active()
        self.assertIn(self.bot, qs)
        
        # Failed bot should not be active
        self.bot.status = BotStatus.FAILED
        self.bot.save()
        qs = TaskBot.objects.active()
        self.assertNotIn(self.bot, qs)
    
    def test_healthy_queryset(self):
        """Test healthy queryset method."""
        # Bot with no heartbeat should not be healthy
        qs = TaskBot.objects.healthy()
        self.assertNotIn(self.bot, qs)
        
        # Update heartbeat to make it healthy
        self.bot.update_heartbeat()
        qs = TaskBot.objects.healthy()
        self.assertIn(self.bot, qs)


class TaskBotServiceTest(TestCase):
    """Test TaskBot service functionality."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123"
        )
        
        self.bot_service = BotService()
        
        self.bot = TaskBot.objects.create(
            name="Test Scanner Bot",
            bot_type=TaskType.IMAGE_SCANNER,
            status=BotStatus.IDLE,
            max_retries=3,
            created_by=self.user
        )
        
        self.submission = SuspiciousSubmission.objects.create(
            content_id="test123",
            submission_type=SubmissionType.IMAGE,
            user=self.user,
            status=ModerationStatus.PENDING
        )
    
    def test_create_bot_success(self):
        """Test successful bot creation."""
        bot = self.bot_service.create_bot(
            name="New Bot",
            bot_type=TaskType.TEXT_SCANNER,
            max_retries=5,
            created_by=self.user,
            config={"batch_size": 10}
        )
        
        self.assertEqual(bot.name, "New Bot")
        self.assertEqual(bot.bot_type, TaskType.TEXT_SCANNER)
        self.assertEqual(bot.max_retries, 5)
        self.assertEqual(bot.config, {"batch_size": 10})
        self.assertEqual(bot.created_by, self.user)
        self.assertEqual(bot.status, BotStatus.IDLE)
    
    def test_create_bot_invalid_type(self):
        """Test bot creation with invalid type."""
        with self.assertRaises(ValueError):
            self.bot_service.create_bot(
                name="Invalid Bot",
                bot_type="invalid_type",
                created_by=self.user
            )
    
    def test_start_bot_success(self):
        """Test successful bot start."""
        result = self.bot_service.start_bot(self.bot)
        
        self.assertTrue(result["success"])
        self.assertEqual(result["status"], BotStatus.RUNNING)
        
        self.bot.refresh_from_db()
        self.assertEqual(self.bot.status, BotStatus.RUNNING)
        self.assertIsNotNone(self.bot.last_run_at)
    
    def test_start_bot_already_running(self):
        """Test starting bot that's already running."""
        self.bot.start()
        
        with self.assertRaises(BotAlreadyRunningError):
            self.bot_service.start_bot(self.bot)
    
    def test_stop_bot_success(self):
        """Test successful bot stop."""
        self.bot.start()
        
        result = self.bot_service.stop_bot(self.bot)
        
        self.assertTrue(result["success"])
        self.assertEqual(result["status"], BotStatus.STOPPED)
        
        self.bot.refresh_from_db()
        self.assertEqual(self.bot.status, BotStatus.STOPPED)
    
    def test_restart_bot_success(self):
        """Test successful bot restart."""
        self.bot.start()
        self.bot.pause()
        
        result = self.bot_service.restart_bot(self.bot)
        
        self.assertTrue(result["success"])
        self.assertEqual(result["status"], BotStatus.RUNNING)
        
        self.bot.refresh_from_db()
        self.assertEqual(self.bot.status, BotStatus.RUNNING)
        self.assertEqual(self.bot.current_retry, 0)
    
    def test_execute_bot_task_success(self):
        """Test successful bot task execution."""
        with patch('api.auto_mod.services.BotService._execute_image_scan') as mock_execute:
            mock_execute.return_value = {
                "status": "success",
                "processed": 5,
                "results": [{"submission_id": "test", "status": "approved"}]
            }
            
            result = self.bot_service.execute_bot_task(
                self.bot,
                task_data={"submission_ids": [str(self.submission.pk)]}
            )
            
            self.assertTrue(result["success"])
            self.assertEqual(result["processed"], 5)
            self.assertIn("results", result)
            
            self.bot.refresh_from_db()
            self.assertEqual(self.bot.status, BotStatus.IDLE)
    
    def test_execute_bot_task_failure(self):
        """Test bot task execution failure."""
        with patch('api.auto_mod.services.BotService._execute_image_scan') as mock_execute:
            mock_execute.side_effect = Exception("Task execution failed")
            
            result = self.bot_service.execute_bot_task(self.bot)
            
            self.assertFalse(result["success"])
            self.assertIn("error", result)
            
            self.bot.refresh_from_db()
            self.assertEqual(self.bot.current_retry, 1)
    
    def test_execute_bot_task_max_retries(self):
        """Test bot task execution with max retries reached."""
        self.bot.current_retry = self.bot.max_retries
        self.bot.save()
        
        with patch('api.auto_mod.services.BotService._execute_image_scan') as mock_execute:
            mock_execute.side_effect = Exception("Task execution failed")
            
            result = self.bot_service.execute_bot_task(self.bot)
            
            self.assertFalse(result["success"])
            
            self.bot.refresh_from_db()
            self.assertEqual(self.bot.status, BotStatus.FAILED)
    
    def test_get_bot_statistics(self):
        """Test bot statistics retrieval."""
        # Create bots with different statuses
        TaskBot.objects.create(
            name="Running Bot",
            bot_type=TaskType.TEXT_SCANNER,
            status=BotStatus.RUNNING,
            created_by=self.user
        )
        
        TaskBot.objects.create(
            name="Failed Bot",
            bot_type=TaskType.OCR_SCANNER,
            status=BotStatus.FAILED,
            created_by=self.user
        )
        
        stats = self.bot_service.get_bot_statistics()
        
        self.assertIn("total_bots", stats)
        self.assertIn("status_breakdown", stats)
        self.assertIn("type_breakdown", stats)
        self.assertIn("healthy_bots", stats)
        self.assertIn("active_bots", stats)
        self.assertGreater(stats["total_bots"], 0)
    
    def test_get_bots_by_type(self):
        """Test getting bots by type."""
        bots = self.bot_service.get_bots_by_type(TaskType.IMAGE_SCANNER)
        
        self.assertIn(self.bot, bots)
        
        bots = self.bot_service.get_bots_by_type(TaskType.TEXT_SCANNER)
        self.assertNotIn(self.bot, bots)
    
    def test_get_healthy_bots(self):
        """Test getting healthy bots."""
        # Bot without heartbeat should not be healthy
        healthy_bots = self.bot_service.get_healthy_bots()
        self.assertNotIn(self.bot, healthy_bots)
        
        # Update heartbeat to make it healthy
        self.bot.update_heartbeat()
        healthy_bots = self.bot_service.get_healthy_bots()
        self.assertIn(self.bot, healthy_bots)
    
    def test_health_check_all_bots(self):
        """Test health check for all bots."""
        # Create another bot
        other_bot = TaskBot.objects.create(
            name="Other Bot",
            bot_type=TaskType.TEXT_SCANNER,
            status=BotStatus.RUNNING,
            created_by=self.user
        )
        other_bot.update_heartbeat()
        
        results = self.bot_service.health_check_all_bots()
        
        self.assertIsInstance(results, list)
        self.assertEqual(len(results), 2)
        
        for result in results:
            self.assertIn("bot_id", result)
            self.assertIn("name", result)
            self.assertIn("is_healthy", result)
            self.assertIn("status", result)
    
    def test_cleanup_failed_bots(self):
        """Test cleanup of failed bots."""
        # Create failed bot
        failed_bot = TaskBot.objects.create(
            name="Failed Bot",
            bot_type=TaskType.TEXT_SCANNER,
            status=BotStatus.FAILED,
            created_by=self.user
        )
        
        results = self.bot_service.cleanup_failed_bots()
        
        self.assertIn("cleaned", results)
        self.assertGreater(results["cleaned"], 0)
        
        # Check bot was restarted
        failed_bot.refresh_from_db()
        self.assertEqual(failed_bot.status, BotStatus.IDLE)
        self.assertEqual(failed_bot.current_retry, 0)


class TaskBotAPITest(TestCase):
    """Test TaskBot API endpoints."""
    
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123"
        )
        self.staff_user = User.objects.create_user(
            username="staffuser",
            email="staff@example.com",
            password="staffpass123",
            is_staff=True
        )
        
        self.bot = TaskBot.objects.create(
            name="Test Bot",
            bot_type=TaskType.IMAGE_SCANNER,
            status=BotStatus.IDLE,
            created_by=self.staff_user
        )
    
    def test_list_bots_unauthorized(self):
        """Test listing bots without authentication."""
        response = self.client.get("/api/auto_mod/bots/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_list_bots_authorized(self):
        """Test listing bots with authentication."""
        self.client.force_authenticate(user=self.user)
        response = self.client.get("/api/auto_mod/bots/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
    
    def test_retrieve_bot(self):
        """Test retrieving a specific bot."""
        self.client.force_authenticate(user=self.user)
        response = self.client.get(f"/api/auto_mod/bots/{self.bot.pk}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], str(self.bot.pk))
    
    def test_create_bot_staff(self):
        """Test creating bot as staff user."""
        self.client.force_authenticate(user=self.staff_user)
        
        data = {
            "name": "New Bot",
            "bot_type": TaskType.TEXT_SCANNER,
            "max_retries": 5,
            "config": {"batch_size": 10}
        }
        
        response = self.client.post("/api/auto_mod/bots/", data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(TaskBot.objects.count(), 2)
    
    def test_create_bot_non_staff(self):
        """Test creating bot as non-staff user."""
        self.client.force_authenticate(user=self.user)
        
        data = {
            "name": "New Bot",
            "bot_type": TaskType.TEXT_SCANNER,
            "max_retries": 5
        }
        
        response = self.client.post("/api/auto_mod/bots/", data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_start_bot(self):
        """Test starting bot action."""
        self.client.force_authenticate(user=self.staff_user)
        
        response = self.client.post(f"/api/auto_mod/bots/{self.bot.pk}/start/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["success"])
        
        self.bot.refresh_from_db()
        self.assertEqual(self.bot.status, BotStatus.RUNNING)
    
    def test_stop_bot(self):
        """Test stopping bot action."""
        self.client.force_authenticate(user=self.staff_user)
        
        self.bot.start()
        
        response = self.client.post(f"/api/auto_mod/bots/{self.bot.pk}/stop/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["success"])
        
        self.bot.refresh_from_db()
        self.assertEqual(self.bot.status, BotStatus.STOPPED)
    
    def test_restart_bot(self):
        """Test restarting bot action."""
        self.client.force_authenticate(user=self.staff_user)
        
        self.bot.start()
        self.bot.pause()
        
        response = self.client.post(f"/api/auto_mod/bots/{self.bot.pk}/restart/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["success"])
        
        self.bot.refresh_from_db()
        self.assertEqual(self.bot.status, BotStatus.RUNNING)
    
    def test_bot_health_check(self):
        """Test bot health check action."""
        self.client.force_authenticate(user=self.staff_user)
        
        response = self.client.get(f"/api/auto_mod/bots/{self.bot.pk}/health/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("is_healthy", response.data)
    
    def test_bot_statistics(self):
        """Test bot statistics endpoint."""
        self.client.force_authenticate(user=self.staff_user)
        
        response = self.client.get("/api/auto_mod/bots/statistics/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("total_bots", response.data)
    
    def test_cleanup_failed_bots(self):
        """Test cleanup failed bots endpoint."""
        self.client.force_authenticate(user=self.staff_user)
        
        # Create failed bot
        failed_bot = TaskBot.objects.create(
            name="Failed Bot",
            bot_type=TaskType.TEXT_SCANNER,
            status=BotStatus.FAILED,
            created_by=self.staff_user
        )
        
        response = self.client.post("/api/auto_mod/bots/cleanup-failed/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("cleaned", response.data)


class BotTaskExecutionTest(TestCase):
    """Test bot task execution functionality."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123"
        )
        
        self.bot_service = BotService()
        
        self.image_bot = TaskBot.objects.create(
            name="Image Scanner Bot",
            bot_type=TaskType.IMAGE_SCANNER,
            status=BotStatus.IDLE,
            created_by=self.user
        )
        
        self.text_bot = TaskBot.objects.create(
            name="Text Scanner Bot",
            bot_type=TaskType.TEXT_SCANNER,
            status=BotStatus.IDLE,
            created_by=self.user
        )
        
        self.ocr_bot = TaskBot.objects.create(
            name="OCR Bot",
            bot_type=TaskType.OCR_SCANNER,
            status=BotStatus.IDLE,
            created_by=self.user
        )
        
        # Create test submissions
        self.submissions = []
        for i in range(5):
            submission = SuspiciousSubmission.objects.create(
                content_id=f"test{i}",
                submission_type=SubmissionType.IMAGE,
                user=self.user,
                status=ModerationStatus.PENDING
            )
            self.submissions.append(submission)
    
    @patch('api.auto_mod.services.BotService.run_image_scan')
    def test_execute_image_scan_task(self, mock_scan):
        """Test executing image scan task."""
        mock_scan.return_value = {
            "status": "success",
            "processed": 3,
            "results": [
                {"submission_id": str(s.pk), "status": "approved"} 
                for s in self.submissions[:3]
            ]
        }
        
        task_data = {
            "submission_ids": [str(s.pk) for s in self.submissions[:3]]
        }
        
        result = self.bot_service._execute_image_scan(task_data)
        
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["processed"], 3)
        self.assertEqual(len(result["results"]), 3)
    
    @patch('api.auto_mod.services.BotService.run_text_analysis')
    def test_execute_text_scan_task(self, mock_analysis):
        """Test executing text scan task."""
        mock_analysis.return_value = {
            "status": "success",
            "processed": 2,
            "results": [
                {"submission_id": str(s.pk), "status": "flagged"} 
                for s in self.submissions[:2]
            ]
        }
        
        task_data = {
            "submission_ids": [str(s.pk) for s in self.submissions[:2]]
        }
        
        result = self.bot_service._execute_text_scan(task_data)
        
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["processed"], 2)
    
    @patch('api.auto_mod.services.BotService.run_ocr_scan')
    def test_execute_ocr_scan_task(self, mock_ocr):
        """Test executing OCR scan task."""
        mock_ocr.return_value = {
            "status": "success",
            "processed": 4,
            "results": [
                {"submission_id": str(s.pk), "text": "Extracted text"} 
                for s in self.submissions[:4]
            ]
        }
        
        task_data = {
            "submission_ids": [str(s.pk) for s in self.submissions[:4]]
        }
        
        result = self.bot_service._execute_ocr_scan(task_data)
        
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["processed"], 4)
    
    def test_execute_task_invalid_bot_type(self):
        """Test executing task with invalid bot type."""
        invalid_bot = TaskBot.objects.create(
            name="Invalid Bot",
            bot_type="invalid_type",
            status=BotStatus.IDLE,
            created_by=self.user
        )
        
        with self.assertRaises(ValueError):
            self.bot_service.execute_bot_task(invalid_bot)
    
    def test_execute_task_missing_data(self):
        """Test executing task with missing data."""
        with self.assertRaises(BotNotReadyError):
            self.bot_service.execute_bot_task(self.image_bot)
    
    def test_execute_task_with_retry(self):
        """Test task execution with retry mechanism."""
        call_count = 0
        
        def failing_scan(task_data):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise Exception("Temporary failure")
            return {
                "status": "success",
                "processed": 1,
                "results": [{"submission_id": task_data["submission_ids"][0], "status": "approved"}]
            }
        
        with patch('api.auto_mod.services.BotService.run_image_scan', side_effect=failing_scan):
            # First attempt should fail
            result1 = self.bot_service.execute_bot_task(self.image_bot, {"submission_ids": [str(self.submissions[0].pk)]})
            self.assertFalse(result1["success"])
            self.assertEqual(self.image_bot.current_retry, 1)
            
            # Reset bot status for retry
            self.image_bot.status = BotStatus.IDLE
            self.image_bot.save()
            
            # Second attempt should succeed
            result2 = self.bot_service.execute_bot_task(self.image_bot, {"submission_ids": [str(self.submissions[0].pk)]})
            self.assertTrue(result2["success"])


class BotIntegrationTest(TestCase):
    """Test bot integration with moderation workflow."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123"
        )
        
        self.bot_service = BotService()
        
        # Create bot
        self.bot = TaskBot.objects.create(
            name="Integration Test Bot",
            bot_type=TaskType.IMAGE_SCANNER,
            status=BotStatus.IDLE,
            max_retries=3,
            created_by=self.user
        )
        
        # Create submissions
        self.submissions = []
        for i in range(10):
            submission = SuspiciousSubmission.objects.create(
                content_id=f"integration_test_{i}",
                submission_type=SubmissionType.IMAGE,
                user=self.user,
                status=ModerationStatus.PENDING
            )
            self.submissions.append(submission)
    
    @patch('api.auto_mod.services.BotService.run_image_scan')
    def test_full_bot_workflow(self, mock_scan):
        """Test complete bot workflow from start to finish."""
        mock_scan.return_value = {
            "status": "success",
            "processed": 10,
            "results": [
                {"submission_id": str(s.pk), "status": "approved", "confidence": 0.95}
                for s in self.submissions
            ]
        }
        
        # Start bot
        start_result = self.bot_service.start_bot(self.bot)
        self.assertTrue(start_result["success"])
        
        # Execute task
        task_data = {
            "submission_ids": [str(s.pk) for s in self.submissions]
        }
        
        execute_result = self.bot_service.execute_bot_task(self.bot, task_data)
        self.assertTrue(execute_result["success"])
        self.assertEqual(execute_result["processed"], 10)
        
        # Verify submissions were processed
        for submission in self.submissions:
            submission.refresh_from_db()
            self.assertNotEqual(submission.status, ModerationStatus.PENDING)
    
    @patch('api.auto_mod.services.BotService.run_image_scan')
    def test_bot_error_recovery(self, mock_scan):
        """Test bot error recovery and retry mechanism."""
        # First call fails, second succeeds
        mock_scan.side_effect = [
            Exception("Service unavailable"),
            {
                "status": "success",
                "processed": 5,
                "results": [
                    {"submission_id": str(s.pk), "status": "approved"}
                    for s in self.submissions[:5]
                ]
            }
        ]
        
        # First execution should fail
        task_data = {"submission_ids": [str(s.pk) for s in self.submissions[:5]]}
        result1 = self.bot_service.execute_bot_task(self.bot, task_data)
        self.assertFalse(result1["success"])
        self.assertEqual(self.bot.current_retry, 1)
        
        # Reset and retry
        self.bot.status = BotStatus.IDLE
        self.bot.save()
        
        result2 = self.bot_service.execute_bot_task(self.bot, task_data)
        self.assertTrue(result2["success"])
        self.assertEqual(result2["processed"], 5)
    
    def test_bot_concurrent_execution(self):
        """Test bot concurrent execution handling."""
        # Create second bot
        bot2 = TaskBot.objects.create(
            name="Concurrent Bot",
            bot_type=TaskType.IMAGE_SCANNER,
            status=BotStatus.IDLE,
            created_by=self.user
        )
        
        # Try to start both bots
        result1 = self.bot_service.start_bot(self.bot)
        result2 = self.bot_service.start_bot(bot2)
        
        self.assertTrue(result1["success"])
        self.assertTrue(result2["success"])
        
        # Both should be running
        self.bot.refresh_from_db()
        bot2.refresh_from_db()
        
        self.assertEqual(self.bot.status, BotStatus.RUNNING)
        self.assertEqual(bot2.status, BotStatus.RUNNING)
    
    @patch('api.auto_mod.services.BotService.run_image_scan')
    def test_bot_performance_monitoring(self, mock_scan):
        """Test bot performance monitoring."""
        import time
        
        def slow_scan(task_data):
            time.sleep(0.1)  # Simulate slow processing
            return {
                "status": "success",
                "processed": len(task_data["submission_ids"]),
                "results": [{"submission_id": sid, "status": "approved"} for sid in task_data["submission_ids"]]
            }
        
        mock_scan.side_effect = slow_scan
        
        # Start bot and execute task
        self.bot_service.start_bot(self.bot)
        
        start_time = timezone.now()
        task_data = {"submission_ids": [str(s.pk) for s in self.submissions[:3]]}
        result = self.bot_service.execute_bot_task(self.bot, task_data)
        end_time = timezone.now()
        
        self.assertTrue(result["success"])
        self.assertGreater((end_time - start_time).total_seconds(), 0.1)
        
        # Check bot runtime stats
        stats = self.bot.get_runtime_stats()
        self.assertIn("last_run_at", stats)
        self.assertIn("is_healthy", stats)
