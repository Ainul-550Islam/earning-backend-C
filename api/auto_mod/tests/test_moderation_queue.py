# =============================================================================
# auto_mod/tests/test_moderation_queue.py
# =============================================================================

"""
Tests for moderation queue functionality.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status

from ..choices import ModerationStatus, SubmissionType, QueuePriority
from ..models import ModerationQueue, SuspiciousSubmission
from api.auto_mod.services.ModerationQueueService import ModerationQueueService
from ..exceptions import QueueAssignmentError, QueueEscalationError

User = get_user_model()


class ModerationQueueModelTest(TestCase):
    """Test ModerationQueue model functionality."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123"
        )
        self.moderator = User.objects.create_user(
            username="moderator",
            email="mod@example.com",
            password="modpass123",
            is_staff=True
        )
        
        self.submission = SuspiciousSubmission.objects.create(
            content_id="test123",
            submission_type=SubmissionType.IMAGE,
            user=self.user,
            status=ModerationStatus.PENDING
        )
        
        self.queue_item = ModerationQueue.objects.create(
            submission=self.submission,
            priority=QueuePriority.NORMAL,
            assigned_to=self.moderator,
            assigned_by=self.moderator
        )
    
    def test_queue_item_creation(self):
        """Test basic queue item creation."""
        self.assertEqual(self.queue_item.submission, self.submission)
        self.assertEqual(self.queue_item.priority, QueuePriority.NORMAL)
        self.assertEqual(self.queue_item.assigned_to, self.moderator)
        self.assertEqual(self.queue_item.assigned_by, self.moderator)
        self.assertEqual(self.queue_item.escalation_level, 0)
        self.assertIsNotNone(self.queue_item.queued_at)
        self.assertIsNone(self.queue_item.completed_at)
    
    def test_queue_item_str_representation(self):
        """Test queue item string representation."""
        expected = f"Queue: {self.submission.content_id} ({self.queue_item.get_priority_display()})"
        self.assertEqual(str(self.queue_item), expected)
    
    def test_assign_to_moderator(self):
        """Test assigning queue item to moderator."""
        new_moderator = User.objects.create_user(
            username="newmod",
            email="newmod@example.com",
            password="newmodpass123",
            is_staff=True
        )
        
        self.queue_item.assign_to(new_moderator)
        self.queue_item.save()
        
        self.assertEqual(self.queue_item.assigned_to, new_moderator)
        self.assertEqual(self.queue_item.escalation_level, 0)
    
    def test_escalate_queue_item(self):
        """Test escalating queue item."""
        old_level = self.queue_item.escalation_level
        self.queue_item.escalate()
        self.queue_item.save()
        
        self.assertEqual(self.queue_item.escalation_level, old_level + 1)
        self.assertEqual(self.queue_item.priority, QueuePriority.HIGH)
    
    def test_is_overdue_property(self):
        """Test is_overdue property."""
        # Fresh item should not be overdue
        self.assertFalse(self.queue_item.is_overdue)
        
        # Make it overdue
        self.queue_item.queued_at = timezone.now() - timezone.timedelta(hours=25)
        self.queue_item.save()
        
        self.assertTrue(self.queue_item.is_overdue)
    
    def test_should_escalate_property(self):
        """Test should_escalate property."""
        # Fresh item should not need escalation
        self.assertFalse(self.queue_item.should_escalate)
        
        # Make it overdue and low priority
        self.queue_item.queued_at = timezone.now() - timezone.timedelta(hours=25)
        self.queue_item.priority = QueuePriority.LOW
        self.queue_item.save()
        
        self.assertTrue(self.queue_item.should_escalate)
    
    def test_complete_queue_item(self):
        """Test completing queue item."""
        self.queue_item.complete()
        self.queue_item.save()
        
        self.assertIsNotNone(self.queue_item.completed_at)
        self.assertEqual(self.queue_item.assigned_to, None)
    
    def test_get_queue_items_for_moderator(self):
        """Test getting queue items for moderator."""
        items = ModerationQueue.objects.get_queue_items_for_moderator(self.moderator)
        self.assertIn(self.queue_item, items)
        
        # Test with different moderator
        other_moderator = User.objects.create_user(
            username="othermod",
            email="othermod@example.com",
            password="othermodpass123",
            is_staff=True
        )
        
        items = ModerationQueue.objects.get_queue_items_for_moderator(other_moderator)
        self.assertNotIn(self.queue_item, items)
    
    def test_get_unassigned_items(self):
        """Test getting unassigned queue items."""
        # Create unassigned item
        unassigned_item = ModerationQueue.objects.create(
            submission=self.submission,
            priority=QueuePriority.HIGH,
            assigned_to=None,
            assigned_by=None
        )
        
        unassigned_items = ModerationQueue.objects.get_unassigned_items()
        self.assertIn(unassigned_item, unassigned_items)
        self.assertNotIn(self.queue_item, unassigned_items)
    
    def test_get_overdue_items(self):
        """Test getting overdue queue items."""
        # Create overdue item
        overdue_item = ModerationQueue.objects.create(
            submission=self.submission,
            priority=QueuePriority.LOW,
            assigned_to=self.moderator,
            assigned_by=self.moderator
        )
        overdue_item.queued_at = timezone.now() - timezone.timedelta(hours=25)
        overdue_item.save()
        
        overdue_items = ModerationQueue.objects.get_overdue_items()
        self.assertIn(overdue_item, overdue_items)
        self.assertNotIn(self.queue_item, overdue_items)


class ModerationQueueServiceTest(TestCase):
    """Test ModerationQueueService functionality."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123"
        )
        self.moderator = User.objects.create_user(
            username="moderator",
            email="mod@example.com",
            password="modpass123",
            is_staff=True
        )
        
        self.queue_service = ModerationQueueService()
        
        self.submission = SuspiciousSubmission.objects.create(
            content_id="test123",
            submission_type=SubmissionType.IMAGE,
            user=self.user,
            status=ModerationStatus.PENDING
        )
    
    def test_add_to_queue_success(self):
        """Test successfully adding submission to queue."""
        queue_item = self.queue_service.add_to_queue(
            submission=self.submission,
            priority=QueuePriority.HIGH,
            due_hours=12
        )
        
        self.assertEqual(queue_item.submission, self.submission)
        self.assertEqual(queue_item.priority, QueuePriority.HIGH)
        self.assertIsNotNone(queue_item.due_at)
        self.assertAlmostEqual(
            queue_item.due_at,
            timezone.now() + timezone.timedelta(hours=12),
            delta=timezone.timedelta(seconds=10)
        )
    
    def test_add_to_queue_already_queued(self):
        """Test adding already queued submission."""
        # First addition should succeed
        self.queue_service.add_to_queue(self.submission)
        
        # Second addition should return existing item
        queue_item = self.queue_service.add_to_queue(self.submission)
        
        self.assertEqual(ModerationQueue.objects.filter(submission=self.submission).count(), 1)
        self.assertEqual(queue_item.submission, self.submission)
    
    def test_assign_to_moderator_success(self):
        """Test successful moderator assignment."""
        queue_item = self.queue_service.add_to_queue(self.submission)
        
        updated_item = self.queue_service.assign_to_moderator(
            queue_item=queue_item,
            moderator=self.moderator,
            assigned_by=self.user,
            notes="Assignment note"
        )
        
        self.assertEqual(updated_item.assigned_to, self.moderator)
        self.assertEqual(updated_item.assigned_by, self.user)
        self.assertEqual(updated_item.processing_notes, "Assignment note")
        self.assertIsNotNone(updated_item.assigned_at)
    
    def test_assign_to_moderator_already_assigned(self):
        """Test assigning already assigned queue item."""
        queue_item = self.queue_service.add_to_queue(self.submission)
        queue_item.assign_to(self.moderator)
        queue_item.save()
        
        with self.assertRaises(QueueAssignmentError):
            self.queue_service.assign_to_moderator(
                queue_item=queue_item,
                moderator=self.moderator,
                assigned_by=self.user
            )
    
    def test_escalate_queue_item_success(self):
        """Test successful queue item escalation."""
        queue_item = self.queue_service.add_to_queue(self.submission)
        
        updated_item = self.queue_service.escalate_queue_item(
            queue_item=queue_item,
            new_priority=QueuePriority.CRITICAL,
            reason="Urgent review needed",
            escalated_by=self.user
        )
        
        self.assertEqual(updated_item.escalation_level, 1)
        self.assertEqual(updated_item.priority, QueuePriority.CRITICAL)
        self.assertIn("Urgent review needed", updated_item.processing_notes)
    
    def test_escalate_queue_item_max_level(self):
        """Test escalation beyond max level."""
        queue_item = self.queue_service.add_to_queue(self.submission)
        queue_item.escalation_level = 3  # Max level
        queue_item.save()
        
        with self.assertRaises(QueueEscalationError):
            self.queue_service.escalate_queue_item(
                queue_item=queue_item,
                escalated_by=self.user
            )
    
    def test_get_available_moderators(self):
        """Test getting available moderators."""
        # Create moderators with different workloads
        busy_moderator = User.objects.create_user(
            username="busymod",
            email="busymod@example.com",
            password="busymodpass123",
            is_staff=True
        )
        
        # Give busy moderator many assignments
        for i in range(15):
            submission = SuspiciousSubmission.objects.create(
                content_id=f"busy_test_{i}",
                submission_type=SubmissionType.IMAGE,
                user=self.user,
                status=ModerationStatus.PENDING
            )
            queue_item = self.queue_service.add_to_queue(submission)
            queue_item.assign_to(busy_moderator)
            queue_item.save()
        
        available_moderators = self.queue_service.get_available_moderators(
            submission_type=SubmissionType.IMAGE,
            max_workload=10
        )
        
        self.assertIn(self.moderator, available_moderators)
        self.assertNotIn(busy_moderator, available_moderators)
    
    def test_auto_assign_queue_items(self):
        """Test auto-assignment of queue items."""
        # Create multiple unassigned items
        submissions = []
        for i in range(5):
            submission = SuspiciousSubmission.objects.create(
                content_id=f"auto_test_{i}",
                submission_type=SubmissionType.IMAGE,
                user=self.user,
                status=ModerationStatus.PENDING
            )
            submissions.append(submission)
            self.queue_service.add_to_queue(submission)
        
        results = self.queue_service.auto_assign_queue_items(
            batch_size=5,
            submission_type=SubmissionType.IMAGE
        )
        
        self.assertGreater(results["assigned"], 0)
        self.assertLessEqual(results["assigned"], 5)
        self.assertGreaterEqual(results["unassigned"], 0)
    
    def test_get_overdue_items(self):
        """Test getting overdue queue items."""
        # Create overdue item
        overdue_submission = SuspiciousSubmission.objects.create(
            content_id="overdue_test",
            submission_type=SubmissionType.IMAGE,
            user=self.user,
            status=ModerationStatus.PENDING
        )
        overdue_item = self.queue_service.add_to_queue(overdue_submission)
        overdue_item.queued_at = timezone.now() - timezone.timedelta(hours=25)
        overdue_item.save()
        
        overdue_items = self.queue_service.get_overdue_items()
        
        self.assertIn(overdue_item, overdue_items)
    
    def test_escalate_overdue_items(self):
        """Test escalating overdue items."""
        # Create overdue item
        overdue_submission = SuspiciousSubmission.objects.create(
            content_id="overdue_escalate",
            submission_type=SubmissionType.IMAGE,
            user=self.user,
            status=ModerationStatus.PENDING
        )
        overdue_item = self.queue_service.add_to_queue(overdue_submission)
        overdue_item.queued_at = timezone.now() - timezone.timedelta(hours=25)
        overdue_item.save()
        
        results = self.queue_service.escalate_overdue_items()
        
        self.assertGreater(results["escalated"], 0)
        
        # Check item was escalated
        overdue_item.refresh_from_db()
        self.assertGreater(overdue_item.escalation_level, 0)
    
    def test_get_queue_statistics(self):
        """Test queue statistics retrieval."""
        # Create items with different statuses
        high_priority_item = self.queue_service.add_to_queue(
            self.submission,
            priority=QueuePriority.HIGH
        )
        
        assigned_item = self.queue_service.add_to_queue(
            SuspiciousSubmission.objects.create(
                content_id="assigned_test",
                submission_type=SubmissionType.IMAGE,
                user=self.user,
                status=ModerationStatus.PENDING
            )
        )
        assigned_item.assign_to(self.moderator)
        assigned_item.save()
        
        stats = self.queue_service.get_queue_statistics()
        
        self.assertIn("total_items", stats)
        self.assertIn("by_priority", stats)
        self.assertIn("by_status", stats)
        self.assertIn("by_escalation_level", stats)
        self.assertIn("average_wait_time", stats)
        self.assertIn("overdue_count", stats)
        self.assertGreater(stats["total_items"], 0)
    
    def test_release_queue_item(self):
        """Test releasing queue item."""
        queue_item = self.queue_service.add_to_queue(self.submission)
        queue_item.assign_to(self.moderator)
        queue_item.save()
        
        updated_item = self.queue_service.release_queue_item(
            queue_item=queue_item,
            released_by=self.user,
            reason="Moderator unavailable"
        )
        
        self.assertIsNone(updated_item.assigned_to)
        self.assertIsNone(updated_item.assigned_at)
        self.assertIn("released", updated_item.processing_notes.lower())
    
    def test_get_queue_items_for_moderator(self):
        """Test getting queue items for specific moderator."""
        # Create items assigned to moderator
        assigned_items = []
        for i in range(3):
            submission = SuspiciousSubmission.objects.create(
                content_id=f"mod_test_{i}",
                submission_type=SubmissionType.IMAGE,
                user=self.user,
                status=ModerationStatus.PENDING
            )
            queue_item = self.queue_service.add_to_queue(submission)
            queue_item.assign_to(self.moderator)
            queue_item.save()
            assigned_items.append(queue_item)
        
        items = self.queue_service.get_queue_items_for_moderator(
            moderator=self.moderator,
            limit=10,
            include_completed=False
        )
        
        self.assertEqual(len(items), 3)
        for item in assigned_items:
            self.assertIn(item, items)


class ModerationQueueAPITest(TestCase):
    """Test ModerationQueue API endpoints."""
    
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123"
        )
        self.moderator = User.objects.create_user(
            username="moderator",
            email="mod@example.com",
            password="modpass123",
            is_staff=True
        )
        
        self.submission = SuspiciousSubmission.objects.create(
            content_id="test123",
            submission_type=SubmissionType.IMAGE,
            user=self.user,
            status=ModerationStatus.PENDING
        )
        
        self.queue_item = ModerationQueue.objects.create(
            submission=self.submission,
            priority=QueuePriority.NORMAL,
            assigned_to=None
        )
    
    def test_list_queue_items_unauthorized(self):
        """Test listing queue items without authentication."""
        response = self.client.get("/api/auto_mod/queue/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_list_queue_items_non_moderator(self):
        """Test listing queue items as non-moderator."""
        self.client.force_authenticate(user=self.user)
        response = self.client.get("/api/auto_mod/queue/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_list_queue_items_moderator(self):
        """Test listing queue items as moderator."""
        self.client.force_authenticate(user=self.moderator)
        response = self.client.get("/api/auto_mod/queue/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
    
    def test_retrieve_queue_item(self):
        """Test retrieving a specific queue item."""
        self.client.force_authenticate(user=self.moderator)
        response = self.client.get(f"/api/auto_mod/queue/{self.queue_item.pk}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], str(self.queue_item.pk))
    
    def test_create_queue_item(self):
        """Test creating a new queue item."""
        self.client.force_authenticate(user=self.moderator)
        
        data = {
            "submission": str(self.submission.pk),
            "priority": QueuePriority.HIGH,
            "due_hours": 6
        }
        
        response = self.client.post("/api/auto_mod/queue/", data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(ModerationQueue.objects.count(), 2)
    
    def test_assign_queue_item(self):
        """Test assigning queue item action."""
        self.client.force_authenticate(user=self.moderator)
        
        response = self.client.post(f"/api/auto_mod/queue/{self.queue_item.pk}/assign/", {
            "moderator_id": str(self.moderator.pk),
            "notes": "Assign to myself"
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.queue_item.refresh_from_db()
        self.assertEqual(self.queue_item.assigned_to, self.moderator)
    
    def test_escalate_queue_item(self):
        """Test escalating queue item action."""
        self.client.force_authenticate(user=self.moderator)
        
        response = self.client.post(f"/api/auto_mod/queue/{self.queue_item.pk}/escalate/", {
            "priority": QueuePriority.CRITICAL,
            "reason": "Urgent review needed"
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.queue_item.refresh_from_db()
        self.assertEqual(self.queue_item.priority, QueuePriority.CRITICAL)
        self.assertGreater(self.queue_item.escalation_level, 0)
    
    def test_release_queue_item(self):
        """Test releasing queue item action."""
        self.client.force_authenticate(user=self.moderator)
        
        # First assign the item
        self.queue_item.assign_to(self.moderator)
        self.queue_item.save()
        
        response = self.client.post(f"/api/auto_mod/queue/{self.queue_item.pk}/release/", {
            "reason": "Moderator unavailable"
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.queue_item.refresh_from_db()
        self.assertIsNone(self.queue_item.assigned_to)
    
    def test_prioritize_queue_item(self):
        """Test changing queue item priority."""
        self.client.force_authenticate(user=self.moderator)
        
        response = self.client.post(f"/api/auto_mod/queue/{self.queue_item.pk}/prioritize/", {
            "priority": QueuePriority.HIGH,
            "reason": "Priority change"
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.queue_item.refresh_from_db()
        self.assertEqual(self.queue_item.priority, QueuePriority.HIGH)
    
    def test_my_queue(self):
        """Test getting current user's queue items."""
        self.client.force_authenticate(user=self.moderator)
        
        # Assign item to moderator
        self.queue_item.assign_to(self.moderator)
        self.queue_item.save()
        
        response = self.client.get("/api/auto_mod/queue/my-queue/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
    
    def test_queue_statistics(self):
        """Test queue statistics endpoint."""
        self.client.force_authenticate(user=self.moderator)
        
        response = self.client.get("/api/auto_mod/queue/statistics/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("total_items", response.data)
    
    def test_auto_assign_queue_items(self):
        """Test auto-assign queue items endpoint."""
        self.client.force_authenticate(user=self.moderator)
        
        response = self.client.post("/api/auto_mod/queue/auto-assign/", {
            "batch_size": 10,
            "submission_type": SubmissionType.IMAGE
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("assigned", response.data)
    
    def test_escalate_overdue_items(self):
        """Test escalate overdue items endpoint."""
        self.client.force_authenticate(user=self.moderator)
        
        # Create overdue item
        overdue_item = ModerationQueue.objects.create(
            submission=self.submission,
            priority=QueuePriority.LOW,
            queued_at=timezone.now() - timezone.timedelta(hours=25)
        )
        
        response = self.client.post("/api/auto_mod/queue/escalate-overdue/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("escalated", response.data)
    
    def test_available_moderators(self):
        """Test available moderators endpoint."""
        self.client.force_authenticate(user=self.moderator)
        
        response = self.client.get("/api/auto_mod/queue/available-moderators/", {
            "submission_type": SubmissionType.IMAGE,
            "max_workload": 10
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, list)


class QueueIntegrationTest(TestCase):
    """Test queue integration with moderation workflow."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123"
        )
        self.moderator = User.objects.create_user(
            username="moderator",
            email="mod@example.com",
            password="modpass123",
            is_staff=True
        )
        
        self.queue_service = ModerationQueueService()
        
        # Create test submissions
        self.submissions = []
        for i in range(10):
            submission = SuspiciousSubmission.objects.create(
                content_id=f"integration_test_{i}",
                submission_type=SubmissionType.IMAGE,
                user=self.user,
                status=ModerationStatus.PENDING
            )
            self.submissions.append(submission)
    
    def test_full_queue_workflow(self):
        """Test complete queue workflow from creation to completion."""
        # Add to queue
        queue_item = self.queue_service.add_to_queue(
            submission=self.submissions[0],
            priority=QueuePriority.HIGH
        )
        
        # Assign to moderator
        assigned_item = self.queue_service.assign_to_moderator(
            queue_item=queue_item,
            moderator=self.moderator,
            assigned_by=self.user
        )
        
        # Complete the item
        assigned_item.complete()
        assigned_item.save()
        
        # Verify workflow
        self.assertEqual(assigned_item.assigned_to, self.moderator)
        self.assertIsNotNone(assigned_item.completed_at)
        self.assertIsNone(assigned_item.assigned_to)  # Should be None after completion
    
    def test_queue_escalation_workflow(self):
        """Test queue escalation workflow."""
        # Add item to queue
        queue_item = self.queue_service.add_to_queue(
            submission=self.submissions[0],
            priority=QueuePriority.LOW
        )
        
        # Make it overdue
        queue_item.queued_at = timezone.now() - timezone.timedelta(hours=25)
        queue_item.save()
        
        # Escalate
        escalated_item = self.queue_service.escalate_queue_item(
            queue_item=queue_item,
            escalated_by=self.user,
            reason="Overdue item"
        )
        
        # Verify escalation
        self.assertGreater(escalated_item.escalation_level, 0)
        self.assertEqual(escalated_item.priority, QueuePriority.HIGH)
    
    def test_auto_assignment_workflow(self):
        """Test auto-assignment workflow."""
        # Add multiple items to queue
        queue_items = []
        for submission in self.submissions[:5]:
            item = self.queue_service.add_to_queue(submission)
            queue_items.append(item)
        
        # Auto-assign
        results = self.queue_service.auto_assign_queue_items(
            batch_size=5,
            submission_type=SubmissionType.IMAGE
        )
        
        # Verify assignments
        self.assertGreater(results["assigned"], 0)
        
        # Check that assigned items have moderators
        assigned_count = ModerationQueue.objects.filter(
            assigned_to__isnull=False
        ).count()
        self.assertGreater(assigned_count, 0)
    
    def test_workload_balancing(self):
        """Test moderator workload balancing."""
        # Create second moderator
        moderator2 = User.objects.create_user(
            username="moderator2",
            email="mod2@example.com",
            password="mod2pass123",
            is_staff=True
        )
        
        # Give first moderator some assignments
        for i in range(3):
            queue_item = self.queue_service.add_to_queue(self.submissions[i])
            queue_item.assign_to(self.moderator)
            queue_item.save()
        
        # Auto-assign remaining items
        results = self.queue_service.auto_assign_queue_items(
            batch_size=5,
            submission_type=SubmissionType.IMAGE
        )
        
        # Check workload distribution
        moderator1_count = ModerationQueue.objects.filter(
            assigned_to=self.moderator
        ).count()
        moderator2_count = ModerationQueue.objects.filter(
            assigned_to=moderator2
        ).count()
        
        # Workload should be balanced
        self.assertGreaterEqual(moderator2_count, moderator1_count - 1)
    
    def test_queue_performance_monitoring(self):
        """Test queue performance monitoring."""
        import time
        
        # Add items and measure processing time
        start_time = timezone.now()
        
        for submission in self.submissions[:5]:
            self.queue_service.add_to_queue(submission)
        
        # Auto-assign
        self.queue_service.auto_assign_queue_items(
            batch_size=5,
            submission_type=SubmissionType.IMAGE
        )
        
        end_time = timezone.now()
        processing_time = (end_time - start_time).total_seconds()
        
        # Get statistics
        stats = self.queue_service.get_queue_statistics()
        
        self.assertIn("average_wait_time", stats)
        self.assertGreater(stats["total_items"], 0)
        self.assertLess(processing_time, 5.0)  # Should complete within 5 seconds


class QueueSignalTest(TestCase):
    """Test queue signal handling."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123"
        )
        self.moderator = User.objects.create_user(
            username="moderator",
            email="mod@example.com",
            password="modpass123",
            is_staff=True
        )
        
        self.queue_service = ModerationQueueService()
        
        self.submission = SuspiciousSubmission.objects.create(
            content_id="signal_test",
            submission_type=SubmissionType.IMAGE,
            user=self.user,
            status=ModerationStatus.PENDING
        )
    
    @patch('api.auto_mod.signals.queue_item_assigned')
    def test_queue_item_assigned_signal(self, mock_signal):
        """Test queue item assigned signal."""
        queue_item = self.queue_service.add_to_queue(self.submission)
        
        self.queue_service.assign_to_moderator(
            queue_item=queue_item,
            moderator=self.moderator,
            assigned_by=self.user
        )
        
        # Verify signal was sent
        mock_signal.assert_called_once()
        call_args = mock_signal.call_args[1]
        self.assertEqual(call_args['queue_item'], queue_item)
        self.assertEqual(call_args['assigned_to'], self.moderator)
        self.assertEqual(call_args['assigned_by'], self.user)
    
    @patch('api.auto_mod.signals.queue_item_escalated')
    def test_queue_item_escalated_signal(self, mock_signal):
        """Test queue item escalated signal."""
        queue_item = self.queue_service.add_to_queue(self.submission)
        
        self.queue_service.escalate_queue_item(
            queue_item=queue_item,
            escalated_by=self.user,
            reason="Test escalation"
        )
        
        # Verify signal was sent
        mock_signal.assert_called_once()
        call_args = mock_signal.call_args[1]
        self.assertEqual(call_args['queue_item'], queue_item)
        self.assertEqual(call_args['old_level'], 0)
        self.assertEqual(call_args['new_level'], 1)
        self.assertEqual(call_args['reason'], "Test escalation")
    
    @patch('api.auto_mod.signals.queue_item_completed')
    def test_queue_item_completed_signal(self, mock_signal):
        """Test queue item completed signal."""
        queue_item = self.queue_service.add_to_queue(self.submission)
        queue_item.assign_to(self.moderator)
        queue_item.save()
        
        queue_item.complete()
        queue_item.save()
        
        # Verify signal was sent
        mock_signal.assert_called_once()
        call_args = mock_signal.call_args[1]
        self.assertEqual(call_args['queue_item'], queue_item)
        self.assertEqual(call_args['completed_by'], self.moderator)
