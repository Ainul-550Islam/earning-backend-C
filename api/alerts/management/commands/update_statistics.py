"""
Django Management Command: Update Alert Statistics
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db.models import Count, Avg, Q, F
from datetime import timedelta
import logging

from alerts.models.core import AlertRule, AlertLog, Notification
from alerts.models.channel import AlertChannel
from alerts.models.incident import Incident
from alerts.models.reporting import MTTRMetric, MTTDMetric, SLABreach
from alerts.tasks.reporting import calculate_mttr_metrics, calculate_mttd_metrics

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Update alert statistics and metrics'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--type',
            type=str,
            choices=['rules', 'logs', 'channels', 'incidents', 'mttr', 'mttd', 'sla', 'all'],
            default='all',
            help='Type of statistics to update (default: all)'
        )
        parser.add_argument(
            '--days',
            type=int,
            default=30,
            help='Calculate statistics for last N days (default: 30)'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force recalculation even if recently updated'
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed statistics'
        )
        parser.add_argument(
            '--save-metrics',
            action='store_true',
            help='Save calculated metrics to database'
        )
        parser.add_argument(
            '--output-format',
            type=str,
            choices=['text', 'json'],
            default='text',
            help='Output format (default: text)'
        )
    
    def handle(self, *args, **options):
        stat_type = options['type']
        days = options['days']
        force = options['force']
        verbose = options['verbose']
        save_metrics = options['save_metrics']
        output_format = options['output_format']
        
        self.stdout.write(self.style.SUCCESS(f'Updating alert statistics for last {days} days'))
        
        cutoff_date = timezone.now() - timedelta(days=days)
        
        # Determine what to update
        if stat_type == 'all':
            stat_types = ['rules', 'logs', 'channels', 'incidents', 'mttr', 'mttd', 'sla']
        else:
            stat_types = [stat_type]
        
        # Collect statistics
        all_stats = {
            'timestamp': timezone.now(),
            'period_days': days,
            'cutoff_date': cutoff_date
        }
        
        for s_type in stat_types:
            try:
                if s_type == 'rules':
                    all_stats['rules'] = self._update_rules_stats(cutoff_date, verbose, save_metrics)
                elif s_type == 'logs':
                    all_stats['logs'] = self._update_logs_stats(cutoff_date, verbose, save_metrics)
                elif s_type == 'channels':
                    all_stats['channels'] = self._update_channels_stats(cutoff_date, verbose, save_metrics)
                elif s_type == 'incidents':
                    all_stats['incidents'] = self._update_incidents_stats(cutoff_date, verbose, save_metrics)
                elif s_type == 'mttr':
                    all_stats['mttr'] = self._update_mttr_stats(cutoff_date, verbose, save_metrics)
                elif s_type == 'mttd':
                    all_stats['mttd'] = self._update_mttd_stats(cutoff_date, verbose, save_metrics)
                elif s_type == 'sla':
                    all_stats['sla'] = self._update_sla_stats(cutoff_date, verbose, save_metrics)
                
                self.stdout.write(f'  - Updated {s_type} statistics')
                
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'  - Failed to update {s_type} statistics: {str(e)}'))
        
        # Output results
        if output_format == 'json':
            self._output_json(all_stats)
        else:
            self._output_text(all_stats, verbose)
        
        # Trigger background tasks for continuous updates
        if save_metrics:
            calculate_mttr_metrics.delay()
            calculate_mttd_metrics.delay()
        
        # Summary
        self.stdout.write(self.style.SUCCESS(f'Statistics update complete:'))
        self.stdout.write(f'  - Period: Last {days} days')
        self.stdout.write(f'  - Types updated: {", ".join(stat_types)}')
        self.stdout.write(f'  - Metrics saved: {save_metrics}')
    
    def _update_rules_stats(self, cutoff_date, verbose, save_metrics):
        """Update alert rules statistics"""
        stats = {}
        
        # Basic counts
        stats['total_rules'] = AlertRule.objects.count()
        stats['active_rules'] = AlertRule.objects.filter(is_active=True).count()
        stats['inactive_rules'] = stats['total_rules'] - stats['active_rules']
        
        # Rules by severity
        severity_breakdown = AlertRule.objects.values('severity').annotate(count=Count('id'))
        stats['severity_breakdown'] = {item['severity']: item['count'] for item in severity_breakdown}
        
        # Rules by type
        type_breakdown = AlertRule.objects.values('alert_type').annotate(count=Count('id'))
        stats['type_breakdown'] = {item['alert_type']: item['count'] for item in type_breakdown}
        
        # Rules with recent activity
        recent_rules = AlertRule.objects.filter(
            last_triggered__gte=cutoff_date
        ).count()
        stats['rules_with_recent_activity'] = recent_rules
        
        # Average threshold values
        avg_thresholds = AlertRule.objects.aggregate(
            avg_threshold=Avg('threshold_value'),
            avg_cooldown=Avg('cooldown_minutes')
        )
        stats['avg_threshold_value'] = avg_thresholds['avg_threshold'] or 0
        stats['avg_cooldown_minutes'] = avg_thresholds['avg_cooldown'] or 0
        
        if verbose:
            self.stdout.write(f'    Rules: {stats["active_rules"]}/{stats["total_rules"]} active')
            self.stdout.write(f'    Recent activity: {stats["rules_with_recent_activity"]} rules')
            self.stdout.write(f'    Avg threshold: {stats["avg_threshold_value"]:.2f}')
        
        return stats
    
    def _update_logs_stats(self, cutoff_date, verbose, save_metrics):
        """Update alert logs statistics"""
        stats = {}
        
        # Basic counts
        total_alerts = AlertLog.objects.filter(triggered_at__gte=cutoff_date).count()
        resolved_alerts = AlertLog.objects.filter(
            triggered_at__gte=cutoff_date,
            is_resolved=True
        ).count()
        
        stats['total_alerts'] = total_alerts
        stats['resolved_alerts'] = resolved_alerts
        stats['unresolved_alerts'] = total_alerts - resolved_alerts
        stats['resolution_rate'] = (resolved_alerts / total_alerts * 100) if total_alerts > 0 else 0
        
        # Alerts by severity
        severity_breakdown = AlertLog.objects.filter(
            triggered_at__gte=cutoff_date
        ).values('rule__severity').annotate(count=Count('id'))
        stats['severity_breakdown'] = {item['rule__severity']: item['count'] for item in severity_breakdown}
        
        # Average resolution time
        resolved_with_time = AlertLog.objects.filter(
            triggered_at__gte=cutoff_date,
            is_resolved=True,
            resolved_at__isnull=False
        )
        
        if resolved_with_time.exists():
            total_resolution_time = sum(
                (alert.resolved_at - alert.triggered_at).total_seconds() / 60
                for alert in resolved_with_time
            )
            stats['avg_resolution_time_minutes'] = total_resolution_time / resolved_with_time.count()
        else:
            stats['avg_resolution_time_minutes'] = 0
        
        # Daily trends
        daily_trends = AlertLog.objects.filter(
            triggered_at__gte=cutoff_date
        ).extra(
            {'day': "date(triggered_at)"}
        ).values('day').annotate(
            total=Count('id'),
            resolved=Count('id', filter=Q(is_resolved=True))
        ).order_by('day')
        
        stats['daily_trends'] = list(daily_trends)
        
        if verbose:
            self.stdout.write(f'    Alerts: {stats["resolved_alerts"]}/{stats["total_alerts"]} resolved')
            self.stdout.write(f'    Resolution rate: {stats["resolution_rate"]:.1f}%')
            self.stdout.write(f'    Avg resolution time: {stats["avg_resolution_time_minutes"]:.1f} min')
        
        return stats
    
    def _update_channels_stats(self, cutoff_date, verbose, save_metrics):
        """Update channels statistics"""
        stats = {}
        
        # Basic counts
        stats['total_channels'] = AlertChannel.objects.count()
        stats['enabled_channels'] = AlertChannel.objects.filter(is_enabled=True).count()
        stats['healthy_channels'] = AlertChannel.objects.filter(status='active').count()
        
        # Channels by type
        type_breakdown = AlertChannel.objects.values('channel_type').annotate(count=Count('id'))
        stats['type_breakdown'] = {item['channel_type']: item['count'] for item in type_breakdown}
        
        # Channel health
        health_breakdown = AlertChannel.objects.values('status').annotate(count=Count('id'))
        stats['health_breakdown'] = {item['status']: item['count'] for item in health_breakdown}
        
        # Recent health checks
        recent_health_checks = AlertChannel.objects.filter(
            last_success__gte=cutoff_date
        ).count()
        stats['channels_with_recent_health_checks'] = recent_health_checks
        
        # Average success rates
        avg_success_rates = AlertChannel.objects.aggregate(
            avg_success_rate=Avg('total_sent') * 100 / (F('total_sent') + F('total_failed'))
        )
        stats['avg_success_rate'] = avg_success_rates['avg_success_rate'] or 0
        
        if verbose:
            self.stdout.write(f'    Channels: {stats["healthy_channels"]}/{stats["total_channels"]} healthy')
            self.stdout.write(f'    Enabled: {stats["enabled_channels"]}')
            self.stdout.write(f'    Avg success rate: {stats["avg_success_rate"]:.1f}%')
        
        return stats
    
    def _update_incidents_stats(self, cutoff_date, verbose, save_metrics):
        """Update incidents statistics"""
        stats = {}
        
        # Basic counts
        total_incidents = Incident.objects.filter(detected_at__gte=cutoff_date).count()
        resolved_incidents = Incident.objects.filter(
            detected_at__gte=cutoff_date,
            status='resolved'
        ).count()
        
        stats['total_incidents'] = total_incidents
        stats['resolved_incidents'] = resolved_incidents
        stats['active_incidents'] = total_incidents - resolved_incidents
        stats['resolution_rate'] = (resolved_incidents / total_incidents * 100) if total_incidents > 0 else 0
        
        # Incidents by severity
        severity_breakdown = Incident.objects.filter(
            detected_at__gte=cutoff_date
        ).values('severity').annotate(count=Count('id'))
        stats['severity_breakdown'] = {item['severity']: item['count'] for item in severity_breakdown}
        
        # Average resolution time
        resolved_with_time = Incident.objects.filter(
            detected_at__gte=cutoff_date,
            status='resolved',
            resolved_at__isnull=False
        )
        
        if resolved_with_time.exists():
            total_resolution_time = sum(
                (incident.resolved_at - incident.detected_at).total_seconds() / 60
                for incident in resolved_with_time
            )
            stats['avg_resolution_time_minutes'] = total_resolution_time / resolved_with_time.count()
        else:
            stats['avg_resolution_time_minutes'] = 0
        
        # Incidents by impact
        impact_breakdown = Incident.objects.filter(
            detected_at__gte=cutoff_date
        ).values('impact').annotate(count=Count('id'))
        stats['impact_breakdown'] = {item['impact']: item['count'] for item in impact_breakdown}
        
        if verbose:
            self.stdout.write(f'    Incidents: {stats["resolved_incidents"]}/{stats["total_incidents"]} resolved')
            self.stdout.write(f'    Resolution rate: {stats["resolution_rate"]:.1f}%')
            self.stdout.write(f'    Avg resolution time: {stats["avg_resolution_time_minutes"]:.1f} min')
        
        return stats
    
    def _update_mttr_stats(self, cutoff_date, verbose, save_metrics):
        """Update MTTR statistics"""
        stats = {}
        
        # Calculate MTTR for different periods
        resolved_alerts = AlertLog.objects.filter(
            is_resolved=True,
            resolved_at__isnull=False,
            resolved_at__gte=cutoff_date
        )
        
        if resolved_alerts.exists():
            # Overall MTTR
            total_time = sum(
                (alert.resolved_at - alert.triggered_at).total_seconds() / 60
                for alert in resolved_alerts
            )
            stats['overall_mttr_minutes'] = total_time / resolved_alerts.count()
            
            # MTTR by severity
            mttr_by_severity = {}
            for severity in ['low', 'medium', 'high', 'critical']:
                severity_alerts = resolved_alerts.filter(rule__severity=severity)
                if severity_alerts.exists():
                    severity_time = sum(
                        (alert.resolved_at - alert.triggered_at).total_seconds() / 60
                        for alert in severity_alerts
                    )
                    mttr_by_severity[severity] = severity_time / severity_alerts.count()
                else:
                    mttr_by_severity[severity] = 0
            
            stats['mttr_by_severity'] = mttr_by_severity
            
            # MTTR trend (last 7 days vs previous 7 days)
            now = timezone.now()
            recent_start = now - timedelta(days=7)
            previous_start = now - timedelta(days=14)
            
            recent_mttr = self._calculate_mttr_for_period(recent_start, now)
            previous_mttr = self._calculate_mttr_for_period(previous_start, recent_start)
            
            stats['recent_mttr'] = recent_mttr
            stats['previous_mttr'] = previous_mttr
            stats['mttr_trend'] = ((recent_mttr - previous_mttr) / previous_mttr * 100) if previous_mttr > 0 else 0
        else:
            stats['overall_mttr_minutes'] = 0
            stats['mttr_by_severity'] = {}
            stats['recent_mttr'] = 0
            stats['previous_mttr'] = 0
            stats['mttr_trend'] = 0
        
        if verbose:
            self.stdout.write(f'    Overall MTTR: {stats["overall_mttr_minutes"]:.1f} minutes')
            self.stdout.write(f'    MTTR trend: {stats["mttr_trend"]:+.1f}%')
        
        return stats
    
    def _update_mttd_stats(self, cutoff_date, verbose, save_metrics):
        """Update MTTD statistics"""
        stats = {}
        
        # Calculate MTTD (Mean Time To Detect)
        # For this example, we'll use triggered_at as detection time
        all_alerts = AlertLog.objects.filter(triggered_at__gte=cutoff_date)
        
        if all_alerts.exists():
            # Overall MTTD (time between first alert and detection)
            # This is a simplified calculation
            stats['overall_mttd_minutes'] = 5.0  # Placeholder
            
            # MTTD by severity
            mttd_by_severity = {}
            for severity in ['low', 'medium', 'high', 'critical']:
                severity_alerts = all_alerts.filter(rule__severity=severity)
                mttd_by_severity[severity] = 5.0  # Placeholder
            
            stats['mttd_by_severity'] = mttd_by_severity
            
            # Detection rate
            total_alerts = all_alerts.count()
            detected_alerts = total_alerts  # All alerts are "detected"
            stats['detection_rate'] = (detected_alerts / total_alerts * 100) if total_alerts > 0 else 0
        else:
            stats['overall_mttd_minutes'] = 0
            stats['mttd_by_severity'] = {}
            stats['detection_rate'] = 0
        
        if verbose:
            self.stdout.write(f'    Overall MTTD: {stats["overall_mttd_minutes"]:.1f} minutes')
            self.stdout.write(f'    Detection rate: {stats["detection_rate"]:.1f}%')
        
        return stats
    
    def _update_sla_stats(self, cutoff_date, verbose, save_metrics):
        """Update SLA statistics"""
        stats = {}
        
        # SLA breaches
        total_breaches = SLABreach.objects.filter(breach_time__gte=cutoff_date).count()
        resolved_breaches = SLABreach.objects.filter(
            breach_time__gte=cutoff_date,
            status='resolved'
        ).count()
        
        stats['total_sla_breaches'] = total_breaches
        stats['resolved_sla_breaches'] = resolved_breaches
        stats['active_sla_breaches'] = total_breaches - resolved_breaches
        
        # SLA compliance rate
        total_alerts = AlertLog.objects.filter(triggered_at__gte=cutoff_date).count()
        if total_alerts > 0:
            stats['sla_compliance_rate'] = ((total_alerts - total_breaches) / total_alerts * 100)
        else:
            stats['sla_compliance_rate'] = 100
        
        # Breaches by severity
        severity_breakdown = SLABreach.objects.filter(
            breach_time__gte=cutoff_date
        ).values('severity').annotate(count=Count('id'))
        stats['breaches_by_severity'] = {item['severity']: item['count'] for item in severity_breakdown}
        
        # Average breach duration
        resolved_breaches_with_time = SLABreach.objects.filter(
            breach_time__gte=cutoff_date,
            status='resolved',
            resolved_at__isnull=False
        )
        
        if resolved_breaches_with_time.exists():
            total_duration = sum(
                (breach.resolved_at - breach.breach_time).total_seconds() / 60
                for breach in resolved_breaches_with_time
            )
            stats['avg_breach_duration_minutes'] = total_duration / resolved_breaches_with_time.count()
        else:
            stats['avg_breach_duration_minutes'] = 0
        
        if verbose:
            self.stdout.write(f'    SLA breaches: {stats["total_sla_breaches"]}')
            self.stdout.write(f'    SLA compliance: {stats["sla_compliance_rate"]:.1f}%')
            self.stdout.write(f'    Avg breach duration: {stats["avg_breach_duration_minutes"]:.1f} min')
        
        return stats
    
    def _calculate_mttr_for_period(self, start_date, end_date):
        """Calculate MTTR for specific period"""
        resolved_alerts = AlertLog.objects.filter(
            is_resolved=True,
            resolved_at__gte=start_date,
            resolved_at__lt=end_date
        )
        
        if resolved_alerts.exists():
            total_time = sum(
                (alert.resolved_at - alert.triggered_at).total_seconds() / 60
                for alert in resolved_alerts
            )
            return total_time / resolved_alerts.count()
        else:
            return 0
    
    def _output_json(self, stats):
        """Output statistics in JSON format"""
        import json
        self.stdout.write(json.dumps(stats, indent=2, default=str))
    
    def _output_text(self, stats, verbose):
        """Output statistics in text format"""
        self.stdout.write(self.style.SUCCESS('=== Alert Statistics Report ==='))
        self.stdout.write(f'Timestamp: {stats["timestamp"]}')
        self.stdout.write(f'Period: Last {stats["period_days"]} days')
        self.stdout.write('')
        
        for key, value in stats.items():
            if key in ['timestamp', 'period_days', 'cutoff_date']:
                continue
            
            if isinstance(value, dict):
                self.stdout.write(self.style.SUCCESS(f'{key.title()}:'))
                for sub_key, sub_value in value.items():
                    self.stdout.write(f'  {sub_key}: {sub_value}')
                self.stdout.write('')
            else:
                self.stdout.write(f'{key}: {value}')
