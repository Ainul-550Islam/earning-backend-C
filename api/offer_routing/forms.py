"""
Forms for Offer Routing System

This module provides Django forms for the offer routing system,
used by template-based views for web interface functionality.
"""

from django import forms
from django.utils import timezone
from .models import (
    OfferRoute, RouteCondition, RouteAction,
    RoutingABTest, PersonalizationConfig,
    OfferRoutingCap, FallbackRule
)


class OfferRouteForm(forms.ModelForm):
    """Form for creating and updating offer routes."""

    class Meta:
        model = OfferRoute
        fields = [
            'name', 'description', 'priority', 'max_offers', 'is_active',
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Route name'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'priority': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 10}),
            'max_offers': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean_priority(self):
        priority = self.cleaned_data.get('priority')
        if priority is not None and (priority < 1 or priority > 10):
            raise forms.ValidationError('Priority must be between 1 and 10.')
        return priority

    def clean_max_offers(self):
        max_offers = self.cleaned_data.get('max_offers')
        if max_offers is not None and max_offers < 1:
            raise forms.ValidationError('Max offers must be at least 1.')
        return max_offers


class RoutingABTestForm(forms.ModelForm):
    """Form for creating and updating A/B tests."""

    class Meta:
        model = RoutingABTest
        fields = [
            'name', 'description', 'control_route', 'variant_route',
            'split_percentage', 'duration_hours', 'min_sample_size',
            'confidence_level', 'success_metric', 'is_active'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Test name'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'control_route': forms.Select(attrs={'class': 'form-select'}),
            'variant_route': forms.Select(attrs={'class': 'form-select'}),
            'split_percentage': forms.NumberInput(attrs={
                'class': 'form-control', 'min': 1, 'max': 99, 'step': 1
            }),
            'duration_hours': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'min_sample_size': forms.NumberInput(attrs={'class': 'form-control', 'min': 100}),
            'confidence_level': forms.NumberInput(attrs={
                'class': 'form-control', 'min': 0.8, 'max': 0.99, 'step': 0.01
            }),
            'success_metric': forms.Select(attrs={'class': 'form-select'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        control_route = cleaned_data.get('control_route')
        variant_route = cleaned_data.get('variant_route')

        if control_route and variant_route and control_route == variant_route:
            raise forms.ValidationError(
                'Control route and variant route must be different.'
            )

        split_percentage = cleaned_data.get('split_percentage')
        if split_percentage is not None and (split_percentage < 1 or split_percentage > 99):
            raise forms.ValidationError('Split percentage must be between 1 and 99.')

        return cleaned_data


class BulkAssignmentForm(forms.Form):
    """Form for bulk route assignment operations."""

    ASSIGNMENT_TYPES = [
        ('assign_route', 'Assign Route'),
        ('remove_route', 'Remove Route'),
        ('update_priority', 'Update Priority'),
        ('activate', 'Activate Routes'),
        ('deactivate', 'Deactivate Routes'),
    ]

    user_ids = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 5,
            'placeholder': 'Enter user IDs, one per line or comma-separated'
        }),
        help_text='Enter user IDs to apply the assignment to.'
    )
    assignment_type = forms.ChoiceField(
        choices=ASSIGNMENT_TYPES,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    route = forms.ModelChoiceField(
        queryset=OfferRoute.objects.none(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        help_text='Select route for assignment operations.'
    )
    new_priority = forms.IntegerField(
        required=False,
        min_value=1,
        max_value=10,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 10}),
        help_text='New priority value (1-10) for update priority operation.'
    )
    dry_run = forms.BooleanField(
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text='Simulate the operation without making changes.'
    )

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, **kwargs)
        if tenant:
            self.fields['route'].queryset = OfferRoute.objects.filter(tenant=tenant)

    def clean_user_ids(self):
        raw = self.cleaned_data.get('user_ids', '')
        ids = []
        for part in raw.replace('\n', ',').split(','):
            part = part.strip()
            if part:
                try:
                    ids.append(int(part))
                except ValueError:
                    raise forms.ValidationError(f'Invalid user ID: {part}')
        if not ids:
            raise forms.ValidationError('At least one user ID is required.')
        return ids

    def clean(self):
        cleaned_data = super().clean()
        assignment_type = cleaned_data.get('assignment_type')
        route = cleaned_data.get('route')
        new_priority = cleaned_data.get('new_priority')

        if assignment_type in ('assign_route', 'remove_route') and not route:
            raise forms.ValidationError(
                'Route is required for assign/remove operations.'
            )
        if assignment_type == 'update_priority' and new_priority is None:
            raise forms.ValidationError(
                'New priority is required for update priority operation.'
            )
        return cleaned_data


class PerformanceReportForm(forms.Form):
    """Form for generating performance reports."""

    REPORT_TYPES = [
        ('overview', 'Overview Report'),
        ('route_performance', 'Route Performance'),
        ('ab_test_results', 'A/B Test Results'),
        ('user_analytics', 'User Analytics'),
        ('revenue_report', 'Revenue Report'),
    ]

    PERIOD_CHOICES = [
        (7, 'Last 7 days'),
        (14, 'Last 14 days'),
        (30, 'Last 30 days'),
        (60, 'Last 60 days'),
        (90, 'Last 90 days'),
    ]

    report_type = forms.ChoiceField(
        choices=REPORT_TYPES,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    period_days = forms.ChoiceField(
        choices=PERIOD_CHOICES,
        initial=30,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    start_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        help_text='Optional: override period with custom start date.'
    )
    end_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        help_text='Optional: override period with custom end date.'
    )
    include_charts = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    export_format = forms.ChoiceField(
        choices=[('json', 'JSON'), ('csv', 'CSV'), ('html', 'HTML')],
        required=False,
        initial='html',
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')

        if start_date and end_date:
            if start_date >= end_date:
                raise forms.ValidationError('Start date must be before end date.')
            if end_date > timezone.now().date():
                raise forms.ValidationError('End date cannot be in the future.')

        return cleaned_data


class SystemConfigForm(forms.Form):
    """Form for system configuration management."""

    CACHE_BACKENDS = [
        ('redis', 'Redis'),
        ('memcached', 'Memcached'),
        ('database', 'Database'),
        ('locmem', 'Local Memory'),
    ]

    cache_enabled = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label='Enable Caching'
    )
    cache_backend = forms.ChoiceField(
        choices=CACHE_BACKENDS,
        initial='redis',
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='Cache Backend'
    )
    default_cache_ttl = forms.IntegerField(
        initial=300,
        min_value=0,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
        label='Default Cache TTL (seconds)'
    )
    routing_timeout_ms = forms.IntegerField(
        initial=500,
        min_value=50,
        max_value=10000,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 50, 'max': 10000}),
        label='Routing Timeout (ms)'
    )
    max_offers_per_request = forms.IntegerField(
        initial=50,
        min_value=1,
        max_value=500,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 500}),
        label='Max Offers Per Request'
    )
    personalization_enabled = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label='Enable Personalization'
    )
    ab_testing_enabled = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label='Enable A/B Testing'
    )
    fallback_enabled = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label='Enable Fallback'
    )
    debug_mode = forms.BooleanField(
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label='Enable Debug Mode'
    )
    log_all_decisions = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label='Log All Routing Decisions'
    )
    decision_log_retention_days = forms.IntegerField(
        initial=30,
        min_value=1,
        max_value=365,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 365}),
        label='Decision Log Retention (days)'
    )

    def clean_routing_timeout_ms(self):
        timeout = self.cleaned_data.get('routing_timeout_ms')
        if timeout is not None and timeout < 50:
            raise forms.ValidationError('Routing timeout must be at least 50ms.')
        return timeout
