# api/cms/models_new/forms.py
"""
FormBuilder — No-code dynamic forms. CMS owns this.
Create contact, lead-capture, survey forms without coding.
Rule: এক কাজের জন্য একটাই মালিক।
"""
import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone


FIELD_TYPES = [
    ('text',      'Short Text'),
    ('textarea',  'Long Text'),
    ('email',     'Email'),
    ('phone',     'Phone Number'),
    ('number',    'Number'),
    ('select',    'Dropdown Select'),
    ('radio',     'Radio Buttons'),
    ('checkbox',  'Checkboxes'),
    ('date',      'Date Picker'),
    ('file',      'File Upload'),
    ('hidden',    'Hidden Field'),
    ('divider',   'Section Divider'),
    ('rating',    'Star Rating'),
]


class DynamicForm(models.Model):
    """A no-code form created via admin."""
    uuid          = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    name          = models.CharField(max_length=200)
    slug          = models.SlugField(max_length=200, unique=True)
    description   = models.TextField(blank=True)
    # Display
    title         = models.CharField(max_length=300, blank=True)
    submit_text   = models.CharField(max_length=100, default='Submit')
    success_message = models.TextField(default='Thank you! Your submission was received.')
    # Behavior
    redirect_url  = models.URLField(blank=True,
                                    help_text="Redirect here after submission (overrides success message)")
    send_email_to = models.EmailField(blank=True, help_text="Notify this email on submission")
    send_confirmation_email = models.BooleanField(default=False,
                                                   help_text="Send email to submitter")
    # Reward on submission (CPAlead integration)
    reward_on_submit = models.BooleanField(default=False)
    reward_coins  = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    # Access control
    is_active     = models.BooleanField(default=True, db_index=True)
    requires_login = models.BooleanField(default=False)
    max_submissions_per_user = models.PositiveIntegerField(default=0,
                                                            help_text="0 = unlimited")
    # Stats
    total_submissions = models.PositiveIntegerField(default=0)
    created_by    = models.ForeignKey(settings.AUTH_USER_MODEL,
                                      on_delete=models.SET_NULL, null=True, blank=True)
    created_at    = models.DateTimeField(auto_now_add=True)
    updated_at    = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "cms"
        verbose_name = "Dynamic Form"
        ordering = ['-created_at']

    def __str__(self):
        return self.name


class FormField(models.Model):
    """A field inside a dynamic form."""
    form         = models.ForeignKey(DynamicForm, on_delete=models.CASCADE,
                                     related_name='fields')
    label        = models.CharField(max_length=200)
    field_type   = models.CharField(max_length=20, choices=FIELD_TYPES, default='text')
    name         = models.SlugField(max_length=100,
                                    help_text="Internal field name (auto from label)")
    placeholder  = models.CharField(max_length=200, blank=True)
    help_text    = models.CharField(max_length=300, blank=True)
    default_value = models.CharField(max_length=500, blank=True)
    choices      = models.TextField(blank=True,
                                    help_text="One choice per line (for select/radio/checkbox)")
    is_required  = models.BooleanField(default=False)
    is_visible   = models.BooleanField(default=True)
    order        = models.PositiveIntegerField(default=0)
    # Validation
    min_length   = models.PositiveIntegerField(null=True, blank=True)
    max_length   = models.PositiveIntegerField(null=True, blank=True)
    regex_pattern = models.CharField(max_length=500, blank=True)
    css_class    = models.CharField(max_length=200, blank=True)

    class Meta:
        app_label = "cms"
        verbose_name = "Form Field"
        ordering = ['order']
        unique_together = [['form', 'name']]

    def __str__(self):
        return f"{self.form.name} → {self.label}"

    def get_choices_list(self):
        if not self.choices:
            return []
        return [c.strip() for c in self.choices.split('\n') if c.strip()]


class FormSubmission(models.Model):
    """A user's form submission."""
    uuid       = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    form       = models.ForeignKey(DynamicForm, on_delete=models.CASCADE,
                                   related_name='submissions')
    user       = models.ForeignKey(settings.AUTH_USER_MODEL,
                                   on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='form_submissions')
    session_key = models.CharField(max_length=100, blank=True)
    data        = models.JSONField(default=dict, help_text="Field name → value")
    ip_address  = models.GenericIPAddressField(null=True, blank=True)
    user_agent  = models.TextField(blank=True)
    # Reward tracking
    reward_given = models.BooleanField(default=False)
    reward_coins = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    # Email
    email_sent   = models.BooleanField(default=False)
    submitted_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        app_label = "cms"
        verbose_name = "Form Submission"
        ordering = ['-submitted_at']
        indexes = [
            models.Index(fields=['form', 'submitted_at']),
            models.Index(fields=['user', 'form']),
            models.Index(fields=['uuid']),
        ]

    def __str__(self):
        return f"{self.form.name} by {self.user or self.ip_address} at {self.submitted_at:%Y-%m-%d %H:%M}"
