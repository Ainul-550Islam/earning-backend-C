# api/support/forms.py
"""
Production-ready support forms with validation.
"""
import logging
from django import forms
from django.core.exceptions import ValidationError

logger = logging.getLogger(__name__)


class SupportTicketForm(forms.Form):
    """User support ticket creation form."""
    category = forms.ChoiceField(
        choices=[
            ('payment', 'Payment Issue'),
            ('coins', 'Coins Not Added'),
            ('account', 'Account Problem'),
            ('technical', 'Technical Issue'),
            ('other', 'Other'),
        ]
    )
    subject = forms.CharField(max_length=200, min_length=5, strip=True)
    description = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 5}),
        min_length=20,
        max_length=5000,
        strip=True
    )
    priority = forms.ChoiceField(
        choices=[
            ('low', 'Low'),
            ('medium', 'Medium'),
            ('high', 'High'),
            ('urgent', 'Urgent'),
        ],
        initial='medium'
    )

    def clean_subject(self):
        value = (self.cleaned_data.get('subject') or '').strip()
        if len(value) < 5:
            raise ValidationError('Subject must be at least 5 characters.')
        return value

    def clean_description(self):
        value = (self.cleaned_data.get('description') or '').strip()
        if len(value) < 20:
            raise ValidationError('Please provide more details (at least 20 characters).')
        return value


class SupportTicketAdminReplyForm(forms.Form):
    """Admin reply to ticket."""
    admin_response = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 4}),
        min_length=1,
        max_length=5000,
        required=True,
        strip=True
    )
    close_ticket = forms.BooleanField(required=False, initial=False)
