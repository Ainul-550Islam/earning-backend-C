# =============================================================================
# auto_mod/middleware.py
# =============================================================================

"""
Middleware for automatic content moderation.
"""

import json
import logging
from django.utils.deprecation import MiddlewareMixin
from django.http import JsonResponse
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.exceptions import PermissionDenied

from .models import SuspiciousSubmission, ProofScanner
from .choices import SubmissionType, ModerationStatus, ScanType
from api.auto_mod.services import BotService, AutoApprovalService
from .validators import validate_submission_data, validate_rate_limit
from .exceptions import InvalidSubmissionError, ScanFailedError

logger = logging.getLogger(__name__)
User = get_user_model()


class ContentModerationMiddleware(MiddlewareMixin):
    """
    Middleware to automatically intercept and scan offer submissions.
    
    This middleware automatically:
    1. Detects content submission requests
    2. Creates SuspiciousSubmission records
    3. Initiates appropriate scans
    4. Applies auto-approval rules
    5. Returns moderation results
    """
    
    # Paths that should be processed by this middleware
    MONITORED_PATHS = getattr(settings, 'AUTO_MOD_MONITORED_PATHS', [
        '/api/offers/',
        '/api/submissions/',
        '/api/content/',
        '/api/user-content/',
    ])
    
    # HTTP methods to monitor
    MONITORED_METHODS = ['POST', 'PUT', 'PATCH']
    
    # Content type mappings
    CONTENT_TYPE_MAPPING = getattr(settings, 'CONTENT_TYPE_MAPPING', {
        'image/jpeg': SubmissionType.IMAGE,
        'image/png': SubmissionType.IMAGE,
        'image/gif': SubmissionType.IMAGE,
        'image/webp': SubmissionType.IMAGE,
        'application/pdf': SubmissionType.DOCUMENT,
        'text/plain': SubmissionType.TEXT,
        'text/csv': SubmissionType.TEXT,
    })
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.bot_service = BotService()
        self.auto_approval_service = AutoApprovalService()
        super().__init__(get_response)
    
    def __call__(self, request):
        """Process the request through moderation pipeline."""
        
        # Check if request should be moderated
        if self._should_moderate_request(request):
            try:
                # Process the request through moderation
                moderation_result = self._process_request(request)
                
                # If moderation blocked the request, return response
                if moderation_result.get('blocked'):
                    return self._create_moderation_response(request, moderation_result)
                
                # Add moderation context to request
                request._moderation_result = moderation_result
                
            except Exception as exc:
                logger.error(f"Content moderation error: {exc}")
                # Don't block the request on moderation errors, just log them
                request._moderation_error = str(exc)
        
        # Continue with normal request processing
        response = self.get_response(request)
        
        # Post-processing if needed
        if hasattr(request, '_moderation_result'):
            self._post_process_request(request, response)
        
        return response
    
    def _should_moderate_request(self, request):
        """Check if request should be moderated."""
        # Check HTTP method
        if request.method not in self.MONITORED_METHODS:
            return False
        
        # Check path
        for path in self.MONITORED_PATHS:
            if request.path.startswith(path):
                return True
        
        return False
    
    def _process_request(self, request):
        """Process request through moderation pipeline."""
        try:
            # Extract content from request
            content_data = self._extract_content_data(request)
            
            # Validate content data
            validate_submission_data(content_data)
            
            # Check rate limits
            user = getattr(request, 'user', None)
            if user and user.is_authenticated:
                validate_rate_limit(user.pk, 'submit')
            
            # Create submission record
            submission = self._create_submission_record(request, content_data)
            
            # Perform initial scans
            scan_results = self._perform_initial_scans(submission)
            
            # Apply auto-approval rules
            approval_result = self._apply_auto_approval_rules(submission, scan_results)
            
            # Update submission status
            self._update_submission_status(submission, approval_result)
            
            return {
                'submission_id': str(submission.pk),
                'content_id': submission.content_id,
                'status': submission.status,
                'risk_score': submission.risk_score,
                'scan_results': scan_results,
                'approval_result': approval_result,
                'blocked': approval_result.get('block_request', False),
                'message': approval_result.get('message', '')
            }
            
        except InvalidSubmissionError as exc:
            logger.warning(f"Invalid submission: {exc}")
            return {
                'blocked': True,
                'error': 'Invalid submission',
                'message': str(exc),
                'error_code': 'INVALID_SUBMISSION'
            }
        
        except Exception as exc:
            logger.error(f"Moderation processing error: {exc}")
            return {
                'blocked': False,  # Don't block on processing errors
                'error': 'Processing error',
                'message': 'Content moderation temporarily unavailable',
                'error_code': 'PROCESSING_ERROR'
            }
    
    def _extract_content_data(self, request):
        """Extract content data from request."""
        content_data = {}
        
        # Parse request body
        try:
            if request.content_type == 'application/json':
                body_data = json.loads(request.body.decode('utf-8'))
            else:
                # Handle form data
                body_data = request.POST.dict()
                if request.FILES:
                    body_data.update(request.FILES.dict())
        except (json.JSONDecodeError, UnicodeDecodeError):
            body_data = {}
        
        # Extract basic fields
        content_data['user'] = getattr(request, 'user', None)
        content_data['content_id'] = body_data.get('content_id') or self._generate_content_id()
        
        # Extract content based on type
        if 'image_file' in body_data or 'image' in body_data:
            content_data['image_file'] = body_data.get('image_file') or body_data.get('image')
            content_data['submission_type'] = SubmissionType.IMAGE
        elif 'text_content' in body_data or 'text' in body_data:
            content_data['text_content'] = body_data.get('text_content') or body_data.get('text')
            content_data['submission_type'] = SubmissionType.TEXT
        elif 'document_file' in body_data or 'document' in body_data:
            content_data['document_file'] = body_data.get('document_file') or body_data.get('document')
            content_data['submission_type'] = SubmissionType.DOCUMENT
        else:
            # Try to detect from content type
            content_type = self._detect_content_type(request)
            content_data['submission_type'] = self.CONTENT_TYPE_MAPPING.get(content_type)
            
            if content_data['submission_type'] == SubmissionType.IMAGE:
                content_data['image_file'] = body_data.get('file')
            elif content_data['submission_type'] == SubmissionType.TEXT:
                content_data['text_content'] = body_data.get('content', '')
            elif content_data['submission_type'] == SubmissionType.DOCUMENT:
                content_data['document_file'] = body_data.get('file')
        
        # Add additional metadata
        content_data['metadata'] = {
            'request_path': request.path,
            'request_method': request.method,
            'user_agent': request.META.get('HTTP_USER_AGENT', ''),
            'ip_address': self._get_client_ip(request),
            'content_type': request.content_type,
            'content_length': request.META.get('CONTENT_LENGTH', '0'),
            'timestamp': timezone.now().isoformat()
        }
        
        return content_data
    
    def _detect_content_type(self, request):
        """Detect content type from request."""
        # Check Content-Type header
        content_type = request.content_type
        
        # Check file if available
        if hasattr(request, 'FILES') and 'file' in request.FILES:
            file_obj = request.FILES['file']
            try:
                import magic
                mime = magic.Magic(mime=True)
                content_type = mime.from_buffer(file_obj.read(1024))
                file_obj.seek(0)
            except Exception as _e:
                pass  # logged: auto_mod silently handles this  # Fall back to header content type
        
        return content_type
    
    def _generate_content_id(self):
        """Generate unique content ID."""
        import uuid
        return str(uuid.uuid4())
    
    def _get_client_ip(self, request):
        """Get client IP address."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    def _create_submission_record(self, request, content_data):
        """Create SuspiciousSubmission record."""
        user = content_data.get('user')
        submission_type = content_data.get('submission_type')
        content_id = content_data['content_id']
        
        # Calculate initial risk score
        initial_risk_score = self._calculate_initial_risk_score(content_data)
        
        submission = SuspiciousSubmission.objects.create(
            content_id=content_id,
            submission_type=submission_type or SubmissionType.IMAGE,
            user=user,
            status=ModerationStatus.PENDING,
            risk_score=initial_risk_score,
            ai_confidence=0.0,
            flag_reason='Automatic moderation check',
            metadata=content_data.get('metadata', {})
        )
        
        logger.info(f"Created submission record: {submission.pk} for user {user}")
        return submission
    
    def _calculate_initial_risk_score(self, content_data):
        """Calculate initial risk score based on various factors."""
        base_score = 5.0  # Neutral score
        
        # Adjust based on user history (if available)
        user = content_data.get('user')
        if user and user.is_authenticated:
            user_submissions = SuspiciousSubmission.objects.filter(user=user)
            total_submissions = user_submissions.count()
            
            if total_submissions > 0:
                # Calculate user's approval rate
                approved_count = user_submissions.filter(
                    status__in=[ModerationStatus.AUTO_APPROVED, ModerationStatus.HUMAN_APPROVED]
                ).count()
                approval_rate = approved_count / total_submissions
                
                # Adjust risk score based on approval rate
                if approval_rate > 0.9:
                    base_score -= 2.0  # Good history
                elif approval_rate < 0.5:
                    base_score += 3.0  # Poor history
        
        # Adjust based on content type
        submission_type = content_data.get('submission_type')
        if submission_type == SubmissionType.TEXT:
            base_score += 1.0  # Text content slightly higher risk
        elif submission_type == SubmissionType.DOCUMENT:
            base_score += 0.5  # Documents moderate risk
        
        # Adjust based on metadata
        metadata = content_data.get('metadata', {})
        
        # Check for suspicious patterns
        user_agent = metadata.get('user_agent', '').lower()
        suspicious_agents = ['bot', 'crawler', 'scraper', 'automated']
        if any(agent in user_agent for agent in suspicious_agents):
            base_score += 2.0
        
        # Ensure score is within bounds
        return max(0.0, min(10.0, base_score))
    
    def _perform_initial_scans(self, submission):
        """Perform initial scans on submission."""
        scan_results = {}
        
        try:
            # Determine appropriate scan types
            scan_types = self._get_required_scan_types(submission)
            
            for scan_type in scan_types:
                try:
                    # Create scanner record
                    scanner = ProofScanner.objects.create(
                        submission=submission,
                        scan_type=scan_type,
                        status='pending',
                        initiated_by=None  # System initiated
                    )
                    
                    # Execute scan
                    if scan_type == ScanType.OCR:
                        result = self.bot_service.run_ocr_scan(submission)
                    elif scan_type == ScanType.IMAGE_ANALYSIS:
                        result = self.bot_service.run_image_scan(submission)
                    elif scan_type == ScanType.TEXT_ANALYSIS:
                        result = self.bot_service.run_text_analysis(submission)
                    else:
                        continue
                    
                    # Update scanner with results
                    if result.get('status') == 'success':
                        scanner.mark_completed('success', result)
                        scan_results[scan_type] = result
                        
                        # Update submission with scan results
                        self._update_submission_with_scan_results(submission, scan_type, result)
                    else:
                        scanner.mark_completed('failed', result)
                        scan_results[scan_type] = result
                        
                except ScanFailedError as exc:
                    logger.warning(f"Scan {scan_type} failed for {submission.pk}: {exc}")
                    scan_results[scan_type] = {'status': 'failed', 'error': str(exc)}
                
        except Exception as exc:
            logger.error(f"Initial scanning error for {submission.pk}: {exc}")
        
        return scan_results
    
    def _get_required_scan_types(self, submission):
        """Get required scan types for submission."""
        scan_types = []
        
        if submission.submission_type == SubmissionType.IMAGE:
            scan_types.append(ScanType.IMAGE_ANALYSIS)
            # Also try OCR in case it contains text
            scan_types.append(ScanType.OCR)
        elif submission.submission_type == SubmissionType.TEXT:
            scan_types.append(ScanType.TEXT_ANALYSIS)
        elif submission.submission_type == SubmissionType.DOCUMENT:
            scan_types.append(ScanType.OCR)
            scan_types.append(ScanType.TEXT_ANALYSIS)
        
        return scan_types
    
    def _update_submission_with_scan_results(self, submission, scan_type, result):
        """Update submission with scan results."""
        if scan_type == ScanType.OCR and 'extracted_text' in result:
            submission.metadata['ocr_text'] = result['extracted_text']
            submission.metadata['ocr_confidence'] = result.get('confidence', 0)
            
            # Update risk score based on OCR results
            if result.get('confidence', 0) < 0.5:
                submission.risk_score += 1.0
        
        elif scan_type == ScanType.IMAGE_ANALYSIS and 'analysis' in result:
            analysis = result['analysis']
            submission.metadata['image_analysis'] = analysis
            
            # Update risk score based on analysis
            if analysis.get('suspicious_content'):
                submission.risk_score += 2.0
            elif analysis.get('confidence', 0) > 0.9:
                submission.risk_score -= 1.0
        
        elif scan_type == ScanType.TEXT_ANALYSIS and 'analysis' in result:
            analysis = result['analysis']
            submission.metadata['text_analysis'] = analysis
            
            # Update risk score based on text analysis
            toxicity = analysis.get('toxicity_score', 0)
            if toxicity > 0.7:
                submission.risk_score += toxicity * 2
            elif toxicity < 0.1:
                submission.risk_score -= 0.5
        
        submission.save(update_fields=['metadata', 'risk_score'])
    
    def _apply_auto_approval_rules(self, submission, scan_results):
        """Apply auto-approval rules to submission."""
        try:
            # Evaluate submission for auto-approval
            evaluation = self.auto_approval_service.evaluate_submission_for_auto_approval(submission)
            
            if evaluation.get('auto_approvable'):
                # Execute auto-approval
                decision = self.auto_approval_service.execute_auto_decision(
                    submission=submission,
                    recommendation=evaluation['recommendation'],
                    confidence=evaluation['confidence'],
                    reason=evaluation['reason'],
                    applied_rules=evaluation.get('matched_rules', [])
                )
                
                return {
                    'auto_approved': True,
                    'decision': decision.decision_type,
                    'confidence': evaluation['confidence'],
                    'reason': evaluation['reason'],
                    'matched_rules': evaluation.get('matched_rules', [])
                }
            else:
                return {
                    'auto_approved': False,
                    'recommendation': evaluation['recommendation'],
                    'confidence': evaluation['confidence'],
                    'reason': evaluation['reason'],
                    'requires_human_review': True
                }
                
        except Exception as exc:
            logger.error(f"Auto-approval evaluation error for {submission.pk}: {exc}")
            return {
                'auto_approved': False,
                'error': str(exc),
                'requires_human_review': True
            }
    
    def _update_submission_status(self, submission, approval_result):
        """Update submission status based on approval result."""
        if approval_result.get('auto_approved'):
            # Status already updated by auto_approval_service
            pass
        else:
            # Mark for human review
            from api.auto_mod.services.ModerationQueueService import ModerationQueueService
            queue_service = ModerationQueueService()
            
            try:
                queue_service.add_to_queue(
                    submission=submission,
                    priority='normal',
                    due_hours=24
                )
            except Exception as exc:
                logger.error(f"Failed to add to queue: {exc}")
    
    def _create_moderation_response(self, request, moderation_result):
        """Create response for blocked requests."""
        response_data = {
            'success': False,
            'error': moderation_result.get('error', 'Content moderation blocked'),
            'message': moderation_result.get('message', 'Your content could not be processed'),
            'error_code': moderation_result.get('error_code', 'MODERATION_BLOCKED'),
            'submission_id': moderation_result.get('submission_id')
        }
        
        return JsonResponse(response_data, status=400)
    
    def _post_process_request(self, request, response):
        """Post-process request after normal processing."""
        moderation_result = getattr(request, '_moderation_result', None)
        
        if not moderation_result:
            return
        
        # Add moderation headers to response
        response['X-Moderation-Status'] = moderation_result.get('status', 'unknown')
        response['X-Moderation-Risk-Score'] = str(moderation_result.get('risk_score', 0))
        response['X-Moderation-Submission-ID'] = moderation_result.get('submission_id', '')
        
        # Log moderation activity
        self._log_moderation_activity(request, response, moderation_result)
    
    def _log_moderation_activity(self, request, response, moderation_result):
        """Log moderation activity for audit purposes."""
        try:
            log_data = {
                'timestamp': timezone.now().isoformat(),
                'request_path': request.path,
                'request_method': request.method,
                'user_id': getattr(request.user, 'pk', None) if hasattr(request, 'user') else None,
                'submission_id': moderation_result.get('submission_id'),
                'content_id': moderation_result.get('content_id'),
                'status': moderation_result.get('status'),
                'risk_score': moderation_result.get('risk_score'),
                'auto_approved': moderation_result.get('approval_result', {}).get('auto_approved', False),
                'blocked': moderation_result.get('blocked', False),
                'response_status': response.status_code
            }
            
            logger.info(f"Content moderation activity: {json.dumps(log_data)}")
            
        except Exception as exc:
            logger.error(f"Failed to log moderation activity: {exc}")


class ModerationLoggingMiddleware(MiddlewareMixin):
    """
    Middleware to log all moderation-related activities.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        super().__init__(get_response)
    
    def __call__(self, request):
        """Log moderation-related requests."""
        # Check if this is a moderation-related request
        if self._is_moderation_request(request):
            self._log_request(request)
        
        response = self.get_response(request)
        
        # Log response for moderation requests
        if self._is_moderation_request(request):
            self._log_response(request, response)
        
        return response
    
    def _is_moderation_request(self, request):
        """Check if request is moderation-related."""
        moderation_paths = [
            '/api/auto_mod/',
            '/api/moderation/',
            '/api/queue/',
            '/api/appeals/',
        ]
        
        return any(request.path.startswith(path) for path in moderation_paths)
    
    def _log_request(self, request):
        """Log incoming moderation request."""
        try:
            log_data = {
                'timestamp': timezone.now().isoformat(),
                'type': 'moderation_request',
                'path': request.path,
                'method': request.method,
                'user_id': getattr(request.user, 'pk', None) if hasattr(request, 'user') else None,
                'ip_address': self._get_client_ip(request),
                'user_agent': request.META.get('HTTP_USER_AGENT', ''),
                'content_length': request.META.get('CONTENT_LENGTH', '0')
            }
            
            logger.info(f"Moderation request: {json.dumps(log_data)}")
            
        except Exception as exc:
            logger.error(f"Failed to log moderation request: {exc}")
    
    def _log_response(self, request, response):
        """Log moderation response."""
        try:
            log_data = {
                'timestamp': timezone.now().isoformat(),
                'type': 'moderation_response',
                'path': request.path,
                'method': request.method,
                'status_code': response.status_code,
                'response_size': len(getattr(response, 'content', b''))
            }
            
            logger.info(f"Moderation response: {json.dumps(log_data)}")
            
        except Exception as exc:
            logger.error(f"Failed to log moderation response: {exc}")
    
    def _get_client_ip(self, request):
        """Get client IP address."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
