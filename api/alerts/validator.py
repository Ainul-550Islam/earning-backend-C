"""
Validation utilities for alerts app
"""
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator, EmailValidator, URLValidator
from django.utils import timezone
from datetime import timedelta
import re
import json


class AlertValidator:
    """Custom validators for alert system"""
    
    @staticmethod
    def validate_threshold_value(value, alert_type):
        """Validate threshold value based on alert type"""
        if alert_type == 'server_error':
            if not 0 <= value <= 100:
                raise ValidationError(f"Error rate must be between 0 and 100, got {value}")
        elif alert_type in ['high_earning', 'payment_spike', 'revenue_drop']:
            if value < 0:
                raise ValidationError(f"Monetary threshold must be non-negative, got {value}")
        elif alert_type == 'mass_signup':
            if value < 1:
                raise ValidationError(f"User count threshold must be at least 1, got {value}")
        
        return value
    
    @staticmethod
    def validate_time_window(value):
        """Validate time window in minutes"""
        if not 1 <= value <= 1440:  # 1 minute to 24 hours
            raise ValidationError("Time window must be between 1 and 1440 minutes")
        return value
    
    @staticmethod
    def validate_cooldown_period(value, time_window):
        """Validate cooldown period against time window"""
        if value >= time_window:
            raise ValidationError("Cooldown period must be less than time window")
        if not 1 <= value <= 1440:
            raise ValidationError("Cooldown period must be between 1 and 1440 minutes")
        return value
    
    @staticmethod
    def validate_recipients(recipients, recipient_type):
        """Validate recipient lists"""
        if not recipients:
            return []
        
        recipient_list = []
        errors = []
        
        for recipient in recipients.split(','):
            recipient = recipient.strip()
            if not recipient:
                continue
            
            if recipient_type == 'email':
                try:
                    EmailValidator()(recipient)
                    recipient_list.append(recipient.lower())
                except ValidationError:
                    errors.append(f"Invalid email: {recipient}")
            
            elif recipient_type == 'phone':
                if not AlertValidator._validate_phone(recipient):
                    errors.append(f"Invalid phone number: {recipient}")
                else:
                    recipient_list.append(AlertValidator._normalize_phone(recipient))
        
        if errors:
            raise ValidationError('; '.join(errors))
        
        return recipient_list
    
    @staticmethod
    def _validate_phone(phone):
        """Validate phone number format"""
        # Remove all non-digit characters
        digits = re.sub(r'\D', '', phone)
        
        # Check for valid length (10-15 digits)
        if len(digits) < 10 or len(digits) > 15:
            return False
        
        return True
    
    @staticmethod
    def _normalize_phone(phone):
        """Normalize phone number format"""
        return re.sub(r'\D', '', phone)
    
    @staticmethod
    def validate_webhook_url(url):
        """Validate webhook URL"""
        try:
            URLValidator()(url)
            
            # Check for allowed schemes
            if not url.startswith(('http://', 'https://')):
                raise ValidationError("Webhook URL must use HTTP or HTTPS")
            
            return url
        except ValidationError:
            raise ValidationError(f"Invalid webhook URL: {url}")
    
    @staticmethod
    def validate_severity(severity):
        """Validate severity level"""
        valid_severities = ['low', 'medium', 'high', 'critical']
        if severity not in valid_severities:
            raise ValidationError(f"Severity must be one of {valid_severities}, got {severity}")
        return severity
    
    @staticmethod
    def validate_alert_type(alert_type):
        """Validate alert type"""
        from .choices import ALERT_TYPES
        valid_types = [choice[0] for choice in ALERT_TYPES]
        
        if alert_type not in valid_types:
            raise ValidationError(f"Invalid alert type: {alert_type}")
        return alert_type


class ScheduleValidator:
    """Validators for alert schedules"""
    
    @staticmethod
    def validate_time_range(start_time, end_time):
        """Validate time range"""
        if start_time >= end_time:
            raise ValidationError("End time must be after start time")
        return True
    
    @staticmethod
    def validate_days_of_week(days):
        """Validate days of week list"""
        if not isinstance(days, list):
            raise ValidationError("Days of week must be a list")
        
        valid_days = list(range(7))  # 0-6 for Monday-Sunday
        for day in days:
            if day not in valid_days:
                raise ValidationError(f"Invalid day of week: {day}")
        
        if not days:
            raise ValidationError("At least one day must be selected")
        
        return days
    
    @staticmethod
    def validate_timezone(timezone_str):
        """Validate timezone string"""
        try:
            import zoneinfo
            zoneinfo.ZoneInfo(timezone_str)
            return timezone_str
        except Exception:
            raise ValidationError(f"Invalid timezone: {timezone_str}")


class EscalationValidator:
    """Validators for alert escalation"""
    
    @staticmethod
    def validate_escalation_level(level):
        """Validate escalation level"""
        if not 1 <= level <= 5:
            raise ValidationError("Escalation level must be between 1 and 5")
        return level
    
    @staticmethod
    def validate_escalation_delay(delay_minutes):
        """Validate escalation delay"""
        if not 5 <= delay_minutes <= 10080:  # 5 minutes to 7 days
            raise ValidationError("Escalation delay must be between 5 and 10080 minutes")
        return delay_minutes
    
    @staticmethod
    def validate_escalation_recipients(recipients):
        """Validate escalation recipients"""
        if not recipients:
            raise ValidationError("At least one escalation recipient must be specified")
        
        # Validate emails and phones
        emails = recipients.get('emails', [])
        phones = recipients.get('phones', [])
        
        for email in emails:
            try:
                EmailValidator()(email)
            except ValidationError:
                raise ValidationError(f"Invalid escalation email: {email}")
        
        for phone in phones:
            if not AlertValidator._validate_phone(phone):
                raise ValidationError(f"Invalid escalation phone: {phone}")
        
        return recipients


class NotificationValidator:
    """Validators for notifications"""
    
    @staticmethod
    def validate_message_length(message, max_length=1000):
        """Validate message length"""
        if len(message) > max_length:
            raise ValidationError(f"Message too long (max {max_length} characters)")
        return message
    
    @staticmethod
    def validate_subject_length(subject, max_length=200):
        """Validate subject length"""
        if len(subject) > max_length:
            raise ValidationError(f"Subject too long (max {max_length} characters)")
        return subject
    
    @staticmethod
    def validate_notification_type(notification_type):
        """Validate notification type"""
        from .choices import NOTIFICATION_TYPES
        valid_types = [choice[0] for choice in NOTIFICATION_TYPES]
        
        if notification_type not in valid_types:
            raise ValidationError(f"Invalid notification type: {notification_type}")
        return notification_type


class ThresholdValidator:
    """Validators for threshold configurations"""
    
    @staticmethod
    def validate_threshold_type(threshold_type):
        """Validate threshold type"""
        valid_types = ['absolute', 'percentage', 'deviation', 'rolling']
        if threshold_type not in valid_types:
            raise ValidationError(f"Invalid threshold type: {threshold_type}")
        return threshold_type
    
    @staticmethod
    def validate_adaptive_threshold_params(params):
        """Validate adaptive threshold parameters"""
        required_params = ['window_size', 'min_samples', 'sensitivity']
        
        for param in required_params:
            if param not in params:
                raise ValidationError(f"Missing required parameter: {param}")
        
        if params['window_size'] < 10:
            raise ValidationError("Window size must be at least 10")
        
        if params['min_samples'] < 5:
            raise ValidationError("Minimum samples must be at least 5")
        
        if not 0.1 <= params['sensitivity'] <= 5.0:
            raise ValidationError("Sensitivity must be between 0.1 and 5.0")
        
        return params


class IncidentValidator:
    """Validators for incidents"""
    
    @staticmethod
    def validate_incident_severity(severity):
        """Validate incident severity"""
        valid_severities = ['low', 'medium', 'high', 'critical']
        if severity not in valid_severities:
            raise ValidationError(f"Invalid incident severity: {severity}")
        return severity
    
    @staticmethod
    def validate_incident_status(status):
        """Validate incident status"""
        valid_statuses = ['investigating', 'identified', 'monitoring', 'resolved', 'post_mortem']
        if status not in valid_statuses:
            raise ValidationError(f"Invalid incident status: {status}")
        return status
    
    @staticmethod
    def validate_incident_timeline(timeline_data):
        """Validate incident timeline data"""
        if not isinstance(timeline_data, list):
            raise ValidationError("Timeline must be a list")
        
        for entry in timeline_data:
            if not isinstance(entry, dict):
                raise ValidationError("Timeline entries must be dictionaries")
            
            required_fields = ['timestamp', 'event', 'description']
            for field in required_fields:
                if field not in entry:
                    raise ValidationError(f"Timeline entry missing required field: {field}")
        
        return timeline_data


class ReportValidator:
    """Validators for reports"""
    
    @staticmethod
    def validate_report_type(report_type):
        """Validate report type"""
        from .choices import REPORT_TYPES
        valid_types = [choice[0] for choice in REPORT_TYPES]
        
        if report_type not in valid_types:
            raise ValidationError(f"Invalid report type: {report_type}")
        return report_type
    
    @staticmethod
    def validate_date_range(start_date, end_date):
        """Validate date range"""
        if start_date >= end_date:
            raise ValidationError("Start date must be before end date")
        
        # Limit to maximum range (e.g., 1 year)
        max_range = timedelta(days=365)
        if end_date - start_date > max_range:
            raise ValidationError("Date range cannot exceed 1 year")
        
        return True
    
    @staticmethod
    def validate_export_format(format_type):
        """Validate export format"""
        valid_formats = ['json', 'csv', 'xlsx', 'pdf']
        if format_type not in valid_formats:
            raise ValidationError(f"Invalid export format: {format_type}")
        return format_type


class SystemHealthValidator:
    """Validators for system health checks"""
    
    @staticmethod
    def validate_health_check_name(name):
        """Validate health check name"""
        if not name or len(name.strip()) == 0:
            raise ValidationError("Health check name cannot be empty")
        
        if len(name) > 100:
            raise ValidationError("Health check name too long (max 100 characters)")
        
        # Alphanumeric with underscores and hyphens
        if not re.match(r'^[a-zA-Z0-9_-]+$', name):
            raise ValidationError("Health check name can only contain letters, numbers, underscores, and hyphens")
        
        return name.strip()
    
    @staticmethod
    def validate_response_time(response_time):
        """Validate response time"""
        if response_time < 0:
            raise ValidationError("Response time cannot be negative")
        
        if response_time > 300000:  # 5 minutes in milliseconds
            raise ValidationError("Response time too high (max 300000 ms)")
        
        return response_time
    
    @staticmethod
    def validate_health_status(status):
        """Validate health status"""
        valid_statuses = ['healthy', 'degraded', 'unhealthy', 'unknown']
        if status not in valid_statuses:
            raise ValidationError(f"Invalid health status: {status}")
        return status


# Custom Django validators
phone_validator = RegexValidator(
    regex=r'^\+?1?\d{9,15}$',
    message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed."
)

alert_name_validator = RegexValidator(
    regex=r'^[a-zA-Z0-9_\-\s]+$',
    message="Alert name can only contain letters, numbers, spaces, underscores, and hyphens."
)

webhook_url_validator = URLValidator(
    schemes=['http', 'https'],
    message="Webhook URL must be a valid HTTP or HTTPS URL."
)
