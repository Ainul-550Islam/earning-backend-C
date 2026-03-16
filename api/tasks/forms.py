# tasks/forms.py
"""
Beautiful & Bulletproof Forms for Task Management System
- Defensive coding principles applied
- Comprehensive validation
- User-friendly error messages
- Clean & beautiful design
"""

from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db.models import Q
from datetime import timedelta
from decimal import Decimal, InvalidOperation
from .models import MasterTask, UserTaskCompletion, AdminLedger
import json
import logging
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)


# ==================== DEFENSIVE UTILITIES ====================

class FormValidator:
    """Defensive validation utilities for forms"""
    
    @staticmethod
    def safe_decimal(value, default=0.0) -> Decimal:
        """Safely convert to decimal"""
        try:
            if value is None or value == '':
                return Decimal(str(default))
            return Decimal(str(value))
        except (ValueError, InvalidOperation, TypeError) as e:
            logger.warning(f"Error converting to decimal: {e}")
            return Decimal(str(default))
    
    @staticmethod
    def safe_int(value, default=0) -> int:
        """Safely convert to int"""
        try:
            if value is None or value == '':
                return default
            return int(value)
        except (ValueError, TypeError) as e:
            logger.warning(f"Error converting to int: {e}")
            return default
    
    @staticmethod
    def safe_json(value, default=None) -> dict:
        """Safely parse JSON"""
        if default is None:
            default = {}
        try:
            if isinstance(value, dict):
                return value
            if isinstance(value, str):
                return json.loads(value)
            return default
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning(f"Error parsing JSON: {e}")
            return default
    
    @staticmethod
    def validate_url(url: str) -> bool:
        """Validate URL format"""
        try:
            if not url:
                return False
            url = url.strip()
            return url.startswith(('http://', 'https://'))
        except Exception:
            return False
    
    @staticmethod
    def validate_json_structure(data: dict, required_fields: List[str]) -> List[str]:
        """Validate JSON structure has required fields"""
        errors = []
        try:
            if not isinstance(data, dict):
                return ['Data must be a valid JSON object']
            
            for field in required_fields:
                if field not in data:
                    errors.append(f"Missing required field: {field}")
            
            return errors
        except Exception as e:
            logger.error(f"Error validating JSON structure: {e}")
            return ['Invalid JSON structure']


# ==================== CUSTOM WIDGETS ====================

class ColorPickerWidget(forms.TextInput):
    """Custom color picker widget"""
    input_type = 'color'
    
    def __init__(self, attrs=None):
        default_attrs = {'class': 'color-picker'}
        if attrs:
            default_attrs.update(attrs)
        super().__init__(attrs=default_attrs)


class JSONEditorWidget(forms.Textarea):
    """Custom JSON editor widget"""
    
    def __init__(self, attrs=None):
        default_attrs = {
            'class': 'json-editor',
            'rows': 10,
            'style': 'font-family: monospace; background: #f5f5f5; padding: 10px; border-radius: 5px;'
        }
        if attrs:
            default_attrs.update(attrs)
        super().__init__(attrs=default_attrs)


class DateTimePickerWidget(forms.DateTimeInput):
    """Custom datetime picker widget"""
    input_type = 'datetime-local'
    
    def __init__(self, attrs=None):
        default_attrs = {'class': 'datetime-picker'}
        if attrs:
            default_attrs.update(attrs)
        super().__init__(attrs=default_attrs, format='%Y-%m-%dT%H:%M')


# ==================== MASTER TASK FORM ====================

class MasterTaskForm(forms.ModelForm):
    """
    Beautiful & Defensive form for MasterTask
    Complete validation with user-friendly error messages
    """
    
    class Meta:
        model = MasterTask
        fields = [
            'name', 'description', 'system_type', 'category',
            'task_metadata', 'rewards', 'constraints', 'ui_config',
            'is_active', 'is_featured', 'sort_order',
            'available_from', 'available_until',
            'target_user_segments', 'min_user_level', 'max_user_level',
            'daily_completion_limit'
        ]
        
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter task name (e.g., "Watch Video Ad")',
                'maxlength': 200
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Describe what users need to do...',
                'rows': 4
            }),
            'system_type': forms.Select(attrs={
                'class': 'form-control',
            }),
            'category': forms.Select(attrs={
                'class': 'form-control',
            }),
            'task_metadata': JSONEditorWidget(),
            'rewards': JSONEditorWidget(),
            'constraints': JSONEditorWidget(),
            'ui_config': JSONEditorWidget(),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'is_featured': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'sort_order': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 0,
                'value': 0
            }),
            'available_from': DateTimePickerWidget(),
            'available_until': DateTimePickerWidget(),
            'target_user_segments': JSONEditorWidget(attrs={'rows': 5}),
            'min_user_level': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1,
                'value': 1
            }),
            'max_user_level': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1
            }),
            'daily_completion_limit': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1,
                'placeholder': 'Leave empty for unlimited'
            }),
        }
        
        labels = {
            'name': '[NOTE] Task Name',
            'description': '[DOC] Description',
            'system_type': '[FIX] System Type',
            'category': '📂 Category',
            'task_metadata': '⚙️ Task Metadata (JSON)',
            'rewards': '[MONEY] Rewards Configuration (JSON)',
            'constraints': '🔒 Constraints (JSON)',
            'ui_config': '🎨 UI Configuration (JSON)',
            'is_active': '[OK] Active',
            'is_featured': '[STAR] Featured',
            'sort_order': '🔢 Sort Order',
            'available_from': '📅 Available From',
            'available_until': '📅 Available Until',
            'target_user_segments': '👥 Target User Segments (JSON)',
            'min_user_level': '🎯 Minimum User Level',
            'max_user_level': '🎯 Maximum User Level',
            'daily_completion_limit': '[STATS] Daily Completion Limit',
        }
        
        help_texts = {
            'name': 'Clear, concise task name that users will see',
            'description': 'Detailed instructions for users',
            'task_metadata': 'System-specific configuration in JSON format',
            'rewards': 'Reward amounts: {"points": 10, "coins": 0, "experience": 5}',
            'constraints': 'Task constraints: {"daily_limit": 5, "cooldown_minutes": 60}',
            'ui_config': 'UI settings: {"icon": "task.png", "color": "#4CAF50"}',
            'sort_order': 'Lower numbers appear first',
            'available_from': 'When this task becomes available',
            'available_until': 'When this task expires (leave empty for no expiry)',
            'min_user_level': 'Minimum level required to access this task',
            'max_user_level': 'Maximum level allowed (leave empty for no limit)',
            'daily_completion_limit': 'Global daily limit for all users',
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Add CSS classes for better styling
        for field_name, field in self.fields.items():
            if field_name not in ['is_active', 'is_featured']:
                if 'class' not in field.widget.attrs:
                    field.widget.attrs['class'] = 'form-control'
    
    def clean_name(self):
        """Validate task name"""
        name = self.cleaned_data.get('name')
        
        try:
            if not name:
                raise ValidationError('[ERROR] Task name is required')
            
            name = name.strip()
            
            if len(name) < 3:
                raise ValidationError('[ERROR] Task name must be at least 3 characters long')
            
            if len(name) > 200:
                raise ValidationError('[ERROR] Task name cannot exceed 200 characters')
            
            # Check for duplicate names (excluding current instance)
            duplicate_query = MasterTask.objects.filter(name=name)
            if self.instance and self.instance.pk:
                duplicate_query = duplicate_query.exclude(pk=self.instance.pk)
            
            if duplicate_query.exists():
                raise ValidationError(f'[ERROR] Task with name "{name}" already exists')
            
            return name
            
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error validating task name: {e}")
            raise ValidationError('[ERROR] Error validating task name')
    
    def clean_description(self):
        """Validate description"""
        description = self.cleaned_data.get('description')
        
        try:
            if description:
                description = description.strip()
                
                if len(description) > 2000:
                    raise ValidationError('[ERROR] Description cannot exceed 2000 characters')
            
            return description or ''
            
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error validating description: {e}")
            raise ValidationError('[ERROR] Error validating description')
    
    def clean_task_metadata(self):
        """Validate and clean task metadata"""
        metadata = self.cleaned_data.get('task_metadata')
        
        try:
            # If string, try to parse as JSON
            if isinstance(metadata, str):
                metadata = metadata.strip()
                if not metadata:
                    return {}
                metadata = json.loads(metadata)
            
            # Ensure it's a dictionary
            if not isinstance(metadata, dict):
                raise ValidationError('[ERROR] Task metadata must be a valid JSON object')
            
            # Validate based on system type
            system_type = self.cleaned_data.get('system_type')
            if system_type:
                validation_errors = self._validate_metadata_by_type(metadata, system_type)
                if validation_errors:
                    raise ValidationError(validation_errors)
            
            return metadata
            
        except json.JSONDecodeError as e:
            logger.warning(f"JSON decode error in task_metadata: {e}")
            raise ValidationError(f'[ERROR] Invalid JSON format: {str(e)}')
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error validating task_metadata: {e}")
            raise ValidationError(f'[ERROR] Error validating metadata: {str(e)}')
    
    def clean_rewards(self):
        """Validate rewards configuration"""
        rewards = self.cleaned_data.get('rewards')
        
        try:
            # If string, try to parse as JSON
            if isinstance(rewards, str):
                rewards = rewards.strip()
                if not rewards:
                    return {'points': 10, 'coins': 0, 'experience': 5}
                rewards = json.loads(rewards)
            
            # Ensure it's a dictionary
            if not isinstance(rewards, dict):
                raise ValidationError('[ERROR] Rewards must be a valid JSON object')
            
            # Validate reward values
            required_fields = ['points', 'coins', 'experience']
            for field in required_fields:
                if field not in rewards:
                    rewards[field] = 0
                
                value = FormValidator.safe_int(rewards[field], 0)
                
                if value < 0:
                    raise ValidationError(f'[ERROR] {field.capitalize()} cannot be negative')
                
                if value > 10000:
                    raise ValidationError(f'[ERROR] {field.capitalize()} cannot exceed 10,000')
                
                rewards[field] = value
            
            # Ensure at least one reward is positive
            if rewards['points'] == 0 and rewards['coins'] == 0 and rewards['experience'] == 0:
                raise ValidationError('[ERROR] At least one reward must be greater than 0')
            
            return rewards
            
        except json.JSONDecodeError as e:
            logger.warning(f"JSON decode error in rewards: {e}")
            raise ValidationError(f'[ERROR] Invalid JSON format: {str(e)}')
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error validating rewards: {e}")
            raise ValidationError(f'[ERROR] Error validating rewards: {str(e)}')
    
    def clean_constraints(self):
        """Validate constraints configuration"""
        constraints = self.cleaned_data.get('constraints')
        
        try:
            # If string, try to parse as JSON
            if isinstance(constraints, str):
                constraints = constraints.strip()
                if not constraints:
                    return {}
                constraints = json.loads(constraints)
            
            # Ensure it's a dictionary
            if not isinstance(constraints, dict):
                raise ValidationError('[ERROR] Constraints must be a valid JSON object')
            
            # Validate constraint values
            if 'daily_limit' in constraints:
                daily_limit = FormValidator.safe_int(constraints['daily_limit'])
                if daily_limit < 0:
                    raise ValidationError('[ERROR] Daily limit cannot be negative')
                constraints['daily_limit'] = daily_limit if daily_limit > 0 else None
            
            if 'total_limit' in constraints:
                total_limit = FormValidator.safe_int(constraints['total_limit'])
                if total_limit < 0:
                    raise ValidationError('[ERROR] Total limit cannot be negative')
                constraints['total_limit'] = total_limit if total_limit > 0 else None
            
            if 'cooldown_minutes' in constraints:
                cooldown = FormValidator.safe_int(constraints['cooldown_minutes'], 0)
                if cooldown < 0:
                    raise ValidationError('[ERROR] Cooldown cannot be negative')
                if cooldown > 1440:  # 24 hours
                    raise ValidationError('[ERROR] Cooldown cannot exceed 24 hours (1440 minutes)')
                constraints['cooldown_minutes'] = cooldown
            
            if 'required_level' in constraints:
                required_level = FormValidator.safe_int(constraints['required_level'], 1)
                if required_level < 1:
                    raise ValidationError('[ERROR] Required level must be at least 1')
                constraints['required_level'] = required_level
            
            return constraints
            
        except json.JSONDecodeError as e:
            logger.warning(f"JSON decode error in constraints: {e}")
            raise ValidationError(f'[ERROR] Invalid JSON format: {str(e)}')
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error validating constraints: {e}")
            raise ValidationError(f'[ERROR] Error validating constraints: {str(e)}')
    
    def clean_ui_config(self):
        """Validate UI configuration"""
        ui_config = self.cleaned_data.get('ui_config')
        
        try:
            # If string, try to parse as JSON
            if isinstance(ui_config, str):
                ui_config = ui_config.strip()
                if not ui_config:
                    return {}
                ui_config = json.loads(ui_config)
            
            # Ensure it's a dictionary
            if not isinstance(ui_config, dict):
                raise ValidationError('[ERROR] UI config must be a valid JSON object')
            
            # Set defaults
            defaults = {
                'icon': 'default_task.png',
                'color': '#4CAF50',
                'button_text': 'Start'
            }
            
            for key, default_value in defaults.items():
                if key not in ui_config:
                    ui_config[key] = default_value
            
            # Validate color format
            color = ui_config.get('color', '')
            if color and not color.startswith('#'):
                raise ValidationError('[ERROR] Color must be in hex format (e.g., #4CAF50)')
            
            return ui_config
            
        except json.JSONDecodeError as e:
            logger.warning(f"JSON decode error in ui_config: {e}")
            raise ValidationError(f'[ERROR] Invalid JSON format: {str(e)}')
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error validating ui_config: {e}")
            raise ValidationError(f'[ERROR] Error validating UI config: {str(e)}')
    
    def clean_target_user_segments(self):
        """Validate target user segments"""
        segments = self.cleaned_data.get('target_user_segments')
        
        try:
            # If string, try to parse as JSON
            if isinstance(segments, str):
                segments = segments.strip()
                if not segments:
                    return []
                segments = json.loads(segments)
            
            # Ensure it's a list
            if not isinstance(segments, list):
                raise ValidationError('[ERROR] Target user segments must be a valid JSON array')
            
            return segments
            
        except json.JSONDecodeError as e:
            logger.warning(f"JSON decode error in target_user_segments: {e}")
            raise ValidationError(f'[ERROR] Invalid JSON format: {str(e)}')
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error validating target_user_segments: {e}")
            raise ValidationError(f'[ERROR] Error validating target user segments: {str(e)}')
    
    def clean_min_user_level(self):
        """Validate minimum user level"""
        min_level = self.cleaned_data.get('min_user_level')
        
        try:
            min_level = FormValidator.safe_int(min_level, 1)
            
            if min_level < 1:
                raise ValidationError('[ERROR] Minimum user level must be at least 1')
            
            if min_level > 1000:
                raise ValidationError('[ERROR] Minimum user level cannot exceed 1000')
            
            return min_level
            
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error validating min_user_level: {e}")
            raise ValidationError('[ERROR] Error validating minimum user level')
    
    def clean_max_user_level(self):
        """Validate maximum user level"""
        max_level = self.cleaned_data.get('max_user_level')
        
        try:
            if max_level:
                max_level = FormValidator.safe_int(max_level)
                
                if max_level < 1:
                    raise ValidationError('[ERROR] Maximum user level must be at least 1')
                
                if max_level > 1000:
                    raise ValidationError('[ERROR] Maximum user level cannot exceed 1000')
            
            return max_level
            
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error validating max_user_level: {e}")
            raise ValidationError('[ERROR] Error validating maximum user level')
    
    def clean_daily_completion_limit(self):
        """Validate daily completion limit"""
        limit = self.cleaned_data.get('daily_completion_limit')
        
        try:
            if limit:
                limit = FormValidator.safe_int(limit)
                
                if limit < 1:
                    raise ValidationError('[ERROR] Daily completion limit must be at least 1')
                
                if limit > 100000:
                    raise ValidationError('[ERROR] Daily completion limit cannot exceed 100,000')
            
            return limit
            
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error validating daily_completion_limit: {e}")
            raise ValidationError('[ERROR] Error validating daily completion limit')
    
    def clean_sort_order(self):
        """Validate sort order"""
        sort_order = self.cleaned_data.get('sort_order')
        
        try:
            sort_order = FormValidator.safe_int(sort_order, 0)
            
            if sort_order < 0:
                raise ValidationError('[ERROR] Sort order cannot be negative')
            
            return sort_order
            
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error validating sort_order: {e}")
            raise ValidationError('[ERROR] Error validating sort order')
    
    def clean(self):
        """Cross-field validation"""
        cleaned_data = super().clean()
        
        try:
            # Validate date range
            available_from = cleaned_data.get('available_from')
            available_until = cleaned_data.get('available_until')
            
            if available_from and available_until:
                if available_from >= available_until:
                    raise ValidationError({
                        'available_until': '[ERROR] "Available until" must be after "Available from"'
                    })
            
            # Validate level range
            min_level = cleaned_data.get('min_user_level')
            max_level = cleaned_data.get('max_user_level')
            
            if min_level and max_level:
                if min_level > max_level:
                    raise ValidationError({
                        'max_user_level': '[ERROR] Maximum level must be greater than or equal to minimum level'
                    })
            
            # Validate metadata based on system type
            system_type = cleaned_data.get('system_type')
            task_metadata = cleaned_data.get('task_metadata', {})
            
            if system_type and task_metadata:
                validation_errors = self._validate_metadata_by_type(task_metadata, system_type)
                if validation_errors:
                    raise ValidationError({
                        'task_metadata': validation_errors
                    })
            
            return cleaned_data
            
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error in clean method: {e}")
            raise ValidationError('[ERROR] Error validating form data')
    
    def _validate_metadata_by_type(self, metadata: dict, system_type: str) -> Optional[str]:
        """Validate metadata based on system type"""
        try:
            if system_type == MasterTask.SystemType.CLICK_VISIT:
                if 'url' not in metadata:
                    return 'Click/Visit tasks require "url" field in metadata'
                
                if not FormValidator.validate_url(metadata['url']):
                    return 'Invalid URL format in metadata'
                
                if 'duration_seconds' not in metadata:
                    return 'Click/Visit tasks require "duration_seconds" field in metadata'
                
                duration = FormValidator.safe_int(metadata['duration_seconds'])
                if duration < 5:
                    return 'Duration must be at least 5 seconds'
            
            elif system_type == MasterTask.SystemType.GAMIFIED:
                if 'game_type' not in metadata:
                    return 'Gamified tasks require "game_type" field in metadata'
                
                valid_game_types = ['spin', 'scratch', 'slot', 'quiz', 'math', 'typing', 'memory', 'find_object']
                if metadata['game_type'] not in valid_game_types:
                    return f'Invalid game_type. Must be one of: {", ".join(valid_game_types)}'
            
            elif system_type == MasterTask.SystemType.DATA_INPUT:
                if 'input_type' not in metadata:
                    return 'Data Input tasks require "input_type" field in metadata'
                
                valid_input_types = ['quiz', 'survey', 'form', 'translation', 'captcha']
                if metadata['input_type'] not in valid_input_types:
                    return f'Invalid input_type. Must be one of: {", ".join(valid_input_types)}'
            
            elif system_type == MasterTask.SystemType.GUIDE_SIGNUP:
                if 'action_type' not in metadata:
                    return 'Guide/Signup tasks require "action_type" field in metadata'
                
                valid_action_types = ['app_install', 'signup', 'follow', 'subscribe', 'share', 'verify']
                if metadata['action_type'] not in valid_action_types:
                    return f'Invalid action_type. Must be one of: {", ".join(valid_action_types)}'
            
            elif system_type == MasterTask.SystemType.EXTERNAL_WALL:
                if 'provider' not in metadata:
                    return 'External Wall tasks require "provider" field in metadata'
                
                valid_providers = ['adgem', 'offertoro', 'fyber', 'pollfish', 'bitlabs']
                if metadata['provider'] not in valid_providers:
                    return f'Invalid provider. Must be one of: {", ".join(valid_providers)}'
            
            return None
            
        except Exception as e:
            logger.error(f"Error validating metadata by type: {e}")
            return f'Error validating metadata: {str(e)}'


# ==================== USER TASK COMPLETION FORM ====================

class UserTaskCompletionForm(forms.ModelForm):
    """
    Beautiful & Defensive form for UserTaskCompletion
    """
    
    class Meta:
        model = UserTaskCompletion
        fields = ['user', 'task', 'status', 'proof_data', 'ip_address', 'user_agent']
        
        widgets = {
            'user': forms.Select(attrs={
                'class': 'form-control',
            }),
            'task': forms.Select(attrs={
                'class': 'form-control',
            }),
            'status': forms.Select(attrs={
                'class': 'form-control',
            }),
            'proof_data': JSONEditorWidget(attrs={'rows': 6}),
            'ip_address': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '192.168.1.1'
            }),
            'user_agent': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Mozilla/5.0...'
            }),
        }
        
        labels = {
            'user': '👤 User',
            'task': '📋 Task',
            'status': '[STATS] Status',
            'proof_data': '[DOC] Proof Data (JSON)',
            'ip_address': '🌐 IP Address',
            'user_agent': '🖥️ User Agent',
        }
        
        help_texts = {
            'proof_data': 'Evidence of task completion in JSON format',
            'ip_address': 'User\'s IP address during task completion',
            'user_agent': 'Browser/device user agent string',
        }
    
    def clean_proof_data(self):
        """Validate proof data"""
        proof_data = self.cleaned_data.get('proof_data')
        
        try:
            # If string, try to parse as JSON
            if isinstance(proof_data, str):
                proof_data = proof_data.strip()
                if not proof_data:
                    return {}
                proof_data = json.loads(proof_data)
            
            # Ensure it's a dictionary
            if not isinstance(proof_data, dict):
                raise ValidationError('[ERROR] Proof data must be a valid JSON object')
            
            return proof_data
            
        except json.JSONDecodeError as e:
            logger.warning(f"JSON decode error in proof_data: {e}")
            raise ValidationError(f'[ERROR] Invalid JSON format: {str(e)}')
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error validating proof_data: {e}")
            raise ValidationError(f'[ERROR] Error validating proof data: {str(e)}')
    
    def clean_ip_address(self):
        """Validate IP address"""
        ip_address = self.cleaned_data.get('ip_address')
        
        try:
            if ip_address:
                import ipaddress
                # Validate IP format
                ipaddress.ip_address(ip_address)
            
            return ip_address
            
        except ValueError:
            raise ValidationError('[ERROR] Invalid IP address format')
        except Exception as e:
            logger.error(f"Error validating ip_address: {e}")
            raise ValidationError('[ERROR] Error validating IP address')


# ==================== ADMIN LEDGER FORM ====================

class AdminLedgerForm(forms.ModelForm):
    """
    Beautiful & Defensive form for AdminLedger
    """
    
    class Meta:
        model = AdminLedger
        fields = [
            'amount', 'source', 'source_type', 'task', 'user',
            'completion', 'metadata', 'description'
        ]
        
        widgets = {
            'amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0.01',
                'step': '0.01',
                'placeholder': '0.00'
            }),
            'source': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., task_TSK001',
                'maxlength': 50
            }),
            'source_type': forms.Select(attrs={
                'class': 'form-control',
            }),
            'task': forms.Select(attrs={
                'class': 'form-control',
            }),
            'user': forms.Select(attrs={
                'class': 'form-control',
            }),
            'completion': forms.Select(attrs={
                'class': 'form-control',
            }),
            'metadata': JSONEditorWidget(attrs={'rows': 6}),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Describe the source of this profit...'
            }),
        }
        
        labels = {
            'amount': '[MONEY] Amount ($)',
            'source': '[STATS] Source',
            'source_type': '📂 Source Type',
            'task': '📋 Related Task',
            'user': '👤 Related User',
            'completion': '[OK] Related Completion',
            'metadata': '[DOC] Metadata (JSON)',
            'description': '[NOTE] Description',
        }
        
        help_texts = {
            'amount': 'Profit amount in USD (must be positive)',
            'source': 'Identifier for the profit source',
            'source_type': 'Category of profit source',
            'metadata': 'Additional information in JSON format',
            'description': 'Human-readable description of this profit entry',
        }
    
    def clean_amount(self):
        """Validate amount"""
        amount = self.cleaned_data.get('amount')
        
        try:
            amount = FormValidator.safe_decimal(amount, 0)
            
            if amount <= 0:
                raise ValidationError('[ERROR] Amount must be greater than 0')
            
            if amount > 100000:
                raise ValidationError('[ERROR] Amount cannot exceed $100,000')
            
            return amount
            
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error validating amount: {e}")
            raise ValidationError('[ERROR] Error validating amount')
    
    def clean_source(self):
        """Validate source"""
        source = self.cleaned_data.get('source')
        
        try:
            if not source:
                raise ValidationError('[ERROR] Source is required')
            
            source = source.strip()
            
            if len(source) < 3:
                raise ValidationError('[ERROR] Source must be at least 3 characters')
            
            if len(source) > 50:
                raise ValidationError('[ERROR] Source cannot exceed 50 characters')
            
            return source
            
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error validating source: {e}")
            raise ValidationError('[ERROR] Error validating source')
    
    def clean_metadata(self):
        """Validate metadata"""
        metadata = self.cleaned_data.get('metadata')
        
        try:
            # If string, try to parse as JSON
            if isinstance(metadata, str):
                metadata = metadata.strip()
                if not metadata:
                    return {}
                metadata = json.loads(metadata)
            
            # Ensure it's a dictionary
            if not isinstance(metadata, dict):
                raise ValidationError('[ERROR] Metadata must be a valid JSON object')
            
            return metadata
            
        except json.JSONDecodeError as e:
            logger.warning(f"JSON decode error in metadata: {e}")
            raise ValidationError(f'[ERROR] Invalid JSON format: {str(e)}')
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error validating metadata: {e}")
            raise ValidationError(f'[ERROR] Error validating metadata: {str(e)}')
    
    def clean(self):
        """Cross-field validation"""
        cleaned_data = super().clean()
        
        try:
            source_type = cleaned_data.get('source_type')
            task = cleaned_data.get('task')
            user = cleaned_data.get('user')
            completion = cleaned_data.get('completion')
            
            # Validate required relationships based on source type
            if source_type == AdminLedger.SOURCE_TASK:
                if not task:
                    raise ValidationError({
                        'task': '[ERROR] Task is required for task revenue'
                    })
            
            if source_type == AdminLedger.SOURCE_WITHDRAWAL_FEE:
                if not user:
                    raise ValidationError({
                        'user': '[ERROR] User is required for withdrawal fee'
                    })
            
            return cleaned_data
            
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error in clean method: {e}")
            raise ValidationError('[ERROR] Error validating form data')


# ==================== TASK QUICK CREATE FORM ====================

class TaskQuickCreateForm(forms.Form):
    """
    Quick form for creating simple tasks
    """
    
    name = forms.CharField(
        label='[NOTE] Task Name',
        max_length=200,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter task name'
        }),
        help_text='Clear, concise name for the task'
    )
    
    system_type = forms.ChoiceField(
        label='[FIX] System Type',
        choices=MasterTask.SystemType.choices,
        widget=forms.Select(attrs={
            'class': 'form-control'
        }),
        help_text='Select the task system type'
    )
    
    points = forms.IntegerField(
        label='[MONEY] Points Reward',
        min_value=1,
        max_value=10000,
        initial=10,
        widget=forms.NumberInput(attrs={
            'class': 'form-control'
        }),
        help_text='Points awarded for completion'
    )
    
    daily_limit = forms.IntegerField(
        label='[STATS] Daily Limit',
        required=False,
        min_value=1,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Leave empty for unlimited'
        }),
        help_text='Maximum completions per user per day'
    )
    
    is_active = forms.BooleanField(
        label='[OK] Activate immediately',
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        })
    )
    
    def clean_name(self):
        """Validate name"""
        name = self.cleaned_data.get('name')
        
        if not name:
            raise ValidationError('[ERROR] Name is required')
        
        name = name.strip()
        
        if len(name) < 3:
            raise ValidationError('[ERROR] Name must be at least 3 characters')
        
        # Check for duplicates
        if MasterTask.objects.filter(name=name).exists():
            raise ValidationError(f'[ERROR] Task with name "{name}" already exists')
        
        return name
    
    def save(self):
        """Create task from quick form"""
        try:
            task = MasterTask.objects.create(
                name=self.cleaned_data['name'],
                system_type=self.cleaned_data['system_type'],
                category=MasterTask.TaskCategory.DAILY_RETENTION,
                task_metadata={},
                rewards={
                    'points': self.cleaned_data['points'],
                    'coins': 0,
                    'experience': self.cleaned_data['points'] // 2
                },
                constraints={
                    'daily_limit': self.cleaned_data.get('daily_limit')
                },
                is_active=self.cleaned_data['is_active']
            )
            
            logger.info(f"Quick created task: {task.task_id}")
            return task
            
        except Exception as e:
            logger.error(f"Error in quick create: {e}")
            raise ValidationError(f'[ERROR] Error creating task: {str(e)}')


# ==================== TASK FILTER FORM ====================

class TaskFilterForm(forms.Form):
    """
    Form for filtering tasks in admin
    """
    
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '🔍 Search tasks...'
        })
    )
    
    system_type = forms.ChoiceField(
        required=False,
        choices=[('', 'All System Types')] + list(MasterTask.SystemType.choices),
        widget=forms.Select(attrs={
            'class': 'form-control'
        })
    )
    
    category = forms.ChoiceField(
        required=False,
        choices=[('', 'All Categories')] + list(MasterTask.TaskCategory.choices),
        widget=forms.Select(attrs={
            'class': 'form-control'
        })
    )
    
    is_active = forms.ChoiceField(
        required=False,
        choices=[
            ('', 'All Status'),
            ('true', 'Active Only'),
            ('false', 'Inactive Only')
        ],
        widget=forms.Select(attrs={
            'class': 'form-control'
        })
    )
    
    is_featured = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        }),
        label='[STAR] Featured Only'
    )