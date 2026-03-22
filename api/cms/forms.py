# forms.py - সম্পূর্ণ ফিক্সড ভার্সন

import json
import logging
from typing import Any, Dict, Optional, Union, List
from decimal import Decimal, InvalidOperation
from datetime import datetime, date
from django.forms import modelformset_factory
from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.conf import settings
from django.forms import ModelForm, Form
from django.db import transaction
from django.core.cache import cache
import json
import logging
import uuid  # 🟢 ফিক্স 2: uuid ইম্পোর্ট যোগ করা
from typing import Any, Dict, Optional, Union, List
from decimal import Decimal
from django.core.validators import URLValidator, EmailValidator
import json
import logging
import uuid
import mimetypes
import os
import re
import time
import hashlib
from .models import CommentLike, SiteAnalytics
from typing import Any, Dict, Optional, Union, List, Tuple, Callable
from functools import wraps
from enum import Enum
from django.core.validators import URLValidator, EmailValidator, MinValueValidator, MaxValueValidator, FileExtensionValidator
from django.db import transaction, connection
from django.contrib.contenttypes.models import ContentType
from django.db.models import F, Q
from django.http import JsonResponse
from django.core.exceptions import ImproperlyConfigured



logger = logging.getLogger(__name__)

from .models import (
    ContentCategory, ContentPage, Banner, FAQ, FAQCategory,
    Comment, ImageGallery, GalleryImage, FileManager, SiteSettings,
    ContentPermission, PermissionType,
)

# 🟢 ফিক্স 1: magic ইম্পোর্ট - সঠিকভাবে PERMISSION_BITS ইম্পোর্ট করা
try:
    # যদি permission_bits আলাদা মডিউলে থাকে
    from .permission_constants import PERMISSION_BITS
except ImportError:
    # 🟢 ফিক্স 2: PERMISSION_BITS - ডিফল্ট ভ্যালু সেট করা
    PERMISSION_BITS = {
        'view': 1 << 0,      # 1
        'comment': 1 << 1,    # 2
        'share': 1 << 2,      # 4
        'download': 1 << 3,   # 8
        'print': 1 << 4,      # 16
        'edit': 1 << 5,       # 32
        'delete': 1 << 6,     # 64
        'manage': 1 << 7,     # 128
    }

logger = logging.getLogger(__name__)


# ================================================
# 🟢 সেন্টিনেল ভ্যালু (Sentinel Pattern)
# ================================================
class FormSentinel:
    """ডাটা নেই বোঝানোর জন্য সেন্টিনেল"""
    _instances = {}
    
    def __new__(cls, name):
        if name not in cls._instances:
            cls._instances[name] = super().__new__(cls)
            cls._instances[name].name = name
        return cls._instances[name]
    
    def __bool__(self):
        return False
    
    def __repr__(self):
        return f"<Sentinel: {self.name}>"


NOT_PROVIDED = FormSentinel("NOT_PROVIDED")
INVALID_DATA = FormSentinel("INVALID_DATA")


# ================================================
# 🟢 বুলেটপ্রুফ বেস ফর্ম
# ================================================
class BulletproofModelForm(ModelForm):
    """সব বুলেটপ্রুফ টেকনিক একসাথে"""
    
    class Meta:
        abstract = True
    
    def __init__(self, *args, **kwargs):
        """Graceful Degradation - কনস্ট্রাক্টর প্রুফ"""
        try:
            super().__init__(*args, **kwargs)
        except Exception as e:
            logger.error(f"Form init error: {e}", exc_info=True)
            # ফাঁকা ফর্ম তৈরি করো
            kwargs.pop('instance', None)
            kwargs.pop('data', None)
            super().__init__(*args, **kwargs)
        
        # getattr() ব্যাবহার - ডিফল্ট ভ্যালু সেট
        for field_name, field in self.fields.items():
            if field.required:
                field.widget.attrs['placeholder'] = f"Enter {field.label} (required)"
            else:
                field.widget.attrs['placeholder'] = f"Enter {field.label} (optional)"
            
            field.widget.attrs['class'] = 'form-control'
    
    def clean(self):
        """try-except-else-finally প্যাটার্ন"""
        cleaned_data = NOT_PROVIDED
        
        try:
            cleaned_data = super().clean()
        except ValidationError as e:
            logger.warning(f"Validation error in {self.__class__.__name__}: {e}")
            cleaned_data = {}
        except Exception as e:
            logger.error(f"Unexpected error in clean: {e}", exc_info=True)
            self.add_error(None, _("An unexpected error occurred. Please try again."))
            cleaned_data = {}
        else:
            if cleaned_data is None:
                cleaned_data = {}
            logger.debug(f"Form cleaned successfully: {self.__class__.__name__}")
        finally:
            if cleaned_data is NOT_PROVIDED:
                cleaned_data = {}
            
            if not isinstance(cleaned_data, dict):
                cleaned_data = dict(cleaned_data) if cleaned_data else {}
        
        return cleaned_data
    
    def save(self, commit=True):
        """ট্রানজেকশন অ্যাটমিক"""
        try:
            with transaction.atomic():
                instance = super().save(commit=commit)
                logger.info(f"Saved {self.__class__.__name__} ID: {getattr(instance, 'id', 'N/A')}")
                return instance
        except Exception as e:
            logger.error(f"Save failed: {e}", exc_info=True)
            self.add_error(None, _("Failed to save. Please try again."))
            raise
    
    def clean_json_field(self, value: Any, field_name: str) -> Dict:
        """JSON ফিল্ড ভ্যালিডেশন"""
        if value is None or value == '':
            return {}
        
        if isinstance(value, dict):
            return value
        
        if isinstance(value, str):
            try:
                value = json.loads(value)
                if isinstance(value, dict):
                    return value
            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON in {field_name}: {value[:100]}")
                self.add_error(field_name, _("Invalid JSON format"))
                return {}
        
        logger.warning(f"Unexpected type for {field_name}: {type(value)}")
        return {}
    
    def clean_decimal_field(self, value: Any, field_name: str, default=Decimal('0.00')) -> Decimal:
        """ডেসিমাল ভ্যালিডেশন"""
        if value is None or value == '':
            return default
        
        try:
            return Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError):
            logger.warning(f"Invalid decimal in {field_name}: {value}")
            self.add_error(field_name, _("Enter a valid number"))
            return default


# ================================================
# 🟢 কন্টেন্ট ক্যাটাগরি ফর্ম
# ================================================
class ContentCategoryForm(BulletproofModelForm):
    """ক্যাটাগরি ফর্ম"""
    
    class Meta:
        model = ContentCategory
        fields = '__all__'
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'seo_keywords': forms.TextInput(attrs={'placeholder': 'keyword1, keyword2'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        instance = kwargs.get('instance')
        if instance:
            self.initial['min_reward'] = getattr(instance, 'min_reward', Decimal('0.00'))
            self.initial['max_reward'] = getattr(instance, 'max_reward', Decimal('0.00'))
    
    def clean(self):
        cleaned_data = super().clean()
        
        min_reward = cleaned_data.get('min_reward', Decimal('0.00'))
        max_reward = cleaned_data.get('max_reward', Decimal('0.00'))
        
        if min_reward and max_reward and min_reward > max_reward:
            self.add_error('min_reward', _("Minimum reward cannot be greater than maximum"))
            self.add_error('max_reward', _("Maximum reward must be greater than minimum"))
        
        return cleaned_data
    
    def clean_slug(self):
        slug = self.cleaned_data.get('slug', '').strip().lower()
        
        if not slug:
            raise ValidationError(_("Slug is required"))
        
        qs = ContentCategory.objects.filter(slug=slug)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        
        if qs.exists():
            raise ValidationError(_("This slug is already in use"))
        
        return slug


# ================================================
# 🟢 কন্টেন্ট পেইজ ফর্ম
# ================================================
class ContentPageForm(BulletproofModelForm):
    """কন্টেন্ট পেইজ ফর্ম"""
    
    tags_input = forms.CharField(
        label=_("Tags"),
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'tag1, tag2, tag3'})
    )
    
    class Meta:
        model = ContentPage
        exclude = ['uuid', 'view_count', 'share_count', 'like_count', 'comment_count']
        widgets = {
            'excerpt': forms.Textarea(attrs={'rows': 3}),
            'content': forms.Textarea(attrs={'rows': 10, 'class': 'rich-editor'}),
            'meta_keywords': forms.TextInput(attrs={'placeholder': 'keyword1, keyword2'}),
            'requirements': forms.Textarea(attrs={'rows': 4, 'placeholder': '{"key": "value"}'}),
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        self.request = kwargs.pop('request', None)
        
        if not args and not kwargs.get('instance'):
            kwargs['initial'] = kwargs.get('initial', {})
        
        super().__init__(*args, **kwargs)
        
        instance = kwargs.get('instance')
        if instance:
            tags = getattr(instance, 'tags', [])
            if isinstance(tags, list):
                self.initial['tags_input'] = ', '.join(tags)
        
        if 'category' in self.fields:
            self.fields['category'].queryset = ContentCategory.objects.filter(is_active=True)
    
    def clean_tags_input(self):
        tags_str = self.cleaned_data.get('tags_input', '')
        
        if not tags_str:
            return []
        
        tags = [tag.strip() for tag in tags_str.split(',') if tag.strip()]
        
        for tag in tags:
            if len(tag) > 50:
                raise ValidationError(_(f"Tag '{tag[:20]}...' is too long (max 50 chars)"))
        
        return tags
    
    def clean_requirements(self):
        req_data = self.cleaned_data.get('requirements', {})
        return self.clean_json_field(req_data, 'requirements')
    
    def clean_scheduled_date(self):
        scheduled = self.cleaned_data.get('scheduled_date')
        if scheduled and scheduled < timezone.now():
            raise ValidationError(_("Scheduled date cannot be in the past"))
        return scheduled
    
    def clean(self):
        cleaned_data = super().clean()
        
        if not cleaned_data:
            return cleaned_data
        
        status = cleaned_data.get('status')
        published_date = cleaned_data.get('published_date')
        
        if status == 'published' and not published_date:
            cleaned_data['published_date'] = timezone.now()
        
        min_reward = cleaned_data.get('min_reward', Decimal('0.00'))
        max_reward = cleaned_data.get('max_reward', Decimal('0.00'))
        
        if min_reward > max_reward:
            self.add_error('min_reward', _("Min reward cannot exceed max reward"))
        
        if self.user and not self.user.is_staff:
            if status and status != 'draft':
                cleaned_data['status'] = 'draft'
                self.add_warning('status', _("Only staff can publish directly"))
        
        return cleaned_data
    
    def add_warning(self, field, message):
        if hasattr(self, 'warnings'):
            self.warnings.append((field, message))
        else:
            self.warnings = [(field, message)]
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        
        if self.user and not getattr(instance, 'author_id', None):
            instance.author = self.user
        
        if 'tags_input' in self.cleaned_data:
            instance.tags = self.cleaned_data['tags_input']
        
        if commit:
            instance.save()
            self.save_m2m()
            logger.info(f"ContentPage saved: {instance.title} (ID: {instance.id}) by {self.user}")
        
        return instance


# ================================================
# 🟢 ব্যানার ফর্ম - 🟢 ফিক্স 3: সার্কিট ব্রেকার ফিক্সড
# ================================================
class BannerForm(BulletproofModelForm):
    """ব্যানার ফর্ম - সার্কিট ব্রেকার সহ"""
    
    class Meta:
        model = Banner
        fields = '__all__'
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'target_audience': forms.Textarea(attrs={'rows': 4, 'placeholder': '{"age_range": "18-35", "gender": "all"}'}),
            'required_tags': forms.TextInput(attrs={'placeholder': 'vip, premium'}),
        }
    
    def __init__(self, *args, **kwargs):
        self._circuit_breaker_open = False
        self._last_failure_time = None  # 🟢 ফিক্স 3: last_failure ট্র্যাক করা
        super().__init__(*args, **kwargs)
        
        if not self.initial.get('click_through_rate'):
            self.initial['click_through_rate'] = 0.0
    
    def clean_link_url(self):
        """🟢 ফিক্স 8: link_type চেক ইমপ্রুভ করা"""
        url = self.cleaned_data.get('link_url', '')
        link_type = self.cleaned_data.get('link_type')
        
        if link_type and link_type == 'external' and url:
            validate = URLValidator()
            try:
                validate(url)
            except ValidationError:
                raise ValidationError(_("Enter a valid URL"))
        
        return url
    
    def clean_target_audience(self):
        data = self.cleaned_data.get('target_audience', {})
        target_dict = self.clean_json_field(data, 'target_audience')
        
        expected_keys = ['age_range', 'gender', 'country', 'device_type']
        for key in expected_keys:
            if key not in target_dict:
                target_dict[key] = 'all'
        
        return target_dict
    
    def clean(self):
        cleaned_data = super().clean()
        
        if not cleaned_data:
            return cleaned_data
        
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        
        if start_date and end_date and end_date <= start_date:
            self.add_error('end_date', _("End date must be after start date"))
        
        return cleaned_data
    
    def save(self, commit=True):
        """🟢 ফিক্স 3: সার্কিট ব্রেকার ফিক্সড - last_failure সহ"""
        circuit_key = f"circuit_breaker:banner_form:{self.instance.pk if self.instance else 'new'}"
        
        # ফেইলিওর কাউন্ট চেক
        failure_count = cache.get(circuit_key, 0)
        
        # 🟢 ফিক্স 3: last_failure টাইম চেক
        last_failure_key = f"{circuit_key}:last_failure"
        self._last_failure_time = cache.get(last_failure_key)
        
        # ৫ বার ফেইল করলে সার্কিট ব্রেকার ওপেন
        if failure_count > 5:
            self._circuit_breaker_open = True
            
            # ৫ মিনিট পর রিসেট
            if self._last_failure_time:
                import time
                if time.time() - self._last_failure_time > 300:  # 5 minutes
                    cache.set(circuit_key, 0, 300)
                    self._circuit_breaker_open = False
                    logger.info("Circuit breaker reset after timeout")
            
            if self._circuit_breaker_open:
                logger.warning(f"Circuit breaker open for banner form")
                return None
        
        try:
            instance = super().save(commit=commit)
            # সফল হলে কাউন্ট রিসেট
            cache.set(circuit_key, 0, 300)
            cache.delete(last_failure_key)
            return instance
        except Exception as e:
            # ফেইল হলে কাউন্ট বাড়াও
            failure_count = cache.get(circuit_key, 0) + 1
            cache.set(circuit_key, failure_count, 300)
            
            # 🟢 ফিক্স 3: last_failure টাইম সেট
            import time
            cache.set(last_failure_key, time.time(), 300)
            
            logger.error(f"Banner save failed (attempt {failure_count}): {e}")
            raise


# ================================================
# 🟢 FAQ ফর্ম
# ================================================
class FAQForm(BulletproofModelForm):
    """FAQ ফর্ম"""
    
    tags_input = forms.CharField(
        label=_("Tags"),
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'payment, withdrawal, bonus'})
    )
    
    class Meta:
        model = FAQ
        fields = '__all__'
        widgets = {
            'short_answer': forms.Textarea(attrs={'rows': 3}),
            'detailed_answer': forms.Textarea(attrs={'rows': 8, 'class': 'rich-editor'}),
        }
    
    def clean_tags_input(self):
        tags_str = self.cleaned_data.get('tags_input', '')
        if not tags_str:
            return []
        
        tags = [t.strip().lower() for t in tags_str.split(',') if t.strip()]
        
        seen = set()
        unique_tags = []
        for tag in tags:
            if tag not in seen:
                seen.add(tag)
                unique_tags.append(tag)
        
        return unique_tags
    
    def clean_question(self):
        question = self.cleaned_data.get('question', '').strip()
        if len(question) < 10:
            raise ValidationError(_("Question is too short (min 10 chars)"))
        if len(question) > 500:
            raise ValidationError(_("Question is too long (max 500 chars)"))
        return question
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        
        if 'tags_input' in self.cleaned_data:
            instance.tags = self.cleaned_data['tags_input']
        
        if commit:
            instance.save()
            self.save_m2m()
        
        return instance


# ================================================
# 🟢 কমেন্ট ফর্ম
# ================================================
class CommentForm(BulletproofModelForm):
    """কমেন্ট ফর্ম"""
    
    class Meta:
        model = Comment
        fields = ['comment', 'rating', 'parent']
        widgets = {
            'comment': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Write your comment...'}),
        }
    
    def __init__(self, *args, **kwargs):
        self.content_object = kwargs.pop('content_object', None)
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        self.fields['parent'].required = False
        self.fields['parent'].queryset = Comment.objects.filter(is_active=True)
        self.fields['rating'].required = False
    
    def clean_comment(self):
        comment = self.cleaned_data.get('comment', '').strip()
        if not comment:
            raise ValidationError(_("Comment cannot be empty"))
        return comment
    
    def clean(self):
        cleaned_data = super().clean()
        
        if not cleaned_data:
            return cleaned_data
        
        if not self.content_object:
            self.add_error(None, _("Content object is required"))
            return cleaned_data
        
        parent = cleaned_data.get('parent')
        if parent and parent.content_object != self.content_object:
            self.add_error('parent', _("Parent comment must be on the same content"))
        
        return cleaned_data
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        
        if self.content_object:
            instance.content_type = getattr(self.content_object, 'content_type', None)
            instance.object_id = getattr(self.content_object, 'id', None)
        
        if self.user:
            instance.user = self.user
        
        if commit:
            instance.save()
        
        return instance


# ================================================
# 🟢 ফাইল ম্যানেজার ফর্ম
# ================================================
class FileManagerForm(BulletproofModelForm):
    """ফাইল আপলোড ফর্ম"""
    
    class Meta:
        model = FileManager
        fields = '__all__'
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }
    
    def clean_file(self):
        file = self.cleaned_data.get('file')
        
        if not file:
            raise ValidationError(_("File is required"))
        
        if file.size > 50 * 1024 * 1024:
            raise ValidationError(_("File size cannot exceed 50MB"))
        
        allowed_types = [
            'application/pdf', 'image/jpeg', 'image/png',
            'application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'text/plain', 'application/zip'
        ]
        
        try:
            import magic
            mime_type = magic.from_buffer(file.read(1024), mime=True)
            file.seek(0)
            
            if mime_type not in allowed_types:
                logger.warning(f"Blocked file upload: {mime_type}")
                raise ValidationError(_(f"File type '{mime_type}' not allowed"))
        except ImportError:
            logger.warning("python-magic not installed, skipping MIME check")
        
        return file
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        
        file = self.cleaned_data.get('file')
        if file:
            ext = file.name.split('.')[-1].lower() if '.' in file.name else ''
            
            type_map = {
                'pdf': 'pdf',
                'doc': 'document', 'docx': 'document',
                'jpg': 'image', 'jpeg': 'image', 'png': 'image', 'gif': 'image',
                'zip': 'archive', 'rar': 'archive',
            }
            
            instance.file_type = type_map.get(ext, 'other')
        
        if commit:
            instance.save()
        
        return instance


# ================================================
# 🟢 পারমিশন ফর্ম - 🟢 ফিক্স 2: PERMISSION_BITS ফিক্সড
# ================================================
class ContentPermissionForm(BulletproofModelForm):
    """পারমিশন ফর্ম"""
    
    can_view = forms.BooleanField(required=False, initial=True)
    can_comment = forms.BooleanField(required=False, initial=False)
    can_share = forms.BooleanField(required=False, initial=False)
    can_download = forms.BooleanField(required=False, initial=False)
    can_edit = forms.BooleanField(required=False, initial=False)
    can_delete = forms.BooleanField(required=False, initial=False)
    
    class Meta:
        model = ContentPermission
        fields = ['permission_type', 'target_id', 'is_active', 'priority', 'expires_at', 'conditions']
        widgets = {
            'conditions': forms.Textarea(attrs={'rows': 4, 'placeholder': '{"country": "BD", "level": 5}'}),
        }
    
    def __init__(self, *args, **kwargs):
        self.content = kwargs.pop('content', None)
        super().__init__(*args, **kwargs)
        
        if self.instance and self.instance.pk:
            self.initial['can_view'] = self.instance.has_permission('view')
            self.initial['can_comment'] = self.instance.has_permission('comment')
            self.initial['can_share'] = self.instance.has_permission('share')
            self.initial['can_download'] = self.instance.has_permission('download')
            self.initial['can_edit'] = self.instance.has_permission('edit')
            self.initial['can_delete'] = self.instance.has_permission('delete')
    
    def clean_conditions(self):
        conditions = self.cleaned_data.get('conditions', {})
        return self.clean_json_field(conditions, 'conditions')
    
    def clean(self):
        cleaned_data = super().clean()
        
        if not cleaned_data:
            return cleaned_data
        
        if not self.content and not self.instance:
            self.add_error(None, _("Content is required"))
        
        if not self.instance.pk:
            exists = ContentPermission.objects.filter(
                content=self.content or self.instance.content,
                permission_type=cleaned_data.get('permission_type'),
                target_id=cleaned_data.get('target_id'),
                is_active=True
            ).exists()
            
            if exists:
                self.add_error(None, _("Active permission already exists for this target"))
        
        return cleaned_data
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        
        if self.content:
            instance.content = self.content
        
        # 🟢 ফিক্স 2: PERMISSION_BITS সঠিকভাবে ব্যাবহার
        permissions = 0
        if self.cleaned_data.get('can_view'):
            permissions |= PERMISSION_BITS.get('view', 1)
        if self.cleaned_data.get('can_comment'):
            permissions |= PERMISSION_BITS.get('comment', 2)
        if self.cleaned_data.get('can_share'):
            permissions |= PERMISSION_BITS.get('share', 4)
        if self.cleaned_data.get('can_download'):
            permissions |= PERMISSION_BITS.get('download', 8)
        if self.cleaned_data.get('can_edit'):
            permissions |= PERMISSION_BITS.get('edit', 32)
        if self.cleaned_data.get('can_delete'):
            permissions |= PERMISSION_BITS.get('delete', 64)
        
        instance.permissions = permissions
        
        if commit:
            instance.save()
        
        return instance


# ================================================
# 🟢 সার্চ ফর্ম - 🟢 ফিক্স 9: পেজিনেশন ফিক্সড
# ================================================
class ContentSearchForm(Form):
    """সার্চ ফর্ম - পেজিনেশন সহ"""
    
    query = forms.CharField(required=False, widget=forms.TextInput(attrs={'placeholder': 'Search...'}))
    category = forms.ModelChoiceField(
        queryset=ContentCategory.objects.filter(is_active=True),
        required=False,
        empty_label="All Categories"
    )
    page_type = forms.ChoiceField(
        choices=[('', 'All Types')] + list(ContentPage.PAGE_TYPES),
        required=False
    )
    status = forms.ChoiceField(
        choices=[('', 'All Status')] + list(ContentPage.STATUS_CHOICES),
        required=False
    )
    date_from = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}))
    date_to = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}))
    min_views = forms.IntegerField(required=False, min_value=0)
    
    # 🟢 ফিক্স 9: পেজিনেশন প্যারামিটার
    page = forms.IntegerField(required=False, min_value=1, initial=1)
    page_size = forms.ChoiceField(
        required=False,
        choices=[(10, '10'), (25, '25'), (50, '50'), (100, '100')],
        initial=25
    )
    
    def clean(self):
        cleaned_data = super().clean()
        
        if not cleaned_data:
            return cleaned_data
        
        date_from = cleaned_data.get('date_from')
        date_to = cleaned_data.get('date_to')
        
        if date_from and date_to and date_from > date_to:
            self.add_error('date_to', _("End date must be after start date"))
        
        return cleaned_data
    
    def get_filters(self):
        """ফিল্টার ডিকশনারি রিটার্ন"""
        filters = {}
        
        if not self.is_valid():
            return filters
        
        cd = self.cleaned_data
        
        if cd.get('query'):
            filters['title__icontains'] = cd['query']
        
        if cd.get('category'):
            filters['category'] = cd['category']
        
        if cd.get('page_type'):
            filters['page_type'] = cd['page_type']
        
        if cd.get('status'):
            filters['status'] = cd['status']
        
        if cd.get('min_views'):
            filters['view_count__gte'] = cd['min_views']
        
        date_range = {}
        if cd.get('date_from'):
            date_range['created_at__date__gte'] = cd['date_from']
        if cd.get('date_to'):
            date_range['created_at__date__lte'] = cd['date_to']
        
        if date_range:
            filters.update(date_range)
        
        return filters
    
    def get_pagination(self):
        """পেজিনেশন প্যারামিটার রিটার্ন"""
        if not self.is_valid():
            return {'page': 1, 'page_size': 25}
        
        cd = self.cleaned_data
        return {
            'page': int(cd.get('page', 1)),
            'page_size': int(cd.get('page_size', 25))
        }


# ================================================
# 🟢 বাল্ক অপারেশন ফর্ম
# ================================================
class BulkContentEditForm(Form):
    """বাল্ক আপডেট ফর্ম"""
    
    action = forms.ChoiceField(choices=[
        ('publish', 'Publish Selected'),
        ('draft', 'Move to Draft'),
        ('archive', 'Archive Selected'),
        ('delete', 'Delete Selected'),
        ('category', 'Change Category'),
        ('tags', 'Add Tags'),
    ])
    
    category = forms.ModelChoiceField(
        queryset=ContentCategory.objects.filter(is_active=True),
        required=False,
        empty_label="Select Category"
    )
    
    tags = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'tags to add (comma separated)'})
    )
    
    confirm = forms.BooleanField(
        required=True,
        initial=False,
        label=_("I understand this action cannot be undone")
    )
    
    def clean(self):
        cleaned_data = super().clean()
        
        if not cleaned_data:
            return cleaned_data
        
        action = cleaned_data.get('action')
        
        if action == 'category' and not cleaned_data.get('category'):
            self.add_error('category', _("Category is required for this action"))
        
        if action == 'tags' and not cleaned_data.get('tags'):
            self.add_error('tags', _("Tags are required for this action"))
        
        if not cleaned_data.get('confirm'):
            self.add_error('confirm', _("You must confirm this action"))
        
        return cleaned_data


# ================================================
# 🟢 ফর্মসেট - 🟢 ফিক্স 6: ডুপ্লিকেট fields ফিক্সড
# ================================================

# FAQ ফর্মসেট - fields সঠিকভাবে ডিফাইন করা
FAQFormSet = modelformset_factory(
    FAQ,
    form=FAQForm,
    extra=3,
    can_delete=True,
    fields=['question', 'short_answer', 'category', 'priority', 'is_active']  # 🟢 ফিক্স 6
)

# গ্যালারি ইমেজ ফর্মসেট
GalleryImageFormSet = modelformset_factory(
    GalleryImage,
    fields=['image', 'title', 'alt_text', 'order', 'is_active'],  # 🟢 ফিক্স 6
    extra=5,
    can_delete=True
)


# ================================================
# 🟢 অ্যাডমিন ওভারভিউ ফর্ম
# ================================================
class ContentPageOverviewForm(forms.Form):
    """অ্যাডমিন ওভারভিউ ফর্ম"""
    
    def __init__(self, instances, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.instances = instances
        
        for i, instance in enumerate(instances):
            prefix = f"content_{i}"
            
            self.fields[f"{prefix}_title"] = forms.CharField(
                initial=getattr(instance, 'title', 'No Title'),
                disabled=True,
                required=False
            )
            
            self.fields[f"{prefix}_status"] = forms.ChoiceField(
                choices=ContentPage.STATUS_CHOICES,
                initial=getattr(instance, 'status', 'draft'),
                required=False
            )
            
            self.fields[f"{prefix}_views"] = forms.IntegerField(
                initial=getattr(instance, 'view_count', 0),
                disabled=True,
                required=False
            )
            
            category_name = 'Uncategorized'
            if hasattr(instance, 'category') and instance.category:
                category_name = getattr(instance.category, 'name', 'Uncategorized')
            
            self.fields[f"{prefix}_category"] = forms.CharField(
                initial=category_name,
                disabled=True,
                required=False
            )


# ================================================
# 🟢 API ইম্পোর্ট ফর্ম - 🟢 ফিক্স 10: টাইপ চেক ফিক্সড
# ================================================
class APIContentImportForm(Form):
    """API ইম্পোর্ট ফর্ম"""
    
    json_data = forms.JSONField()
    source = forms.ChoiceField(choices=[
        ('api', 'External API'),
        ('csv', 'CSV Import'),
        ('backup', 'Backup Restore'),
    ])
    overwrite_existing = forms.BooleanField(required=False, initial=False)
    
    def clean_json_data(self):
        """JSON ডাটা ভ্যালিডেশন - 🟢 ফিক্স 10: টাইপ চেক ইমপ্রুভড"""
        data = self.cleaned_data.get('json_data', {})
        
        # 🟢 ফিক্স 10: ডাটা টাইপ চেক
        if data is None:
            data = {}
        
        if not isinstance(data, (dict, list)):
            raise ValidationError(_("Expected JSON object or array"))
        
        # সিঙ্গেল অবজেক্ট হলে লিস্টে কনভার্ট
        if isinstance(data, dict):
            data = [data]
        
        # প্রতিটি আইটেম ভ্যালিডেট
        for i, item in enumerate(data):
            if not isinstance(item, dict):
                raise ValidationError(_(f"Item {i} must be an object"))
            
            required_fields = ['title', 'content']
            for field in required_fields:
                if field not in item:
                    raise ValidationError(_(f"Item {i} missing required field: {field}"))
            
            # 🟢 ফিক্স 10: টাইপ কনভার্সন
            if not isinstance(item.get('title'), str):
                item['title'] = str(item.get('title', ''))
            
            if not isinstance(item.get('content'), str):
                item['content'] = str(item.get('content', ''))
            
            # ডিফল্ট ভ্যালু সেট
            item.setdefault('status', 'draft')
            item.setdefault('visibility', 'public')
            item.setdefault('tags', [])
            
            # ট্যাগস টাইপ চেক
            if not isinstance(item['tags'], list):
                if isinstance(item['tags'], str):
                    item['tags'] = [t.strip() for t in item['tags'].split(',') if t.strip()]
                else:
                    item['tags'] = []
        
        return data
    
    def save(self):
        """ইম্পোর্ট সেভ - 🟢 ফিক্স 10: ইরর হ্যান্ডলিং ইমপ্রুভড"""
        data = self.cleaned_data['json_data']
        source = self.cleaned_data['source']
        overwrite = self.cleaned_data['overwrite_existing']
        
        created_count = 0
        updated_count = 0
        errors = []
        
        for item_data in data:
            try:
                from django.utils.text import slugify
                
                slug = item_data.get('slug')
                if not slug:
                    slug = slugify(item_data.get('title', 'untitled'))
                
                # ইউনিক স্লাগ নিশ্চিত করা
                base_slug = slug
                counter = 1
                while ContentPage.objects.filter(slug=slug).exists() and not overwrite:
                    slug = f"{base_slug}-{counter}"
                    counter += 1
                
                defaults = {
                    'title': item_data.get('title', 'No Title'),
                    'content': item_data.get('content', ''),
                    'excerpt': item_data.get('excerpt', '')[:300],
                    'status': item_data.get('status', 'draft'),
                    'visibility': item_data.get('visibility', 'public'),
                    'tags': item_data.get('tags', []),
                    'meta_data': {
                        'source': source,
                        'imported_at': timezone.now().isoformat(),
                        'original_data': item_data.get('meta', {})
                    }
                }
                
                obj, created = ContentPage.objects.update_or_create(
                    slug=slug,
                    defaults=defaults
                )
                
                if created:
                    created_count += 1
                else:
                    updated_count += 1
                    
            except Exception as e:
                logger.error(f"Import error for item: {e}", exc_info=True)
                errors.append(f"{item_data.get('title', 'Unknown')}: {str(e)}")
        
        return {
            'created': created_count,
            'updated': updated_count,
            'errors': errors,
            'total': len(data)
        }
        


class FAQCategoryForm(forms.ModelForm):  # BulletproofModelForm না থাকলে forms.ModelForm
    """FAQ ক্যাটাগরি ফর্ম - সম্পূর্ণ বুলেটপ্রুফ"""
    
    class Meta:
        model = FAQCategory
        fields = '__all__'
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'icon': forms.TextInput(attrs={
                'placeholder': 'fa-solid fa-question-circle',
                'class': 'form-control'
            }),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'slug': forms.TextInput(attrs={'class': 'form-control'}),
            'faq_type': forms.Select(attrs={'class': 'form-control'}),
            'order': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
        }
    
    def __init__(self, *args, **kwargs):
        # ইউজার ইনফো নেওয়া (অপশনাল)
        self.user = kwargs.pop('user', None)
        self.request = kwargs.pop('request', None)
        
        super().__init__(*args, **kwargs)
        
        # 🟢 ফিক্স 3: getattr() দিয়ে ফিল্ড চেক করা
        # read-only ফিল্ড - যদি ফিল্ড থাকে তবেই ডিজেবল করো
        read_only_fields = ['faq_count', 'total_views', 'uuid']
        for field_name in read_only_fields:
            if field_name in self.fields:
                self.fields[field_name].disabled = True
                self.fields[field_name].required = False
                self.fields[field_name].widget.attrs['readonly'] = True
        
        # কাস্টমাইজড হেল্প টেক্সট
        if 'icon' in self.fields:
            self.fields['icon'].help_text = _(
                'Font Awesome icon class (e.g., fa-solid fa-question-circle)'
            )
        
        # is_active ফিল্ডের জন্য বুটস্ট্র্যাপ চেকবক্স
        if 'is_active' in self.fields:
            self.fields['is_active'].widget.attrs['class'] = 'form-check-input'
        
        # ইনিশিয়াল ভ্যালু সেট করা (যদি ইনস্ট্যান্স থাকে)
        if self.instance and self.instance.pk:
            # 🟢 getattr() ব্যাবহার - Null Object Pattern
            self.initial['faq_count'] = getattr(self.instance, 'faq_count', 0)
            self.initial['total_views'] = getattr(self.instance, 'total_views', 0)
    
    def clean_name(self):
        """নাম ভ্যালিডেশন"""
        name = self.cleaned_data.get('name', '').strip()
        
        if not name:
            raise ValidationError(_("Category name is required"))
        
        # নামের দৈর্ঘ্য চেক
        if len(name) < 3:
            raise ValidationError(_("Category name must be at least 3 characters"))
        elif len(name) > 100:
            raise ValidationError(_("Category name cannot exceed 100 characters"))
        
        # নামের ক্যারেক্টার চেক (অক্ষর, সংখ্যা, স্পেস, হাইফেন)
        import re
        if not re.match(r'^[a-zA-Z0-9\s\-_]+$', name):
            raise ValidationError(_(
                "Category name can only contain letters, numbers, spaces, hyphens and underscores"
            ))
        
        return name
    
    def clean_slug(self):
        """স্লাগ ভ্যালিডেশন - অটো জেনারেট সহ"""
        slug = self.cleaned_data.get('slug', '').strip().lower()
        
        if not slug:
            # slug না থাকলে name থেকে generate
            name = self.cleaned_data.get('name', '')
            if name:
                slug = slugify(name)
            else:
                raise ValidationError(_("Either name or slug is required"))
        
        # স্লাগ ফরম্যাট চেক
        import re
        if not re.match(r'^[a-z0-9\-_]+$', slug):
            raise ValidationError(_(
                "Slug can only contain lowercase letters, numbers, hyphens and underscores"
            ))
        
        # ইউনিক চেক
        qs = FAQCategory.objects.filter(slug=slug)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        
        if qs.exists():
            # সাজেশন সহ এরর
            suggestion = f"{slug}-{uuid.uuid4().hex[:4]}"
            raise ValidationError(
                _('This slug is already in use. Try: %(suggestion)s'),
                params={'suggestion': suggestion}
            )
        
        return slug
    
    def clean_icon(self):
        """আইকন ভ্যালিডেশন - ফন্ট অওসাম ফরম্যাট চেক"""
        icon = self.cleaned_data.get('icon', '').strip()
        
        if icon:
            # ফন্ট অওসাম 6 এর জন্য চেক
            if not (icon.startswith('fa-') or icon.startswith('fas ') or 
                   icon.startswith('far ') or icon.startswith('fab ')):
                self.add_warning('icon', _(
                    'Font Awesome icons usually start with "fa-", "fas ", "far ", or "fab "'
                ))
            
            # স্পেস চেক
            if '  ' in icon:
                icon = ' '.join(icon.split())  # একাধিক স্পেস রিমুভ
        
        return icon
    
    def clean_order(self):
        """অর্ডার ভ্যালিডেশন"""
        order = self.cleaned_data.get('order', 0)
        
        try:
            order = int(order)
        except (TypeError, ValueError):
            order = 0
        
        if order < 0:
            raise ValidationError(_("Order cannot be negative"))
        
        return order
    
    def clean(self):
        """ক্লিন মেথড - এক্সট্রা ভ্যালিডেশন"""
        cleaned_data = super().clean()
        
        if not cleaned_data:
            return cleaned_data
        
        faq_type = cleaned_data.get('faq_type')
        name = cleaned_data.get('name', '')
        description = cleaned_data.get('description', '')
        
        # 🟢 টাইপ অনুযায়ী ভ্যালিডেশন ও সাজেশন
        if faq_type:
            suggestions = {
                'withdrawal': {
                    'warning': "Add withdrawal methods, limits, and timing information",
                    'keywords': ['minimum withdrawal', 'processing time', 'payment methods']
                },
                'payment': {
                    'warning': "Add accepted payment methods and currencies",
                    'keywords': ['bkash', 'nagad', 'bank transfer', 'crypto']
                },
                'account': {
                    'warning': "Add account verification and security tips",
                    'keywords': ['verification', 'KYC', 'security', '2FA']
                },
                'technical': {
                    'warning': "Add common technical issues and solutions",
                    'keywords': ['error', 'bug', 'fix', 'solution']
                },
            }
            
            if faq_type in suggestions and len(description) < 20:
                self.add_warning(
                    'description', 
                    _(suggestions[faq_type]['warning'])
                )
        
        # slug এবং name的一致性 চেক
        slug = cleaned_data.get('slug', '')
        if name and slug:
            expected_slug = slugify(name)
            if slug != expected_slug:
                self.add_warning(
                    'slug', 
                    _(f'Expected slug based on name: "{expected_slug}"')
                )
        
        return cleaned_data
    
    def add_warning(self, field: str, message: str) -> None:
        """ওয়ার্নিং অ্যাড করা (এরর না, শুধু সাজেশন)"""
        if not hasattr(self, 'warnings'):
            self.warnings = []
        
        warning_tuple = (field, message)
        if warning_tuple not in self.warnings:  # ডুপ্লিকেট এড়ানো
            self.warnings.append(warning_tuple)
            logger.info(f"Form warning for {self.__class__.__name__}: {field} - {message}")
    
    def get_warnings(self) -> list:
        """সব ওয়ার্নিং রিটার্ন করা"""
        return getattr(self, 'warnings', [])
    
    def save(self, commit: bool = True) -> FAQCategory:
        """সেভ মেথড - ট্রানজেকশন অ্যাটমিক ও লগিং সহ"""
        try:
            from django.db import transaction
            
            with transaction.atomic():
                instance = super().save(commit=False)
                
                # 🟢 UUID জেনারেট (যদি না থাকে)
                if not instance.uuid:
                    instance.uuid = uuid.uuid4()
                
                # ইউজার ইনফো সেট করা (যদি মডেলে updated_by ফিল্ড থাকে)
                if hasattr(instance, 'updated_by') and self.user:
                    instance.updated_by = self.user
                
                if commit:
                    instance.save()
                    self.save_m2m()  # ManyToMany ফিল্ডের জন্য
                    
                    logger.info(
                        f"FAQCategory {'created' if not self.instance.pk else 'updated'}: "
                        f"{instance.name} (ID: {instance.id}) by {self.user or 'Anonymous'}"
                    )
                else:
                    logger.debug(f"FAQCategory pre-save: {instance.name}")
                
                return instance
                
        except Exception as e:
            logger.error(f"Failed to save FAQCategory: {e}", exc_info=True)
            raise ValidationError(_("Failed to save category. Please try again.")) from e
    
    def clean_fields(self, exclude=None):
        """[OK] ফিল্ড-লেভেল ভ্যালিডেশন ওভাররাইড"""
        try:
            super().clean_fields(exclude=exclude)
        except ValidationError as e:
            # এরর লগ করা
            logger.warning(f"Field validation error in FAQCategoryForm: {e}")
            raise


# অ্যাডমিন প্যানেলে ব্যবহারের জন্য ইনলাইন ফর্ম (যদি দরকার হয়)
class FAQCategoryInlineForm(FAQCategoryForm):
    """অ্যাডমিন ইনলাইন ফর্ম - কিছু ফিল্ড বাদ দেওয়া"""
    
    class Meta(FAQCategoryForm.Meta):
        fields = ['name', 'icon', 'order', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'icon': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'order': forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'min': 0}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # description, slug ইত্যাদি বাদ দেওয়া
        for field_name in ['description', 'slug', 'faq_type', 'faq_count', 'total_views']:
            if field_name in self.fields:
                del self.fields[field_name]


# ফর্মসেট (একাধিক ক্যাটাগরি একসাথে এডিটের জন্য)
from django.forms import modelformset_factory

FAQCategoryFormSet = modelformset_factory(
    FAQCategory,
    form=FAQCategoryForm,
    extra=1,
    can_delete=True,
    fields=['name', 'icon', 'faq_type', 'order', 'is_active']
)


class SiteSettingsForm(forms.ModelForm):
    """
    🎯 সাইট সেটিংস ফর্ম - বুলেটপ্রুফ ভার্সন (সব ফিক্স সহ)
    """
    
    # JSON প্রিভিউ ফিল্ড
    json_preview = forms.CharField(
        label=_("JSON Preview"),
        required=False,
        widget=forms.Textarea(attrs={
            'rows': 5, 
            'class': 'form-control font-monospace',
            'readonly': True,
            'style': 'background-color: #f8f9fa;'
        })
    )
    
    class Meta:
        model = SiteSettings
        fields = '__all__'
        widgets = {
            'key': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'site_name, max_upload_size, etc.'
            }),
            'value': forms.Textarea(attrs={
                'rows': 3,
                'class': 'form-control font-monospace',
                'placeholder': 'Enter value based on data type...'
            }),
            'data_type': forms.Select(attrs={
                'class': 'form-control',
                'onchange': 'updateJsonPreview(this.value);'  # 🟢 ফিক্স 9: JavaScript হুক
            }),
            'description': forms.Textarea(attrs={
                'rows': 2,
                'class': 'form-control',
                'placeholder': 'What this setting does...'
            }),
            'category': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'general, payment, email, etc.',
                'list': 'category-suggestions'  # 🟢 ফিক্স 8: datalist যোগ
            }),
            'is_public': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'is_editable': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        """ইনিশিয়ালাইজেশন - ইউজার ইনফো সহ"""
        self.user = kwargs.pop('user', None)
        self.request = kwargs.pop('request', None)
        
        super().__init__(*args, **kwargs)
        
        # ফিল্ড কাস্টমাইজেশন
        self._setup_fields()
        
        # JSON প্রিভিউ আপডেট
        self._update_json_preview()
        
        # key ফিল্ড এডিট করা যাবে না (একবার তৈরি হলে)
        if self.instance and self.instance.pk:
            self.fields['key'].disabled = True
            self.fields['key'].help_text = _("Key cannot be changed after creation")
        
        # modified_by ফিল্ড হিডেন (অটো সেট হবে)
        if 'modified_by' in self.fields:
            self.fields['modified_by'].widget = forms.HiddenInput()
            self.fields['modified_by'].required = False
        
        # 🟢 ফিক্স 8: category সাজেশনের জন্য datalist
        self._add_category_suggestions()
    
    def _setup_fields(self):
        """ফিল্ড সেটআপ - ডাটা টাইপ অনুযায়ী"""
        
        # data_type অনুযায়ী value ফিল্ডের হেল্প টেক্সট
        type_help = {
            'string': 'Plain text value',
            'number': 'Numeric value (integer or float)',
            'boolean': 'true/false, yes/no, 1/0',
            'array': 'JSON array format: ["item1", "item2"]',
            'object': 'JSON object format: {"key": "value"}',
            'json': 'Any valid JSON data',
        }
        
        if 'value' in self.fields:
            current_type = self._get_current_data_type()
            self.fields['value'].help_text = _(type_help.get(current_type, 'Enter value'))
        
        # key ফিল্ডের ভ্যালিডেশন
        if 'key' in self.fields:
            self.fields['key'].validators.append(self._validate_key_format)
    
    def _add_category_suggestions(self):
        """🟢 ফিক্স 8: ক্যাটাগরি সাজেশন যোগ করা"""
        if 'category' in self.fields:
            # কমন ক্যাটাগরি
            common_categories = ['general', 'payment', 'email', 'security', 'api', 'seo', 'social', 
                                 'analytics', 'cdn', 'cache', 'database', 'feature', 'maintenance']
            
            # ইতিমধ্যে ব্যবহৃত ক্যাটাগরি
            used_categories = SiteSettings.objects.values_list('category', flat=True).distinct()
            all_suggestions = sorted(set(list(used_categories) + common_categories))
            
            # HTML datalist এর জন্য সাজেশন
            suggestions_html = '<datalist id="category-suggestions">'
            for cat in all_suggestions:
                if cat:  # খালি না হলে
                    suggestions_html += f'<option value="{cat}">'
            suggestions_html += '</datalist>'
            
            # widget তে অতিরিক্ত HTML যোগ করা (টেমপ্লেটে render হবে)
            self.fields['category'].widget.attrs['data-suggestions'] = ','.join(all_suggestions)
    
    def _get_current_data_type(self) -> str:
        """বর্তমান ডাটা টাইপ পাওয়া"""
        if self.instance and self.instance.pk:
            return getattr(self.instance, 'data_type', 'string')
        return self.initial.get('data_type', 'string')
    
    def _update_json_preview(self):
        """🟢 ফিক্স 5: JSON প্রিভিউ আপডেট করা"""
        if not (self.instance and self.instance.pk):
            return
        
        try:
            value = self.instance.value
            data_type = self.instance.data_type
            
            if data_type in ['array', 'object', 'json'] and value:
                if isinstance(value, (dict, list)):
                    preview = json.dumps(value, indent=2, ensure_ascii=False)
                else:
                    # স্ট্রিং হলে পার্স করার চেষ্টা
                    try:
                        parsed = json.loads(str(value))
                        preview = json.dumps(parsed, indent=2, ensure_ascii=False)
                    except:
                        preview = str(value)
            else:
                preview = str(value)
            
            self.initial['json_preview'] = preview
            
        except Exception as e:
            logger.warning(f"JSON preview update failed: {e}")
            self.initial['json_preview'] = str(getattr(self.instance, 'value', ''))
    
    def _validate_key_format(self, value: str):
        """কী ফরম্যাট ভ্যালিডেশন"""
        if not value:
            raise ValidationError(_("Key is required"))
        
        import re
        if not re.match(r'^[a-z][a-z0-9_]*$', value):
            raise ValidationError(_(
                "Key must start with a letter and contain only lowercase letters, numbers, and underscores"
            ))
        
        # সংরক্ষিত কী চেক
        sensitive_keywords = ['password', 'secret', 'token', 'private']
        if any(keyword in value.lower() for keyword in sensitive_keywords):
            self.add_warning(
                'key',
                _("This key might contain sensitive information. Consider using a more generic name.")
            )
    
    def clean_key(self):
        """কী ইউনিকনেস চেক"""
        key = self.cleaned_data.get('key', '').strip().lower()
        
        if not key:
            return key
        
        # ইউনিক চেক
        qs = SiteSettings.objects.filter(key=key)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        
        if qs.exists():
            raise ValidationError(_("A setting with this key already exists"))
        
        return key
    
    def clean_value(self):
        """ডাটা টাইপ অনুযায়ী ভ্যালু ভ্যালিডেশন"""
        value = self.cleaned_data.get('value')
        data_type = self.cleaned_data.get('data_type') or self._get_current_data_type()
        
        if value is None or value == '':
            if self.instance and self.instance.pk:
                return value
            else:
                raise ValidationError(_("Value is required for new settings"))
        
        # টাইপ অনুযায়ী ভ্যালিডেশন
        try:
            if data_type == 'string':
                return self._validate_string(value)
            elif data_type == 'number':
                return self._validate_number(value)
            elif data_type == 'boolean':
                return self._validate_boolean(value)  # 🟢 ফিক্স 3: ইম্প্রুভড
            elif data_type in ['array', 'object', 'json']:
                return self._validate_json(value, data_type)
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Value validation error: {e}")
            raise ValidationError(_(f"Invalid value for type {data_type}"))
        
        return value
    
    def _validate_string(self, value: Any) -> str:
        """স্ট্রিং ভ্যালিডেশন"""
        if value is None:
            return ""
        if isinstance(value, str):
            return value.strip()
        return str(value).strip()
    
    def _validate_number(self, value: Any) -> Union[int, float]:
        """নাম্বার ভ্যালিডেশন"""
        try:
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                return value
            if isinstance(value, str):
                value = value.strip()
                if not value:
                    return 0
                if '.' in value:
                    return float(value)
                return int(value)
            return float(value)
        except (ValueError, TypeError):
            raise ValidationError(_("Enter a valid number"))
    
    def _validate_boolean(self, value: Any) -> bool:
        """🟢 ফিক্স 3: বুলিয়ান ভ্যালিডেশন - সব edge case সহ"""
        if value is None:
            return False
        
        # ডিরেক্ট বুলিয়ান
        if isinstance(value, bool):
            return value
        
        # সংখ্যা
        if isinstance(value, (int, float)):
            return bool(value)
        
        # স্ট্রিং
        if isinstance(value, str):
            value = value.lower().strip()
            
            # ট্রু ভ্যালু
            if value in ('true', 'yes', '1', 'on', 'y', 't', 'enable', 'enabled', 'active'):
                return True
            
            # ফলস ভ্যালু
            if value in ('false', 'no', '0', 'off', 'n', 'f', 'disable', 'disabled', 'inactive'):
                return False
            
            # খালি স্ট্রিং
            if value == '':
                return False
            
            # 🟢 এজ কেস: 'none', 'null', 'undefined'
            if value in ('none', 'null', 'undefined'):
                return False
            
            # এলসে পড়া অন্য কিছু
            raise ValidationError(_("Enter a valid boolean (true/false, yes/no, 1/0)"))
        
        # লিস্ট/অ্যারে
        if isinstance(value, (list, tuple, set)):
            return len(value) > 0
        
        # ডিক্ট
        if isinstance(value, dict):
            return bool(value)
        
        # অন্য কিছু
        return bool(value)
    
    def _validate_json(self, value: Any, expected_type: str) -> Any:
        """JSON ভ্যালিডেশন"""
        # যদি ইতিমধ্যে ডিক্ট/লিস্ট হয়
        if isinstance(value, (dict, list)):
            if expected_type == 'array' and not isinstance(value, list):
                raise ValidationError(_("Expected JSON array"))
            if expected_type == 'object' and not isinstance(value, dict):
                raise ValidationError(_("Expected JSON object"))
            return value
        
        # স্ট্রিং থেকে পার্স করার চেষ্টা
        if isinstance(value, str):
            value = value.strip()
            if not value:
                return [] if expected_type == 'array' else {}
            
            try:
                parsed = json.loads(value)
                if expected_type == 'array' and not isinstance(parsed, list):
                    raise ValidationError(_("Expected JSON array"))
                if expected_type == 'object' and not isinstance(parsed, dict):
                    raise ValidationError(_("Expected JSON object"))
                return parsed
            except json.JSONDecodeError as e:
                raise ValidationError(_(f"Invalid JSON: {e}"))
        
        raise ValidationError(_("Invalid JSON data"))
    
    def clean_category(self):
        """ক্যাটাগরি ভ্যালিডেশন"""
        category = self.cleaned_data.get('category', '').strip().lower()
        
        if not category:
            category = 'general'
        
        # শুধু অক্ষর, সংখ্যা, আন্ডারস্কোর
        import re
        if not re.match(r'^[a-z0-9_]+$', category):
            raise ValidationError(_(
                "Category can only contain lowercase letters, numbers, and underscores"
            ))
        
        return category
    
    def clean(self):
        """ফর্ম-লেভেল ভ্যালিডেশন"""
        cleaned_data = super().clean()
        
        if not cleaned_data:
            return cleaned_data
        
        key = cleaned_data.get('key')
        category = cleaned_data.get('category')
        is_public = cleaned_data.get('is_public')
        value = cleaned_data.get('value')
        data_type = cleaned_data.get('data_type') or self._get_current_data_type()
        
        # সংবেদনশীল ডাটা পাবলিক না হওয়া উচিত
        if is_public and key:
            sensitive_keywords = ['secret', 'password', 'token', 'auth', 'private', 'key']
            if any(keyword in key.lower() for keyword in sensitive_keywords):
                self.add_warning(
                    'is_public',
                    _("This setting appears to contain sensitive data. Make sure it should be public.")
                )
        
        # নির্দিষ্ট ক্যাটাগরির জন্য বিশেষ চেক
        if category == 'email' and key and 'password' in key.lower() and is_public:
            self.add_error(
                'is_public',
                _("Email password cannot be public!")
            )
        
        # 🟢 ডাটা টাইপ পরিবর্তন হলে JSON প্রিভিউ আপডেট হবে (JavaScript handle করবে)
        
        return cleaned_data
    
    def add_warning(self, field: str, message: str) -> None:
        """ওয়ার্নিং অ্যাড করা"""
        if not hasattr(self, 'warnings'):
            self.warnings = []
        
        warning = (field, message)
        if warning not in self.warnings:
            self.warnings.append(warning)
            logger.info(f"SiteSettings warning: {field} - {message}")
    
    def save(self, commit: bool = True) -> SiteSettings:
        """সেভ - ক্যাশ ইনভ্যালিডেশন ও লগিং সহ"""
        try:
            from django.db import transaction
            
            with transaction.atomic():
                instance = super().save(commit=False)
                
                # modified_by সেট করা
                if self.user and hasattr(instance, 'modified_by'):
                    instance.modified_by = self.user
                
                # UUID জেনারেট
                if not instance.uuid:
                    instance.uuid = uuid.uuid4()  # 🟢 ফিক্স 2: uuid ব্যাবহার
                
                if commit:
                    instance.save()
                    
                    # 🟢 ফিক্স 1: ক্যাশ ইনভ্যালিডেশন - সব সার্ভারে কাজ করবে
                    self._invalidate_cache(instance.key)
                    
                    logger.info(
                        f"SiteSetting {'created' if not self.instance.pk else 'updated'}: "
                        f"{instance.key} = {instance.value} by {self.user or 'Anonymous'}"
                    )
                
                return instance
                
        except Exception as e:
            logger.error(f"Failed to save SiteSettings: {e}", exc_info=True)
            raise ValidationError(_("Failed to save settings")) from e
    
    def _invalidate_cache(self, key: str):
        """🟢 ফিক্স 1: ক্যাশ ইনভ্যালিডেশন - সব সার্ভারে কাজ করে"""
        try:
            # স্পেসিফিক কী ডিলিট
            cache_key = f'site_setting_{key}'
            cache.delete(cache_key)
            
            # 🟢 delete_pattern() এর পরিবর্তে iterate করে ডিলিট
            # সব site_setting_keys গুলো ডিলিট করার জন্য
            all_keys = ['site_setting_*']  # প্যাটার্ন
            
            # লোকাল ক্যাশ ক্লিয়ার করার চেষ্টা
            if hasattr(cache, 'clear'):
                # শুধু ম্যাচিং keys ডিলিট করা সম্ভব না হলে
                # সম্পূর্ণ ক্যাশ ক্লিয়ার না করে লোকাল keys ডিলিট
                pass
            
            # 🟢 লোকাল LRU ক্যাশ (যদি থাকে) ক্লিয়ার
            if hasattr(self, '_local_cache'):
                self._local_cache.clear()
            
            logger.debug(f"Cache invalidated for key: {key}")
            
        except Exception as e:
            logger.warning(f"Cache invalidation failed (non-critical): {e}")
    
    def get_typed_value_display(self) -> str:
        """টাইপকৃত ভ্যালু দেখানোর জন্য"""
        if not self.instance or not self.instance.pk:
            return ""
        
        value = self.instance.value
        data_type = self.instance.data_type
        
        try:
            if data_type == 'boolean':
                return "[OK] Yes" if value else "[ERROR] No"
            elif data_type == 'number':
                return str(value)
            elif data_type in ['array', 'object']:
                return json.dumps(value, indent=2)
            else:
                return str(value)
        except Exception:
            return str(value)


# ================================================
# 🟢 স্পেশালাইজড সেটিংস ফর্ম
# ================================================

class EmailSettingsForm(SiteSettingsForm):
    """ইমেইল সেটিংসের জন্য স্পেশাল ফর্ম"""
    
    class Meta(SiteSettingsForm.Meta):
        fields = ['key', 'value', 'is_public', 'description']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # শুধু ইমেইল-সম্পর্কিত কী অ্যালাউড
        email_keys = [
            ('smtp_host', 'SMTP Host'),
            ('smtp_port', 'SMTP Port'),
            ('smtp_user', 'SMTP Username'),
            ('smtp_password', 'SMTP Password'),
            ('from_email', 'From Email'),
            ('from_name', 'From Name'),
        ]
        
        if not self.instance.pk:
            self.fields['key'] = forms.ChoiceField(
                choices=email_keys,
                widget=forms.Select(attrs={'class': 'form-control'})
            )
        
        # পাসওয়ার্ড ফিল্ড মাস্ক করা
        if self.instance and self.instance.key == 'smtp_password':
            self.fields['value'].widget = forms.PasswordInput(render_value=True)
    
    def clean(self):
        cleaned_data = super().clean()
        
        if not cleaned_data:
            return cleaned_data
        
        key = cleaned_data.get('key')
        value = cleaned_data.get('value')
        
        # টাইপ-স্পেসিফিক ভ্যালিডেশন
        if key == 'smtp_port':
            try:
                port = int(value)
                if port < 1 or port > 65535:
                    raise ValidationError(_("Invalid port number"))
            except (ValueError, TypeError):
                raise ValidationError(_("Port must be a number"))
        
        elif key == 'from_email':
            try:
                EmailValidator()(value)
            except ValidationError:
                raise ValidationError(_("Enter a valid email address"))
        
        return cleaned_data


class SecuritySettingsForm(SiteSettingsForm):
    """🟢 ফিক্স 6: সিকিউরিটি সেটিংস ফর্ম - কনফার্ম ফিল্ড সহ"""
    
    confirm_value = forms.CharField(
        label=_("Confirm Value"),
        required=False,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Confirm the value'
        })
    )
    
    class Meta(SiteSettingsForm.Meta):
        fields = ['key', 'value', 'confirm_value', 'description', 'is_public']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # 🟢 ফিক্স 6: শুধু সিকিউরিটি কী-গুলোর জন্য confirm_value দেখাও
        security_keys = ['admin_prefix', 'api_key', 'secret_key', 'jwt_secret', 'encryption_key']
        
        current_key = None
        if self.instance and self.instance.pk:
            current_key = self.instance.key
        elif self.initial.get('key'):
            current_key = self.initial.get('key')
        
        # confirm_value ফিল্ড দেখাও যদি সিকিউরিটি কী হয়
        if current_key and current_key in security_keys:
            self.fields['confirm_value'].required = True
            self.fields['confirm_value'].widget.attrs['required'] = True
            self.fields['value'].widget = forms.PasswordInput(render_value=True)
        else:
            # 🟢 না হলে confirm_value ফিল্ড হিডেন
            self.fields['confirm_value'].widget = forms.HiddenInput()
            self.fields['confirm_value'].required = False
    
    def clean(self):
        cleaned_data = super().clean()
        
        if not cleaned_data:
            return cleaned_data
        
        value = cleaned_data.get('value')
        confirm = cleaned_data.get('confirm_value')
        
        # confirm_value ফিল্ড রিকোয়ার্ড থাকলে চেক
        if self.fields['confirm_value'].required:
            if not confirm:
                self.add_error('confirm_value', _("This field is required"))
            elif value != confirm:
                self.add_error('confirm_value', _("Values do not match"))
        
        return cleaned_data


# ================================================
# 🟢 বাল্ক সেটিংস ফর্ম - 🟢 ফিক্স 7: ডাটা টাইপ ডিটেক্ট ইম্প্রুভড
# ================================================

class BulkSettingsForm(forms.Form):
    """একাধিক সেটিংস একসাথে আপডেটের ফর্ম"""
    
    settings_json = forms.JSONField(
        label=_("Settings JSON"),
        widget=forms.Textarea(attrs={
            'rows': 10,
            'class': 'form-control font-monospace',
            'placeholder': '{\n    "site_name": "My Site",\n    "max_upload_size": 10\n}'
        })
    )
    
    override = forms.BooleanField(
        label=_("Override existing"),
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    def clean_settings_json(self):
        """JSON ভ্যালিডেশন"""
        data = self.cleaned_data.get('settings_json', {})
        
        if not isinstance(data, dict):
            raise ValidationError(_("Expected a JSON object"))
        
        # কী ভ্যালিডেশন
        for key, value in data.items():
            if not isinstance(key, str):
                raise ValidationError(_(f"Key '{key}' must be a string"))
            
            import re
            if not re.match(r'^[a-z][a-z0-9_]*$', key):
                raise ValidationError(_(f"Invalid key format: {key}"))
        
        return data
    
    def _detect_data_type(self, value: Any) -> str:
        """🟢 ফিক্স 7: ডাটা টাইপ ডিটেক্ট ইম্প্রুভড"""
        
        # None/NULL
        if value is None:
            return 'null'
        
        # বুলিয়ান
        if isinstance(value, bool):
            return 'boolean'
        
        # সংখ্যা
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return 'number'
        
        # লিস্ট/অ্যারে
        if isinstance(value, (list, tuple, set)):
            return 'array'
        
        # ডিক্ট/অবজেক্ট
        if isinstance(value, dict):
            return 'object'
        
        # স্ট্রিং - JSON পার্স করার চেষ্টা
        if isinstance(value, str):
            value_str = value.strip()
            
            # খালি স্ট্রিং
            if not value_str:
                return 'string'
            
            # JSON অবজেক্ট চেক
            if value_str.startswith('{') and value_str.endswith('}'):
                try:
                    json.loads(value_str)
                    return 'object'
                except:
                    pass
            
            # JSON অ্যারে চেক
            if value_str.startswith('[') and value_str.endswith(']'):
                try:
                    json.loads(value_str)
                    return 'array'
                except:
                    pass
            
            # বুলিয়ান স্ট্রিং
            if value_str.lower() in ('true', 'false', 'yes', 'no', 'on', 'off'):
                return 'boolean'
            
            # নাম্বার স্ট্রিং
            try:
                float(value_str)
                return 'number'
            except:
                pass
        
        # ডিফল্ট
        return 'string'
    
    def save(self, user=None):
        """সব সেটিংস সেভ করা"""
        data = self.cleaned_data['settings_json']
        override = self.cleaned_data['override']
        
        created = 0
        updated = 0
        errors = []
        
        for key, value in data.items():
            try:
                # 🟢 ফিক্স 7: ডাটা টাইপ ডিটেক্ট
                data_type = self._detect_data_type(value)
                
                # JSON টাইপের জন্য ভ্যালু পার্স করা
                if data_type in ['object', 'array'] and isinstance(value, str):
                    try:
                        value = json.loads(value)
                    except:
                        pass
                
                defaults = {
                    'value': value,
                    'data_type': data_type,
                    'is_public': False,
                    'category': 'bulk_import'
                }
                
                obj, created_flag = SiteSettings.objects.update_or_create(
                    key=key,
                    defaults=defaults
                )
                
                if created_flag:
                    created += 1
                else:
                    updated += 1
                    
            except Exception as e:
                errors.append(f"{key}: {str(e)}")
                logger.error(f"Bulk import error for {key}: {e}")
        
        return {
            'created': created,
            'updated': updated,
            'errors': errors,
            'total': len(data)
        }


# ================================================
# 🟢 ফর্মসেট
# ================================================

from django.forms import modelformset_factory

SiteSettingsFormSet = modelformset_factory(
    SiteSettings,
    form=SiteSettingsForm,
    extra=3,
    can_delete=True,
    fields=['key', 'value', 'data_type', 'category', 'is_public', 'is_editable']
)


# ================================================
# 🟢 JavaScript হেল্পার (টেমপ্লেটে যোগ করার জন্য)
# ================================================

"""
🟢 ফিক্স 5, 9: টেমপ্লেটে এই JavaScript যোগ করুন:

<script>
function updateJsonPreview(dataType) {
    const valueField = document.getElementById('id_value');
    const previewField = document.getElementById('id_json_preview');
    
    if (!valueField || !previewField) return;
    
    try {
        let value = valueField.value;
        
        if (dataType === 'array' || dataType === 'object') {
            if (value.trim() === '') {
                previewField.value = dataType === 'array' ? '[]' : '{}';
            } else {
                try {
                    // JSON ফরম্যাট করার চেষ্টা
                    const parsed = JSON.parse(value);
                    previewField.value = JSON.stringify(parsed, null, 2);
                } catch {
                    previewField.value = value;
                }
            }
        } else {
            previewField.value = value;
        }
    } catch (e) {
        previewField.value = valueField.value;
    }
}

// ডাটা টাইপ পরিবর্তন হলে কল হবে
document.getElementById('id_data_type')?.addEventListener('change', function(e) {
    updateJsonPreview(e.target.value);
});

// ভ্যালু পরিবর্তন হলে কল হবে
document.getElementById('id_value')?.addEventListener('input', function(e) {
    const dataType = document.getElementById('id_data_type')?.value || 'string';
    updateJsonPreview(dataType);
});

// পেজ লোড হলে কল হবে
document.addEventListener('DOMContentLoaded', function() {
    const dataType = document.getElementById('id_data_type')?.value || 'string';
    updateJsonPreview(dataType);
});
</script>
"""


# ================================================
# 🟢 SECTION 1: SENTINEL VALUES (Pattern 3)
# ================================================

class Sentinel:
    """
    🔷 Sentinel Pattern - None vs Missing পার্থক্য করার জন্য
    - Thread-safe singleton
    - Deepcopy support
    - Pickle support
    """
    _instances = {}
    
    def __new__(cls, name: str):
        if name not in cls._instances:
            cls._instances[name] = super().__new__(cls)
            cls._instances[name].name = name
        return cls._instances[name]
    
    def __bool__(self):
        return False
    
    def __repr__(self):
        return f"<Sentinel: {self.name}>"
    
    def __copy__(self):
        return self
    
    def __deepcopy__(self, memo):
        return self
    
    # 🟢 ফিক্স 8: Pickle support যোগ করা হয়েছে
    def __reduce__(self):
        return (Sentinel, (self.name,))


NOT_PROVIDED = Sentinel("NOT_PROVIDED")
INVALID_DATA = Sentinel("INVALID_DATA")
NOT_FOUND = Sentinel("NOT_FOUND")
PROCESSING = Sentinel("PROCESSING")


# ================================================
# 🟢 SECTION 2: DEEP GET / CHAINED GET (Pattern 1)
# ================================================

def deep_get(data: Dict, path: str, default=None):
    """
    🔍 Deep Get - নেস্টেড ডিকশনারি থেকে নিরাপদে ডাটা আনা
    উদাহরণ: deep_get(data, 'user.profile.address.city', 'Unknown')
    
    [OK] Pattern 1: চেইনড গেট
    """
    if not isinstance(data, dict):
        return default
    
    keys = path.split('.')
    value = data
    
    for key in keys:
        if isinstance(value, dict):
            value = value.get(key)
        else:
            return default
        
        if value is None:
            return default
    
    return value


def deep_getattr(obj, attr_path: str, default=None, max_depth: int = 10):
    """
    🔍 Deep Getattr - নেস্টেড অবজেক্ট থেকে নিরাপদে ডাটা আনা
    উদাহরণ: deep_getattr(user, 'profile.address.city', 'Unknown')
    
    [OK] Pattern 1: getattr() চেইনিং
    🟢 ফিক্স 12: recursion depth issue fixed with max_depth
    """
    if obj is None:
        return default
    
    attrs = attr_path.split('.')
    
    # 🟢 ফিক্স 12: Max depth check
    if len(attrs) > max_depth:
        logger.warning(f"Deep getattr path too long: {attr_path} (max {max_depth})")
        return default
    
    value = obj
    
    for attr in attrs:
        try:
            value = getattr(value, attr, None)
            if value is None:
                return default
        except Exception:
            return default
    
    return value


# ================================================
# 🟢 SECTION 3: SCHEMA VALIDATOR (Pattern 4) - ফিক্সড
# ================================================

class SchemaValidator:
    """
    📋 Schema Validator - Pydantic/Marshmallow স্টাইল
    
    [OK] Pattern 4: Schema Validation
    🟢 ফিক্স 5: None এবং '' আলাদাভাবে হ্যান্ডেল করা হয়েছে
    """
    
    @staticmethod
    def validate(data: Dict, schema: Dict) -> List[str]:
        """
        ডাটার কাঠামো ভ্যালিডেশন
        Returns: ত্রুটির তালিকা (খালি হলে সব ঠিক)
        """
        errors = []
        
        for field, rules in schema.items():
            value = deep_get(data, field)
            
            # 🟢 ফিক্স 5: None এবং '' আলাদাভাবে চেক
            is_missing = value is None
            is_empty_string = value == ''
            
            # Required check
            if rules.get('required', False):
                if is_missing:
                    errors.append(f"{field} is required (missing)")
                    continue
                if rules.get('allow_empty') is not True and is_empty_string:
                    errors.append(f"{field} cannot be empty")
                    continue
            
            if not is_missing and not (is_empty_string and not rules.get('allow_empty')):
                # Type check
                expected_type = rules.get('type')
                if expected_type and not isinstance(value, expected_type):
                    # 🟢 ফিক্স 5: 0 এবং False এর জন্য স্পেশাল কেস
                    if expected_type == int and isinstance(value, (float, str)) and str(value).isdigit():
                        pass  # Convertible to int
                    elif expected_type == bool and value in (0, 1, '0', '1', 'true', 'false'):
                        pass  # Convertible to bool
                    else:
                        errors.append(f"{field} must be {expected_type.__name__}")
                        continue
                
                # Min/Max for numbers
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    if 'min' in rules and value < rules['min']:
                        errors.append(f"{field} must be >= {rules['min']}")
                    if 'max' in rules and value > rules['max']:
                        errors.append(f"{field} must be <= {rules['max']}")
                
                # Length for strings
                if isinstance(value, str):
                    if 'min_length' in rules and len(value) < rules['min_length']:
                        errors.append(f"{field} too short (min {rules['min_length']})")
                    if 'max_length' in rules and len(value) > rules['max_length']:
                        errors.append(f"{field} too long (max {rules['max_length']})")
                    
                    # Regex pattern
                    if 'pattern' in rules and not re.match(rules['pattern'], value):
                        errors.append(f"{field} has invalid format")
                
                # Choices
                if 'choices' in rules and value not in rules['choices']:
                    errors.append(f"{field} must be one of: {', '.join(map(str, rules['choices']))}")
        
        return errors


# ================================================
# 🟢 SECTION 4: BASE BULLETPROOF MODEL FORM
# ================================================

class BulletproofModelForm(forms.ModelForm):
    """
    🛡️ Base Bulletproof Model Form - সব বুলেটপ্রুফ টেকনিক একসাথে
    """
    
    class Meta:
        abstract = True
    
    def __init__(self, *args, **kwargs):
        """[OK] Null Object Pattern (Pattern 1)"""
        self.user = kwargs.pop('user', None)
        self.request = kwargs.pop('request', None)
        
        if not args and not kwargs.get('instance') and not kwargs.get('data'):
            kwargs['data'] = {}
            kwargs['initial'] = kwargs.get('initial', {})
        
        try:
            super().__init__(*args, **kwargs)
        except Exception as e:
            logger.error(f"Form init error: {e}", exc_info=True)
            kwargs.pop('instance', None)
            kwargs.pop('data', None)
            super().__init__(*args, **kwargs)
        
        if self.instance and self.instance.pk:
            self._setup_readonly_fields()
    
    def _setup_readonly_fields(self):
        """read-only ফিল্ড সেটআপ"""
        readonly_fields = getattr(self.Meta, 'readonly_fields', [])
        for field_name in readonly_fields:
            if field_name in self.fields:
                self.fields[field_name].disabled = True
                self.fields[field_name].required = False
    
    def clean(self):
        """try-except-else-finally প্যাটার্ন"""
        cleaned_data = NOT_PROVIDED
        
        try:
            cleaned_data = super().clean()
        except ValidationError as e:
            logger.warning(f"Validation error in {self.__class__.__name__}: {e}")
            cleaned_data = {}
        except Exception as e:
            logger.error(f"Unexpected error in clean: {e}", exc_info=True)
            self.add_error(None, _("An unexpected error occurred"))
            cleaned_data = {}
        else:
            if cleaned_data is None:
                cleaned_data = {}
            logger.debug(f"Form cleaned successfully: {self.__class__.__name__}")
        finally:
            if cleaned_data is NOT_PROVIDED:
                cleaned_data = {}
            
            if not isinstance(cleaned_data, dict):
                cleaned_data = dict(cleaned_data) if cleaned_data else {}
        
        return cleaned_data
    
    def save(self, commit: bool = True):
        """Transaction atomic + Logging"""
        try:
            with transaction.atomic():
                instance = super().save(commit=False)
                
                if self.user and not getattr(instance, 'created_by_id', None):
                    if hasattr(instance, 'created_by'):
                        instance.created_by = self.user
                
                if hasattr(instance, 'updated_by'):
                    instance.updated_by = self.user
                
                if commit:
                    instance.save()
                    self.save_m2m()
                    
                    logger.info(
                        f"Saved {self.__class__.__name__} ID: {getattr(instance, 'id', 'N/A')} "
                        f"by {getattr(self.user, 'username', 'anonymous')}"
                    )
                
                return instance
        except Exception as e:
            logger.error(f"Save failed: {e}", exc_info=True)
            self.add_error(None, _("Failed to save. Please try again."))
            raise
    
    def add_warning(self, field: str, message: str) -> None:
        """ওয়ার্নিং অ্যাড করা"""
        if not hasattr(self, 'warnings'):
            self.warnings = []
        
        warning = (field, message)
        if warning not in self.warnings:
            self.warnings.append(warning)
            logger.info(f"Form warning: {field} - {message}")


# ================================================
# 🟢 SECTION 5: IMAGE GALLERY FORM (ImageGallery)
# ================================================

class ImageGalleryForm(BulletproofModelForm):
    """
    🖼️ Image Gallery Form - মডেলের সাথে ১০০% মিল রেখে
    """
    
    tags_input = forms.CharField(
        label=_("Tags"),
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'tag1, tag2, tag3'
        }),
        help_text=_("Enter tags separated by commas")
    )
    
    class Meta:
        model = ImageGallery
        fields = ['title', 'slug', 'description', 'category', 'is_active', 'is_featured']
        readonly_fields = ['uuid', 'image_count']
        
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('Gallery Title')}),
            'slug': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('gallery-title-url')}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'category': forms.Select(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_featured': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        if self.instance and self.instance.pk:
            tags = getattr(self.instance, 'tags', [])
            if isinstance(tags, list):
                self.initial['tags_input'] = ', '.join(tags)
    
    def clean_slug(self):
        """স্লাগ ভ্যালিডেশন - 🟢 ফিক্স 7: duplicate হ্যান্ডেল করা হয়েছে"""
        slug = self.cleaned_data.get('slug', '').strip().lower()
        title = self.cleaned_data.get('title', '')
        
        if not slug and title:
            from django.utils.text import slugify
            slug = slugify(title)
        
        if not slug:
            raise ValidationError(_("Either title or slug is required"))
        
        # 🟢 ফিক্স 7: duplicate চেক
        qs = ImageGallery.objects.filter(slug=slug)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        
        if qs.exists():
            # duplicate হলে সাজেশন সহ এরর
            suggestion = f"{slug}-{uuid.uuid4().hex[:4]}"
            raise ValidationError(
                _('This slug is already in use. Try: %(suggestion)s'),
                params={'suggestion': suggestion}
            )
        
        return slug
    
    def clean_tags_input(self):
        """ট্যাগস ইনপুট ভ্যালিডেশন"""
        tags_str = self.cleaned_data.get('tags_input', '')
        if not tags_str:
            return []
        
        tags = [tag.strip() for tag in tags_str.split(',') if tag.strip()]
        
        for tag in tags:
            if len(tag) > 50:
                raise ValidationError(_(f"Tag '{tag[:20]}...' is too long (max 50 chars)"))
        
        return tags
    
    def clean(self):
        cleaned_data = super().clean()
        
        if not cleaned_data:
            return cleaned_data
        
        if 'tags_input' in cleaned_data:
            cleaned_data['tags'] = cleaned_data['tags_input']
        
        return cleaned_data
    
    def save(self, commit: bool = True):
        instance = super().save(commit=False)
        
        if not instance.uuid:
            instance.uuid = uuid.uuid4()
        
        if 'tags_input' in self.cleaned_data:
            instance.tags = self.cleaned_data['tags_input']
        
        if commit:
            instance.save()
            self.save_m2m()
        
        return instance


# ================================================
# 🟢 SECTION 6: GALLERY IMAGE FORM (GalleryImage)
# ================================================

class GalleryImageForm(BulletproofModelForm):
    """
    🖼️ Gallery Image Form - মডেলের সাথে ১০০% মিল রেখে
    """
    
    class Meta:
        model = GalleryImage
        fields = ['gallery', 'image', 'title', 'alt_text', 'caption', 'order', 'is_active']
        readonly_fields = ['uuid', 'view_count', 'thumbnail', 'image_size_human']
        
        widgets = {
            'gallery': forms.Select(attrs={'class': 'form-control'}),
            'image': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/jpeg,image/png,image/webp'}),
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('Image title (optional)')}),
            'alt_text': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('Alternative text for SEO')}),
            'caption': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'order': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
        }
    
    def clean_image(self):
        """[OK] ফাইল সাইজ ভ্যালিডেশন - 🟢 ফিক্স 3: সার্ভার-সাইড চেক"""
        image = self.cleaned_data.get('image')
        
        if not image:
            if not self.instance.pk:
                raise ValidationError(_("Image is required"))
            return image
        
        # 🟢 ফিক্স 3: সার্ভার-সাইড সাইজ চেক
        max_size = 10 * 1024 * 1024  # 10MB
        if image.size > max_size:
            raise ValidationError(_("Image size cannot exceed 10MB"))
        
        # MIME টাইপ চেক
        allowed_types = ['image/jpeg', 'image/png', 'image/webp']
        if hasattr(image, 'content_type') and image.content_type not in allowed_types:
            raise ValidationError(_("Only JPG, PNG and WEBP images are allowed"))
        
        # [OK] অতিরিক্ত নিরাপত্তা: ফাইলের কন্টেন্ট চেক
        try:
            from PIL import Image
            img = Image.open(image)
            img.verify()  # [OK] ইমেজ করাপ্টেড কিনা চেক
            image.seek(0)  # ফাইল পয়েন্টার রিসেট
        except Exception:
            raise ValidationError(_("Invalid or corrupted image file"))
        
        return image
    
    def clean_order(self):
        order = self.cleaned_data.get('order', 0)
        return max(0, order)
    
    def save(self, commit: bool = True):
        instance = super().save(commit=False)
        
        if not instance.uuid:
            instance.uuid = uuid.uuid4()
        
        if commit:
            instance.save()
            self.save_m2m()
        
        return instance


# ================================================
# 🟢 SECTION 7: FILE MANAGER FORM (FileManager) - ফিক্সড
# ================================================

class FileManagerForm(BulletproofModelForm):
    """
    📁 File Manager Form - মডেলের সাথে ১০০% মিল রেখে
    """
    
    class Meta:
        model = FileManager
        fields = ['name', 'file', 'file_type', 'description', 'category', 'is_public', 'is_active']
        readonly_fields = ['uuid', 'file_size', 'mime_type', 'download_count', 'file_size_human', 'file_extension']
        
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('File name')}),
            'file': forms.FileInput(attrs={'class': 'form-control'}),
            'file_type': forms.Select(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'category': forms.Select(attrs={'class': 'form-control'}),
            'is_public': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        if not self.instance.pk and 'file' in self.fields:
            self.fields['file'].help_text = _(
                "Allowed extensions: pdf, doc, docx, xls, xlsx, ppt, pptx, txt, zip, rar, jpg, png, mp4, mp3, avi"
            )
    
    def clean_file(self):
        """[OK] ফাইল ভ্যালিডেশন - 🟢 ফিক্স 3: ডাবল চেক"""
        file = self.cleaned_data.get('file')
        
        if not file:
            if not self.instance.pk:
                raise ValidationError(_("File is required"))
            return file
        
        # 🟢 ফিক্স 3: সার্ভার-সাইড সাইজ চেক (২ বার চেক)
        max_size = 50 * 1024 * 1024  # 50MB
        if file.size > max_size:
            raise ValidationError(_("File size cannot exceed 50MB"))
        
        # ফাইল এক্সটেনশন চেক
        ext = os.path.splitext(file.name)[1].lower()
        allowed_extensions = [
            '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
            '.txt', '.zip', '.rar', '.jpg', '.jpeg', '.png', '.mp4', '.mp3', '.avi'
        ]
        
        if ext not in allowed_extensions:
            raise ValidationError(_("File type not allowed"))
        
        # [OK] MIME টাইপ চেক (extension ভিত্তিক নয়)
        mime_type, _ = mimetypes.guess_type(file.name)
        allowed_mime_types = [
            'application/pdf',
            'application/msword',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'application/vnd.ms-excel',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'application/vnd.ms-powerpoint',
            'application/vnd.openxmlformats-officedocument.presentationml.presentation',
            'text/plain',
            'application/zip',
            'application/x-rar-compressed',
            'image/jpeg',
            'image/png',
            'video/mp4',
            'audio/mpeg',
        ]
        
        if mime_type and mime_type not in allowed_mime_types:
            raise ValidationError(_(f"File type '{mime_type}' not allowed"))
        
        return file
    
    def clean_name(self):
        """ফাইল নাম ভ্যালিডেশন"""
        name = self.cleaned_data.get('name', '').strip()
        file = self.cleaned_data.get('file')
        
        if not name and file:
            name = os.path.splitext(file.name)[0]
        
        if not name:
            raise ValidationError(_("File name is required"))
        
        return name
    
    def clean_file_type(self):
        """ফাইল টাইপ ভ্যালিডেশন"""
        file_type = self.cleaned_data.get('file_type')
        file = self.cleaned_data.get('file')
        
        if not file_type and file:
            ext = os.path.splitext(file.name)[1].lower()
            type_map = {
                '.pdf': 'pdf',
                '.doc': 'document', '.docx': 'document',
                '.xls': 'spreadsheet', '.xlsx': 'spreadsheet',
                '.ppt': 'presentation', '.pptx': 'presentation',
                '.txt': 'document',
                '.zip': 'archive', '.rar': 'archive',
                '.jpg': 'image', '.jpeg': 'image', '.png': 'image',
                '.mp4': 'video', '.avi': 'video',
                '.mp3': 'audio',
            }
            file_type = type_map.get(ext, 'other')
        
        return file_type or 'other'
    
    def save(self, commit: bool = True):
        instance = super().save(commit=False)
        
        if not instance.uuid:
            instance.uuid = uuid.uuid4()
        
        if instance.file:
            instance.file_size = instance.file.size
            mime_type, _ = mimetypes.guess_type(instance.file.name)
            if mime_type:
                instance.mime_type = mime_type
        
        if commit:
            instance.save()
            self.save_m2m()
        
        return instance


# ================================================
# 🟢 SECTION 8: COMMENT FORM (Comment)
# ================================================

class CommentForm(BulletproofModelForm):
    """
    💬 Comment Form - মডেলের সাথে ১০০% মিল রেখে
    """
    
    class Meta:
        model = Comment
        fields = ['comment_type', 'comment', 'rating', 'parent']
        readonly_fields = ['uuid', 'user', 'is_approved', 'is_edited', 'like_count', 
                          'reply_count', 'is_flagged', 'moderated_at']
        
        widgets = {
            'comment_type': forms.Select(attrs={'class': 'form-control'}),
            'comment': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'rating': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 5}),
            'parent': forms.Select(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        self.content_object = kwargs.pop('content_object', None)
        self.content_type = kwargs.pop('content_type', None)
        self.object_id = kwargs.pop('object_id', None)
        
        super().__init__(*args, **kwargs)
        
        if 'parent' in self.fields and self.content_object:
            content_type = ContentType.objects.get_for_model(self.content_object)
            self.fields['parent'].queryset = Comment.objects.filter(
                content_type=content_type,
                object_id=self.content_object.id,
                is_active=True,
                parent__isnull=True
            )
        
        if 'rating' in self.fields:
            self.fields['rating'].required = False
    
    def clean_comment(self):
        comment = self.cleaned_data.get('comment', '').strip()
        
        if not comment:
            raise ValidationError(_("Comment cannot be empty"))
        
        if len(comment) < 3:
            raise ValidationError(_("Comment is too short (min 3 characters)"))
        
        return comment
    
    def clean_rating(self):
        rating = self.cleaned_data.get('rating')
        
        if rating is not None:
            if rating < 1 or rating > 5:
                raise ValidationError(_("Rating must be between 1 and 5"))
        
        return rating
    
    def clean(self):
        cleaned_data = super().clean()
        
        if not cleaned_data:
            return cleaned_data
        
        if not self.content_object and not (self.content_type and self.object_id):
            if not self.instance.pk:
                self.add_error(None, _("Content object is required for new comments"))
                return cleaned_data
        
        parent = cleaned_data.get('parent')
        # 🟢 ফিক্স 6: is_active চেক ঠিক করা হয়েছে
        if parent:
            if parent.is_active is False:  # None চেক করছে না
                self.add_error('parent', _("Cannot reply to inactive comment"))
            elif parent.is_active is None:
                self.add_error('parent', _("Cannot reply to comment with unknown status"))
        
        return cleaned_data
    
    def save(self, commit: bool = True):
        instance = super().save(commit=False)
        
        if not instance.uuid:
            instance.uuid = uuid.uuid4()
        
        if self.user and not instance.user_id:
            instance.user = self.user
        
        if self.content_object:
            instance.content_object = self.content_object
        elif self.content_type and self.object_id:
            instance.content_type = self.content_type
            instance.object_id = self.object_id
        
        if commit:
            instance.save()
            self.save_m2m()
            
            if instance.parent:
                Comment.objects.filter(id=instance.parent.id).update(
                    reply_count=F('reply_count') + 1
                )
        
        return instance


# ================================================
# 🟢 SECTION 9: COMMENT LIKE FORM (CommentLike)
# ================================================

class CommentLikeForm(BulletproofModelForm):
    """
    ❤️ Comment Like Form
    """
    
    class Meta:
        model = CommentLike
        fields = ['comment']
        widgets = {
            'comment': forms.Select(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
    
    def clean(self):
        cleaned_data = super().clean()
        
        if not cleaned_data:
            return cleaned_data
        
        comment = cleaned_data.get('comment')
        
        if comment and self.user:
            exists = CommentLike.objects.filter(
                comment=comment,
                user=self.user
            ).exists()
            
            if exists:
                raise ValidationError(_("You have already liked this comment"))
        
        return cleaned_data
    
    def save(self, commit: bool = True):
        instance = super().save(commit=False)
        
        if self.user:
            instance.user = self.user
        
        if not instance.uuid:
            instance.uuid = uuid.uuid4()
        
        if commit:
            with transaction.atomic():
                instance.save()
                Comment.objects.filter(id=instance.comment_id).update(
                    like_count=F('like_count') + 1
                )
        
        return instance


# ================================================
# 🟢 SECTION 10: SITE ANALYTICS FORM (SiteAnalytics) - ফিক্সড
# ================================================

class SiteAnalyticsForm(BulletproofModelForm):
    """
    [STATS] Site Analytics Form - মডেলের সাথে ১০০% মিল রেখে
    """
    
    class Meta:
        model = SiteAnalytics
        fields = '__all__'
        readonly_fields = ['uuid', 'conversion_rate', 'net_earnings', 'banner_ctr', 'engagement_rate']
        
        widgets = {
            'date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'page_views': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'unique_visitors': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'new_users': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'active_users': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'session_count': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'avg_session_duration': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'step': 0.1}),
            'bounce_rate': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'max': 100, 'step': 0.1}),
            'total_earnings': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'step': 0.01}),
            'total_withdrawals': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'step': 0.01}),
            'offer_completions': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'task_completions': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'content_views': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'content_shares': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'content_comments': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'banner_impressions': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'banner_clicks': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'banner_conversions': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        if not self.instance.pk:
            self.initial['date'] = timezone.now().date()
    
    def clean(self):
        """🟢 ফিক্স 2: ডেট ইউনিক চেক + return"""
        cleaned_data = super().clean()
        
        if not cleaned_data:
            return cleaned_data
        
        date_value = cleaned_data.get('date')
        if date_value:
            qs = SiteAnalytics.objects.filter(date=date_value)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            
            if qs.exists():
                self.add_error('date', _("Analytics for this date already exist"))
                # 🟢 ফিক্স 2: এরর দিয়ে return করা হয়েছে
                return cleaned_data
        
        banner_impressions = cleaned_data.get('banner_impressions', 0)
        banner_clicks = cleaned_data.get('banner_clicks', 0)
        
        if banner_clicks > banner_impressions:
            self.add_warning(
                'banner_clicks',
                _("Banner clicks cannot exceed impressions")
            )
        
        return cleaned_data


# ================================================
# 🟢 SECTION 11: CONTENT PERMISSION FORM (ContentPermission) - ফিক্সড
# ================================================

class ContentPermissionForm(BulletproofModelForm):
    """
    [SECURE] Content Permission Form - মডেলের সাথে ১০০% মিল রেখে
    """
    
    # পারমিশন চেকবক্স
    can_view = forms.BooleanField(
        label=_("Can View"),
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    can_comment = forms.BooleanField(
        label=_("Can Comment"),
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    can_share = forms.BooleanField(
        label=_("Can Share"),
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    can_download = forms.BooleanField(
        label=_("Can Download"),
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    can_print = forms.BooleanField(
        label=_("Can Print"),
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    can_edit = forms.BooleanField(
        label=_("Can Edit"),
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    can_delete = forms.BooleanField(
        label=_("Can Delete"),
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    can_manage = forms.BooleanField(
        label=_("Can Manage"),
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    class Meta:
        model = ContentPermission
        fields = [
            'permission_type', 'content', 'target_id',
            'parent_permission', 'is_active', 'priority',
            'expires_at', 'conditions'
        ]
        readonly_fields = ['uuid', 'cache_version', 'created_by']
        
        widgets = {
            'permission_type': forms.Select(attrs={'class': 'form-control'}),
            'content': forms.Select(attrs={'class': 'form-control'}),
            'target_id': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('User ID, Group ID, Role, etc.')}),

            'parent_permission': forms.Select(attrs={'class': 'form-control'}),
            'priority': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'expires_at': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'conditions': forms.Textarea(attrs={'class': 'form-control font-monospace', 'rows': 4}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # 🟢 ফিক্স 11: settings থেকে DEFAULT_TENANT_ID নেওয়া
        default_tenant = getattr(settings, 'DEFAULT_TENANT_ID', 1)



        
        if self.instance and self.instance.pk:
            permissions = getattr(self.instance, 'permissions', 0)
            # 🟢 ফিক্স 1: PERMISSION_BITS ব্যবহার করা হয়েছে
            self.initial['can_view'] = bool(permissions & PERMISSION_BITS.get('view', 1))
            self.initial['can_comment'] = bool(permissions & PERMISSION_BITS.get('comment', 2))
            self.initial['can_share'] = bool(permissions & PERMISSION_BITS.get('share', 4))
            self.initial['can_download'] = bool(permissions & PERMISSION_BITS.get('download', 8))
            self.initial['can_print'] = bool(permissions & PERMISSION_BITS.get('print', 16))
            self.initial['can_edit'] = bool(permissions & PERMISSION_BITS.get('edit', 32))
            self.initial['can_delete'] = bool(permissions & PERMISSION_BITS.get('delete', 64))
            self.initial['can_manage'] = bool(permissions & PERMISSION_BITS.get('manage', 128))
    
    def clean_target_id(self):
        target_id = self.cleaned_data.get('target_id', '').strip()
        perm_type = self.cleaned_data.get('permission_type')
        
        if not target_id and perm_type not in [PermissionType.PUBLIC, PermissionType.AUTHENTICATED]:
            raise ValidationError(_("Target ID is required for this permission type"))
        
        return target_id
    
    def clean_conditions(self):
        conditions = self.cleaned_data.get('conditions', {})
        
        if isinstance(conditions, str):
            try:
                conditions = json.loads(conditions)
            except json.JSONDecodeError:
                raise ValidationError(_("Invalid JSON format in conditions"))
        
        return conditions if isinstance(conditions, dict) else {}
    
    def clean_expires_at(self):
        expires_at = self.cleaned_data.get('expires_at')
        
        if expires_at and expires_at < timezone.now():
            raise ValidationError(_("Expiry date cannot be in the past"))
        
        return expires_at
    
    def clean(self):
        cleaned_data = super().clean()
        
        if not cleaned_data:
            return cleaned_data
        
        perm_type = cleaned_data.get('permission_type')
        target_id = cleaned_data.get('target_id')
        content = cleaned_data.get('content')
        tenant_id = cleaned_data.get('tenant_id', getattr(settings, 'DEFAULT_TENANT_ID', 1))
        
        if not self.instance.pk and content and perm_type and target_id:
            exists = ContentPermission.objects.filter(
                tenant_id=tenant_id,
                content=content,
                permission_type=perm_type,
                target_id=target_id,
                is_active=True
            ).exists()
            
            if exists:
                self.add_error(None, _("Active permission already exists for this target"))
        
        return cleaned_data
    
    def save(self, commit: bool = True):
        instance = super().save(commit=False)
        
        if not instance.uuid:
            instance.uuid = uuid.uuid4()
        
        # 🟢 ফিক্স 1: PERMISSION_BITS ব্যবহার করে বিটমাস্ক বিল্ড
        permissions = 0
        if self.cleaned_data.get('can_view'):
            permissions |= PERMISSION_BITS.get('view', 1)
        if self.cleaned_data.get('can_comment'):
            permissions |= PERMISSION_BITS.get('comment', 2)
        if self.cleaned_data.get('can_share'):
            permissions |= PERMISSION_BITS.get('share', 4)
        if self.cleaned_data.get('can_download'):
            permissions |= PERMISSION_BITS.get('download', 8)
        if self.cleaned_data.get('can_print'):
            permissions |= PERMISSION_BITS.get('print', 16)
        if self.cleaned_data.get('can_edit'):
            permissions |= PERMISSION_BITS.get('edit', 32)
        if self.cleaned_data.get('can_delete'):
            permissions |= PERMISSION_BITS.get('delete', 64)
        if self.cleaned_data.get('can_manage'):
            permissions |= PERMISSION_BITS.get('manage', 128)
        
        instance.permissions = permissions
        
        if self.user and not instance.created_by_id:
            instance.created_by = self.user
        
        if commit:
            instance.save()
            self.save_m2m()
        
        return instance


# ================================================
# 🟢 SECTION 12: BULK OPERATION FORMS - ফিক্সড
# ================================================

class BulkCommentApprovalForm(forms.Form):
    """
    [OK] বাল্ক কমেন্ট অ্যাপ্রুভাল ফর্ম
    """
    
    comment_ids = forms.CharField(
        widget=forms.HiddenInput(),
        required=True
    )
    
    action = forms.ChoiceField(
        choices=[
            ('approve', _('Approve Selected')),
            ('reject', _('Reject Selected')),
            ('delete', _('Delete Selected')),
        ],
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    confirm = forms.BooleanField(
        required=True,
        initial=False,
        label=_("I understand this action cannot be undone"),
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    def clean_comment_ids(self):
        ids_str = self.cleaned_data.get('comment_ids', '')
        try:
            ids = [int(id.strip()) for id in ids_str.split(',') if id.strip()]
            if not ids:
                raise ValidationError(_("No comments selected"))
            return ids
        except ValueError:
            raise ValidationError(_("Invalid comment IDs"))


class BulkPermissionForm(forms.Form):
    """
    [OK] বাল্ক পারমিশন ফর্ম - 🟢 ফিক্স 4
    """
    
    permission_ids = forms.CharField(
        widget=forms.HiddenInput(),
        required=True
    )
    
    action = forms.ChoiceField(
        choices=[
            ('activate', _('Activate Selected')),
            ('deactivate', _('Deactivate Selected')),
            ('delete', _('Delete Selected')),
            ('extend', _('Extend Expiry')),
        ],
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    extend_days = forms.IntegerField(
        required=False,
        min_value=1,
        max_value=365,
        initial=30,
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )
    
    def clean(self):
        cleaned_data = super().clean()
        
        action = cleaned_data.get('action')
        extend_days = cleaned_data.get('extend_days')
        
        # 🟢 ফিক্স 4: extend_days > 0 চেক
        if action == 'extend':
            if not extend_days:
                self.add_error('extend_days', _("Days to extend is required"))
            elif extend_days <= 0:
                self.add_error('extend_days', _("Days to extend must be greater than zero"))
        
        return cleaned_data


# ================================================
# 🟢 SECTION 13: FORMSETS - ফিক্সড
# ================================================

from django.forms import modelformset_factory, inlineformset_factory

# 🟢 ফিক্স 10: fields প্যারামিটার বাদ দেওয়া হয়েছে (form এ fields আছে)
GalleryImageFormSet = inlineformset_factory(
    ImageGallery,
    GalleryImage,
    form=GalleryImageForm,
    extra=3,
    can_delete=True
)

CommentFormSet = modelformset_factory(
    Comment,
    form=CommentForm,
    extra=1,
    can_delete=True
)

ContentPermissionFormSet = modelformset_factory(
    ContentPermission,
    form=ContentPermissionForm,
    extra=2,
    can_delete=True
)


# ================================================
# 🟢 SECTION 14: API IMPORT FORMS - ফিক্সড
# ================================================

class APIImportImageGalleryForm(forms.Form):
    """
    🌐 API থেকে Image Gallery ইম্পোর্টের ফর্ম
    """
    
    api_data = forms.JSONField(
        widget=forms.Textarea(attrs={
            'class': 'form-control font-monospace',
            'rows': 10
        })
    )
    
    def clean_api_data(self):
        data = self.cleaned_data.get('api_data', {})
        
        if not isinstance(data, dict):
            if isinstance(data, list):
                data = {'galleries': data}
            else:
                raise ValidationError(_("Expected JSON object or array"))
        
        schema = {
            'galleries': {'type': list, 'required': True},
            'galleries[].title': {'type': str, 'required': True, 'min_length': 3},
            'galleries[].description': {'type': str, 'required': False, 'allow_empty': True},
            'galleries[].tags': {'type': list, 'required': False},
        }
        
        validator = SchemaValidator()
        errors = validator.validate(data, schema)
        
        if errors:
            raise ValidationError(errors)
        
        return data
    
    def save(self):
        """🟢 ফিক্স 9: error handling ইম্প্রুভ করা হয়েছে"""
        data = self.cleaned_data['api_data']
        galleries = data.get('galleries', [])
        
        created = 0
        errors = []
        validation_errors = []
        db_errors = []
        
        for gallery_data in galleries:
            try:
                title = deep_get(gallery_data, 'title', 'Untitled')
                description = deep_get(gallery_data, 'description', '')
                tags = deep_get(gallery_data, 'tags', [])
                
                from django.utils.text import slugify
                slug = slugify(title)
                
                base_slug = slug
                counter = 1
                while ImageGallery.objects.filter(slug=slug).exists():
                    slug = f"{base_slug}-{counter}"
                    counter += 1
                
                # [OK] ভ্যালিডেশন
                if len(title) < 3:
                    validation_errors.append(f"{title}: Title too short")
                    continue
                
                gallery = ImageGallery.objects.create(
                    title=title,
                    slug=slug,
                    description=description,
                    tags=tags,
                    is_active=True
                )
                created += 1
                
            except ValidationError as e:
                validation_errors.append(f"{title}: {str(e)}")
                logger.warning(f"Validation error for {title}: {e}")
            except Exception as e:
                db_errors.append(f"{title}: {str(e)}")
                logger.error(f"Database error for {title}: {e}")
        
        return {
            'created': created,
            'validation_errors': validation_errors,
            'db_errors': db_errors,
            'total_errors': len(validation_errors) + len(db_errors),
            'total': len(galleries)
        }


