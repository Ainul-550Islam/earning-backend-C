# alerts/views.py
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse
from django.views import View
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.urls import reverse_lazy
from django.utils import timezone
from django.db.models import Q, Count, Avg, Max, Min, Sum
from django.core.paginator import Paginator
from django.core.cache import cache
import json
import logging
from datetime import datetime, timedelta

# তোমার EXACT models import
from .models import (
    AlertRule, AlertLog, Notification, AlertSchedule,
    AlertEscalation, AlertTemplate, AlertAnalytics,
    AlertGroup, AlertSuppression, SystemHealthCheck,
    AlertRuleHistory, AlertDashboardConfig, SystemMetrics
)

logger = logging.getLogger(__name__)


# ============================================
# DASHBOARD VIEWS
# ============================================

class DashboardView(LoginRequiredMixin, View):
    """তোমার AlertDashboardConfig model এর সাথে compatible dashboard"""
    
    def get(self, request):
        # তোমার AlertDashboardConfig model ব্যবহার করে
        config, created = AlertDashboardConfig.objects.get_or_create(user=request.user)
        
        context = {
            'config': config,
            'stats': self._get_stats(),
            'recent_alerts': self._get_recent_alerts(),
            'system_health': self._get_system_health(),
            'active_rules': AlertRule.active.all().count(),
            'unresolved_alerts': AlertLog.unresolved().count(),
        }
        
        return render(request, 'alerts/dashboard.html', context)
    
    def _get_stats(self):
        """তোমার AlertLog model থেকে stats"""
        today = timezone.now().date()
        
        return {
            'alerts_today': AlertLog.objects.filter(triggered_at__date=today).count(),
            'resolved_today': AlertLog.objects.filter(
                triggered_at__date=today, 
                is_resolved=True
            ).count(),
            'escalated_today': AlertLog.objects.filter(
                triggered_at__date=today,
                escalation_level__gt=0
            ).count(),
        }
    
    def _get_recent_alerts(self):
        """তোমার AlertLog model থেকে recent alerts"""
        return AlertLog.objects.select_related('rule').order_by('-triggered_at')[:10]
    
    def _get_system_health(self):
        """তোমার SystemHealthCheck model থেকে health"""
        return {
            'overall': SystemHealthCheck.get_overall_status(),
            'checks': SystemHealthCheck.objects.filter(is_active=True)[:5],
        }


# ============================================
# ALERT RULE VIEWS (তোমার AlertRule model এর জন্য)
# ============================================

class AlertRuleListView(LoginRequiredMixin, ListView):
    """তোমার AlertRule model এর list view"""
    model = AlertRule
    template_name = 'alerts/alert_rule_list.html'
    context_object_name = 'rules'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = AlertRule.objects.all().order_by('-created_at')
        
        # Filter তোমার model fields অনুযায়ী
        if self.request.GET.get('is_active'):
            queryset = queryset.filter(is_active=True)
        if self.request.GET.get('alert_type'):
            queryset = queryset.filter(alert_type=self.request.GET.get('alert_type'))
        if self.request.GET.get('severity'):
            queryset = queryset.filter(severity=self.request.GET.get('severity'))
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['alert_types'] = AlertRule.ALERT_TYPES
        context['severities'] = AlertRule.SEVERITY
        return context


class AlertRuleCreateView(LoginRequiredMixin, CreateView):
    """তোমার AlertRule model create view"""
    model = AlertRule
    template_name = 'alerts/alert_rule_form.html'
    fields = [
        'name', 'alert_type', 'severity', 'description',
        'threshold_value', 'time_window_minutes',
        'send_email', 'send_telegram', 'send_sms',
        'email_recipients', 'telegram_chat_id', 'sms_recipients',
        'is_active', 'cooldown_minutes'
    ]
    
    def form_valid(self, form):
        # তোমার model এ created_by field আছে
        form.instance.created_by = self.request.user
        
        # তোমার model এর clean method call হবে
        try:
            form.instance.full_clean()
        except Exception as e:
            messages.error(self.request, f"Validation error: {e}")
            return self.form_invalid(form)
        
        response = super().form_valid(form)
        
        # তোমার AlertRuleHistory model এ log
        AlertRuleHistory.log_change(
            rule=form.instance,
            action='create',
            changed_by=self.request.user,
            old_data=None,
            new_data=form.cleaned_data,
            changed_fields=list(form.cleaned_data.keys())
        )
        
        messages.success(self.request, f'Alert rule "{form.instance.name}" created!')
        return response
    
    def get_success_url(self):
        return reverse_lazy('alert_rule_detail', kwargs={'pk': self.object.pk})


class AlertRuleDetailView(LoginRequiredMixin, DetailView):
    """তোমার AlertRule model detail view"""
    model = AlertRule
    template_name = 'alerts/alert_rule_detail.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # তোমার model relations ব্যবহার করে
        alert_rule = self.object
        
        context['recent_alerts'] = alert_rule.logs.all().order_by('-triggered_at')[:10]
        context['schedules'] = alert_rule.schedules.filter(is_active=True)
        context['escalations'] = alert_rule.escalations.filter(is_active=True)
        context['history'] = alert_rule.history.all().order_by('-changed_at')[:10]
        
        # তোমার model method ব্যবহার করে
        context['trigger_count_today'] = alert_rule.trigger_count_today()
        context['can_trigger_now'] = alert_rule.can_trigger_now()
        
        return context


class AlertRuleUpdateView(LoginRequiredMixin, UpdateView):
    """তোমার AlertRule model update view"""
    model = AlertRule
    template_name = 'alerts/alert_rule_form.html'
    fields = [
        'name', 'alert_type', 'severity', 'description',
        'threshold_value', 'time_window_minutes',
        'send_email', 'send_telegram', 'send_sms',
        'email_recipients', 'telegram_chat_id', 'sms_recipients',
        'is_active', 'cooldown_minutes'
    ]
    
    def form_valid(self, form):
        # Old data store করছি history এর জন্য
        old_data = {}
        for field in self.object._meta.fields:
            if field.name not in ['id', 'created_at', 'updated_at']:
                old_data[field.name] = getattr(self.object, field.name)
        
        response = super().form_valid(form)
        
        # তোমার AlertRuleHistory model এ log
        AlertRuleHistory.log_change(
            rule=self.object,
            action='update',
            changed_by=self.request.user,
            old_data=old_data,
            new_data=form.cleaned_data,
            changed_fields=form.changed_data
        )
        
        # Cache clear করছি
        cache_key = f'active_alert_rules_AlertRule'
        cache.delete(cache_key)
        
        messages.success(self.request, f'Alert rule "{form.instance.name}" updated!')
        return response
    
    def get_success_url(self):
        return reverse_lazy('alert_rule_detail', kwargs={'pk': self.object.pk})


class AlertRuleDeleteView(LoginRequiredMixin, DeleteView):
    """তোমার AlertRule model delete view"""
    model = AlertRule
    template_name = 'alerts/alert_rule_confirm_delete.html'
    
    def get_success_url(self):
        messages.success(self.request, f'Alert rule "{self.object.name}" deleted!')
        return reverse_lazy('alert_rule_list')


@login_required
def toggle_alert_rule_active(request, pk):
    """তোমার AlertRule model এর is_active toggle"""
    alert_rule = get_object_or_404(AlertRule, pk=pk)
    alert_rule.is_active = not alert_rule.is_active
    alert_rule.save()
    
    # তোমার AlertRuleHistory model এ log
    action = 'activate' if alert_rule.is_active else 'deactivate'
    AlertRuleHistory.log_change(
        rule=alert_rule,
        action=action,
        changed_by=request.user
    )
    
    status = "activated" if alert_rule.is_active else "deactivated"
    messages.success(request, f'Alert rule "{alert_rule.name}" {status}!')
    return redirect('alert_rule_detail', pk=pk)


@login_required
def test_alert_rule(request, pk):
    """তোমার AlertRule model test trigger"""
    alert_rule = get_object_or_404(AlertRule, pk=pk)
    
    if not alert_rule.can_trigger_now():
        messages.error(request, 'Alert rule is in cooldown period!')
        return redirect('alert_rule_detail', pk=pk)
    
    try:
        # তোমার AlertLog model create করছি
        alert_log = AlertLog.objects.create(
            rule=alert_rule,
            trigger_value=alert_rule.threshold_value * 1.5,  # Test value
            threshold_value=alert_rule.threshold_value,
            message=f"Test alert for rule: {alert_rule.name}",
            details={
                'test': True,
                'triggered_by': request.user.username,
                'triggered_at': timezone.now().isoformat()
            }
        )
        
        # তোমার model method ব্যবহার করে
        alert_log.mark_as_processing()
        
        # তোমার AlertRule method থেকে recipients পাচ্ছি
        recipients = alert_rule.get_recipients()
        
        # তোমার Notification model create করছি
        if alert_rule.send_email and recipients['emails']:
            for email in recipients['emails']:
                Notification.objects.create(
                    alert_log=alert_log,
                    notification_type='email',
                    recipient=email,
                    subject=f"[TEST] Alert: {alert_rule.name}",
                    message=f"Test alert triggered for {alert_rule.name}",
                    status='sent',
                    sent_at=timezone.now(),
                )
                alert_log.email_sent = True
                alert_log.email_sent_at = timezone.now()
        
        alert_log.mark_as_complete()
        
        # তোমার AlertRule update করছি
        alert_rule.last_triggered = alert_log.triggered_at
        alert_rule.save()
        
        # তোমার AlertRuleHistory model এ log
        AlertRuleHistory.log_change(
            rule=alert_rule,
            action='test',
            changed_by=request.user
        )
        
        messages.success(request, f'Test alert triggered for "{alert_rule.name}"!')
        
    except Exception as e:
        messages.error(request, f'Error: {str(e)}')
    
    return redirect('alert_rule_detail', pk=pk)


# ============================================
# ALERT LOG VIEWS (তোমার AlertLog model এর জন্য)
# ============================================

class AlertLogListView(LoginRequiredMixin, ListView):
    """তোমার AlertLog model এর list view"""
    model = AlertLog
    template_name = 'alerts/alert_log_list.html'
    context_object_name = 'alerts'
    paginate_by = 50
    
    def get_queryset(self):
        queryset = AlertLog.objects.select_related('rule', 'resolved_by').order_by('-triggered_at')
        
        # তোমার model fields অনুযায়ী filter
        if self.request.GET.get('resolved') == 'true':
            queryset = queryset.filter(is_resolved=True)
        elif self.request.GET.get('resolved') == 'false':
            queryset = queryset.filter(is_resolved=False)
        
        if self.request.GET.get('severity'):
            queryset = queryset.filter(rule__severity=self.request.GET.get('severity'))
        
        if self.request.GET.get('alert_type'):
            queryset = queryset.filter(rule__alert_type=self.request.GET.get('alert_type'))
        
        if self.request.GET.get('rule_id'):
            queryset = queryset.filter(rule_id=self.request.GET.get('rule_id'))
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['rules'] = AlertRule.objects.all()
        context['severities'] = AlertRule.SEVERITY
        context['alert_types'] = AlertRule.ALERT_TYPES
        return context


class AlertLogDetailView(LoginRequiredMixin, DetailView):
    """তোমার AlertLog model detail view"""
    model = AlertLog
    template_name = 'alerts/alert_log_detail.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # তোমার Notification model থেকে related data
        context['notifications'] = self.object.notifications.all()
        
        # তোমার model property ব্যবহার করে
        context['time_to_resolve'] = self.object.time_to_resolve
        
        return context


@login_required
def resolve_alert_log(request, pk):
    """তোমার AlertLog model resolve"""
    alert_log = get_object_or_404(AlertLog, pk=pk)
    
    if alert_log.is_resolved:
        messages.warning(request, 'Alert already resolved!')
        return redirect('alert_log_detail', pk=pk)
    
    alert_log.is_resolved = True
    alert_log.resolved_at = timezone.now()
    alert_log.resolved_by = request.user
    
    if request.POST.get('resolution_note'):
        alert_log.resolution_note = request.POST.get('resolution_note')
    
    alert_log.save()
    
    messages.success(request, 'Alert resolved successfully!')
    return redirect('alert_log_detail', pk=pk)


@login_required
def bulk_resolve_alerts(request):
    """তোমার AlertLog model bulk resolve"""
    if request.method == 'POST':
        alert_ids = request.POST.getlist('alert_ids')
        
        if not alert_ids:
            messages.warning(request, 'No alerts selected!')
            return redirect('alert_log_list')
        
        alerts = AlertLog.objects.filter(id__in=alert_ids, is_resolved=False)
        count = alerts.count()
        
        if count > 0:
            alerts.update(
                is_resolved=True,
                resolved_at=timezone.now(),
                resolved_by=request.user
            )
            messages.success(request, f'{count} alerts resolved!')
        else:
            messages.warning(request, 'No unresolved alerts found!')
    
    return redirect('alert_log_list')


# ============================================
# NOTIFICATION VIEWS (তোমার Notification model এর জন্য)
# ============================================

class NotificationListView(LoginRequiredMixin, ListView):
    """তোমার Notification model list view"""
    model = Notification
    template_name = 'alerts/notification_list.html'
    context_object_name = 'notifications'
    paginate_by = 50
    
    def get_queryset(self):
        queryset = Notification.objects.select_related('alert_log', 'alert_log__rule').order_by('-created_at')
        
        # তোমার model fields অনুযায়ী filter
        if self.request.GET.get('status'):
            queryset = queryset.filter(status=self.request.GET.get('status'))
        
        if self.request.GET.get('type'):
            queryset = queryset.filter(notification_type=self.request.GET.get('type'))
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['status_choices'] = Notification.STATUS_CHOICES
        context['type_choices'] = Notification.NOTIFICATION_TYPES
        return context


@login_required
def retry_notification(request, pk):
    """তোমার Notification model retry"""
    notification = get_object_or_404(Notification, pk=pk)
    
    # তোমার model method ব্যবহার করে
    if not notification.can_retry():
        messages.warning(request, 'Cannot retry this notification!')
        return redirect('notification_list')
    
    notification.status = 'pending'
    notification.save()
    
    messages.success(request, 'Notification queued for retry!')
    return redirect('notification_list')


# ============================================
# ALERT GROUP VIEWS (তোমার AlertGroup model এর জন্য)
# ============================================

class AlertGroupListView(LoginRequiredMixin, ListView):
    """তোমার AlertGroup model list view"""
    model = AlertGroup
    template_name = 'alerts/alert_group_list.html'
    context_object_name = 'groups'
    
    def get_queryset(self):
        return AlertGroup.objects.all().prefetch_related('rules')


class AlertGroupDetailView(LoginRequiredMixin, DetailView):
    """তোমার AlertGroup model detail view"""
    model = AlertGroup
    template_name = 'alerts/alert_group_detail.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # তোমার AlertGroup model methods ব্যবহার করে
        alert_group = self.object
        
        context['active_alerts'] = alert_group.get_active_alerts()
        context['should_send_group_alert'] = alert_group.should_send_group_alert()
        context['group_recipients'] = alert_group.get_group_recipients()
        
        return context


@login_required
def send_group_alert(request, pk):
    """তোমার AlertGroup model group alert send"""
    alert_group = get_object_or_404(AlertGroup, pk=pk)
    
    # তোমার model method ব্যবহার করে
    result = alert_group.send_group_alert()
    
    if result:
        messages.success(request, f'Group alert sent for "{alert_group.name}"!')
    else:
        messages.warning(request, 'Group alert conditions not met!')
    
    return redirect('alert_group_detail', pk=pk)


# ============================================
# ALERT SUPPRESSION VIEWS (তোমার AlertSuppression model এর জন্য)
# ============================================

class AlertSuppressionListView(LoginRequiredMixin, ListView):
    """তোমার AlertSuppression model list view"""
    model = AlertSuppression
    template_name = 'alerts/alert_suppression_list.html'
    context_object_name = 'suppressions'
    
    def get_queryset(self):
        queryset = AlertSuppression.objects.all().select_related('rule', 'created_by')
        
        if self.request.GET.get('active') == 'true':
            # তোমার model method ব্যবহার করে
            active_suppressions = []
            for suppression in queryset:
                if suppression.is_active_now():
                    active_suppressions.append(suppression)
            return active_suppressions
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # তোমার class method ব্যবহার করে
        context['active_suppressions'] = AlertSuppression.get_active_suppressions()
        
        return context


# ============================================
# SYSTEM HEALTH CHECK VIEWS (তোমার SystemHealthCheck model এর জন্য)
# ============================================

class SystemHealthCheckListView(LoginRequiredMixin, ListView):
    """তোমার SystemHealthCheck model list view"""
    model = SystemHealthCheck
    template_name = 'alerts/system_health_check_list.html'
    context_object_name = 'health_checks'
    
    def get_queryset(self):
        queryset = SystemHealthCheck.objects.all()
        
        if self.request.GET.get('status'):
            queryset = queryset.filter(status=self.request.GET.get('status'))
        
        if self.request.GET.get('check_type'):
            queryset = queryset.filter(check_type=self.request.GET.get('check_type'))
        
        return queryset.order_by('priority')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # তোমার class methods ব্যবহার করে
        context['overall_status'] = SystemHealthCheck.get_overall_status()
        context['checks_needed'] = SystemHealthCheck.get_checks_needed()
        
        return context


# ============================================
# API VIEWS
# ============================================

class TriggerAlertAPIView(View):
    """তোমার models ব্যবহার করে API endpoint"""
    
    def post(self, request):
        try:
            data = json.loads(request.body)
            
            # তোমার AlertRule model থেকে rule fetch
            rule_id = data.get('rule_id')
            try:
                alert_rule = AlertRule.objects.get(id=rule_id, is_active=True)
            except AlertRule.DoesNotExist:
                return JsonResponse({
                    'error': 'Alert rule not found or inactive'
                }, status=404)
            
            # তোমার AlertRule method ব্যবহার করে cooldown check
            if not alert_rule.can_trigger_now():
                return JsonResponse({
                    'error': 'Alert rule in cooldown'
                }, status=429)
            
            # তোমার AlertLog model create
            alert_log = AlertLog.objects.create(
                rule=alert_rule,
                trigger_value=data.get('trigger_value', 0),
                threshold_value=alert_rule.threshold_value,
                message=data.get('message', 'Alert triggered via API'),
                details=data.get('details', {}),
            )
            
            # তোমার AlertLog methods ব্যবহার
            alert_log.mark_as_processing()
            
            # তোমার AlertRule method থেকে recipients
            recipients = alert_rule.get_recipients()
            
            # তোমার Notification model create
            if alert_rule.send_email and recipients['emails']:
                for email in recipients['emails']:
                    Notification.objects.create(
                        alert_log=alert_log,
                        notification_type='email',
                        recipient=email,
                        subject=f"Alert: {alert_rule.name}",
                        message=alert_log.message,
                        status='pending'
                    )
            
            alert_log.mark_as_complete()
            
            # তোমার AlertRule update
            alert_rule.last_triggered = alert_log.triggered_at
            alert_rule.save()
            
            return JsonResponse({
                'success': True,
                'alert_id': alert_log.id,
                'message': 'Alert triggered successfully'
            })
            
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)


class SystemHealthAPIView(View):
    """তোমার SystemHealthCheck model API"""
    
    def get(self, request):
        try:
            # তোমার class method ব্যবহার
            overall_status = SystemHealthCheck.get_overall_status()
            
            checks = SystemHealthCheck.objects.filter(
                is_active=True
            ).values(
                'check_name', 'check_type', 'status',
                'status_message', 'response_time_ms'
            )
            
            # তোমার SystemMetrics model
            system_metrics = SystemMetrics.get_latest()
            metrics_data = None
            if system_metrics:
                metrics_data = {
                    'cpu_usage': system_metrics.cpu_usage_percent,
                    'memory_usage': system_metrics.memory_usage_percent,
                    'disk_usage': system_metrics.disk_usage_percent,
                    'is_healthy': system_metrics.is_healthy,
                }
            
            return JsonResponse({
                'overall_status': overall_status,
                'checks': list(checks),
                'system_metrics': metrics_data,
                'timestamp': timezone.now().isoformat()
            })
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)


# ============================================
# ANALYTICS VIEWS (তোমার AlertAnalytics model এর জন্য)
# ============================================

@login_required
def analytics_dashboard(request):
    """তোমার AlertAnalytics model analytics"""
    date_from = request.GET.get('date_from', (timezone.now() - timedelta(days=7)).date())
    date_to = request.GET.get('date_to', timezone.now().date())
    
    # তোমার AlertAnalytics model generate করছি
    analytics = []
    current_date = date_from
    while current_date <= date_to:
        analytic = AlertAnalytics.generate_for_date(current_date)
        if analytic:
            analytics.append(analytic)
        current_date += timedelta(days=1)
    
    context = {
        'date_from': date_from,
        'date_to': date_to,
        'analytics': analytics,
    }
    
    return render(request, 'alerts/analytics_dashboard.html', context)


# ============================================
# REAL-TIME UPDATES
# ============================================

class RealTimeUpdatesView(LoginRequiredMixin, View):
    """তোমার models এর real-time updates"""
    
    def get(self, request):
        last_update = request.GET.get('last_update')
        if last_update:
            last_update = datetime.fromisoformat(last_update.replace('Z', '+00:00'))
        else:
            last_update = timezone.now() - timedelta(minutes=5)
        
        # তোমার AlertLog model থেকে new alerts
        new_alerts = AlertLog.objects.filter(
            triggered_at__gt=last_update
        ).select_related('rule')[:10]
        
        alerts_data = [
            {
                'id': alert.id,
                'rule': alert.rule.name,
                'severity': alert.rule.severity,
                'message': alert.message[:100],
                'triggered_at': alert.triggered_at.isoformat(),
            }
            for alert in new_alerts
        ]
        
        return JsonResponse({
            'alerts': alerts_data,
            'timestamp': timezone.now().isoformat()
        })


