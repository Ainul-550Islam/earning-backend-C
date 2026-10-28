# =============================================================================
# auto_mod/tests/test_proof_scanner.py
# =============================================================================

"""
Tests for proof scanner functionality.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status

from ..choices import ScanType, ScanStatus, SubmissionType, ModerationStatus
from ..models import ProofScanner, SuspiciousSubmission
from api.auto_mod.services import BotService
from ..exceptions import ScanFailedError, OCRExtractionError

User = get_user_model()


class ProofScannerModelTest(TestCase):
    """Test ProofScanner model functionality."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123"
        )
        
        self.submission = SuspiciousSubmission.objects.create(
            content_id="test123",
            submission_type=SubmissionType.IMAGE,
            user=self.user,
            status=ModerationStatus.PENDING
        )
        
        self.scanner = ProofScanner.objects.create(
            submission=self.submission,
            scan_type=ScanType.OCR,
            status=ScanStatus.PENDING,
            initiated_by=self.user
        )
    
    def test_scanner_creation(self):
        """Test basic scanner creation."""
        self.assertEqual(self.scanner.submission, self.submission)
        self.assertEqual(self.scanner.scan_type, ScanType.OCR)
        self.assertEqual(self.scanner.status, ScanStatus.PENDING)
        self.assertEqual(self.scanner.initiated_by, self.user)
        self.assertIsNotNone(self.scanner.started_at)
        self.assertIsNone(self.scanner.completed_at)
        self.assertIsNone(self.scanner.result_data)
    
    def test_scanner_str_representation(self):
        """Test scanner string representation."""
        expected = f"{self.scanner.get_scan_type_display()} - {self.submission.content_id}"
        self.assertEqual(str(self.scanner), expected)
    
    def test_mark_completed_success(self):
        """Test marking scanner as completed successfully."""
        result_data = {"extracted_text": "Sample text", "confidence": 0.95}
        
        self.scanner.mark_completed(ScanStatus.SUCCESS, result_data)
        
        self.assertEqual(self.scanner.status, ScanStatus.SUCCESS)
        self.assertEqual(self.scanner.result_data, result_data)
        self.assertIsNotNone(self.scanner.completed_at)
        self.assertGreater(self.scanner.duration_seconds, 0)
    
    def test_mark_completed_failed(self):
        """Test marking scanner as failed."""
        error_message = "OCR processing failed"
        
        self.scanner.mark_completed(ScanStatus.FAILED, {"error": error_message})
        
        self.assertEqual(self.scanner.status, ScanStatus.FAILED)
        self.assertEqual(self.scanner.result_data, {"error": error_message})
        self.assertIsNotNone(self.scanner.completed_at)
    
    def test_duration_calculation(self):
        """Test duration calculation."""
        # Mark as completed after some time
        import time
        time.sleep(0.1)  # Small delay
        
        self.scanner.mark_completed(ScanStatus.SUCCESS, {"test": "data"})
        
        self.assertGreater(self.scanner.duration_seconds, 0)
        self.assertLess(self.scanner.duration_seconds, 1)  # Should be less than 1 second
    
    def test_duration_not_completed(self):
        """Test duration calculation for incomplete scan."""
        self.assertIsNone(self.scanner.duration_seconds)
    
    def test_for_submission_queryset(self):
        """Test for_submission queryset method."""
        qs = ProofScanner.objects.for_submission(self.submission)
        self.assertIn(self.scanner, qs)
        
        # Create another submission
        other_submission = SuspiciousSubmission.objects.create(
            content_id="other123",
            submission_type=SubmissionType.IMAGE,
            user=self.user,
            status=ModerationStatus.PENDING
        )
        
        qs = ProofScanner.objects.for_submission(other_submission)
        self.assertNotIn(self.scanner, qs)
    
    def test_by_status_queryset(self):
        """Test by_status queryset method."""
        qs = ProofScanner.objects.by_status(ScanStatus.PENDING)
        self.assertIn(self.scanner, qs)
        
        # Complete the scanner
        self.scanner.mark_completed(ScanStatus.SUCCESS, {"test": "data"})
        
        qs = ProofScanner.objects.by_status(ScanStatus.PENDING)
        self.assertNotIn(self.scanner, qs)
        
        qs = ProofScanner.objects.by_status(ScanStatus.SUCCESS)
        self.assertIn(self.scanner, qs)
    
    def test_recent_queryset(self):
        """Test recent queryset method."""
        qs = ProofScanner.objects.recent()
        self.assertIn(self.scanner, qs)
        
        # Create old scanner
        old_time = timezone.now() - timezone.timedelta(hours=25)
        old_scanner = ProofScanner.objects.create(
            submission=self.submission,
            scan_type=ScanType.OCR,
            status=ScanStatus.PENDING,
            initiated_by=self.user,
            started_at=old_time
        )
        
        qs = ProofScanner.objects.recent()
        self.assertIn(self.scanner, qs)
        self.assertNotIn(old_scanner, qs)


class ProofScannerServiceTest(TestCase):
    """Test proof scanner service functionality."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123"
        )
        
        self.submission = SuspiciousSubmission.objects.create(
            content_id="test123",
            submission_type=SubmissionType.IMAGE,
            user=self.user,
            status=ModerationStatus.PENDING
        )
        
        self.bot_service = BotService()
    
    @patch('api.auto_mod.services.BotService.run_ocr_scan')
    def test_initiate_ocr_scan_success(self, mock_ocr_scan):
        """Test successful OCR scan initiation."""
        mock_ocr_scan.return_value = {
            "status": "success",
            "extracted_text": "Sample OCR text",
            "confidence": 0.95
        }
        
        scanner = self.bot_service.initiate_ocr_scan(self.submission, self.user)
        
        self.assertEqual(scanner.submission, self.submission)
        self.assertEqual(scanner.scan_type, ScanType.OCR)
        self.assertEqual(scanner.initiated_by, self.user)
        self.assertEqual(scanner.status, ScanStatus.SUCCESS)
        self.assertIn("extracted_text", scanner.result_data)
        self.assertIsNotNone(scanner.completed_at)
        
        mock_ocr_scan.assert_called_once_with(self.submission)
    
    @patch('api.auto_mod.services.BotService.run_ocr_scan')
    def test_initiate_ocr_scan_failure(self, mock_ocr_scan):
        """Test OCR scan failure."""
        mock_ocr_scan.side_effect = OCRExtractionError("OCR failed")
        
        scanner = self.bot_service.initiate_ocr_scan(self.submission, self.user)
        
        self.assertEqual(scanner.status, ScanStatus.FAILED)
        self.assertIn("error", scanner.result_data)
        self.assertIsNotNone(scanner.completed_at)
    
    @patch('api.auto_mod.services.BotService.run_image_analysis')
    def test_initiate_image_analysis_success(self, mock_image_analysis):
        """Test successful image analysis initiation."""
        mock_image_analysis.return_value = {
            "status": "success",
            "analysis": {
                "objects": ["person", "car"],
                "confidence": 0.87,
                "suspicious_content": False
            }
        }
        
        scanner = self.bot_service.initiate_image_analysis(self.submission, self.user)
        
        self.assertEqual(scanner.scan_type, ScanType.IMAGE_ANALYSIS)
        self.assertEqual(scanner.status, ScanStatus.SUCCESS)
        self.assertIn("analysis", scanner.result_data)
        
        mock_image_analysis.assert_called_once_with(self.submission)
    
    @patch('api.auto_mod.services.BotService.run_image_analysis')
    def test_initiate_image_analysis_failure(self, mock_image_analysis):
        """Test image analysis failure."""
        mock_image_analysis.side_effect = ScanFailedError("Analysis failed")
        
        scanner = self.bot_service.initiate_image_analysis(self.submission, self.user)
        
        self.assertEqual(scanner.status, ScanStatus.FAILED)
        self.assertIn("error", scanner.result_data)
    
    @patch('api.auto_mod.services.BotService.run_text_analysis')
    def test_initiate_text_analysis_success(self, mock_text_analysis):
        """Test successful text analysis initiation."""
        mock_text_analysis.return_value = {
            "status": "success",
            "analysis": {
                "sentiment": "neutral",
                "toxicity_score": 0.1,
                "spam_probability": 0.05
            }
        }
        
        scanner = self.bot_service.initiate_text_analysis(self.submission, self.user)
        
        self.assertEqual(scanner.scan_type, ScanType.TEXT_ANALYSIS)
        self.assertEqual(scanner.status, ScanStatus.SUCCESS)
        self.assertIn("analysis", scanner.result_data)
        
        mock_text_analysis.assert_called_once_with(self.submission)
    
    def test_initiate_scan_invalid_type(self):
        """Test initiating scan with invalid type."""
        with self.assertRaises(ValueError):
            self.bot_service.initiate_scan(self.submission, "invalid_type", self.user)
    
    def test_get_scan_statistics(self):
        """Test scan statistics retrieval."""
        # Create various scanners
        ProofScanner.objects.create(
            submission=self.submission,
            scan_type=ScanType.OCR,
            status=ScanStatus.SUCCESS,
            initiated_by=self.user
        )
        
        ProofScanner.objects.create(
            submission=self.submission,
            scan_type=ScanType.IMAGE_ANALYSIS,
            status=ScanStatus.FAILED,
            initiated_by=self.user
        )
        
        stats = self.bot_service.get_scan_statistics()
        
        self.assertIn("total_scans", stats)
        self.assertIn("status_breakdown", stats)
        self.assertIn("type_breakdown", stats)
        self.assertIn("avg_duration", stats)
        self.assertGreater(stats["total_scans"], 0)


class ProofScannerAPITest(TestCase):
    """Test ProofScanner API endpoints."""
    
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
        
        self.submission = SuspiciousSubmission.objects.create(
            content_id="test123",
            submission_type=SubmissionType.IMAGE,
            user=self.user,
            status=ModerationStatus.PENDING
        )
        
        self.scanner = ProofScanner.objects.create(
            submission=self.submission,
            scan_type=ScanType.OCR,
            status=ScanStatus.PENDING,
            initiated_by=self.staff_user
        )
    
    def test_list_scanners_unauthorized(self):
        """Test listing scanners without authentication."""
        response = self.client.get("/api/auto_mod/scanners/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_list_scanners_authorized(self):
        """Test listing scanners with authentication."""
        self.client.force_authenticate(user=self.user)
        response = self.client.get("/api/auto_mod/scanners/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
    
    def test_retrieve_scanner(self):
        """Test retrieving a specific scanner."""
        self.client.force_authenticate(user=self.user)
        response = self.client.get(f"/api/auto_mod/scanners/{self.scanner.pk}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], str(self.scanner.pk))
    
    def test_create_scanner(self):
        """Test creating a new scanner."""
        self.client.force_authenticate(user=self.staff_user)
        
        data = {
            "submission": str(self.submission.pk),
            "scan_type": ScanType.OCR
        }
        
        response = self.client.post("/api/auto_mod/scanners/", data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(ProofScanner.objects.count(), 2)
    
    def test_create_scanner_non_staff(self):
        """Test creating scanner as non-staff user."""
        self.client.force_authenticate(user=self.user)
        
        data = {
            "submission": str(self.submission.pk),
            "scan_type": ScanType.OCR
        }
        
        response = self.client.post("/api/auto_mod/scanners/", data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_run_ocr_scan(self):
        """Test running OCR scan action."""
        self.client.force_authenticate(user=self.staff_user)
        
        with patch('api.auto_mod.services.BotService.run_ocr_scan') as mock_ocr:
            mock_ocr.return_value = {
                "status": "success",
                "extracted_text": "Sample text",
                "confidence": 0.95
            }
            
            response = self.client.post(f"/api/auto_mod/scanners/{self.scanner.pk}/run_ocr/")
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertIn("extracted_text", response.data)
    
    def test_run_image_analysis(self):
        """Test running image analysis action."""
        self.client.force_authenticate(user=self.staff_user)
        
        with patch('api.auto_mod.services.BotService.run_image_analysis') as mock_analysis:
            mock_analysis.return_value = {
                "status": "success",
                "analysis": {"objects": ["person"], "confidence": 0.87}
            }
            
            response = self.client.post(f"/api/auto_mod/scanners/{self.scanner.pk}/run_image_analysis/")
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertIn("analysis", response.data)
    
    def test_run_text_analysis(self):
        """Test running text analysis action."""
        self.client.force_authenticate(user=self.staff_user)
        
        with patch('api.auto_mod.services.BotService.run_text_analysis') as mock_analysis:
            mock_analysis.return_value = {
                "status": "success",
                "analysis": {"sentiment": "neutral", "toxicity": 0.1}
            }
            
            response = self.client.post(f"/api/auto_mod/scanners/{self.scanner.pk}/run_text_analysis/")
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertIn("analysis", response.data)
    
    def test_scan_statistics(self):
        """Test scan statistics endpoint."""
        self.client.force_authenticate(user=self.staff_user)
        
        response = self.client.get("/api/auto_mod/scanners/statistics/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("total_scans", response.data)


class ScanIntegrationTest(TestCase):
    """Test scan integration with submission workflow."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123"
        )
        
        self.submission = SuspiciousSubmission.objects.create(
            content_id="test123",
            submission_type=SubmissionType.IMAGE,
            user=self.user,
            status=ModerationStatus.PENDING
        )
    
    @patch('api.auto_mod.services.BotService.run_ocr_scan')
    def test_submission_scan_workflow(self, mock_ocr_scan):
        """Test complete submission scan workflow."""
        mock_ocr_scan.return_value = {
            "status": "success",
            "extracted_text": "Sample OCR text",
            "confidence": 0.95
        }
        
        # Initiate scan
        bot_service = BotService()
        scanner = bot_service.initiate_ocr_scan(self.submission, self.user)
        
        # Verify scanner created and completed
        self.assertEqual(scanner.status, ScanStatus.SUCCESS)
        self.assertIsNotNone(scanner.completed_at)
        
        # Verify submission updated with scan results
        self.submission.refresh_from_db()
        self.assertIn("ocr_text", self.submission.metadata)
        self.assertEqual(self.submission.metadata["ocr_text"], "Sample OCR text")
    
    @patch('api.auto_mod.services.BotService.run_ocr_scan')
    @patch('api.auto_mod.services.BotService.run_image_analysis')
    def test_multiple_scans_workflow(self, mock_image_analysis, mock_ocr_scan):
        """Test multiple scans for a submission."""
        mock_ocr_scan.return_value = {
            "status": "success",
            "extracted_text": "Sample OCR text",
            "confidence": 0.95
        }
        
        mock_image_analysis.return_value = {
            "status": "success",
            "analysis": {
                "objects": ["person", "car"],
                "confidence": 0.87,
                "suspicious_content": False
            }
        }
        
        bot_service = BotService()
        
        # Run OCR scan
        ocr_scanner = bot_service.initiate_ocr_scan(self.submission, self.user)
        
        # Run image analysis
        image_scanner = bot_service.initiate_image_analysis(self.submission, self.user)
        
        # Verify both scans completed
        self.assertEqual(ocr_scanner.status, ScanStatus.SUCCESS)
        self.assertEqual(image_scanner.status, ScanStatus.SUCCESS)
        
        # Verify submission has both scan results
        self.submission.refresh_from_db()
        self.assertIn("ocr_text", self.submission.metadata)
        self.assertIn("image_analysis", self.submission.metadata)
    
    def test_scan_failure_handling(self):
        """Test handling of scan failures."""
        with patch('api.auto_mod.services.BotService.run_ocr_scan') as mock_ocr:
            mock_ocr.side_effect = OCRExtractionError("OCR service unavailable")
            
            bot_service = BotService()
            scanner = bot_service.initiate_ocr_scan(self.submission, self.user)
            
            # Verify scan marked as failed
            self.assertEqual(scanner.status, ScanStatus.FAILED)
            self.assertIn("error", scanner.result_data)
            
            # Verify submission not updated with scan results
            self.submission.refresh_from_db()
            self.assertNotIn("ocr_text", self.submission.metadata)
    
    def test_scan_timeout_handling(self):
        """Test handling of scan timeouts."""
        with patch('api.auto_mod.services.BotService.run_ocr_scan') as mock_ocr:
            mock_ocr.side_effect = TimeoutError("Scan timeout")
            
            bot_service = BotService()
            scanner = bot_service.initiate_ocr_scan(self.submission, self.user)
            
            # Verify scan marked as failed
            self.assertEqual(scanner.status, ScanStatus.FAILED)
            self.assertIn("timeout", scanner.result_data["error"].lower())
    
    def test_scan_retry_mechanism(self):
        """Test scan retry mechanism."""
        with patch('api.auto_mod.services.BotService.run_ocr_scan') as mock_ocr:
            # First call fails, second succeeds
            mock_ocr.side_effect = [
                OCRExtractionError("Temporary failure"),
                {
                    "status": "success",
                    "extracted_text": "Sample OCR text",
                    "confidence": 0.95
                }
            ]
            
            bot_service = BotService()
            
            # First attempt
            scanner1 = bot_service.initiate_ocr_scan(self.submission, self.user)
            self.assertEqual(scanner1.status, ScanStatus.FAILED)
            
            # Retry attempt
            scanner2 = bot_service.initiate_ocr_scan(self.submission, self.user)
            self.assertEqual(scanner2.status, ScanStatus.SUCCESS)
            self.assertIn("extracted_text", scanner2.result_data)


class ScanPerformanceTest(TestCase):
    """Test scan performance and optimization."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123"
        )
        
        # Create multiple submissions for batch testing
        self.submissions = []
        for i in range(10):
            submission = SuspiciousSubmission.objects.create(
                content_id=f"test{i}",
                submission_type=SubmissionType.IMAGE,
                user=self.user,
                status=ModerationStatus.PENDING
            )
            self.submissions.append(submission)
    
    @patch('api.auto_mod.services.BotService.run_ocr_scan')
    def test_batch_scan_performance(self, mock_ocr_scan):
        """Test batch scan performance."""
        mock_ocr_scan.return_value = {
            "status": "success",
            "extracted_text": "Sample text",
            "confidence": 0.95
        }
        
        bot_service = BotService()
        
        # Run scans in batch
        scanners = []
        for submission in self.submissions:
            scanner = bot_service.initiate_ocr_scan(submission, self.user)
            scanners.append(scanner)
        
        # Verify all scans completed successfully
        successful_scans = [s for s in scanners if s.status == ScanStatus.SUCCESS]
        self.assertEqual(len(successful_scans), len(self.submissions))
        
        # Verify mock was called correct number of times
        self.assertEqual(mock_ocr_scan.call_count, len(self.submissions))
    
    def test_scan_duration_tracking(self):
        """Test scan duration tracking accuracy."""
        with patch('api.auto_mod.services.BotService.run_ocr_scan') as mock_ocr:
            # Simulate scan taking some time
            import time
            def slow_scan(submission):
                time.sleep(0.1)  # 100ms delay
                return {
                    "status": "success",
                    "extracted_text": "Sample text",
                    "confidence": 0.95
                }
            
            mock_ocr.side_effect = slow_scan
            
            bot_service = BotService()
            scanner = bot_service.initiate_ocr_scan(self.submissions[0], self.user)
            
            # Verify duration is tracked accurately
            self.assertIsNotNone(scanner.duration_seconds)
            self.assertGreater(scanner.duration_seconds, 0.05)  # At least 50ms
            self.assertLess(scanner.duration_seconds, 1.0)     # Less than 1 second
    
    def test_concurrent_scans(self):
        """Test handling of concurrent scans."""
        with patch('api.auto_mod.services.BotService.run_ocr_scan') as mock_ocr:
            mock_ocr.return_value = {
                "status": "success",
                "extracted_text": "Sample text",
                "confidence": 0.95
            }
            
            bot_service = BotService()
            
            # Start multiple scans concurrently
            import threading
            scanners = []
            
            def run_scan(submission):
                scanner = bot_service.initiate_ocr_scan(submission, self.user)
                scanners.append(scanner)
            
            threads = []
            for submission in self.submissions[:5]:  # Test with 5 submissions
                thread = threading.Thread(target=run_scan, args=(submission,))
                threads.append(thread)
                thread.start()
            
            # Wait for all threads to complete
            for thread in threads:
                thread.join()
            
            # Verify all scans completed
            self.assertEqual(len(scanners), 5)
            successful_scans = [s for s in scanners if s.status == ScanStatus.SUCCESS]
            self.assertEqual(len(successful_scans), 5)
