# api/kyc/forms.py
"""
Production-ready KYC forms with strict validation.
"""
import logging
import re
from datetime import date
from django import forms
from django.core.exceptions import ValidationError

logger = logging.getLogger(__name__)

PHONE_REGEX = re.compile(r'^\+?[0-9]{10,15}$')
PAYMENT_NUMBER_REGEX = re.compile(r'^01[3-9][0-9]{8}$|^\+8801[3-9][0-9]{8}$')  # BD mobile


class KYCSubmissionForm(forms.Form):
    """User KYC submission form."""
    full_name = forms.CharField(max_length=200, strip=True, min_length=2)
    date_of_birth = forms.DateField(required=False)
    phone_number = forms.CharField(max_length=20)
    payment_number = forms.CharField(max_length=20, help_text='bKash/Nagad number')
    payment_method = forms.ChoiceField(
        choices=[('bkash', 'bKash'), ('nagad', 'Nagad'), ('rocket', 'Rocket')],
        initial='bkash'
    )
    address_line = forms.CharField(max_length=500, required=False, strip=True)
    city = forms.CharField(max_length=100, required=False, strip=True)
    country = forms.CharField(max_length=100, initial='Bangladesh', strip=True)
    document_type = forms.ChoiceField(
        choices=[
            ('nid', 'National ID'),
            ('passport', 'Passport'),
            ('driving_license', 'Driving License'),
        ],
        required=False
    )
    document_number = forms.CharField(max_length=50, required=False, strip=True)

    def clean_full_name(self):
        value = (self.cleaned_data.get('full_name') or '').strip()
        if len(value) < 2:
            raise ValidationError('Full name must be at least 2 characters.')
        return value

    def clean_phone_number(self):
        value = (self.cleaned_data.get('phone_number') or '').strip().replace(' ', '')
        if not PHONE_REGEX.match(value):
            raise ValidationError('Enter a valid phone number (10-15 digits, optional +).')
        return value

    def clean_payment_number(self):
        value = (self.cleaned_data.get('payment_number') or '').strip().replace(' ', '')
        if not value.isdigit() or len(value) < 10:
            raise ValidationError('Enter a valid bKash/Nagad/Rocket number (digits only, min 10).')
        return value

    def clean_date_of_birth(self):
        value = self.cleaned_data.get('date_of_birth')
        if value and value > date.today():
            raise ValidationError('Date of birth cannot be in the future.')
        if value:
            age = (date.today() - value).days // 365
            if age < 18:
                raise ValidationError('You must be at least 18 years old.')
        return value


class KYCAdminReviewForm(forms.Form):
    """Admin KYC review form."""
    status = forms.ChoiceField(
        choices=[
            ('pending', 'Pending'),
            ('verified', 'Verified'),
            ('rejected', 'Rejected'),
        ]
    )
    rejection_reason = forms.CharField(
        required=False,
        widget=forms.Textarea,
        max_length=1000
    )
    admin_notes = forms.CharField(required=False, widget=forms.Textarea, max_length=2000)

    def clean(self):
        data = super().clean()
        if data.get('status') == 'rejected' and not data.get('rejection_reason'):
            raise ValidationError({'rejection_reason': 'Rejection reason is required when rejecting.'})
        return data
