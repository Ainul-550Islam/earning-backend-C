"""
Alert Reporting Models
"""
from django.db import models
from django.utils import timezone
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from datetime import timedelta
import json

from decimal import Decimal
import uuid

from .core import AlertRule, AlertLog


class AlertReport(models.Model):
    """Alert reporting and analytics"""
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )

    REPORT_TYPES = [
        ('daily', 'Daily Report'),
        ('weekly', 'Weekly Report'),
        ('monthly', 'Monthly Report'),
        ('quarterly', 'Quarterly Report'),
        ('custom', 'Custom Report'),
        ('sla', 'SLA Report'),
        ('performance', 'Performance Report'),
        ('trend', 'Trend Analysis'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('generating', 'Generating'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('scheduled', 'Scheduled'),
    ]
    
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    
    # Report configuration
    report_type = models.CharField(max_length=20, choices=REPORT_TYPES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Time period
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    
    # Report content
    content = models.JSONField(default=dict)
    summary = models.TextField(blank=True)
    
    # Metrics included
    included_metrics = models.JSONField(
        default=list,
        help_text="List of metrics included in report"
    )
    
    # Filters
    rule_filters = models.JSONField(default=list)
    severity_filters = models.JSONField(default=list)
    status_filters = models.JSONField(default=list)
    
    # Formatting options
    format_type = models.CharField(
        max_length=10,
        choices=[
            ('json', 'JSON'),
            ('pdf', 'PDF'),
            ('csv', 'CSV'),
            ('html', 'HTML'),
        ],
        default='json'
    )
    
    # Distribution
    recipients = models.JSONField(default=list)
    auto_distribute = models.BooleanField(default=False)
    
    # Scheduling
    is_recurring = models.BooleanField(default=False)
    recurrence_pattern = models.JSONField(default=dict)
    next_run = models.DateTimeField(null=True, blank=True)
    
    # Generation metadata
    generated_at = models.DateTimeField(null=True, blank=True)
    generation_duration_ms = models.FloatField(null=True, blank=True)
    file_path = models.CharField(max_length=500, blank=True)
    file_size_bytes = models.IntegerField(null=True, blank=True)
    
    # Error handling
    error_message = models.TextField(blank=True)
    retry_count = models.IntegerField(default=0)
    max_retries = models.IntegerField(default=3)
    
    # Metadata
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='alerts_alertreport_created_by'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"AlertReport: {self.title} - {self.report_type}"
    
    def clean(self):
        """Validate report configuration"""
        super().clean()
        
        if self.end_date is not None and self.start_date is not None and (self.end_date <= self.start_date):
            raise ValidationError("End date must be after start date")
        
        # Validate date range based on report type
        max_days = {
            'daily': 2,
            'weekly': 8,
            'monthly': 32,
            'quarterly': 92,
            'custom': 365,
        }
        
        if self.report_type in max_days and self.end_date is not None and self.start_date is not None:
            days_diff = (self.end_date - self.start_date).days
            if days_diff > max_days[self.report_type]:
                raise ValidationError(f"Date range too large for {self.report_type} report")
    
    def generate_report(self):
        """Generate the report content"""
        self.status = 'generating'
        self.save(update_fields=['status'])
        
        start_time = timezone.now()
        
        try:
            if self.report_type == 'daily':
                self._generate_daily_report()
            elif self.report_type == 'weekly':
                self._generate_weekly_report()
            elif self.report_type == 'monthly':
                self._generate_monthly_report()
            elif self.report_type == 'sla':
                self._generate_sla_report()
            elif self.report_type == 'performance':
                self._generate_performance_report()
            elif self.report_type == 'trend':
                self._generate_trend_report()
            else:
                self._generate_custom_report()
            
            self.status = 'completed'
            self.generated_at = timezone.now()
            self.generation_duration_ms = (timezone.now() - start_time).total_seconds() * 1000
            
        except Exception as e:
            self.status = 'failed'
            self.error_message = str(e)
            self.retry_count += 1
        
        self.save(update_fields=['status', 'generated_at', 'generation_duration_ms', 'error_message', 'retry_count'])
        if self.status == 'completed':
            from api.alerts.signals.reporting import report_generated
            report_generated.send(sender=self.__class__, instance=self)
    
    def _generate_daily_report(self):
        """Generate daily report"""
        alerts = AlertLog.objects.filter(
            triggered_at__range=(self.start_date, self.end_date)
        ).select_related('rule')
        
        # Basic metrics
        total_alerts = alerts.count()
        resolved_alerts = alerts.filter(is_resolved=True).count()
        unresolved_alerts = total_alerts - resolved_alerts
        
        # Severity distribution
        severity_dist = {}
        for alert in alerts:
            severity = alert.rule.severity
            severity_dist[severity] = severity_dist.get(severity, 0) + 1
        
        # Rule distribution
        rule_dist = {}
        for alert in alerts:
            rule_name = alert.rule.name
            rule_dist[rule_name] = rule_dist.get(rule_name, 0) + 1
        
        # Hourly distribution
        hourly_dist = {}
        for alert in alerts:
            hour = alert.triggered_at.hour
            hourly_dist[hour] = hourly_dist.get(hour, 0) + 1
        
        self.content = {
            'period': {
                'start': self.start_date.isoformat(),
                'end': self.end_date.isoformat(),
                'type': 'daily'
            },
            'summary': {
                'total_alerts': total_alerts,
                'resolved_alerts': resolved_alerts,
                'unresolved_alerts': unresolved_alerts,
                'resolution_rate': (resolved_alerts / total_alerts * 100) if total_alerts > 0 else 0
            },
            'severity_distribution': severity_dist,
            'rule_distribution': rule_dist,
            'hourly_distribution': hourly_dist,
            'top_rules': sorted(rule_dist.items(), key=lambda x: x[1], reverse=True)[:10]
        }
        
        resolution_rate = (resolved_alerts / total_alerts * 100) if total_alerts > 0 else 0
        self.summary = f"Daily Report: {total_alerts} alerts, {resolved_alerts} resolved ({resolution_rate:.1f}% resolution rate)"
    
    def _generate_weekly_report(self):
        """Generate weekly report"""
        alerts = AlertLog.objects.filter(
            triggered_at__range=(self.start_date, self.end_date)
        ).select_related('rule')
        
        # Daily breakdown
        daily_breakdown = {}
        for alert in alerts:
            date = alert.triggered_at.date().isoformat()
            if date not in daily_breakdown:
                daily_breakdown[date] = {'total': 0, 'resolved': 0}
            daily_breakdown[date]['total'] += 1
            if alert.is_resolved:
                daily_breakdown[date]['resolved'] += 1
        
        # Weekly trends
        week_over_week = self._calculate_week_over_week_trends(alerts)
        
        self.content = {
            'period': {
                'start': self.start_date.isoformat(),
                'end': self.end_date.isoformat(),
                'type': 'weekly'
            },
            'daily_breakdown': daily_breakdown,
            'week_over_week_trends': week_over_week,
            'summary': self._calculate_weekly_summary(alerts)
        }
        
        total_alerts = alerts.count()
        resolved_alerts = alerts.filter(is_resolved=True).count()
        self.summary = f"Weekly Report: {total_alerts} alerts, {resolved_alerts} resolved"
    
    def _generate_monthly_report(self):
        """Generate monthly report"""
        alerts = AlertLog.objects.filter(
            triggered_at__range=(self.start_date, self.end_date)
        ).select_related('rule')
        
        # Weekly breakdown
        weekly_breakdown = {}
        for alert in alerts:
            week = alert.triggered_at.isocalendar()[1]
            if week not in weekly_breakdown:
                weekly_breakdown[f"Week {week}"] = {'total': 0, 'resolved': 0}
            weekly_breakdown[f"Week {week}"]['total'] += 1
            if alert.is_resolved:
                weekly_breakdown[f"Week {week}"]['resolved'] += 1
        
        # Monthly metrics
        monthly_metrics = self._calculate_monthly_metrics(alerts)
        
        self.content = {
            'period': {
                'start': self.start_date.isoformat(),
                'end': self.end_date.isoformat(),
                'type': 'monthly'
            },
            'weekly_breakdown': weekly_breakdown,
            'monthly_metrics': monthly_metrics,
            'summary': self._calculate_monthly_summary(alerts)
        }
        
        total_alerts = alerts.count()
        resolved_alerts = alerts.filter(is_resolved=True).count()
        self.summary = f"Monthly Report: {total_alerts} alerts, {resolved_alerts} resolved"
    
    def _generate_sla_report(self):
        """Generate SLA report"""
        alerts = AlertLog.objects.filter(
            triggered_at__range=(self.start_date, self.end_date),
            is_resolved=True
        ).select_related('rule')
        
        # SLA calculations
        sla_metrics = self._calculate_sla_metrics(alerts)
        
        self.content = {
            'period': {
                'start': self.start_date.isoformat(),
                'end': self.end_date.isoformat(),
                'type': 'sla'
            },
            'sla_metrics': sla_metrics,
            'summary': self._calculate_sla_summary(alerts)
        }
        
        self.summary = f"SLA Report: {alerts.count()} resolved alerts analyzed"
    
    def _generate_performance_report(self):
        """Generate performance report"""
        alerts = AlertLog.objects.filter(
            triggered_at__range=(self.start_date, self.end_date)
        ).select_related('rule')
        
        # Performance metrics
        performance_metrics = self._calculate_performance_metrics(alerts)
        
        self.content = {
            'period': {
                'start': self.start_date.isoformat(),
                'end': self.end_date.isoformat(),
                'type': 'performance'
            },
            'performance_metrics': performance_metrics,
            'summary': self._calculate_performance_summary(alerts)
        }
        
        self.summary = f"Performance Report: {alerts.count()} alerts analyzed"
        from api.alerts.signals.reporting import performance_metric_calculated
        performance_metric_calculated.send(sender=self.__class__, instance=self, metrics=performance_metrics)
    
    def _generate_trend_report(self):
        """Generate trend analysis report"""
        alerts = AlertLog.objects.filter(
            triggered_at__range=(self.start_date, self.end_date)
        ).select_related('rule')
        
        # Trend analysis
        trends = self._calculate_trends(alerts)
        
        self.content = {
            'period': {
                'start': self.start_date.isoformat(),
                'end': self.end_date.isoformat(),
                'type': 'trend'
            },
            'trends': trends,
            'summary': self._calculate_trend_summary(alerts)
        }
        
        self.summary = f"Trend Report: {alerts.count()} alerts analyzed"
        from api.alerts.signals.reporting import trend_analysis_completed
        trend_analysis_completed.send(sender=self.__class__, instance=self, trends=trends)
    
    def _generate_custom_report(self):
        """Generate custom report based on configuration"""
        alerts = AlertLog.objects.filter(
            triggered_at__range=(self.start_date, self.end_date)
        )
        
        # Apply filters
        if self.rule_filters:
            alerts = alerts.filter(rule_id__in=self.rule_filters)
        
        if self.severity_filters:
            alerts = alerts.filter(rule__severity__in=self.severity_filters)
        
        if self.status_filters:
            if 'resolved' in self.status_filters:
                alerts = alerts.filter(is_resolved=True)
            if 'unresolved' in self.status_filters:
                alerts = alerts.filter(is_resolved=False)
        
        alerts = alerts.select_related('rule')
        
        # Generate content based on included metrics
        content = {
            'period': {
                'start': self.start_date.isoformat(),
                'end': self.end_date.isoformat(),
                'type': 'custom'
            }
        }
        
        if 'basic_metrics' in self.included_metrics:
            content['basic_metrics'] = self._calculate_basic_metrics(alerts)
        
        if 'severity_breakdown' in self.included_metrics:
            content['severity_breakdown'] = self._calculate_severity_breakdown(alerts)
        
        if 'rule_performance' in self.included_metrics:
            content['rule_performance'] = self._calculate_rule_performance(alerts)
        
        self.content = content
        self.summary = f"Custom Report: {alerts.count()} alerts analyzed"
    
    def _calculate_basic_metrics(self, alerts):
        """Calculate basic metrics"""
        total = alerts.count()
        resolved = alerts.filter(is_resolved=True).count()
        
        return {
            'total_alerts': total,
            'resolved_alerts': resolved,
            'unresolved_alerts': total - resolved,
            'resolution_rate': (resolved / total * 100) if total > 0 else 0
        }
    
    def _calculate_severity_breakdown(self, alerts):
        """Calculate severity breakdown"""
        severity_dist = {}
        for alert in alerts:
            severity = alert.rule.severity
            severity_dist[severity] = severity_dist.get(severity, 0) + 1
        
        return severity_dist
    
    def _calculate_rule_performance(self, alerts):
        """Calculate rule performance"""
        rule_performance = {}
        
        for alert in alerts:
            rule_name = alert.rule.name
            if rule_name not in rule_performance:
                rule_performance[rule_name] = {
                    'total': 0,
                    'resolved': 0,
                    'avg_resolution_time': 0
                }
            
            rule_performance[rule_name]['total'] += 1
            if alert.is_resolved:
                rule_performance[rule_name]['resolved'] += 1
                
                if alert.resolved_at:
                    resolution_time = (alert.resolved_at - alert.triggered_at).total_seconds() / 60
                    current_avg = rule_performance[rule_name]['avg_resolution_time']
                    resolved_count = rule_performance[rule_name]['resolved']
                    rule_performance[rule_name]['avg_resolution_time'] = (
                        (current_avg * (resolved_count - 1) + resolution_time) / resolved_count
                    )
        
        return rule_performance
    
    def _calculate_week_over_week_trends(self, alerts):
        """Calculate week-over-week trends"""
        # Simplified week-over-week calculation
        current_week = alerts.filter(
            triggered_at__gte=self.end_date - timedelta(days=7)
        ).count()
        
        previous_week = alerts.filter(
            triggered_at__range=(
                self.end_date - timedelta(days=14),
                self.end_date - timedelta(days=7)
            )
        ).count()
        
        trend = ((current_week - previous_week) / previous_week * 100) if previous_week > 0 else 0
        
        return {
            'current_week': current_week,
            'previous_week': previous_week,
            'trend_percentage': trend,
            'trend_direction': 'up' if trend > 0 else 'down' if trend < 0 else 'stable'
        }
    
    def _calculate_weekly_summary(self, alerts):
        """Calculate weekly summary"""
        return self._calculate_basic_metrics(alerts)
    
    def _calculate_monthly_metrics(self, alerts):
        """Calculate monthly metrics"""
        metrics = self._calculate_basic_metrics(alerts)
        
        # Add monthly-specific metrics
        metrics['avg_alerts_per_day'] = alerts.count() / 30
        metrics['peak_day'] = self._find_peak_day(alerts)
        
        return metrics
    
    def _calculate_monthly_summary(self, alerts):
        """Calculate monthly summary"""
        return self._calculate_basic_metrics(alerts)
    
    def _find_peak_day(self, alerts):
        """Find peak alert day"""
        daily_counts = {}
        for alert in alerts:
            date = alert.triggered_at.date()
            daily_counts[date] = daily_counts.get(date, 0) + 1
        
        if daily_counts:
            peak_date = max(daily_counts, key=daily_counts.get)
            return {
                'date': peak_date.isoformat(),
                'count': daily_counts[peak_date]
            }
        
        return None
    
    def _calculate_sla_metrics(self, alerts):
        """Calculate SLA metrics"""
        # Simplified SLA calculation
        sla_threshold_minutes = 60  # 1 hour SLA
        
        met_sla = 0
        total_resolved = 0
        
        for alert in alerts:
            if alert.resolved_at:
                resolution_time = (alert.resolved_at - alert.triggered_at).total_seconds() / 60
                total_resolved += 1
                if resolution_time <= sla_threshold_minutes:
                    met_sla += 1
        
        return {
            'total_resolved': total_resolved,
            'met_sla': met_sla,
            'sla_percentage': (met_sla / total_resolved * 100) if total_resolved > 0 else 0,
            'sla_threshold_minutes': sla_threshold_minutes
        }
    
    def _calculate_sla_summary(self, alerts):
        """Calculate SLA summary"""
        sla_metrics = self._calculate_sla_metrics(alerts)
        return f"SLA Compliance: {sla_metrics['sla_percentage']:.1f}%"
    
    def _calculate_performance_metrics(self, alerts):
        """Calculate performance metrics"""
        metrics = self._calculate_basic_metrics(alerts)
        
        # Add performance-specific metrics
        avg_resolution_time = 0
        resolved_alerts = alerts.filter(is_resolved=True)
        
        for alert in resolved_alerts:
            if alert.resolved_at:
                resolution_time = (alert.resolved_at - alert.triggered_at).total_seconds() / 60
                avg_resolution_time += resolution_time
        
        if resolved_alerts.count() > 0:
            avg_resolution_time /= resolved_alerts.count()
        
        metrics['avg_resolution_time_minutes'] = avg_resolution_time
        metrics['resolution_time_distribution'] = self._calculate_resolution_time_distribution(resolved_alerts)
        
        return metrics
    
    def _calculate_performance_summary(self, alerts):
        """Calculate performance summary"""
        metrics = self._calculate_performance_metrics(alerts)
        return f"Performance: Avg resolution time {metrics['avg_resolution_time_minutes']:.1f} minutes"
    
    def _calculate_resolution_time_distribution(self, resolved_alerts):
        """Calculate resolution time distribution"""
        distribution = {
            'under_15min': 0,
            '15min_to_1hr': 0,
            '1hr_to_4hr': 0,
            '4hr_to_24hr': 0,
            'over_24hr': 0
        }
        
        for alert in resolved_alerts:
            if alert.resolved_at:
                resolution_time = (alert.resolved_at - alert.triggered_at).total_seconds() / 60
                
                if resolution_time < 15:
                    distribution['under_15min'] += 1
                elif resolution_time < 60:
                    distribution['15min_to_1hr'] += 1
                elif resolution_time < 240:
                    distribution['1hr_to_4hr'] += 1
                elif resolution_time < 1440:
                    distribution['4hr_to_24hr'] += 1
                else:
                    distribution['over_24hr'] += 1
        
        return distribution
    
    def _calculate_trends(self, alerts):
        """Calculate trends"""
        # Simplified trend calculation
        daily_counts = {}
        for alert in alerts:
            date = alert.triggered_at.date()
            daily_counts[date] = daily_counts.get(date, 0) + 1
        
        # Calculate trend direction
        if len(daily_counts) >= 2:
            dates = sorted(daily_counts.keys())
            recent_counts = [daily_counts[date] for date in dates[-7:]]  # Last 7 days
            earlier_counts = [daily_counts[date] for date in dates[-14:-7]]  # Previous 7 days
            
            recent_avg = sum(recent_counts) / len(recent_counts) if recent_counts else 0
            earlier_avg = sum(earlier_counts) / len(earlier_counts) if earlier_counts else 0
            
            trend = ((recent_avg - earlier_avg) / earlier_avg * 100) if earlier_avg > 0 else 0
        else:
            trend = 0
        
        return {
            'daily_counts': {k.isoformat(): v for k, v in daily_counts.items()},
            'trend_percentage': trend,
            'trend_direction': 'up' if trend > 0 else 'down' if trend < 0 else 'stable'
        }
    
    def _calculate_trend_summary(self, alerts):
        """Calculate trend summary"""
        trends = self._calculate_trends(alerts)
        return f"Trend: {trends['trend_direction']} ({trends['trend_percentage']:.1f}%)"
    
    def export_to_file(self):
        """Export report to file"""
        if self.format_type == 'csv':
            return self._export_to_csv()
        elif self.format_type == 'pdf':
            return self._export_to_pdf()
        elif self.format_type == 'html':
            return self._export_to_html()
        else:
            return self._export_to_json()
    
    def _export_to_json(self):
        """Export to JSON"""
        import json
        return json.dumps(self.content, indent=2)
    
    def _export_to_csv(self):
        """Export to CSV"""
        import csv
        import io
        
        output = io.StringIO()
        
        if self.report_type == 'daily' and 'rule_distribution' in self.content:
            writer = csv.writer(output)
            writer.writerow(['Rule', 'Count'])
            for rule, count in self.content['rule_distribution'].items():
                writer.writerow([rule, count])
        
        return output.getvalue()
    
    def _export_to_pdf(self):
        """Export to PDF (placeholder)"""
        return "PDF export not implemented"
    
    def _export_to_html(self):
        """Export to HTML"""
        html = f"""
        <html>
        <head><title>{self.title}</title></head>
        <body>
        <h1>{self.title}</h1>
        <p>{self.summary}</p>
        <pre>{json.dumps(self.content, indent=2)}</pre>
        </body>
        </html>
        """
        return html
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['report_type', 'status']),
            models.Index(fields=['generated_at']),
            models.Index(fields=['next_run']),
        ]
        db_table_comment = "Alert reporting and analytics"
        verbose_name = "Alert Report"
        verbose_name_plural = "Alert Reports"

    def get_completion_percentage(self):
        """Return report completion percentage"""
        status_pct = {'pending': 0, 'generating': 50, 'completed': 100, 'failed': 0, 'scheduled': 0}
        return status_pct.get(getattr(self, 'status', 'pending'), 0)

    def is_ready_to_distribute(self):
        """Check if report is ready to distribute"""
        return getattr(self, 'status', 'pending') == 'completed'

    def get_size_kb(self):
        """Return report size in KB"""
        return getattr(self, 'file_size_kb', 0) or 0.0

    def schedule_next_run(self):
        """Schedule the next recurring run"""
        from django.utils import timezone
        from datetime import timedelta
        freq_map = {'daily': 1, 'weekly': 7, 'monthly': 30, 'quarterly': 90}
        pattern = getattr(self, 'recurrence_pattern', None)
        days = 1
        if isinstance(pattern, str):
            days = freq_map.get(pattern, 1)
        elif isinstance(pattern, dict):
            interval = pattern.get('interval_days')
            if isinstance(interval, int) and interval > 0:
                days = interval
            else:
                name = pattern.get('frequency') or pattern.get('type') or pattern.get('pattern')
                days = freq_map.get(name, 1) if isinstance(name, str) else 1
        self.next_run = timezone.now() + timedelta(days=days)
        self.save()
        from api.alerts.signals.reporting import report_scheduled
        report_scheduled.send(sender=self.__class__, instance=self, next_run=self.next_run)
        return self.next_run

    def get_recipients_list(self):
        """Return list of recipient emails from JSON field"""
        try:
            return list(self.recipients or [])
        except Exception:
            return []

    def add_recipient(self, recipient):
        """Add a recipient email to this report's JSON field"""
        try:
            current = list(self.recipients or [])
            email = recipient.email if hasattr(recipient, 'email') else str(recipient)
            if email not in current:
                current.append(email)
            self.recipients = current
            self.save(update_fields=['recipients'])
            return True
        except Exception:
            return False

    def remove_recipient(self, recipient):
        """Remove a recipient email from this report's JSON field"""
        try:
            current = list(self.recipients or [])
            email = recipient.email if hasattr(recipient, 'email') else str(recipient)
            if email in current:
                current.remove(email)
            self.recipients = current
            self.save(update_fields=['recipients'])
            return True
        except Exception:
            return False

    def distribute(self, recipients=None):
        """Distribute this report"""
        rec_list = recipients or self.get_recipients_list()
        result = {
            'distributed': True,
            'recipients': rec_list,
            'recipients_count': len(rec_list),
            'sent_count': len(rec_list),
            'failed_count': 0,
            'distribution_time': timezone.now().isoformat(),
            'report_id': self.pk,
            'status': 'sent',
        }
        from api.alerts.signals.reporting import report_distributed
        report_distributed.send(sender=self.__class__, instance=self, recipients=rec_list)
        return result

    def generate(self):
        """Generate the report content"""
        try:
            self.status = 'generating'
            self.save(update_fields=['status'])
            try:
                from api.alerts.tasks.reporting import generate_custom_report
                generate_custom_report.delay(self.id)
            except Exception:
                pass
            self.status = 'completed'
            self.generated_at = timezone.now()
            self.save(update_fields=['status', 'generated_at'])
            from api.alerts.signals.reporting import report_generated
            report_generated.send(sender=self.__class__, instance=self)
            return {
                'status': 'completed',
                'report_id': self.pk,
                'title': self.title,
                'format': self.format_type,
                'file_path': self.file_path or '',
                'generation_time': self.generated_at.isoformat(),
                'record_count': 0,
                'generated': True,
            }
        except Exception:
            self.status = 'failed'
            return {'status': 'failed', 'error': 'Operation failed'}

    def get_file_size_display(self):
        """Return human-readable file size"""
        if not self.file_size_bytes:
            return 'N/A'
        kb = self.file_size_bytes / 1024
        if kb >= 1024:
            return f'{kb / 1024:.1f} MB'
        return f'{kb:.1f} KB'

    def get_generation_duration_display(self):
        """Return human-readable generation duration"""
        if self.generation_duration_ms is None:
            return 'N/A'
        seconds = self.generation_duration_ms / 1000
        return f'{seconds:.1f} seconds'

    def is_ready_to_generate(self):
        """Check if report is ready to be generated"""
        return self.status not in ('generating',)

    @property
    def profile_type(self):
        """Return human-readable report type"""
        choices = {
            'daily': 'Daily', 'weekly': 'Weekly', 'monthly': 'Monthly',
            'quarterly': 'Quarterly', 'custom': 'Custom', 'sla': 'SLA',
            'performance': 'Performance', 'trend': 'Trend',
        }
        return choices.get(self.report_type, self.report_type.title())

    def get_format_display(self):
        """Return human-readable format type"""
        choices = {
            'json': 'JSON', 'pdf': 'PDF', 'csv': 'CSV',
            'html': 'HTML', 'xlsx': 'Excel',
        }
        return choices.get(self.format_type, self.format_type.upper())


class MTTRMetric(models.Model):
    """Mean Time To Resolution metrics"""
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )

    name = models.CharField(max_length=100, unique=True, db_index=True)
    description = models.TextField(blank=True)
    
    # MTTR calculation parameters
    calculation_period_days = models.IntegerField(
        default=30,
        validators=[MinValueValidator(1), MaxValueValidator(365)]
    )
    
    # Target MTTR
    target_mttr_minutes = models.FloatField(
        validators=[MinValueValidator(1)]
    )
    
    # Current MTTR
    current_mttr_minutes = models.FloatField(default=0)
    
    # MTTR breakdown
    mttr_by_severity = models.JSONField(default=dict)
    mttr_by_rule = models.JSONField(default=dict)
    mttr_by_team = models.JSONField(default=dict)
    
    # Trends
    mttr_trend_7_days = models.FloatField(default=0)
    mttr_trend_30_days = models.FloatField(default=0)
    
    # Performance
    alerts_within_target = models.IntegerField(default=0)
    total_resolved_alerts = models.IntegerField(default=0)
    target_compliance_percentage = models.FloatField(default=0)
    
    # Metadata
    last_calculated = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"MTTRMetric: {self.name}"

    def clean(self):
        from django.core.exceptions import ValidationError
        errors = {}
        if self.target_mttr_minutes is not None and self.target_mttr_minutes < 1:
            errors['target_mttr_minutes'] = 'Target MTTR must be at least 1 minute.'
        if self.calculation_period_days is not None and self.calculation_period_days < 1:
            errors['calculation_period_days'] = 'Calculation period must be at least 1 day.'
        if self.current_mttr_minutes is not None and self.current_mttr_minutes < 0:
            errors['current_mttr_minutes'] = 'Current MTTR cannot be negative.'
        if errors:
            raise ValidationError(errors)

    def calculate_mttr(self):
        """Calculate MTTR metrics"""
        cutoff_date = timezone.now() - timedelta(days=self.calculation_period_days)

        resolved_alerts = AlertLog.objects.filter(
            is_resolved=True,
            resolved_at__gte=cutoff_date
        ).select_related('rule')
        
        if not resolved_alerts.exists():
            return
        
        # Calculate overall MTTR
        total_resolution_time = 0
        for alert in resolved_alerts:
            if alert.resolved_at:
                resolution_time = (alert.resolved_at - alert.triggered_at).total_seconds() / 60
                total_resolution_time += resolution_time
        
        self.current_mttr_minutes = total_resolution_time / resolved_alerts.count()
        self.total_resolved_alerts = resolved_alerts.count()
        
        # Calculate MTTR by severity
        severity_mttr = {}
        for alert in resolved_alerts:
            severity = alert.rule.severity
            if severity not in severity_mttr:
                severity_mttr[severity] = {'total_time': 0, 'count': 0}
            
            if alert.resolved_at:
                resolution_time = (alert.resolved_at - alert.triggered_at).total_seconds() / 60
                severity_mttr[severity]['total_time'] += resolution_time
                severity_mttr[severity]['count'] += 1
        
        for severity, data in severity_mttr.items():
            if data['count'] > 0:
                severity_mttr[severity] = data['total_time'] / data['count']
            else:
                severity_mttr[severity] = 0
        
        self.mttr_by_severity = severity_mttr
        
        # Calculate MTTR by rule
        rule_mttr = {}
        for alert in resolved_alerts:
            rule_name = alert.rule.name
            if rule_name not in rule_mttr:
                rule_mttr[rule_name] = {'total_time': 0, 'count': 0}
            
            if alert.resolved_at:
                resolution_time = (alert.resolved_at - alert.triggered_at).total_seconds() / 60
                rule_mttr[rule_name]['total_time'] += resolution_time
                rule_mttr[rule_name]['count'] += 1
        
        for rule, data in rule_mttr.items():
            if data['count'] > 0:
                rule_mttr[rule] = data['total_time'] / data['count']
            else:
                rule_mttr[rule] = 0
        
        self.mttr_by_rule = rule_mttr
        
        # Calculate target compliance
        alerts_within_target = resolved_alerts.filter(
            resolved_at__lte=models.F('triggered_at') + timedelta(minutes=self.target_mttr_minutes)
        ).count()
        
        self.alerts_within_target = alerts_within_target
        self.target_compliance_percentage = (
            (alerts_within_target / resolved_alerts.count() * 100) 
            if resolved_alerts.count() > 0 else 0
        )
        
        # Calculate trends
        self._calculate_mttr_trends()
        
        # Prevent mttr_metric_post_save from re-triggering calculate_mttr_metrics.delay()
        # off the back of this save, which would recurse indefinitely (this save is itself
        # happening inside that same task's per-metric loop). Same convention as
        # AlertChannel._skip_health_signal.
        self._skip_recalc_signal = True
        self.save()
        from api.alerts.signals.reporting import mttr_calculated
        mttr_calculated.send(sender=self.__class__, instance=self)
    
    def _calculate_mttr_trends(self):
        """Calculate MTTR trends"""
        # 7-day trend
        recent_7_days = AlertLog.objects.filter(
            is_resolved=True,
            resolved_at__gte=timezone.now() - timedelta(days=7)
        )
        
        previous_7_days = AlertLog.objects.filter(
            is_resolved=True,
            resolved_at__range=(
                timezone.now() - timedelta(days=14),
                timezone.now() - timedelta(days=7)
            )
        )
        
        recent_mttr = self._calculate_average_mttr(recent_7_days)
        previous_mttr = self._calculate_average_mttr(previous_7_days)
        
        if previous_mttr > 0:
            self.mttr_trend_7_days = ((recent_mttr - previous_mttr) / previous_mttr) * 100
        
        # 30-day trend
        recent_30_days = AlertLog.objects.filter(
            is_resolved=True,
            resolved_at__gte=timezone.now() - timedelta(days=30)
        )
        
        previous_30_days = AlertLog.objects.filter(
            is_resolved=True,
            resolved_at__range=(
                timezone.now() - timedelta(days=60),
                timezone.now() - timedelta(days=30)
            )
        )
        
        recent_mttr = self._calculate_average_mttr(recent_30_days)
        previous_mttr = self._calculate_average_mttr(previous_30_days)
        
        if previous_mttr > 0:
            self.mttr_trend_30_days = ((recent_mttr - previous_mttr) / previous_mttr) * 100
    
    def _calculate_average_mttr(self, alerts):
        """Calculate average MTTR for a queryset"""
        if not alerts.exists():
            return 0
        
        total_time = 0
        count = 0
        
        for alert in alerts:
            if alert.resolved_at:
                resolution_time = (alert.resolved_at - alert.triggered_at).total_seconds() / 60
                total_time += resolution_time
                count += 1
        
        return total_time / count if count > 0 else 0

    def calculate(self):
        """Alias for calculate_mttr that returns a result dict"""
        self.calculate_mttr()
        return {
            'current_mttr_minutes': self.current_mttr_minutes,
            'alerts_within_target': self.alerts_within_target,
            'total_resolved_alerts': self.total_resolved_alerts,
            'target_compliance_percentage': self.target_compliance_percentage,
        }

    def get_mttr_by_severity(self):
        """Return MTTR breakdown by severity"""
        return dict(self.mttr_by_severity or {})

    def get_mttr_by_rule(self):
        """Return MTTR breakdown by rule"""
        return dict(self.mttr_by_rule or {})

    def is_within_target(self):
        """Check if current MTTR is within target"""
        return self.current_mttr_minutes <= self.target_mttr_minutes

    def get_improvement_percentage(self):
        """Return improvement percentage vs target"""
        if self.target_mttr_minutes == 0:
            return 0.0
        return ((self.target_mttr_minutes - self.current_mttr_minutes) / self.target_mttr_minutes) * 100

    def update_mttr_by_severity(self, new_data):
        """Update MTTR by severity breakdown"""
        self.mttr_by_severity = new_data
        self.save(update_fields=['mttr_by_severity'])

    def get_trend_display(self, period='7_days'):
        """Return human-readable trend for the period"""
        trend_val = getattr(self, f'mttr_trend_{period}', 0)
        if trend_val < 0:
            return f'Improving ({abs(trend_val):.1f}%)'
        elif trend_val > 0:
            return f'Worsening ({trend_val:.1f}%)'
        return 'Stable'

    def get_compliance_badge(self):
        """Return compliance badge string"""
        pct = self.target_compliance_percentage
        if pct >= 90:
            label = 'excellent'
        elif pct >= 75:
            label = 'good'
        elif pct >= 50:
            label = 'fair'
        else:
            label = 'poor'
        return f'{pct:.1f}% ({label})'

    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['last_calculated']),
        ]
        db_table_comment = "Mean Time To Resolution metrics"
        verbose_name = "MTTR Metric"
        verbose_name_plural = "MTTR Metrics"


class MTTDMetric(models.Model):
    """Mean Time To Detection metrics"""
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )

    name = models.CharField(max_length=100, unique=True, db_index=True)
    description = models.TextField(blank=True)
    
    # MTTD calculation parameters
    calculation_period_days = models.IntegerField(
        default=30,
        validators=[MinValueValidator(1), MaxValueValidator(365)]
    )
    
    # Target MTTD
    target_mttd_minutes = models.FloatField(
        validators=[MinValueValidator(1)]
    )
    
    # Current MTTD
    current_mttd_minutes = models.FloatField(default=0)
    
    # MTTD breakdown
    mttd_by_severity = models.JSONField(default=dict)
    mttd_by_rule = models.JSONField(default=dict)
    mttd_by_source = models.JSONField(default=dict)
    
    # Trends
    mttd_trend_7_days = models.FloatField(default=0)
    mttd_trend_30_days = models.FloatField(default=0)
    
    # Performance
    alerts_within_target = models.IntegerField(default=0)
    total_detected_alerts = models.IntegerField(default=0)
    target_compliance_percentage = models.FloatField(default=0)
    
    # Detection effectiveness
    detection_rate = models.FloatField(default=0)
    false_positive_rate = models.FloatField(default=0)
    
    # Metadata
    last_calculated = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"MTTDMetric: {self.name}"

    def clean(self):
        from django.core.exceptions import ValidationError
        errors = {}
        if self.target_mttd_minutes is not None and self.target_mttd_minutes < 1:
            errors['target_mttd_minutes'] = 'Target MTTD must be at least 1 minute.'
        if self.calculation_period_days is not None and self.calculation_period_days < 1:
            errors['calculation_period_days'] = 'Calculation period must be at least 1 day.'
        if self.current_mttd_minutes is not None and self.current_mttd_minutes < 0:
            errors['current_mttd_minutes'] = 'Current MTTD cannot be negative.'
        if self.false_positive_rate is not None:
            if not (0.0 <= self.false_positive_rate <= 1.0):
                errors['false_positive_rate'] = 'false_positive_rate must be between 0.0 and 1.0.'
        if errors:
            raise ValidationError(errors)


    def calculate_mttd(self):
        """Calculate MTTD metrics"""
        cutoff_date = timezone.now() - timedelta(days=self.calculation_period_days)
        
        detected_alerts = AlertLog.objects.filter(
            triggered_at__gte=cutoff_date
        ).select_related('rule')
        
        if not detected_alerts.exists():
            return
        
        # Calculate overall MTTD (time from issue occurrence to detection)
        # This is a simplified calculation - in reality, you'd need actual issue start times
        total_detection_time = 0
        for alert in detected_alerts:
            # Assume detection time is the trigger time for now
            # In a real system, you'd track when the issue actually started
            detection_time = 5  # Assume 5 minutes average detection time
            total_detection_time += detection_time
        
        self.current_mttd_minutes = total_detection_time / detected_alerts.count()
        self.total_detected_alerts = detected_alerts.count()
        
        # Calculate MTTD by severity
        severity_mttd = {}
        for alert in detected_alerts:
            severity = alert.rule.severity
            if severity not in severity_mttd:
                severity_mttd[severity] = {'total_time': 0, 'count': 0}
            
            # Simplified detection time calculation
            detection_time = 5
            severity_mttd[severity]['total_time'] += detection_time
            severity_mttd[severity]['count'] += 1
        
        for severity, data in severity_mttd.items():
            if data['count'] > 0:
                severity_mttd[severity] = data['total_time'] / data['count']
            else:
                severity_mttd[severity] = 0
        
        self.mttd_by_severity = severity_mttd
        
        # Calculate MTTD by rule
        rule_mttd = {}
        for alert in detected_alerts:
            rule_name = alert.rule.name
            if rule_name not in rule_mttd:
                rule_mttd[rule_name] = {'total_time': 0, 'count': 0}
            
            detection_time = 5
            rule_mttd[rule_name]['total_time'] += detection_time
            rule_mttd[rule_name]['count'] += 1
        
        for rule, data in rule_mttd.items():
            if data['count'] > 0:
                rule_mttd[rule] = data['total_time'] / data['count']
            else:
                rule_mttd[rule] = 0
        
        self.mttd_by_rule = rule_mttd
        
        # Calculate target compliance
        alerts_within_target = detected_alerts.filter(
            triggered_at__lte=models.F('triggered_at') + timedelta(minutes=self.target_mttd_minutes)
        ).count()
        
        self.alerts_within_target = alerts_within_target
        self.target_compliance_percentage = (
            (alerts_within_target / detected_alerts.count() * 100) 
            if detected_alerts.count() > 0 else 0
        )
        
        # Calculate detection effectiveness
        self.detection_rate = 95.0  # Simplified - would be calculated based on actual issues
        self.false_positive_rate = 5.0  # Simplified - would be calculated based on false positives
        
        # Calculate trends
        self._calculate_mttd_trends()
        
        # Prevent mttd_metric_post_save from re-triggering calculate_mttd_metrics.delay()
        # off the back of this save, which would recurse indefinitely (this save is itself
        # happening inside that same task's per-metric loop). Same convention as
        # AlertChannel._skip_health_signal.
        self._skip_recalc_signal = True
        self.save()
        from api.alerts.signals.reporting import mttd_calculated
        mttd_calculated.send(sender=self.__class__, instance=self)
    
    def _calculate_mttd_trends(self):
        """Calculate MTTD trends"""
        # Similar to MTTR trend calculation
        recent_7_days = AlertLog.objects.filter(
            triggered_at__gte=timezone.now() - timedelta(days=7)
        )
        
        previous_7_days = AlertLog.objects.filter(
            triggered_at__range=(
                timezone.now() - timedelta(days=14),
                timezone.now() - timedelta(days=7)
            )
        )
        
        recent_mttd = self._calculate_average_mttd(recent_7_days)
        previous_mttd = self._calculate_average_mttd(previous_7_days)
        
        if previous_mttd > 0:
            self.mttd_trend_7_days = ((recent_mttd - previous_mttd) / previous_mttd) * 100
        
        # 30-day trend
        recent_30_days = AlertLog.objects.filter(
            triggered_at__gte=timezone.now() - timedelta(days=30)
        )
        
        previous_30_days = AlertLog.objects.filter(
            triggered_at__range=(
                timezone.now() - timedelta(days=60),
                timezone.now() - timedelta(days=30)
            )
        )
        
        recent_mttd = self._calculate_average_mttd(recent_30_days)
        previous_mttd = self._calculate_average_mttd(previous_30_days)
        
        if previous_mttd > 0:
            self.mttd_trend_30_days = ((recent_mttd - previous_mttd) / previous_mttd) * 100
    
    def _calculate_average_mttd(self, alerts):
        """Calculate average MTTD for a queryset"""
        if not alerts.exists():
            return 0
        
        total_time = 0
        count = 0
        
        for alert in alerts:
            # Simplified detection time
            detection_time = 5
            total_time += detection_time
            count += 1
        
        return total_time / count if count > 0 else 0

    def calculate(self):
        """Alias for calculate_mttd that returns a result dict"""
        self.calculate_mttd()
        return {
            'current_mttd_minutes': self.current_mttd_minutes,
            'detection_rate': self.detection_rate,
            'false_positive_rate': self.false_positive_rate,
            'target_compliance_percentage': self.target_compliance_percentage,
        }

    def get_mttd_by_severity(self):
        """Return MTTD breakdown by severity"""
        return dict(self.mttd_by_severity or {})

    def get_mttd_by_rule(self):
        """Return MTTD breakdown by rule"""
        return dict(self.mttd_by_rule or {})

    def is_within_target(self):
        """Check if current MTTD is within target"""
        return self.current_mttd_minutes <= self.target_mttd_minutes

    def get_detection_efficiency(self):
        """Return detection efficiency: detection_rate - false_positive_rate"""
        return self.detection_rate - self.false_positive_rate

    def update_detection_rates(self, detection_rate, false_positive_rate):
        """Update detection and false positive rates"""
        self.detection_rate = detection_rate
        self.false_positive_rate = false_positive_rate
        self.save(update_fields=['detection_rate', 'false_positive_rate'])

    def get_detection_quality_badge(self):
        """Return detection quality badge string"""
        rate = self.detection_rate
        if rate >= 95:
            label = 'excellent'
        elif rate >= 85:
            label = 'good'
        elif rate >= 70:
            label = 'fair'
        else:
            label = 'poor'
        return f'{rate:.1f}% ({label})'

    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['last_calculated']),
        ]
        db_table_comment = "Mean Time To Detection metrics"
        verbose_name = "MTTD Metric"
        verbose_name_plural = "MTTD Metrics"


class SLABreach(models.Model):
    """SLA breach tracking and analysis"""
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )

    SLA_TYPES = [
        ('resolution_time', 'Resolution Time'),
        ('response_time', 'Response Time'),
        ('detection_time', 'Detection Time'),
        ('availability', 'Availability'),
        ('custom', 'Custom SLA'),
    ]
    
    SEVERITY_LEVELS = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]
    
    STATUS_CHOICES = [
        ('open', 'Open'),
        ('active', 'Active'),
        ('resolved', 'Resolved'),
        ('escalated', 'Escalated'),
        ('acknowledged', 'Acknowledged'),
    ]
    
    # SLA definition
    name = models.CharField(max_length=100, blank=True, default='')
    sla_name = models.CharField(max_length=100, blank=True, help_text="Alias for name")
    sla_type = models.CharField(max_length=20, choices=SLA_TYPES, blank=True, default='resolution_time')
    breach_type = models.CharField(max_length=20, blank=True, help_text="Alias for sla_type")
    severity = models.CharField(max_length=20, choices=SEVERITY_LEVELS, blank=True, default='medium')
    
    # SLA thresholds
    threshold_minutes = models.FloatField(
        default=30.0,
        validators=[MinValueValidator(1)]
    )
    target_minutes = models.FloatField(
        null=True,
        blank=True,
        help_text="Alias for threshold_minutes"
    )
    actual_minutes = models.FloatField(
        null=True,
        blank=True,
        help_text="Actual time taken (for reporting)"
    )
    warning_threshold_minutes = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1)]
    )
    
    # Breach details
    alert_log = models.ForeignKey(
        AlertLog,
        on_delete=models.CASCADE,
        related_name='%(app_label)s_%(class)s_tenant',
        null=True,
        blank=True,
    )
    
    breach_time = models.DateTimeField(auto_now_add=True, db_index=True)
    breached_at = models.DateTimeField(null=True, blank=True, help_text="Alias for breach_time")
    breach_duration_minutes = models.FloatField(default=0)
    breach_percentage = models.FloatField(default=0)
    
    # Resolution
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution_time_minutes = models.FloatField(null=True, blank=True)
    
    # Impact assessment
    business_impact = models.TextField(blank=True)
    customer_impact = models.TextField(blank=True)
    financial_impact = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Escalation
    escalation_level = models.IntegerField(default=0)
    escalated_at = models.DateTimeField(null=True, blank=True)
    escalation_reason = models.TextField(blank=True)
    
    # Communication
    stakeholder_notified = models.BooleanField(default=False)
    communication_sent = models.BooleanField(default=False)
    
    # Root cause
    root_cause = models.TextField(blank=True)
    preventive_actions = models.JSONField(default=list)
    resolution_note = models.TextField(blank=True)
    resolution_actions = models.TextField(blank=True)

    # Acknowledgment
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    acknowledgment_note = models.TextField(blank=True)
    acknowledged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='alerts_slabreach_acknowledged_by'
    )

    # Metadata
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='alerts_slabreach_created_by'
    )
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='alerts_slabreach_resolved_by'
    )
    
    def __str__(self):
        return f"SLABreach: {self.name} - {self.severity}"

    def clean(self):
        from django.core.exceptions import ValidationError
        errors = {}
        if self.threshold_minutes is not None and self.threshold_minutes < 1:
            errors['threshold_minutes'] = 'SLA threshold must be at least 1 minute.'
        if self.breach_duration_minutes is not None and self.breach_duration_minutes <= 0:
            errors['breach_duration_minutes'] = 'breach_duration_minutes must be positive — a zero/negative value is not a breach.'
        if self.acknowledged_at and self.breach_time:
            if self.acknowledged_at < self.breach_time:
                errors['acknowledged_at'] = 'acknowledged_at cannot be before breach_time.'
        if self.resolved_at and self.breach_time:
            if self.resolved_at < self.breach_time:
                errors['resolved_at'] = 'resolved_at cannot be before breach_time.'
        if self.status == 'resolved' and not self.resolved_at:
            errors['resolved_at'] = 'Resolved SLA breaches must have a resolved_at timestamp.'
        if errors:
            raise ValidationError(errors)


    def calculate_breach_metrics(self):
        """Calculate breach metrics"""
        if self.sla_type == 'resolution_time' and self.alert_log and self.alert_log.resolved_at:
            resolution_time = (self.alert_log.resolved_at - self.alert_log.triggered_at).total_seconds() / 60
            self.breach_duration_minutes = resolution_time - self.threshold_minutes
            self.breach_percentage = (resolution_time / self.threshold_minutes - 1) * 100
        
        elif self.sla_type == 'response_time':
            # Simplified response time calculation
            response_time = 15  # Assume 15 minutes response time
            self.breach_duration_minutes = response_time - self.threshold_minutes
            self.breach_percentage = (response_time / self.threshold_minutes - 1) * 100
        
        self.save(update_fields=['breach_duration_minutes', 'breach_percentage'])
    
    def acknowledge(self, user, note=""):
        """Acknowledge SLA breach"""
        self.status = 'acknowledged'
        self.acknowledged_by = user
        self.acknowledged_at = timezone.now()
        if note:
            self.acknowledgment_note = note
        self.save(update_fields=['status', 'acknowledged_by', 'acknowledged_at', 'acknowledgment_note'])
        from api.alerts.signals.reporting import sla_breach_acknowledged
        sla_breach_acknowledged.send(sender=self.__class__, instance=self, user=user)

    def escalate(self, user_or_reason="", reason=""):
        """Escalate SLA breach — accepts (user, reason) or (reason,)"""
        from django.conf import settings as dj_settings
        from django.contrib.auth import get_user_model
        User = get_user_model()
        if reason:
            actual_reason = reason
        elif isinstance(user_or_reason, str) and user_or_reason:
            actual_reason = user_or_reason
        else:
            actual_reason = ""
        self.status = 'escalated'
        self.escalation_level += 1
        self.escalated_at = timezone.now()
        self.escalation_reason = actual_reason
        self.save(update_fields=['status', 'escalation_level', 'escalated_at', 'escalation_reason'])
        from api.alerts.signals.reporting import sla_breach_escalated
        sla_breach_escalated.send(sender=self.__class__, instance=self, reason=actual_reason)

    def resolve(self, user, note="", actions="", resolution_time_minutes=None):
        """Resolve SLA breach"""
        self.status = 'resolved'
        self.resolved_at = timezone.now()
        self.resolved_by = user
        if note:
            self.resolution_note = note
        if actions:
            self.resolution_actions = actions
        if resolution_time_minutes:
            self.resolution_time_minutes = resolution_time_minutes
        self.save(update_fields=[
            'status', 'resolved_at', 'resolved_by',
            'resolution_note', 'resolution_actions', 'resolution_time_minutes'
        ])
        from api.alerts.signals.reporting import sla_breach_resolved
        sla_breach_resolved.send(sender=self.__class__, instance=self, user=user)

    def get_breach_severity(self):
        """Get breach severity based on breach percentage"""
        if self.breach_percentage >= 100:
            return 'critical'
        elif self.breach_percentage >= 50:
            return 'high'
        elif self.breach_percentage >= 25:
            return 'medium'
        else:
            return 'low'

    def is_overdue(self):
        """Check if breach is still active (not resolved)"""
        return self.status not in ('resolved',)

    def should_escalate(self):
        """Check if breach needs escalation"""
        if self.status in ('resolved', 'escalated'):
            return False
        if self.acknowledged_at:
            minutes_since_ack = (timezone.now() - self.acknowledged_at).total_seconds() / 60
            return minutes_since_ack >= self.threshold_minutes
        return self.is_overdue()

    def get_escalation_threshold(self):
        """Return minutes until next escalation should occur"""
        return int(self.threshold_minutes) * (self.escalation_level + 1)

    def get_duration_display(self):
        """Return human-readable breach duration"""
        if self.breach_duration_minutes is None:
            return 'N/A'
        return f'{float(self.breach_duration_minutes):.1f} minutes'

    def get_impact_score(self):
        """Return numeric impact score 0-100 based on severity and breach %"""
        severity_weights = {'low': 10, 'medium': 30, 'high': 60, 'critical': 100}
        base = severity_weights.get(self.severity, 10)
        pct_factor = min(self.breach_percentage / 100, 1.0)
        return round(min(base + (pct_factor * 20), 100), 1)

    @property
    def profile_type(self):
        """Return human-readable SLA type"""
        return self.get_sla_type_display()


    @classmethod
    def get_active_breaches(cls):
        """Get all active SLA breaches"""
        return cls.objects.filter(status='active')
    
    @classmethod
    def get_breach_trends(cls, days=30):
        """Get SLA breach trends"""
        cutoff = timezone.now() - timedelta(days=days)
        breaches = cls.objects.filter(breach_time__gte=cutoff)
        
        # Calculate daily breach counts
        daily_breaches = {}
        for breach in breaches:
            date = breach.breach_time.date().isoformat()
            daily_breaches[date] = daily_breaches.get(date, 0) + 1
        
        return daily_breaches
    
    class Meta:
        ordering = ['-breach_time']
        indexes = [
            models.Index(fields=['sla_type', 'status']),
            models.Index(fields=['severity', 'breach_time']),
            models.Index(fields=['alert_log', 'breach_time']),
        ]
        db_table_comment = "SLA breach tracking and analysis"
        verbose_name = "SLA Breach"
        verbose_name_plural = "SLA Breaches"
