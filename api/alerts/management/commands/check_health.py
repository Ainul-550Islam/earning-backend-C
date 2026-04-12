"""
Django Management Command: Check System Health
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
import logging

from alerts.models.core import AlertRule, AlertLog, SystemMetrics
from alerts.models.channel import AlertChannel, ChannelHealthLog
from alerts.models.incident import Incident
from alerts.tasks.core import check_system_health

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Check system health and generate health report'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--hours',
            type=int,
            default=24,
            help='Check health for last N hours (default: 24)'
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed health information'
        )
        parser.add_argument(
            '--alerts-only',
            action='store_true',
            help='Check only alert system health'
        )
        parser.add_argument(
            '--channels-only',
            action='store_true',
            help='Check only channel health'
        )
        parser.add_argument(
            '--incidents-only',
            action='store_true',
            help='Check only incident system health'
        )
        parser.add_argument(
            '--output-format',
            type=str,
            choices=['text', 'json', 'csv'],
            default='text',
            help='Output format (default: text)'
        )
        parser.add_argument(
            '--threshold',
            type=float,
            default=0.8,
            help='Health threshold (0.0-1.0, default: 0.8)'
        )
        parser.add_argument(
            '--save-results',
            action='store_true',
            help='Save health check results to database'
        )
    
    def handle(self, *args, **options):
        hours = options['hours']
        verbose = options['verbose']
        alerts_only = options['alerts_only']
        channels_only = options['channels_only']
        incidents_only = options['incidents_only']
        output_format = options['output_format']
        threshold = options['threshold']
        save_results = options['save_results']
        
        self.stdout.write(self.style.SUCCESS(f'Checking system health for last {hours} hours'))
        
        # Determine what to check
        check_alerts = not channels_only and not incidents_only
        check_channels = not alerts_only and not incidents_only
        check_incidents = not alerts_only and not channels_only
        
        cutoff_time = timezone.now() - timedelta(hours=hours)
        
        # Collect health data
        health_data = {
            'timestamp': timezone.now(),
            'period_hours': hours,
            'threshold': threshold
        }
        
        if check_alerts:
            health_data['alerts'] = self._check_alerts_health(cutoff_time, verbose, threshold)
        
        if check_channels:
            health_data['channels'] = self._check_channels_health(cutoff_time, verbose, threshold)
        
        if check_incidents:
            health_data['incidents'] = self._check_incidents_health(cutoff_time, verbose, threshold)
        
        # Calculate overall health
        health_data['overall_health'] = self._calculate_overall_health(health_data)
        
        # Output results
        if output_format == 'json':
            self._output_json(health_data)
        elif output_format == 'csv':
            self._output_csv(health_data)
        else:
            self._output_text(health_data, verbose)
        
        # Save results if requested
        if save_results:
            self._save_results(health_data)
        
        # Trigger Celery task for continuous monitoring
        check_system_health.delay()
        
        # Summary
        overall_health = health_data['overall_health']
        if overall_health >= threshold:
            self.stdout.write(self.style.SUCCESS(f'System health: GOOD ({overall_health:.2%})'))
        else:
            self.stdout.write(self.style.WARNING(f'System health: POOR ({overall_health:.2%})'))
    
    def _check_alerts_health(self, cutoff_time, verbose, threshold):
        """Check alert system health"""
        alerts_data = {}
        
        # Alert rules health
        total_rules = AlertRule.objects.count()
        active_rules = AlertRule.objects.filter(is_active=True).count()
        alerts_data['rules'] = {
            'total': total_rules,
            'active': active_rules,
            'active_percentage': (active_rules / total_rules * 100) if total_rules > 0 else 0
        }
        
        # Alert logs health
        total_alerts = AlertLog.objects.filter(triggered_at__gte=cutoff_time).count()
        resolved_alerts = AlertLog.objects.filter(
            triggered_at__gte=cutoff_time,
            is_resolved=True
        ).count()
        alerts_data['logs'] = {
            'total': total_alerts,
            'resolved': resolved_alerts,
            'resolution_rate': (resolved_alerts / total_alerts * 100) if total_alerts > 0 else 0
        }
        
        # Alert severity breakdown
        severity_breakdown = AlertLog.objects.filter(
            triggered_at__gte=cutoff_time
        ).values('rule__severity').annotate(count=models.Count('id'))
        
        alerts_data['severity'] = {}
        for item in severity_breakdown:
            alerts_data['severity'][item['rule__severity']] = item['count']
        
        # Alert trends
        hourly_trends = AlertLog.objects.filter(
            triggered_at__gte=cutoff_time
        ).extra(
            {'hour': "strftime('%%Y-%%m-%%d %%H:00:00', triggered_at)"}
        ).values('hour').annotate(count=models.Count('id')).order_by('hour')
        
        alerts_data['trends'] = list(hourly_trends)
        
        # Calculate alerts health score
        alerts_health = self._calculate_alerts_health_score(alerts_data, threshold)
        alerts_data['health_score'] = alerts_health
        
        if verbose:
            self.stdout.write(f'  Alert Rules: {active_rules}/{total_rules} active ({alerts_data["rules"]["active_percentage"]:.1f}%)')
            self.stdout.write(f'  Alert Resolution Rate: {alerts_data["logs"]["resolution_rate"]:.1f}%')
            self.stdout.write(f'  Alerts Health Score: {alerts_health:.2%}')
        
        return alerts_data
    
    def _check_channels_health(self, cutoff_time, verbose, threshold):
        """Check channel system health"""
        channels_data = {}
        
        # Channel status
        total_channels = AlertChannel.objects.count()
        active_channels = AlertChannel.objects.filter(is_enabled=True).count()
        healthy_channels = AlertChannel.objects.filter(status='active').count()
        
        channels_data['status'] = {
            'total': total_channels,
            'active': active_channels,
            'healthy': healthy_channels,
            'health_percentage': (healthy_channels / total_channels * 100) if total_channels > 0 else 0
        }
        
        # Recent health checks
        recent_health_checks = ChannelHealthLog.objects.filter(
            checked_at__gte=cutoff_time
        ).count()
        
        channels_data['health_checks'] = {
            'total': recent_health_checks,
            'healthy': ChannelHealthLog.objects.filter(
                checked_at__gte=cutoff_time,
                status='healthy'
            ).count(),
            'warning': ChannelHealthLog.objects.filter(
                checked_at__gte=cutoff_time,
                status='warning'
            ).count(),
            'critical': ChannelHealthLog.objects.filter(
                checked_at__gte=cutoff_time,
                status='critical'
            ).count()
        }
        
        # Channel types breakdown
        channel_types = AlertChannel.objects.values('channel_type').annotate(count=models.Count('id'))
        channels_data['types'] = {}
        for item in channel_types:
            channels_data['types'][item['channel_type']] = item['count']
        
        # Calculate channels health score
        channels_health = self._calculate_channels_health_score(channels_data, threshold)
        channels_data['health_score'] = channels_health
        
        if verbose:
            self.stdout.write(f'  Channels: {healthy_channels}/{total_channels} healthy ({channels_data["status"]["health_percentage"]:.1f}%)')
            self.stdout.write(f'  Health Checks: {channels_data["health_checks"]["total"]} checks')
            self.stdout.write(f'  Channels Health Score: {channels_health:.2%}')
        
        return channels_data
    
    def _check_incidents_health(self, cutoff_time, verbose, threshold):
        """Check incident system health"""
        incidents_data = {}
        
        # Incident status
        total_incidents = Incident.objects.filter(detected_at__gte=cutoff_time).count()
        resolved_incidents = Incident.objects.filter(
            detected_at__gte=cutoff_time,
            status='resolved'
        ).count()
        active_incidents = Incident.objects.filter(
            detected_at__gte=cutoff_time,
            status__in=['open', 'investigating', 'identified', 'monitoring']
        ).count()
        
        incidents_data['status'] = {
            'total': total_incidents,
            'resolved': resolved_incidents,
            'active': active_incidents,
            'resolution_rate': (resolved_incidents / total_incidents * 100) if total_incidents > 0 else 0
        }
        
        # Incident severity breakdown
        severity_breakdown = Incident.objects.filter(
            detected_at__gte=cutoff_time
        ).values('severity').annotate(count=models.Count('id'))
        
        incidents_data['severity'] = {}
        for item in severity_breakdown:
            incidents_data['severity'][item['severity']] = item['count']
        
        # Average resolution time
        resolved_incidents_with_time = Incident.objects.filter(
            detected_at__gte=cutoff_time,
            status='resolved',
            resolved_at__isnull=False
        )
        
        if resolved_incidents_with_time.exists():
            total_resolution_time = sum(
                (incident.resolved_at - incident.detected_at).total_seconds() / 60
                for incident in resolved_incidents_with_time
            )
            avg_resolution_time = total_resolution_time / resolved_incidents_with_time.count()
            incidents_data['avg_resolution_time'] = avg_resolution_time
        else:
            incidents_data['avg_resolution_time'] = 0
        
        # Calculate incidents health score
        incidents_health = self._calculate_incidents_health_score(incidents_data, threshold)
        incidents_data['health_score'] = incidents_health
        
        if verbose:
            self.stdout.write(f'  Incidents: {resolved_incidents}/{total_incidents} resolved ({incidents_data["status"]["resolution_rate"]:.1f}%)')
            self.stdout.write(f'  Active Incidents: {active_incidents}')
            self.stdout.write(f'  Avg Resolution Time: {incidents_data["avg_resolution_time"]:.1f} minutes')
            self.stdout.write(f'  Incidents Health Score: {incidents_health:.2%}')
        
        return incidents_data
    
    def _calculate_overall_health(self, health_data):
        """Calculate overall system health"""
        scores = []
        
        if 'alerts' in health_data:
            scores.append(health_data['alerts']['health_score'])
        
        if 'channels' in health_data:
            scores.append(health_data['channels']['health_score'])
        
        if 'incidents' in health_data:
            scores.append(health_data['incidents']['health_score'])
        
        return sum(scores) / len(scores) if scores else 0
    
    def _calculate_alerts_health_score(self, alerts_data, threshold):
        """Calculate alerts health score"""
        scores = [
            alerts_data['rules']['active_percentage'] / 100,
            alerts_data['logs']['resolution_rate'] / 100
        ]
        return sum(scores) / len(scores)
    
    def _calculate_channels_health_score(self, channels_data, threshold):
        """Calculate channels health score"""
        return channels_data['status']['health_percentage'] / 100
    
    def _calculate_incidents_health_score(self, incidents_data, threshold):
        """Calculate incidents health score"""
        return incidents_data['status']['resolution_rate'] / 100
    
    def _output_text(self, health_data, verbose):
        """Output health data in text format"""
        self.stdout.write(self.style.SUCCESS('=== System Health Report ==='))
        self.stdout.write(f'Timestamp: {health_data["timestamp"]}')
        self.stdout.write(f'Period: Last {health_data["period_hours"]} hours')
        self.stdout.write(f'Overall Health: {health_data["overall_health"]:.2%}')
        self.stdout.write(f'Health Threshold: {health_data["threshold"]}')
        self.stdout.write('')
        
        if 'alerts' in health_data:
            self.stdout.write(self.style.SUCCESS('Alerts System:'))
            alerts = health_data['alerts']
            self.stdout.write(f'  Rules: {alerts["rules"]["active"]}/{alerts["rules"]["total"]} active')
            self.stdout.write(f'  Resolution Rate: {alerts["logs"]["resolution_rate"]:.1f}%')
            self.stdout.write(f'  Health Score: {alerts["health_score"]:.2%}')
            self.stdout.write('')
        
        if 'channels' in health_data:
            self.stdout.write(self.style.SUCCESS('Channels System:'))
            channels = health_data['channels']
            self.stdout.write(f'  Channels: {channels["status"]["healthy"]}/{channels["status"]["total"]} healthy')
            self.stdout.write(f'  Health Score: {channels["health_score"]:.2%}')
            self.stdout.write('')
        
        if 'incidents' in health_data:
            self.stdout.write(self.style.SUCCESS('Incidents System:'))
            incidents = health_data['incidents']
            self.stdout.write(f'  Resolution Rate: {incidents["status"]["resolution_rate"]:.1f}%')
            self.stdout.write(f'  Avg Resolution Time: {incidents["avg_resolution_time"]:.1f} minutes')
            self.stdout.write(f'  Health Score: {incidents["health_score"]:.2%}')
            self.stdout.write('')
    
    def _output_json(self, health_data):
        """Output health data in JSON format"""
        import json
        self.stdout.write(json.dumps(health_data, indent=2, default=str))
    
    def _output_csv(self, health_data):
        """Output health data in CSV format"""
        import csv
        import io
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow(['Metric', 'Value'])
        
        # Write data
        writer.writerow(['Timestamp', health_data['timestamp']])
        writer.writerow(['Overall Health', f"{health_data['overall_health']:.2%}"])
        
        if 'alerts' in health_data:
            alerts = health_data['alerts']
            writer.writerow(['Alerts Health Score', f"{alerts['health_score']:.2%}"])
            writer.writerow(['Active Rules', f"{alerts['rules']['active']}/{alerts['rules']['total']}"])
            writer.writerow(['Alert Resolution Rate', f"{alerts['logs']['resolution_rate']:.1f}%"])
        
        if 'channels' in health_data:
            channels = health_data['channels']
            writer.writerow(['Channels Health Score', f"{channels['health_score']:.2%}"])
            writer.writerow(['Healthy Channels', f"{channels['status']['healthy']}/{channels['status']['total']}"])
        
        if 'incidents' in health_data:
            incidents = health_data['incidents']
            writer.writerow(['Incidents Health Score', f"{incidents['health_score']:.2%}"])
            writer.writerow(['Incident Resolution Rate', f"{incidents['status']['resolution_rate']:.1f}%"])
            writer.writerow(['Avg Resolution Time', f"{incidents['avg_resolution_time']:.1f}"])
        
        self.stdout.write(output.getvalue())
    
    def _save_results(self, health_data):
        """Save health check results to database"""
        try:
            from alerts.models.core import SystemHealthCheck
            
            health_check = SystemHealthCheck.objects.create(
                check_name='Management Command Health Check',
                check_type='comprehensive',
                status='healthy' if health_data['overall_health'] >= health_data['threshold'] else 'warning',
                response_time_ms=0,
                status_message=f'Overall health: {health_data["overall_health"]:.2%}',
                details=health_data
            )
            
            self.stdout.write(f'Health check results saved to database (ID: {health_check.id})')
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Failed to save health check results: {str(e)}'))
