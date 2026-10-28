"""
Security Forms Module
Django forms for security-related operations
"""

import logging
from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.core.validators import RegexValidator
from .models import SecurityPolicy, PasswordPolicy, TrustedDevice, IPBlacklist
from .utils import SecurityUtils, PasswordValidator

User = get_user_model()
logger = logging.getLogger('security.forms')


class SecurityPolicyForm(forms.ModelForm):
    """Form for creating and updating security policies"""
    
    class Meta:
        model = SecurityPolicy
        fields = ['policy_key', 'value', 'policy_type', 'description', 'priority', 'is_active']
        widgets = {
            'policy_key': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter policy key'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Enter description'}),
            'priority': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 1000}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['policy_type'].widget = forms.Select(
            choices=SecurityPolicy.POLICY_TYPES,
            attrs={'class': 'form-select'}
        )
        
        # Add help text
        self.fields['policy_key'].help_text = 'Unique key for the policy (e.g., password_min_length)'
        self.fields['value'].help_text = 'Policy value (JSON format for complex policies)'
        self.fields['priority'].help_text = 'Priority level (1-1000, lower numbers have higher priority)'
    
    def clean_policy_key(self):
        """Validate policy key format"""
        policy_key = self.cleaned_data.get('policy_key')
        if policy_key:
            # Check for valid format (alphanumeric with underscores)
            if not SecurityUtils.validate_policy_key(policy_key):
                raise ValidationError("Policy key must contain only letters, numbers, and underscores")
        return policy_key
    
    def clean_value(self):
        """Validate policy value"""
        value = self.cleaned_data.get('value')
        if value:
            # Try to parse as JSON if it looks like JSON
            if isinstance(value, str) and (value.startswith('{') or value.startswith('[')):
                try:
                    import json
                    json.loads(value)
                except json.JSONDecodeError:
                    raise ValidationError("Invalid JSON format for policy value")
        return value


class PasswordPolicyForm(forms.ModelForm):
    """Form for password policy configuration"""
    
    class Meta:
        model = PasswordPolicy
        fields = [
            'name', 'min_length', 'max_length', 'require_uppercase',
            'require_lowercase', 'require_digits', 'require_special_chars',
            'min_special_chars', 'forbidden_patterns', 'password_history_count',
            'expiry_days', 'is_active'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'min_length': forms.NumberInput(attrs={'class': 'form-control', 'min': 6, 'max': 128}),
            'max_length': forms.NumberInput(attrs={'class': 'form-control', 'min': 6, 'max': 128}),
            'min_special_chars': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'max': 10}),
            'password_history_count': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'max': 50}),
            'expiry_days': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'max': 365}),
            'forbidden_patterns': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['require_uppercase'].widget = forms.CheckboxInput(attrs={'class': 'form-check-input'})
        self.fields['require_lowercase'].widget = forms.CheckboxInput(attrs={'class': 'form-check-input'})
        self.fields['require_digits'].widget = forms.CheckboxInput(attrs={'class': 'form-check-input'})
        self.fields['require_special_chars'].widget = forms.CheckboxInput(attrs={'class': 'form-check-input'})
    
    def clean(self):
        """Validate password policy consistency"""
        cleaned_data = super().clean()
        min_length = cleaned_data.get('min_length')
        max_length = cleaned_data.get('max_length')
        require_special_chars = cleaned_data.get('require_special_chars')
        min_special_chars = cleaned_data.get('min_special_chars')
        
        if min_length and max_length and min_length > max_length:
            raise ValidationError("Minimum length cannot be greater than maximum length")
        
        if require_special_chars and min_special_chars and min_special_chars > min_length:
            raise ValidationError("Minimum special characters cannot exceed minimum password length")
        
        return cleaned_data


class TrustedDeviceForm(forms.ModelForm):
    """Form for adding trusted devices"""
    
    class Meta:
        model = TrustedDevice
        fields = ['device_name', 'device_type', 'platform', 'browser', 'expires_at']
        widgets = {
            'device_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter device name'}),
            'device_type': forms.Select(attrs={'class': 'form-select'}),
            'platform': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Windows, iOS, Android'}),
            'browser': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Chrome, Firefox, Safari'}),
            'expires_at': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['device_type'].choices = TrustedDevice.DEVICE_TYPES
        self.fields['expires_at'].help_text = 'Leave blank for no expiration'
    
    def clean_expires_at(self):
        """Validate expiration date"""
        expires_at = self.cleaned_data.get('expires_at')
        if expires_at and expires_at <= timezone.now():
            raise ValidationError("Expiration date must be in the future")
        return expires_at


class IPBlacklistForm(forms.ModelForm):
    """Form for IP blacklist management"""
    
    class Meta:
        model = IPBlacklist
        fields = ['ip_address', 'ip_range', 'reason', 'is_active', 'expires_at']
        widgets = {
            'ip_address': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter IP address'}),
            'ip_range': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter IP range (e.g., 192.168.1.0/24)'}),
            'reason': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Enter reason for blacklisting'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'expires_at': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['expires_at'].help_text = 'Leave blank for permanent blacklist'
    
    def clean(self):
        """Validate IP address or range"""
        cleaned_data = super().clean()
        ip_address = cleaned_data.get('ip_address')
        ip_range = cleaned_data.get('ip_range')
        
        if not ip_address and not ip_range:
            raise ValidationError("Either IP address or IP range must be provided")
        
        if ip_address and ip_range:
            raise ValidationError("Cannot specify both IP address and IP range")
        
        if ip_address and not SecurityUtils.is_valid_ip_address(ip_address):
            raise ValidationError("Invalid IP address format")
        
        if ip_range:
            try:
                import ipaddress
                ipaddress.ip_network(ip_range, strict=False)
            except ValueError:
                raise ValidationError("Invalid IP range format")
        
        expires_at = cleaned_data.get('expires_at')
        if expires_at and expires_at <= timezone.now():
            raise ValidationError("Expiration date must be in the future")
        
        return cleaned_data


class UserSecurityForm(forms.Form):
    """Form for user security settings"""
    
    current_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        required=False,
        help_text="Required for password changes"
    )
    new_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        required=False,
        help_text="Leave blank to keep current password"
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        required=False,
        help_text="Confirm new password"
    )
    email_notifications = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    two_factor_enabled = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    session_timeout = forms.IntegerField(
        min_value=5,
        max_value=1440,  # 24 hours
        initial=30,
        widget=forms.NumberInput(attrs={'class': 'form-control'}),
        help_text="Session timeout in minutes"
    )
    
    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        
        # Set initial values from user settings
        self.fields['email_notifications'].initial = getattr(user, 'email_notifications', True)
        self.fields['two_factor_enabled'].initial = getattr(user, 'two_factor_enabled', False)
        self.fields['session_timeout'].initial = getattr(user, 'session_timeout', 30)
    
    def clean_current_password(self):
        """Validate current password"""
        current_password = self.cleaned_data.get('current_password')
        new_password = self.cleaned_data.get('new_password')
        
        if new_password and not current_password:
            raise ValidationError("Current password is required to change password")
        
        if current_password and not self.user.check_password(current_password):
            raise ValidationError("Current password is incorrect")
        
        return current_password
    
    def clean(self):
        """Validate form consistency"""
        cleaned_data = super().clean()
        new_password = cleaned_data.get('new_password')
        confirm_password = cleaned_data.get('confirm_password')
        
        if new_password and confirm_password and new_password != confirm_password:
            raise ValidationError("New passwords do not match")
        
        if new_password:
            # Validate password strength
            validation_result = PasswordValidator.validate_password_strength(new_password)
            if not validation_result['is_valid']:
                raise ValidationError(validation_result['issues'])
        
        return cleaned_data
    
    def save(self):
        """Save user security settings"""
        user = self.user
        
        # Update password if changed
        new_password = self.cleaned_data.get('new_password')
        if new_password:
            user.set_password(new_password)
        
        # Update security settings
        user.email_notifications = self.cleaned_data.get('email_notifications', True)
        user.two_factor_enabled = self.cleaned_data.get('two_factor_enabled', False)
        user.session_timeout = self.cleaned_data.get('session_timeout', 30)
        
        user.save()
        
        return user


class SecurityIncidentForm(forms.Form):
    """Form for reporting security incidents"""
    
    incident_type = forms.ChoiceField(
        choices=[
            ('phishing', 'Phishing Attempt'),
            ('malware', 'Malware Detection'),
            ('data_breach', 'Data Breach'),
            ('unauthorized_access', 'Unauthorized Access'),
            ('social_engineering', 'Social Engineering'),
            ('other', 'Other')
        ],
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    severity = forms.ChoiceField(
        choices=[
            ('low', 'Low'),
            ('medium', 'Medium'),
            ('high', 'High'),
            ('critical', 'Critical')
        ],
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    title = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Brief incident title'})
    )
    description = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 5, 'placeholder': 'Detailed description of the incident'})
    )
    affected_systems = forms.MultipleChoiceField(
        choices=[
            ('web_application', 'Web Application'),
            ('database', 'Database'),
            ('api', 'API'),
            ('authentication', 'Authentication'),
            ('file_system', 'File System'),
            ('network', 'Network'),
            ('other', 'Other')
        ],
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'})
    )
    evidence = forms.FileField(
        required=False,
        widget=forms.FileInput(attrs={'class': 'form-control'}),
        help_text="Upload evidence files (screenshots, logs, etc.)"
    )
    reporter_name = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Your name (optional)'})
    )
    reporter_email = forms.EmailField(
        required=False,
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Your email (optional)'})
    )
    
    def clean_title(self):
        """Validate title"""
        title = self.cleaned_data.get('title')
        if title and len(title.strip()) < 5:
            raise ValidationError("Title must be at least 5 characters long")
        return title.strip()
    
    def clean_description(self):
        """Validate description"""
        description = self.cleaned_data.get('description')
        if description and len(description.strip()) < 20:
            raise ValidationError("Description must be at least 20 characters long")
        return description.strip()
    
    def clean_evidence(self):
        """Validate evidence file"""
        evidence = self.cleaned_data.get('evidence')
        if evidence:
            # Check file size (max 10MB)
            if evidence.size > 10 * 1024 * 1024:
                raise ValidationError("Evidence file cannot be larger than 10MB")
            
            # Check file type
            allowed_types = ['image/jpeg', 'image/png', 'image/gif', 'application/pdf', 'text/plain']
            if evidence.content_type not in allowed_types:
                raise ValidationError("Only images, PDFs, and text files are allowed")
        
        return evidence


class SecurityAuditForm(forms.Form):
    """Form for security audit requests"""
    
    audit_type = forms.ChoiceField(
        choices=[
            ('full_security', 'Full Security Audit'),
            ('access_control', 'Access Control Audit'),
            ('data_protection', 'Data Protection Audit'),
            ('compliance', 'Compliance Audit'),
            ('vulnerability', 'Vulnerability Assessment'),
            ('penetration', 'Penetration Testing')
        ],
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    scope = forms.MultipleChoiceField(
        choices=[
            ('users', 'User Accounts'),
            ('permissions', 'Permissions'),
            ('data', 'Data Access'),
            ('logs', 'Security Logs'),
            ('infrastructure', 'Infrastructure'),
            ('applications', 'Applications')
        ],
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'})
    )
    start_date = forms.DateField(
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    end_date = forms.DateField(
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    priority = forms.ChoiceField(
        choices=[
            ('low', 'Low'),
            ('medium', 'Medium'),
            ('high', 'High'),
            ('urgent', 'Urgent')
        ],
        initial='medium',
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    additional_notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Additional notes or requirements'})
    )
    
    def clean(self):
        """Validate date range"""
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        
        if start_date and end_date and start_date > end_date:
            raise ValidationError("Start date cannot be after end date")
        
        if start_date and start_date > timezone.now().date():
            raise ValidationError("Start date cannot be in the future")
        
        return cleaned_data


# Export all forms
__all__ = [
    'SecurityPolicyForm',
    'PasswordPolicyForm',
    'TrustedDeviceForm',
    'IPBlacklistForm',
    'UserSecurityForm',
    'SecurityIncidentForm',
    'SecurityAuditForm'
]