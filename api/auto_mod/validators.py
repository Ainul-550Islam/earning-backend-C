# =============================================================================
# auto_mod/validators.py
# =============================================================================

"""
Validation functions for auto moderation system.
"""

import os
import imghdr
import magic
from django.core.exceptions import ValidationError
from django.core.files.images import get_image_dimensions
from django.conf import settings
from django.utils.translation import gettext_lazy as _

from .choices import SubmissionType, ScanType
from .exceptions import InvalidSubmissionError, ScanFailedError
import logging

logger = logging.getLogger(__name__)


def validate_image_size(image_file, max_size_mb=None):
    """
    Validate image file size.
    
    Args:
        image_file: Uploaded image file
        max_size_mb: Maximum allowed size in MB (default from settings)
        
    Raises:
        ValidationError: If image is too large
    """
    if max_size_mb is None:
        max_size_mb = getattr(settings, 'MAX_IMAGE_SIZE_MB', 10)
    
    if image_file.size > max_size_mb * 1024 * 1024:
        raise ValidationError(
            _(f'Image size cannot exceed {max_size_mb} MB. '
              f'Current size: {image_file.size / (1024*1024):.2f} MB')
        )
    
    return True


def validate_content_type(file_obj, allowed_types=None):
    """
    Validate file content type using python-magic.
    
    Args:
        file_obj: Uploaded file object
        allowed_types: List of allowed MIME types (default from settings)
        
    Raises:
        ValidationError: If file type is not allowed
    """
    if allowed_types is None:
        allowed_types = getattr(settings, 'ALLOWED_CONTENT_TYPES', [
            'image/jpeg',
            'image/png',
            'image/gif',
            'image/webp',
            'application/pdf',
            'text/plain',
            'text/csv'
        ])
    
    # Reset file pointer
    file_obj.seek(0)
    
    try:
        # Use python-magic for content type detection
        mime = magic.Magic(mime=True)
        content_type = mime.from_buffer(file_obj.read(1024))
        
        # Reset file pointer
        file_obj.seek(0)
        
        if content_type not in allowed_types:
            raise ValidationError(
                _(f'File type {content_type} is not allowed. '
                  f'Allowed types: {", ".join(allowed_types)}')
            )
        
        return content_type
        
    except Exception as exc:
        logger.error(f"Content type validation failed: {exc}")
        raise ValidationError(
            _('Unable to determine file content type. Please upload a valid file.')
        )


def validate_scan_threshold(confidence, scan_type=None, min_threshold=None):
    """
    Validate scan confidence threshold.
    
    Args:
        confidence: Confidence score (0.0 to 1.0)
        scan_type: Type of scan (optional, for type-specific validation)
        min_threshold: Minimum allowed threshold (default from settings)
        
    Raises:
        ValidationError: If confidence is below threshold or invalid
    """
    if not isinstance(confidence, (int, float)):
        raise ValidationError(_('Confidence must be a numeric value'))
    
    if not 0.0 <= confidence <= 1.0:
        raise ValidationError(_('Confidence must be between 0.0 and 1.0'))
    
    # Get minimum threshold based on scan type
    if min_threshold is None:
        threshold_settings = getattr(settings, 'SCAN_THRESHOLDS', {
            ScanType.OCR: 0.7,
            ScanType.IMAGE_ANALYSIS: 0.8,
            ScanType.TEXT_ANALYSIS: 0.75
        })
        
        if scan_type:
            min_threshold = threshold_settings.get(scan_type, 0.7)
        else:
            min_threshold = min(threshold_settings.values())
    
    if confidence < min_threshold:
        raise ValidationError(
            _(f'Confidence {confidence:.3f} is below minimum threshold '
              f'{min_threshold:.3f} for {scan_type or "scan"}')
        )
    
    return True


def validate_submission_data(submission_data, submission_type=None):
    """
    Validate submission data based on type and requirements.
    
    Args:
        submission_data: Dictionary containing submission data
        submission_type: Type of submission (optional)
        
    Raises:
        ValidationError: If submission data is invalid
    """
    required_fields = ['content_id', 'user']
    
    for field in required_fields:
        if field not in submission_data or not submission_data[field]:
            raise ValidationError(_(f'Required field {field} is missing'))
    
    # Type-specific validation
    if submission_type:
        if submission_type == SubmissionType.IMAGE:
            validate_image_submission(submission_data)
        elif submission_type == SubmissionType.TEXT:
            validate_text_submission(submission_data)
        elif submission_type == SubmissionType.DOCUMENT:
            validate_document_submission(submission_data)
    
    return True


def validate_image_submission(submission_data):
    """
    Validate image-specific submission data.
    
    Args:
        submission_data: Dictionary containing image submission data
        
    Raises:
        ValidationError: If image submission is invalid
    """
    # Check for image file or URL
    if 'image_file' not in submission_data and 'image_url' not in submission_data:
        raise ValidationError(_('Either image_file or image_url is required'))
    
    # Validate image dimensions if file is provided
    if 'image_file' in submission_data:
        image_file = submission_data['image_file']
        
        try:
            width, height = get_image_dimensions(image_file)
            
            # Check minimum dimensions
            min_width = getattr(settings, 'MIN_IMAGE_WIDTH', 100)
            min_height = getattr(settings, 'MIN_IMAGE_HEIGHT', 100)
            
            if width < min_width or height < min_height:
                raise ValidationError(
                    _(f'Image must be at least {min_width}x{min_height} pixels. '
                      f'Current size: {width}x{height}')
                )
            
            # Check maximum dimensions
            max_width = getattr(settings, 'MAX_IMAGE_WIDTH', 4096)
            max_height = getattr(settings, 'MAX_IMAGE_HEIGHT', 4096)
            
            if width > max_width or height > max_height:
                raise ValidationError(
                    _(f'Image cannot exceed {max_width}x{max_height} pixels. '
                      f'Current size: {width}x{height}')
                )
        
        except Exception as exc:
            logger.error(f"Image dimension validation failed: {exc}")
            raise ValidationError(_('Unable to validate image dimensions'))
    
    return True


def validate_text_submission(submission_data):
    """
    Validate text-specific submission data.
    
    Args:
        submission_data: Dictionary containing text submission data
        
    Raises:
        ValidationError: If text submission is invalid
    """
    if 'text_content' not in submission_data:
        raise ValidationError(_('text_content is required for text submissions'))
    
    text_content = submission_data['text_content']
    
    if not isinstance(text_content, str):
        raise ValidationError(_('text_content must be a string'))
    
    # Check minimum text length
    min_length = getattr(settings, 'MIN_TEXT_LENGTH', 10)
    if len(text_content.strip()) < min_length:
        raise ValidationError(
            _(f'Text must be at least {min_length} characters long')
        )
    
    # Check maximum text length
    max_length = getattr(settings, 'MAX_TEXT_LENGTH', 10000)
    if len(text_content) > max_length:
        raise ValidationError(
            _(f'Text cannot exceed {max_length} characters')
        )
    
    return True


def validate_document_submission(submission_data):
    """
    Validate document-specific submission data.
    
    Args:
        submission_data: Dictionary containing document submission data
        
    Raises:
        ValidationError: If document submission is invalid
    """
    if 'document_file' not in submission_data and 'document_url' not in submission_data:
        raise ValidationError(_('Either document_file or document_url is required'))
    
    # Validate file if provided
    if 'document_file' in submission_data:
        document_file = submission_data['document_file']
        
        # Check file extension
        allowed_extensions = getattr(settings, 'ALLOWED_DOCUMENT_EXTENSIONS', 
                                  ['.pdf', '.doc', '.docx', '.txt'])
        
        file_extension = os.path.splitext(document_file.name)[1].lower()
        if file_extension not in allowed_extensions:
            raise ValidationError(
                _(f'Document type {file_extension} is not allowed. '
                  f'Allowed types: {", ".join(allowed_extensions)}')
            )
        
        # Validate file size
        max_size_mb = getattr(settings, 'MAX_DOCUMENT_SIZE_MB', 20)
        validate_image_size(document_file, max_size_mb)
    
    return True


def validate_scan_parameters(scan_params, scan_type):
    """
    Validate scan parameters for specific scan type.
    
    Args:
        scan_params: Dictionary containing scan parameters
        scan_type: Type of scan being performed
        
    Raises:
        ValidationError: If scan parameters are invalid
    """
    if scan_type == ScanType.OCR:
        validate_ocr_parameters(scan_params)
    elif scan_type == ScanType.IMAGE_ANALYSIS:
        validate_image_analysis_parameters(scan_params)
    elif scan_type == ScanType.TEXT_ANALYSIS:
        validate_text_analysis_parameters(scan_params)
    
    return True


def validate_ocr_parameters(scan_params):
    """
    Validate OCR-specific parameters.
    
    Args:
        scan_params: Dictionary containing OCR parameters
        
    Raises:
        ValidationError: If OCR parameters are invalid
    """
    # Validate language settings
    if 'languages' in scan_params:
        languages = scan_params['languages']
        
        if not isinstance(languages, list):
            raise ValidationError(_('OCR languages must be a list'))
        
        supported_languages = getattr(settings, 'SUPPORTED_OCR_LANGUAGES', 
                                     ['eng', 'spa', 'fra', 'deu', 'ita', 'por'])
        
        for lang in languages:
            if lang not in supported_languages:
                raise ValidationError(
                    _(f'OCR language {lang} is not supported. '
                      f'Supported: {", ".join(supported_languages)}')
                )
    
    # Validate DPI setting
    if 'dpi' in scan_params:
        dpi = scan_params['dpi']
        
        if not isinstance(dpi, int) or not 150 <= dpi <= 600:
            raise ValidationError(_('OCR DPI must be between 150 and 600'))
    
    return True


def validate_image_analysis_parameters(scan_params):
    """
    Validate image analysis parameters.
    
    Args:
        scan_params: Dictionary containing image analysis parameters
        
    Raises:
        ValidationError: If image analysis parameters are invalid
    """
    # Validate confidence threshold
    if 'confidence_threshold' in scan_params:
        threshold = scan_params['confidence_threshold']
        validate_scan_threshold(threshold, ScanType.IMAGE_ANALYSIS)
    
    # Validate object detection settings
    if 'detect_objects' in scan_params:
        detect_objects = scan_params['detect_objects']
        
        if not isinstance(detect_objects, bool):
            raise ValidationError(_('detect_objects must be a boolean'))
    
    # Validate analysis depth
    if 'analysis_depth' in scan_params:
        depth = scan_params['analysis_depth']
        
        valid_depths = ['basic', 'standard', 'detailed']
        if depth not in valid_depths:
            raise ValidationError(
                _(f'Analysis depth must be one of: {", ".join(valid_depths)}')
            )
    
    return True


def validate_text_analysis_parameters(scan_params):
    """
    Validate text analysis parameters.
    
    Args:
        scan_params: Dictionary containing text analysis parameters
        
    Raises:
        ValidationError: If text analysis parameters are invalid
    """
    # Validate language detection
    if 'detect_language' in scan_params:
        detect_language = scan_params['detect_language']
        
        if not isinstance(detect_language, bool):
            raise ValidationError(_('detect_language must be a boolean'))
    
    # Validate sentiment analysis
    if 'analyze_sentiment' in scan_params:
        analyze_sentiment = scan_params['analyze_sentiment']
        
        if not isinstance(analyze_sentiment, bool):
            raise ValidationError(_('analyze_sentiment must be a boolean'))
    
    # Validate toxicity detection
    if 'detect_toxicity' in scan_params:
        detect_toxicity = scan_params['detect_toxicity']
        
        if not isinstance(detect_toxicity, bool):
            raise ValidationError(_('detect_toxicity must be a boolean'))
    
    return True


def validate_batch_scan_parameters(submissions, scan_config):
    """
    Validate parameters for batch scanning operations.
    
    Args:
        submissions: List of submissions to scan
        scan_config: Scan configuration dictionary
        
    Raises:
        ValidationError: If batch scan parameters are invalid
    """
    if not submissions:
        raise ValidationError(_('No submissions provided for batch scan'))
    
    # Check batch size limits
    max_batch_size = getattr(settings, 'MAX_BATCH_SCAN_SIZE', 100)
    if len(submissions) > max_batch_size:
        raise ValidationError(
            _(f'Batch size cannot exceed {max_batch_size}. '
              f'Current size: {len(submissions)}')
        )
    
    # Validate scan configuration
    if not isinstance(scan_config, dict):
        raise ValidationError(_('Scan configuration must be a dictionary'))
    
    required_config_fields = ['scan_type']
    for field in required_config_fields:
        if field not in scan_config:
            raise ValidationError(_(f'Required config field {field} is missing'))
    
    # Validate scan type for all submissions
    scan_type = scan_config['scan_type']
    for submission in submissions:
        if not validate_scan_type_compatibility(submission.submission_type, scan_type):
            raise ValidationError(
                _(f'Scan type {scan_type} is not compatible with '
                  f'submission type {submission.submission_type}')
            )
    
    return True


def validate_scan_type_compatibility(submission_type, scan_type):
    """
    Validate that scan type is compatible with submission type.
    
    Args:
        submission_type: Type of submission
        scan_type: Type of scan
        
    Returns:
        bool: True if compatible, False otherwise
    """
    compatibility_matrix = {
        SubmissionType.IMAGE: [ScanType.IMAGE_ANALYSIS, ScanType.OCR],
        SubmissionType.TEXT: [ScanType.TEXT_ANALYSIS],
        SubmissionType.DOCUMENT: [ScanType.OCR, ScanType.TEXT_ANALYSIS],
        SubmissionType.VIDEO: [ScanType.IMAGE_ANALYSIS],  # Frame analysis
        SubmissionType.AUDIO: [ScanType.TEXT_ANALYSIS],   # Transcription
    }
    
    return scan_type in compatibility_matrix.get(submission_type, [])


def validate_api_key(api_key, service_name):
    """
    Validate API key for external services.
    
    Args:
        api_key: API key string
        service_name: Name of the service (for error messages)
        
    Raises:
        ValidationError: If API key is invalid
    """
    if not api_key:
        raise ValidationError(_(f'API key is required for {service_name}'))
    
    if not isinstance(api_key, str):
        raise ValidationError(_(f'API key must be a string for {service_name}'))
    
    # Basic format validation (can be extended based on service requirements)
    min_length = getattr(settings, f'{service_name.upper()}_API_KEY_MIN_LENGTH', 20)
    if len(api_key) < min_length:
        raise ValidationError(
            _(f'{service_name} API key must be at least {min_length} characters')
        )
    
    return True


def validate_rate_limit(user_id, action_type, window_minutes=60):
    """
    Validate rate limit for user actions.
    
    Args:
        user_id: User identifier
        action_type: Type of action (scan, submit, appeal, etc.)
        window_minutes: Time window in minutes
        
    Raises:
        ValidationError: If rate limit is exceeded
    """
    from django.core.cache import cache
    
    # Get rate limit settings
    rate_limits = getattr(settings, 'RATE_LIMITS', {
        'scan': {'max_requests': 100, 'window_minutes': 60},
        'submit': {'max_requests': 50, 'window_minutes': 60},
        'appeal': {'max_requests': 10, 'window_minutes': 1440},  # 24 hours
    })
    
    if action_type not in rate_limits:
        return True  # No rate limit for this action type
    
    limit_config = rate_limits[action_type]
    max_requests = limit_config['max_requests']
    window = limit_config['window_minutes']
    
    # Check current usage
    cache_key = f"rate_limit_{action_type}_{user_id}"
    current_count = cache.get(cache_key, 0)
    
    if current_count >= max_requests:
        raise ValidationError(
            _(f'Rate limit exceeded for {action_type}. '
              f'Max {max_requests} requests per {window} minutes.')
        )
    
    # Increment counter
    cache.set(cache_key, current_count + 1, window * 60)
    
    return True


def validate_file_integrity(file_path, expected_checksum=None):
    """
    Validate file integrity using checksum.
    
    Args:
        file_path: Path to the file
        expected_checksum: Expected checksum (optional)
        
    Raises:
        ValidationError: If file integrity check fails
    """
    import hashlib
    
    if not os.path.exists(file_path):
        raise ValidationError(_('File does not exist'))
    
    try:
        # Calculate file checksum
        hasher = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hasher.update(chunk)
        
        actual_checksum = hasher.hexdigest()
        
        # Compare with expected checksum if provided
        if expected_checksum and actual_checksum != expected_checksum:
            raise ValidationError(
                _('File integrity check failed. Checksum mismatch.')
            )
        
        return actual_checksum
        
    except Exception as exc:
        logger.error(f"File integrity validation failed: {exc}")
        raise ValidationError(_('Unable to validate file integrity'))


def validate_moderator_workload(moderator, additional_items=0):
    """
    Validate moderator workload capacity.
    
    Args:
        moderator: Moderator user object
        additional_items: Number of additional items to assign
        
    Raises:
        ValidationError: If moderator is at capacity
    """
    from .models import ModerationQueue
    
    # Get current workload
    current_workload = ModerationQueue.objects.filter(
        assigned_to=moderator,
        completed_at__isnull=True
    ).count()
    
    # Get moderator capacity
    max_workload = getattr(settings, 'MAX_MODERATOR_WORKLOAD', 50)
    
    if current_workload + additional_items > max_workload:
        raise ValidationError(
            _(f'Moderator {moderator.username} is at capacity. '
              f'Current: {current_workload}, Max: {max_workload}')
        )
    
    return True


def validate_appeal_eligibility(decision, user, time_limit_hours=72):
    """
    Validate if user can appeal a decision.
    
    Args:
        decision: ModerationDecision object
        user: User making the appeal
        time_limit_hours: Time limit for appeals
        
    Raises:
        ValidationError: If appeal is not eligible
    """
    # Check if decision is recent enough
    from django.utils import timezone
    time_ago = timezone.now() - timezone.timedelta(hours=time_limit_hours)
    
    if decision.decided_at < time_ago:
        raise ValidationError(
            _(f'Appeals must be made within {time_limit_hours} hours of decision.')
        )
    
    # Check if user is the decision recipient
    if decision.submission.user != user:
        raise ValidationError(_('Only the content owner can appeal the decision.'))
    
    # Check if appeal already exists
    from .models import ModerationAppeal
    existing_appeal = ModerationAppeal.objects.filter(
        original_decision=decision,
        user=user
    ).first()
    
    if existing_appeal:
        raise ValidationError(_('An appeal for this decision already exists.'))
    
    return True


def validate_rule_conditions(conditions):
    """
    Validate auto-approval rule conditions.
    
    Args:
        conditions: List of condition dictionaries
        
    Raises:
        ValidationError: If conditions are invalid
    """
    if not conditions:
        raise ValidationError(_('At least one condition is required'))
    
    if not isinstance(conditions, list):
        raise ValidationError(_('Conditions must be a list'))
    
    max_conditions = getattr(settings, 'MAX_CONDITIONS_PER_RULE', 10)
    if len(conditions) > max_conditions:
        raise ValidationError(
            _(f'Maximum {max_conditions} conditions allowed per rule')
        )
    
    # Validate each condition
    for i, condition in enumerate(conditions):
        if not isinstance(condition, dict):
            raise ValidationError(_(f'Condition {i+1} must be a dictionary'))
        
        required_fields = ['field', 'operator', 'value']
        for field in required_fields:
            if field not in condition:
                raise ValidationError(
                    _(f'Condition {i+1} is missing required field: {field}')
                )
        
        # Validate operator
        valid_operators = ['equals', 'not_equals', 'greater_than', 'less_than', 
                          'greater_equal', 'less_equal', 'in', 'not_in', 
                          'contains', 'not_contains']
        
        if condition['operator'] not in valid_operators:
            raise ValidationError(
                _(f'Invalid operator: {condition["operator"]}. '
                  f'Valid: {", ".join(valid_operators)}')
            )
    
    return True
