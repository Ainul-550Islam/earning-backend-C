"""
Enhanced Security Report Export Management Command
Comprehensive security incident and threat intelligence data export
Author: System Security Team
Version: 2.0.0
"""

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.db import transaction
from django.conf import settings
from django.contrib.auth import get_user_model
import logging
import json
import csv
import zipfile
import io
from datetime import datetime, timedelta
from collections import defaultdict

from ...models import (
    SecurityLog, SecurityIncident, UserBan, IPBlacklist, 
    ThreatIntelligence, RiskScore, DeviceInfo, TrustedDevice,
    PasswordHistory, SecurityPolicy, SecurityInsight
)

User = get_user_model()

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Export security incidents and threat intelligence data'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--report-type',
            type=str,
            choices=['incidents', 'threats', 'logs', 'users', 'devices', 'policies', 'comprehensive'],
            default='comprehensive',
            help='Type of security report to export'
        )
        parser.add_argument(
            '--format',
            type=str,
            choices=['json', 'csv', 'excel', 'pdf'],
            default='json',
            help='Export format'
        )
        parser.add_argument(
            '--days',
            type=int,
            default=30,
            help='Number of days to include in report'
        )
        parser.add_argument(
            '--date-from',
            type=str,
            help='Start date (YYYY-MM-DD format)'
        )
        parser.add_argument(
            '--date-to',
            type=str,
            help='End date (YYYY-MM-DD format)'
        )
        parser.add_argument(
            '--severity',
            type=str,
            choices=['low', 'medium', 'high', 'critical', 'all'],
            default='all',
            help='Filter by severity level'
        )
        parser.add_argument(
            '--status',
            type=str,
            choices=['open', 'investigating', 'resolved', 'closed', 'all'],
            default='all',
            help='Filter by incident status'
        )
        parser.add_argument(
            '--user-id',
            type=int,
            help='Export data for specific user ID'
        )
        parser.add_argument(
            '--output-file',
            type=str,
            help='Output file path (if not specified, prints to stdout)'
        )
        parser.add_argument(
            '--include-raw-data',
            action='store_true',
            help='Include raw log data in export'
        )
        parser.add_argument(
            '--compress',
            action='store_true',
            help='Compress output file'
        )
        parser.add_argument(
            '--email-to',
            type=str,
            help='Email report to specified address'
        )
    
    def handle(self, *args, **options):
        """Execute the export command"""
        self.options = options
        self.export_start_time = timezone.now()
        
        try:
            # Parse date range
            date_from, date_to = self._parse_date_range()
            
            self.stdout.write(
                self.style.SUCCESS(
                    f"Starting security report export: {options['report_type']} for period {date_from} to {date_to}"
                )
            )
            
            # Initialize report data
            self.report_data = {
                'export_info': {
                    'report_type': options['report_type'],
                    'format': options['format'],
                    'exported_at': self.export_start_time.isoformat(),
                    'date_range': {
                        'from': date_from.isoformat(),
                        'to': date_to.isoformat()
                    },
                    'filters': {
                        'severity': options['severity'],
                        'status': options['status'],
                        'user_id': options.get('user_id'),
                        'include_raw_data': options['include_raw_data']
                    }
                },
                'summary': {},
                'data': {}
            }
            
            # Generate report based on type
            if options['report_type'] == 'comprehensive':
                self._generate_comprehensive_report(date_from, date_to)
            elif options['report_type'] == 'incidents':
                self._generate_incidents_report(date_from, date_to)
            elif options['report_type'] == 'threats':
                self._generate_threats_report(date_from, date_to)
            elif options['report_type'] == 'logs':
                self._generate_logs_report(date_from, date_to)
            elif options['report_type'] == 'users':
                self._generate_users_report(date_from, date_to)
            elif options['report_type'] == 'devices':
                self._generate_devices_report(date_from, date_to)
            elif options['report_type'] == 'policies':
                self._generate_policies_report(date_from, date_to)
            
            # Generate summary
            self._generate_summary()
            
            # Export data
            self._export_data()
            
            # Send email if requested
            if options['email_to']:
                self._send_email_report()
            
            self.stdout.write(
                self.style.SUCCESS(
                    f"Security report export completed successfully"
                )
            )
            
        except Exception as e:
            logger.error(f"Security report export failed: {str(e)}")
            raise CommandError(f"Security report export failed: {str(e)}")
    
    def _parse_date_range(self):
        """Parse date range from options"""
        if self.options['date_from']:
            date_from = datetime.strptime(self.options['date_from'], '%Y-%m-%d').date()
            date_from = timezone.make_aware(datetime.combine(date_from, datetime.min.time()))
        else:
            date_from = timezone.now() - timedelta(days=self.options['days'])
        
        if self.options['date_to']:
            date_to = datetime.strptime(self.options['date_to'], '%Y-%m-%d').date()
            date_to = timezone.make_aware(datetime.combine(date_to, datetime.max.time().replace(microsecond=0)))
        else:
            date_to = timezone.now()
        
        return date_from, date_to
    
    def _generate_comprehensive_report(self, date_from, date_to):
        """Generate comprehensive security report"""
        self.stdout.write("Generating comprehensive security report...")
        
        # Incidents
        self.report_data['data']['incidents'] = self._get_incidents_data(date_from, date_to)
        
        # Threat Intelligence
        self.report_data['data']['threat_intelligence'] = self._get_threat_intelligence_data(date_from, date_to)
        
        # Security Logs
        self.report_data['data']['security_logs'] = self._get_security_logs_data(date_from, date_to)
        
        # User Security Data
        self.report_data['data']['users'] = self._get_users_security_data(date_from, date_to)
        
        # Device Security Data
        self.report_data['data']['devices'] = self._get_devices_security_data(date_from, date_to)
        
        # Risk Scores
        self.report_data['data']['risk_scores'] = self._get_risk_scores_data(date_from, date_to)
        
        # Security Policies
        self.report_data['data']['policies'] = self._get_policies_data(date_from, date_to)
        
        # IP Blacklist
        self.report_data['data']['blacklist'] = self._get_blacklist_data(date_from, date_to)
        
        # User Bans
        self.report_data['data']['user_bans'] = self._get_user_bans_data(date_from, date_to)
    
    def _generate_incidents_report(self, date_from, date_to):
        """Generate incidents report"""
        self.stdout.write("Generating incidents report...")
        self.report_data['data']['incidents'] = self._get_incidents_data(date_from, date_to)
    
    def _generate_threats_report(self, date_from, date_to):
        """Generate threats report"""
        self.stdout.write("Generating threats report...")
        self.report_data['data']['threat_intelligence'] = self._get_threat_intelligence_data(date_from, date_to)
    
    def _generate_logs_report(self, date_from, date_to):
        """Generate logs report"""
        self.stdout.write("Generating logs report...")
        self.report_data['data']['security_logs'] = self._get_security_logs_data(date_from, date_to)
    
    def _generate_users_report(self, date_from, date_to):
        """Generate users security report"""
        self.stdout.write("Generating users security report...")
        self.report_data['data']['users'] = self._get_users_security_data(date_from, date_to)
    
    def _generate_devices_report(self, date_from, date_to):
        """Generate devices security report"""
        self.stdout.write("Generating devices security report...")
        self.report_data['data']['devices'] = self._get_devices_security_data(date_from, date_to)
    
    def _generate_policies_report(self, date_from, date_to):
        """Generate policies report"""
        self.stdout.write("Generating policies report...")
        self.report_data['data']['policies'] = self._get_policies_data(date_from, date_to)
    
    def _get_incidents_data(self, date_from, date_to):
        """Get incidents data"""
        incidents = SecurityIncident.objects.filter(
            created_at__gte=date_from,
            created_at__lte=date_to
        )
        
        # Apply filters
        if self.options['severity'] != 'all':
            incidents = incidents.filter(severity=self.options['severity'])
        
        if self.options['status'] != 'all':
            incidents = incidents.filter(status=self.options['status'])
        
        if self.options.get('user_id'):
            incidents = incidents.filter(user_id=self.options['user_id'])
        
        incidents_data = []
        for incident in incidents.select_related('user', 'assigned_to').order_by('-created_at'):
            incident_data = {
                'id': str(incident.id),
                'incident_id': incident.incident_id,
                'user': incident.user.username if incident.user else None,
                'assigned_to': incident.assigned_to.username if incident.assigned_to else None,
                'incident_type': incident.incident_type,
                'severity': incident.severity,
                'status': incident.status,
                'title': incident.title,
                'description': incident.description,
                'created_at': incident.created_at.isoformat(),
                'updated_at': incident.updated_at.isoformat(),
                'resolved_at': incident.resolved_at.isoformat() if incident.resolved_at else None,
                'evidence': incident.evidence,
                'metadata': incident.metadata
            }
            
            # Add timeline if available
            if hasattr(incident, 'get_timeline'):
                incident_data['timeline'] = incident.get_timeline()
            
            incidents_data.append(incident_data)
        
        return incidents_data
    
    def _get_threat_intelligence_data(self, date_from, date_to):
        """Get threat intelligence data"""
        threats = ThreatIntelligence.objects.filter(
            created_at__gte=date_from,
            created_at__lte=date_to
        )
        
        threats_data = []
        for threat in threats.order_by('-created_at'):
            threat_data = {
                'id': str(threat.id),
                'threat_type': threat.threat_type,
                'indicator_type': threat.indicator_type,
                'indicators': threat.indicators,
                'severity': threat.severity,
                'confidence': threat.confidence,
                'source': threat.source,
                'description': threat.description,
                'is_active': threat.is_active,
                'created_at': threat.created_at.isoformat(),
                'updated_at': threat.updated_at.isoformat(),
                'expires_at': threat.expires_at.isoformat() if threat.expires_at else None,
                'metadata': threat.metadata
            }
            
            threats_data.append(threat_data)
        
        return threats_data
    
    def _get_security_logs_data(self, date_from, date_to):
        """Get security logs data"""
        logs = SecurityLog.objects.filter(
            created_at__gte=date_from,
            created_at__lte=date_to
        )
        
        # Apply filters
        if self.options['severity'] != 'all':
            logs = logs.filter(severity=self.options['severity'])
        
        if self.options.get('user_id'):
            logs = logs.filter(user_id=self.options['user_id'])
        
        logs_data = []
        for log in logs.select_related('user').order_by('-created_at')[:10000]:  # Limit for performance
            log_data = {
                'id': str(log.id),
                'user': log.user.username if log.user else None,
                'event_type': log.event_type,
                'severity': log.severity,
                'ip_address': log.ip_address,
                'user_agent': log.user_agent,
                'country': log.country,
                'city': log.city,
                'created_at': log.created_at.isoformat(),
                'metadata': log.metadata if self.options['include_raw_data'] else None
            }
            
            # Include request/response data if requested
            if self.options['include_raw_data']:
                log_data['request_data'] = log.request_data
                log_data['response_data'] = log.response_data
            
            logs_data.append(log_data)
        
        return logs_data
    
    def _get_users_security_data(self, date_from, date_to):
        """Get users security data"""
        users_data = {}
        
        # Get users with security activity
        active_users = SecurityLog.objects.filter(
            created_at__gte=date_from,
            created_at__lte=date_to,
            user__isnull=False
        ).values('user_id').distinct()
        
        for user_data in active_users:
            try:
                user = User.objects.get(id=user_data['user_id'])
                
                # Get user's security logs
                user_logs = SecurityLog.objects.filter(
                    user=user,
                    created_at__gte=date_from,
                    created_at__lte=date_to
                )
                
                # Get user's incidents
                user_incidents = SecurityIncident.objects.filter(
                    user=user,
                    created_at__gte=date_from,
                    created_at__lte=date_to
                )
                
                # Get user's risk scores
                user_risk_scores = RiskScore.objects.filter(
                    user=user,
                    created_at__gte=date_from,
                    created_at__lte=date_to
                ).order_by('-created_at')
                
                # Get user's bans
                user_bans = UserBan.objects.filter(
                    user=user,
                    created_at__gte=date_from,
                    created_at__lte=date_to
                )
                
                user_security_data = {
                    'user_id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'is_active': user.is_active,
                    'last_login': user.last_login.isoformat() if user.last_login else None,
                    'security_stats': {
                        'total_logs': user_logs.count(),
                        'failed_logins': user_logs.filter(event_type='login_failure').count(),
                        'successful_logins': user_logs.filter(event_type='login_success').count(),
                        'incidents_count': user_incidents.count(),
                        'bans_count': user_bans.count(),
                        'current_risk_score': user_risk_scores.first().current_score if user_risk_scores.exists() else None
                    },
                    'recent_incidents': [
                        {
                            'id': str(inc.id),
                            'type': inc.incident_type,
                            'severity': inc.severity,
                            'status': inc.status,
                            'created_at': inc.created_at.isoformat()
                        }
                        for inc in user_incidents.order_by('-created_at')[:5]
                    ],
                    'risk_history': [
                        {
                            'score': score.current_score,
                            'risk_factors': score.risk_factors,
                            'created_at': score.created_at.isoformat()
                        }
                        for score in user_risk_scores[:10]
                    ]
                }
                
                users_data[user.username] = user_security_data
                
            except User.DoesNotExist:
                continue
        
        return users_data
    
    def _get_devices_security_data(self, date_from, date_to):
        """Get devices security data"""
        devices_data = {}
        
        # Get devices with activity
        active_devices = DeviceInfo.objects.filter(
            created_at__gte=date_from,
            created_at__lte=date_to
        )
        
        for device in active_devices.select_related('user'):
            # Get device's security logs
            device_logs = SecurityLog.objects.filter(
                ip_address=device.ip_address,
                created_at__gte=date_from,
                created_at__lte=date_to
            )
            
            # Get trusted device info
            try:
                trusted_device = TrustedDevice.objects.get(
                    user=device.user,
                    device_fingerprint=device.device_fingerprint
                )
                is_trusted = trusted_device.is_trusted
                trust_score = trusted_device.trust_score
            except TrustedDevice.DoesNotExist:
                is_trusted = False
                trust_score = 0
            
            device_security_data = {
                'device_id': str(device.id),
                'device_fingerprint': device.device_fingerprint,
                'device_name': device.device_name,
                'device_type': device.device_type,
                'platform': device.platform,
                'browser': device.browser,
                'ip_address': device.ip_address,
                'user': device.user.username if device.user else None,
                'trust_score': device.trust_score,
                'is_trusted': device.is_trusted,
                'security_stats': {
                    'total_logs': device_logs.count(),
                    'unique_users': device_logs.values('user_id').distinct().count(),
                    'failed_attempts': device_logs.filter(event_type='login_failure').count(),
                    'suspicious_events': device_logs.filter(severity__in=['warning', 'error', 'critical', 'security']).count()
                },
                'created_at': device.created_at.isoformat(),
                'last_seen_at': device.last_seen_at.isoformat() if device.last_seen_at else None
            }
            
            devices_data[device.device_fingerprint] = device_security_data
        
        return devices_data
    
    def _get_risk_scores_data(self, date_from, date_to):
        """Get risk scores data"""
        risk_scores = RiskScore.objects.filter(
            created_at__gte=date_from,
            created_at__lte=date_to
        ).select_related('user').order_by('-current_score')
        
        risk_scores_data = []
        for score in risk_scores:
            score_data = {
                'id': str(score.id),
                'user': score.user.username,
                'current_score': score.current_score,
                'risk_level': score.get_risk_level(),
                'risk_factors': score.risk_factors,
                'expires_at': score.expires_at.isoformat() if score.expires_at else None,
                'created_at': score.created_at.isoformat(),
                'updated_at': score.updated_at.isoformat(),
                'metadata': score.metadata
            }
            
            risk_scores_data.append(score_data)
        
        return risk_scores_data
    
    def _get_policies_data(self, date_from, date_to):
        """Get security policies data"""
        policies = SecurityPolicy.objects.filter(
            created_at__gte=date_from,
            created_at__lte=date_to
        ).select_related('user').order_by('-created_at')
        
        policies_data = []
        for policy in policies:
            policy_data = {
                'id': str(policy.id),
                'user': policy.user.username if policy.user else None,
                'policy_key': policy.policy_key,
                'policy_value': policy.policy_value,
                'is_active': policy.is_active,
                'created_at': policy.created_at.isoformat(),
                'updated_at': policy.updated_at.isoformat(),
                'metadata': policy.metadata
            }
            
            policies_data.append(policy_data)
        
        return policies_data
    
    def _get_blacklist_data(self, date_from, date_to):
        """Get IP blacklist data"""
        blacklist = IPBlacklist.objects.filter(
            created_at__gte=date_from,
            created_at__lte=date_to
        ).order_by('-created_at')
        
        blacklist_data = []
        for entry in blacklist:
            entry_data = {
                'id': str(entry.id),
                'ip_address': entry.ip_address,
                'blacklist_type': entry.blacklist_type,
                'reason': entry.reason,
                'confidence': entry.confidence,
                'source': entry.source,
                'is_active': entry.is_active,
                'created_at': entry.created_at.isoformat(),
                'updated_at': entry.updated_at.isoformat(),
                'expires_at': entry.expires_at.isoformat() if entry.expires_at else None,
                'metadata': entry.metadata
            }
            
            blacklist_data.append(entry_data)
        
        return blacklist_data
    
    def _get_user_bans_data(self, date_from, date_to):
        """Get user bans data"""
        bans = UserBan.objects.filter(
            created_at__gte=date_from,
            created_at__lte=date_to
        ).select_related('user', 'created_by').order_by('-created_at')
        
        bans_data = []
        for ban in bans:
            ban_data = {
                'id': str(ban.id),
                'user': ban.user.username,
                'created_by': ban.created_by.username if ban.created_by else None,
                'reason': ban.reason,
                'ban_type': ban.ban_type,
                'is_active': ban.is_active,
                'created_at': ban.created_at.isoformat(),
                'updated_at': ban.updated_at.isoformat(),
                'expires_at': ban.expires_at.isoformat() if ban.expires_at else None,
                'metadata': ban.metadata
            }
            
            bans_data.append(ban_data)
        
        return bans_data
    
    def _generate_summary(self):
        """Generate report summary"""
        summary = {
            'data_counts': {},
            'key_metrics': {},
            'trends': {}
        }
        
        # Count data items
        for data_type, data_items in self.report_data['data'].items():
            if isinstance(data_items, list):
                summary['data_counts'][data_type] = len(data_items)
            elif isinstance(data_items, dict):
                summary['data_counts'][data_type] = len(data_items)
        
        # Key metrics
        if 'incidents' in self.report_data['data']:
            incidents = self.report_data['data']['incidents']
            summary['key_metrics']['incidents'] = {
                'total': len(incidents),
                'by_severity': self._count_by_field(incidents, 'severity'),
                'by_status': self._count_by_field(incidents, 'status'),
                'by_type': self._count_by_field(incidents, 'incident_type')
            }
        
        if 'threat_intelligence' in self.report_data['data']:
            threats = self.report_data['data']['threat_intelligence']
            summary['key_metrics']['threats'] = {
                'total': len(threats),
                'by_type': self._count_by_field(threats, 'threat_type'),
                'by_severity': self._count_by_field(threats, 'severity'),
                'active_count': len([t for t in threats if t['is_active']])
            }
        
        if 'security_logs' in self.report_data['data']:
            logs = self.report_data['data']['security_logs']
            summary['key_metrics']['logs'] = {
                'total': len(logs),
                'by_severity': self._count_by_field(logs, 'severity'),
                'by_event_type': self._count_by_field(logs, 'event_type'),
                'unique_ips': len(set(log['ip_address'] for log in logs if log['ip_address']))
            }
        
        self.report_data['summary'] = summary
    
    def _count_by_field(self, items, field):
        """Count items by field value"""
        counts = defaultdict(int)
        for item in items:
            value = item.get(field, 'unknown')
            counts[value] += 1
        return dict(counts)
    
    def _export_data(self):
        """Export data in specified format"""
        format_type = self.options['format']
        
        if format_type == 'json':
            self._export_json()
        elif format_type == 'csv':
            self._export_csv()
        elif format_type == 'excel':
            self._export_excel()
        elif format_type == 'pdf':
            self._export_pdf()
    
    def _export_json(self):
        """Export data as JSON"""
        json_data = json.dumps(self.report_data, indent=2, default=str)
        
        if self.options['output_file']:
            with open(self.options['output_file'], 'w') as f:
                f.write(json_data)
            self.stdout.write(f"JSON report exported to {self.options['output_file']}")
        else:
            self.stdout.write(json_data)
    
    def _export_csv(self):
        """Export data as CSV"""
        if not self.options['output_file']:
            raise CommandError("Output file required for CSV export")
        
        with open(self.options['output_file'], 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            
            # Write header
            writer.writerow(['Report Type', 'Data Type', 'ID', 'Title/Name', 'Status', 'Created At'])
            
            # Write data
            for data_type, data_items in self.report_data['data'].items():
                if isinstance(data_items, list):
                    for item in data_items:
                        writer.writerow([
                            self.options['report_type'],
                            data_type,
                            item.get('id', ''),
                            item.get('title', item.get('name', item.get('username', ''))),
                            item.get('status', item.get('is_active', '')),
                            item.get('created_at', '')
                        ])
                elif isinstance(data_items, dict):
                    for key, item in data_items.items():
                        writer.writerow([
                            self.options['report_type'],
                            data_type,
                            item.get('id', ''),
                            key,
                            item.get('status', item.get('is_active', '')),
                            item.get('created_at', '')
                        ])
        
        self.stdout.write(f"CSV report exported to {self.options['output_file']}")
    
    def _export_excel(self):
        """Export data as Excel (placeholder - would need openpyxl)"""
        try:
            import openpyxl
            from openpyxl.styles import Font, Alignment
            
            if not self.options['output_file']:
                raise CommandError("Output file required for Excel export")
            
            wb = openpyxl.Workbook()
            
            # Create summary sheet
            summary_sheet = wb.active
            summary_sheet.title = "Summary"
            
            # Write summary data
            row = 1
            summary_sheet.cell(row=row, column=1, value="Security Report Summary").font = Font(bold=True)
            row += 2
            
            for key, value in self.report_data['summary'].items():
                summary_sheet.cell(row=row, column=1, value=str(key)).font = Font(bold=True)
                row += 1
                
                if isinstance(value, dict):
                    for sub_key, sub_value in value.items():
                        summary_sheet.cell(row=row, column=2, value=str(sub_key))
                        summary_sheet.cell(row=row, column=3, value=str(sub_value))
                        row += 1
                else:
                    summary_sheet.cell(row=row, column=2, value=str(value))
                    row += 1
                row += 1
            
            # Create data sheets
            for data_type, data_items in self.report_data['data'].items():
                if not data_items:
                    continue
                
                sheet = wb.create_sheet(title=data_type.capitalize())
                row = 1
                
                # Write headers based on first item
                if isinstance(data_items, list) and data_items:
                    headers = list(data_items[0].keys())
                    for col, header in enumerate(headers, 1):
                        sheet.cell(row=row, column=col, value=header).font = Font(bold=True)
                    row += 1
                    
                    # Write data
                    for item in data_items:
                        for col, header in enumerate(headers, 1):
                            value = item.get(header, '')
                            if isinstance(value, (dict, list)):
                                value = json.dumps(value, default=str)
                            sheet.cell(row=row, column=col, value=str(value))
                        row += 1
            
            # Save workbook
            wb.save(self.options['output_file'])
            self.stdout.write(f"Excel report exported to {self.options['output_file']}")
            
        except ImportError:
            raise CommandError("openpyxl is required for Excel export")
    
    def _export_pdf(self):
        """Export data as PDF (placeholder - would need reportlab)"""
        try:
            from reportlab.lib.pagesizes import letter, A4
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.lib.units import inch
            import io
            
            if not self.options['output_file']:
                raise CommandError("Output file required for PDF export")
            
            # Create PDF document
            doc = SimpleDocTemplate(self.options['output_file'], pagesize=A4)
            styles = getSampleStyleSheet()
            story = []
            
            # Title
            title = Paragraph(f"Security Report - {self.options['report_type'].title()}", styles['Title'])
            story.append(title)
            story.append(Spacer(1, 12))
            
            # Summary
            summary_text = f"""
            Report Type: {self.options['report_type']}
            Export Date: {self.export_start_time.strftime('%Y-%m-%d %H:%M:%S')}
            Date Range: {self.report_data['export_info']['date_range']['from']} to {self.report_data['export_info']['date_range']['to']}
            """
            
            summary_para = Paragraph(summary_text, styles['Normal'])
            story.append(summary_para)
            story.append(Spacer(1, 12))
            
            # Data summary table
            if self.report_data['summary']['data_counts']:
                data = [['Data Type', 'Count']]
                for data_type, count in self.report_data['summary']['data_counts'].items():
                    data.append([data_type.title(), str(count)])
                
                table = Table(data)
                table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 14),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black)
                ]))
                
                story.append(table)
            
            # Build PDF
            doc.build(story)
            self.stdout.write(f"PDF report exported to {self.options['output_file']}")
            
        except ImportError:
            raise CommandError("reportlab is required for PDF export")
    
    def _send_email_report(self):
        """Send report via email"""
        try:
            from django.core.mail import EmailMessage
            from django.core.mail import get_connection
            
            # Create email
            subject = f"Security Report - {self.options['report_type'].title()}"
            
            body = f"""
            Security Report Export
            
            Report Type: {self.options['report_type']}
            Format: {self.options['format']}
            Export Date: {self.export_start_time.strftime('%Y-%m-%d %H:%M:%S')}
            
            Please find the detailed report attached.
            """
            
            email = EmailMessage(
                subject=subject,
                body=body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[self.options['email_to']]
            )
            
            # Attach report file if specified
            if self.options['output_file']:
                email.attach_file(self.options['output_file'])
            
            # Send email
            email.send()
            
            self.stdout.write(f"Report sent to {self.options['email_to']}")
            
        except Exception as e:
            logger.error(f"Failed to send email report: {str(e)}")
            raise CommandError(f"Failed to send email report: {str(e)}")


# Import required modules for the command
from django.db.models import Count, Avg, Max
from openpyxl import styles
from openpyxl.styles import colors
from reportlab.lib import colors
# DeviceInfo stub — replace with real import if available
try:
    from api.security.models import DeviceInfo
except ImportError:
    class DeviceInfo:
        pass

