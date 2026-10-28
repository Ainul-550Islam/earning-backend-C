"""
Enhanced Security Scan Management Command
Comprehensive security audit using FraudDetectionEngine and VPNDetector
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
import time
from datetime import datetime, timedelta

from ...vpn_detector import VPNDetector, VPNServiceError
from ...services.ThreatIntelService import ThreatIntelService
from ...services.IncidentService import IncidentService
from ...models import (
    SecurityLog, SecurityIncident, UserBan, IPBlacklist, 
    ThreatIntelligence, RiskScore, DeviceInfo, TrustedDevice
)

User = get_user_model()

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Run comprehensive security scan using FraudDetectionEngine and VPNDetector'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--scan-type',
            type=str,
            choices=['full', 'vpn', 'threat', 'risk', 'users', 'devices'],
            default='full',
            help='Type of security scan to perform'
        )
        parser.add_argument(
            '--user-id',
            type=int,
            help='Specific user ID to scan (for user-specific scans)'
        )
        parser.add_argument(
            '--ip-range',
            type=str,
            help='IP range to scan (format: 192.168.1.0/24)'
        )
        parser.add_argument(
            '--days',
            type=int,
            default=7,
            help='Number of days to look back for security events'
        )
        parser.add_argument(
            '--create-incidents',
            action='store_true',
            help='Create security incidents for detected threats'
        )
        parser.add_argument(
            '--auto-block',
            action='store_true',
            help='Automatically block high-risk IPs and users'
        )
        parser.add_argument(
            '--output-format',
            type=str,
            choices=['json', 'text', 'csv'],
            default='text',
            help='Output format for scan results'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Perform scan without taking any actions'
        )
    
    def handle(self, *args, **options):
        """Execute the security scan command"""
        self.scan_start_time = timezone.now()
        self.options = options
        self.results = {
            'scan_info': {
                'scan_type': options['scan_type'],
                'started_at': self.scan_start_time.isoformat(),
                'options': options
            },
            'findings': [],
            'incidents_created': [],
            'actions_taken': [],
            'statistics': {}
        }
        
        try:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Starting security scan: {options['scan_type']} at {self.scan_start_time}"
                )
            )
            
            # Initialize services
            self.vpn_detector = VPNDetector()
            self.threat_service = ThreatIntelService()
            self.incident_service = IncidentService()
            
            # Execute scan based on type
            if options['scan_type'] == 'full':
                self._run_full_scan()
            elif options['scan_type'] == 'vpn':
                self._run_vpn_scan()
            elif options['scan_type'] == 'threat':
                self._run_threat_scan()
            elif options['scan_type'] == 'risk':
                self._run_risk_scan()
            elif options['scan_type'] == 'users':
                self._run_user_scan()
            elif options['scan_type'] == 'devices':
                self._run_device_scan()
            
            # Calculate statistics
            self._calculate_statistics()
            
            # Output results
            self._output_results()
            
            # Send summary
            self._send_summary_notification()
            
        except Exception as e:
            logger.error(f"Security scan failed: {str(e)}")
            raise CommandError(f"Security scan failed: {str(e)}")
    
    def _run_full_scan(self):
        """Run comprehensive security scan"""
        self.stdout.write("Running full security scan...")
        
        # VPN/Proxy Detection
        self._run_vpn_scan()
        
        # Threat Intelligence
        self._run_threat_scan()
        
        # Risk Assessment
        self._run_risk_scan()
        
        # User Security Analysis
        self._run_user_scan()
        
        # Device Security Analysis
        self._run_device_scan()
        
        # Account Security Analysis
        self._run_account_security_scan()
        
        # Network Security Analysis
        self._run_network_security_scan()
    
    def _run_vpn_scan(self):
        """Run VPN/Proxy detection scan"""
        self.stdout.write("Scanning for VPN/Proxy usage...")
        
        try:
            # Get recent security logs with IP addresses
            cutoff_date = timezone.now() - timedelta(days=self.options['days'])
            security_logs = SecurityLog.objects.filter(
                created_at__gte=cutoff_date,
                ip_address__isnull=False
            ).distinct('ip_address')
            
            vpn_findings = []
            proxy_findings = []
            
            for log in security_logs:
                if not log.ip_address:
                    continue
                
                try:
                    # Check for VPN/Proxy
                    vpn_result = self.vpn_detector.is_vpn(
                        log.ip_address,
                        include_details=True
                    )
                    
                    if vpn_result.get('is_vpn'):
                        vpn_findings.append({
                            'ip_address': log.ip_address,
                            'user': log.user.username if log.user else 'Anonymous',
                            'vpn_type': vpn_result.get('vpn_type', 'unknown'),
                            'confidence': vpn_result.get('confidence', 0),
                            'details': vpn_result.get('details', {}),
                            'detected_at': timezone.now().isoformat()
                        })
                    
                    if vpn_result.get('is_proxy'):
                        proxy_findings.append({
                            'ip_address': log.ip_address,
                            'user': log.user.username if log.user else 'Anonymous',
                            'proxy_type': vpn_result.get('proxy_type', 'unknown'),
                            'confidence': vpn_result.get('confidence', 0),
                            'details': vpn_result.get('details', {}),
                            'detected_at': timezone.now().isoformat()
                        })
                        
                except VPNServiceError as e:
                    logger.warning(f"VPN detection failed for IP {log.ip_address}: {str(e)}")
                    continue
            
            # Store findings
            self.results['findings'].append({
                'scan_type': 'vpn_detection',
                'title': 'VPN/Proxy Detection Results',
                'vpn_findings': vpn_findings,
                'proxy_findings': proxy_findings,
                'total_vpn_detections': len(vpn_findings),
                'total_proxy_detections': len(proxy_findings)
            })
            
            # Create incidents if requested
            if self.options['create_incidents']:
                self._create_vpn_incidents(vpn_findings, proxy_findings)
            
            # Auto-block if requested
            if self.options['auto_block'] and not self.options['dry_run']:
                self._auto_block_vpn_ips(vpn_findings, proxy_findings)
            
            self.stdout.write(
                self.style.SUCCESS(
                    f"VPN scan completed: {len(vpn_findings)} VPNs, {len(proxy_findings)} proxies detected"
                )
            )
            
        except Exception as e:
            logger.error(f"VPN scan failed: {str(e)}")
            self.results['findings'].append({
                'scan_type': 'vpn_detection',
                'error': str(e),
                'status': 'failed'
            })
    
    def _run_threat_scan(self):
        """Run threat intelligence scan"""
        self.stdout.write("Scanning for threat intelligence...")
        
        try:
            # Get recent security events
            cutoff_date = timezone.now() - timedelta(days=self.options['days'])
            recent_events = SecurityLog.objects.filter(
                created_at__gte=cutoff_date,
                severity__in=['warning', 'error', 'critical', 'security']
            )
            
            threat_findings = []
            
            # Analyze IP addresses for threats
            unique_ips = recent_events.values_list('ip_address', flat=True).distinct()
            
            for ip in unique_ips:
                if not ip:
                    continue
                
                try:
                    threat_result = self.threat_service.check_ip_reputation(ip)
                    
                    if threat_result.get('risk_score', 0) > 50:  # High risk threshold
                        threat_findings.append({
                            'ip_address': ip,
                            'risk_score': threat_result.get('risk_score', 0),
                            'is_blacklisted': threat_result.get('is_blacklisted', False),
                            'threat_types': threat_result.get('threat_types', []),
                            'sources': threat_result.get('sources', []),
                            'confidence': threat_result.get('confidence', 0),
                            'detected_at': timezone.now().isoformat()
                        })
                        
                except Exception as e:
                    logger.warning(f"Threat check failed for IP {ip}: {str(e)}")
                    continue
            
            # Check for existing threat intelligence matches
            active_threats = ThreatIntelligence.objects.filter(
                is_active=True,
                expires_at__gt=timezone.now()
            )
            
            threat_matches = []
            for threat in active_threats:
                matching_events = recent_events.filter(
                    ip_address__in=threat.indicators
                ).count()
                
                if matching_events > 0:
                    threat_matches.append({
                        'threat_id': str(threat.id),
                        'threat_type': threat.threat_type,
                        'severity': threat.severity,
                        'confidence': threat.confidence,
                        'matching_events': matching_events,
                        'indicators': threat.indicators,
                        'detected_at': timezone.now().isoformat()
                    })
            
            # Store findings
            self.results['findings'].append({
                'scan_type': 'threat_intelligence',
                'title': 'Threat Intelligence Results',
                'high_risk_ips': threat_findings,
                'threat_matches': threat_matches,
                'total_high_risk_ips': len(threat_findings),
                'total_threat_matches': len(threat_matches)
            })
            
            # Create incidents if requested
            if self.options['create_incidents']:
                self._create_threat_incidents(threat_findings, threat_matches)
            
            self.stdout.write(
                self.style.SUCCESS(
                    f"Threat scan completed: {len(threat_findings)} high-risk IPs, {len(threat_matches)} threat matches"
                )
            )
            
        except Exception as e:
            logger.error(f"Threat scan failed: {str(e)}")
            self.results['findings'].append({
                'scan_type': 'threat_intelligence',
                'error': str(e),
                'status': 'failed'
            })
    
    def _run_risk_scan(self):
        """Run risk assessment scan"""
        self.stdout.write("Running risk assessment scan...")
        
        try:
            cutoff_date = timezone.now() - timedelta(days=self.options['days'])
            
            # Get risk scores
            risk_scores = RiskScore.objects.filter(
                created_at__gte=cutoff_date
            ).order_by('-current_score')
            
            high_risk_users = []
            medium_risk_users = []
            
            for risk_score in risk_scores:
                user_data = {
                    'user_id': risk_score.user.id,
                    'username': risk_score.user.username,
                    'current_score': risk_score.current_score,
                    'risk_level': risk_score.get_risk_level(),
                    'risk_factors': risk_score.risk_factors,
                    'expires_at': risk_score.expires_at.isoformat() if risk_score.expires_at else None
                }
                
                if risk_score.current_score >= 70:
                    high_risk_users.append(user_data)
                elif risk_score.current_score >= 40:
                    medium_risk_users.append(user_data)
            
            # Analyze risk trends
            recent_scores = RiskScore.objects.filter(
                created_at__gte=cutoff_date
            ).values('user_id').annotate(
                avg_score=models.Avg('current_score'),
                max_score=models.Max('current_score'),
                score_count=models.Count('id')
            ).order_by('-avg_score')
            
            risk_trends = []
            for trend in recent_scores:
                user = User.objects.get(id=trend['user_id'])
                risk_trends.append({
                    'user_id': trend['user_id'],
                    'username': user.username,
                    'avg_score': trend['avg_score'],
                    'max_score': trend['max_score'],
                    'score_count': trend['score_count']
                })
            
            # Store findings
            self.results['findings'].append({
                'scan_type': 'risk_assessment',
                'title': 'Risk Assessment Results',
                'high_risk_users': high_risk_users,
                'medium_risk_users': medium_risk_users,
                'risk_trends': risk_trends,
                'total_high_risk': len(high_risk_users),
                'total_medium_risk': len(medium_risk_users)
            })
            
            # Create incidents for high-risk users if requested
            if self.options['create_incidents']:
                self._create_risk_incidents(high_risk_users)
            
            self.stdout.write(
                self.style.SUCCESS(
                    f"Risk scan completed: {len(high_risk_users)} high-risk, {len(medium_risk_users)} medium-risk users"
                )
            )
            
        except Exception as e:
            logger.error(f"Risk scan failed: {str(e)}")
            self.results['findings'].append({
                'scan_type': 'risk_assessment',
                'error': str(e),
                'status': 'failed'
            })
    
    def _run_user_scan(self):
        """Run user security scan"""
        self.stdout.write("Running user security scan...")
        
        try:
            cutoff_date = timezone.now() - timedelta(days=self.options['days'])
            
            # Get suspicious user activities
            suspicious_users = []
            
            # Check for failed login attempts
            users_with_failures = SecurityLog.objects.filter(
                created_at__gte=cutoff_date,
                security_type='login_failure'
            ).values('user_id').annotate(
                failure_count=models.Count('id')
            ).filter(failure_count__gte=5)
            
            for user_data in users_with_failures:
                user = User.objects.get(id=user_data['user_id'])
                suspicious_users.append({
                    'user_id': user.id,
                    'username': user.username,
                    'issue_type': 'multiple_login_failures',
                    'failure_count': user_data['failure_count'],
                    'last_activity': SecurityLog.objects.filter(
                        user=user
                    ).order_by('-created_at').first().created_at.isoformat()
                })
            
            # Check for unusual login locations
            user_login_locations = SecurityLog.objects.filter(
                created_at__gte=cutoff_date,
                security_type='login_success',
                country__isnull=False
            ).values('user_id', 'country').annotate(
                location_count=models.Count('country')
            ).filter(location_count__gte=3)
            
            for location_data in user_login_locations:
                user = User.objects.get(id=location_data['user_id'])
                suspicious_users.append({
                    'user_id': user.id,
                    'username': user.username,
                    'issue_type': 'multiple_login_locations',
                    'location_count': location_data['location_count'],
                    'last_activity': SecurityLog.objects.filter(
                        user=user
                    ).order_by('-created_at').first().created_at.isoformat()
                })
            
            # Check for banned users
            banned_users = UserBan.objects.filter(
                is_active=True,
                created_at__gte=cutoff_date
            ).select_related('user')
            
            for ban in banned_users:
                suspicious_users.append({
                    'user_id': ban.user.id,
                    'username': ban.user.username,
                    'issue_type': 'user_banned',
                    'ban_reason': ban.reason,
                    'ban_type': ban.ban_type,
                    'banned_at': ban.created_at.isoformat()
                })
            
            # Store findings
            self.results['findings'].append({
                'scan_type': 'user_security',
                'title': 'User Security Analysis',
                'suspicious_users': suspicious_users,
                'total_suspicious_users': len(suspicious_users)
            })
            
            # Create incidents if requested
            if self.options['create_incidents']:
                self._create_user_incidents(suspicious_users)
            
            self.stdout.write(
                self.style.SUCCESS(
                    f"User scan completed: {len(suspicious_users)} suspicious users detected"
                )
            )
            
        except Exception as e:
            logger.error(f"User scan failed: {str(e)}")
            self.results['findings'].append({
                'scan_type': 'user_security',
                'error': str(e),
                'status': 'failed'
            })
    
    def _run_device_scan(self):
        """Run device security scan"""
        self.stdout.write("Running device security scan...")
        
        try:
            cutoff_date = timezone.now() - timedelta(days=self.options['days'])
            
            # Get suspicious device activities
            suspicious_devices = []
            
            # Check for devices with multiple users
            devices_with_multiple_users = DeviceInfo.objects.filter(
                created_at__gte=cutoff_date
            ).values('device_fingerprint').annotate(
                user_count=models.Count('user_id', distinct=True)
            ).filter(user_count__gte=3)
            
            for device_data in devices_with_multiple_users:
                devices = DeviceInfo.objects.filter(
                    device_fingerprint=device_data['device_fingerprint']
                )
                suspicious_devices.append({
                    'device_fingerprint': device_data['device_fingerprint'],
                    'issue_type': 'multiple_users',
                    'user_count': device_data['user_count'],
                    'device_names': list(devices.values_list('device_name', flat=True).distinct()),
                    'last_seen': devices.order_by('-last_seen_at').first().last_seen_at.isoformat()
                })
            
            # Check for untrusted devices with high activity
            untrusted_devices = DeviceInfo.objects.filter(
                is_trusted=False,
                created_at__gte=cutoff_date
            ).annotate(
                activity_count=models.Count('securitylog')
            ).filter(activity_count__gte=10)
            
            for device in untrusted_devices:
                suspicious_devices.append({
                    'device_id': str(device.id),
                    'device_fingerprint': device.device_fingerprint,
                    'issue_type': 'untrusted_high_activity',
                    'activity_count': device.activity_count,
                    'user': device.user.username if device.user else 'Anonymous',
                    'trust_score': device.trust_score
                })
            
            # Check for trusted devices with suspicious activity
            trusted_devices = TrustedDevice.objects.filter(
                is_trusted=True,
                created_at__gte=cutoff_date
            )
            
            for device in trusted_devices:
                # Check for unusual login times or locations
                recent_logs = SecurityLog.objects.filter(
                    user=device.user,
                    created_at__gte=cutoff_date
                )
                
                if recent_logs.count() > 50:  # High activity threshold
                    suspicious_devices.append({
                        'device_id': str(device.id),
                        'device_fingerprint': device.device_fingerprint,
                        'issue_type': 'trusted_high_activity',
                        'activity_count': recent_logs.count(),
                        'user': device.user.username,
                        'trust_score': device.trust_score
                    })
            
            # Store findings
            self.results['findings'].append({
                'scan_type': 'device_security',
                'title': 'Device Security Analysis',
                'suspicious_devices': suspicious_devices,
                'total_suspicious_devices': len(suspicious_devices)
            })
            
            # Create incidents if requested
            if self.options['create_incidents']:
                self._create_device_incidents(suspicious_devices)
            
            self.stdout.write(
                self.style.SUCCESS(
                    f"Device scan completed: {len(suspicious_devices)} suspicious devices detected"
                )
            )
            
        except Exception as e:
            logger.error(f"Device scan failed: {str(e)}")
            self.results['findings'].append({
                'scan_type': 'device_security',
                'error': str(e),
                'status': 'failed'
            })
    
    def _run_account_security_scan(self):
        """Run account security scan"""
        self.stdout.write("Running account security scan...")
        
        try:
            cutoff_date = timezone.now() - timedelta(days=self.options['days'])
            
            # Check for inactive accounts with recent activity
            inactive_accounts = []
            
            users = User.objects.filter(
                is_active=True,
                last_login__lt=cutoff_date
            )
            
            for user in users:
                recent_security_events = SecurityLog.objects.filter(
                    user=user,
                    created_at__gte=cutoff_date
                ).count()
                
                if recent_security_events > 0:
                    inactive_accounts.append({
                        'user_id': user.id,
                        'username': user.username,
                        'last_login': user.last_login.isoformat() if user.last_login else None,
                        'recent_events': recent_security_events,
                        'days_inactive': (timezone.now() - user.last_login).days if user.last_login else 0
                    })
            
            # Store findings
            self.results['findings'].append({
                'scan_type': 'account_security',
                'title': 'Account Security Analysis',
                'inactive_accounts': inactive_accounts,
                'total_inactive_accounts': len(inactive_accounts)
            })
            
            self.stdout.write(
                self.style.SUCCESS(
                    f"Account security scan completed: {len(inactive_accounts)} inactive accounts with activity"
                )
            )
            
        except Exception as e:
            logger.error(f"Account security scan failed: {str(e)}")
            self.results['findings'].append({
                'scan_type': 'account_security',
                'error': str(e),
                'status': 'failed'
            })
    
    def _run_network_security_scan(self):
        """Run network security scan"""
        self.stdout.write("Running network security scan...")
        
        try:
            cutoff_date = timezone.now() - timedelta(days=self.options['days'])
            
            # Analyze IP patterns
            ip_analysis = []
            
            # Get top IP addresses by activity
            top_ips = SecurityLog.objects.filter(
                created_at__gte=cutoff_date,
                ip_address__isnull=False
            ).values('ip_address').annotate(
                event_count=models.Count('id'),
                user_count=models.Count('user_id', distinct=True)
            ).order_by('-event_count')[:50]
            
            for ip_data in top_ips:
                # Check if IP is in blacklist
                is_blacklisted = IPBlacklist.objects.filter(
                    ip_address=ip_data['ip_address'],
                    is_active=True
                ).exists()
                
                # Check for threat intelligence
                threat_matches = ThreatIntelligence.objects.filter(
                    indicators__contains=[ip_data['ip_address']],
                    is_active=True
                ).count()
                
                ip_analysis.append({
                    'ip_address': ip_data['ip_address'],
                    'event_count': ip_data['event_count'],
                    'user_count': ip_data['user_count'],
                    'is_blacklisted': is_blacklisted,
                    'threat_matches': threat_matches,
                    'risk_score': self._calculate_ip_risk_score(ip_data)
                })
            
            # Store findings
            self.results['findings'].append({
                'scan_type': 'network_security',
                'title': 'Network Security Analysis',
                'ip_analysis': ip_analysis,
                'total_analyzed_ips': len(ip_analysis)
            })
            
            self.stdout.write(
                self.style.SUCCESS(
                    f"Network security scan completed: {len(ip_analysis)} IPs analyzed"
                )
            )
            
        except Exception as e:
            logger.error(f"Network security scan failed: {str(e)}")
            self.results['findings'].append({
                'scan_type': 'network_security',
                'error': str(e),
                'status': 'failed'
            })
    
    def _calculate_ip_risk_score(self, ip_data):
        """Calculate risk score for IP address"""
        score = 0
        
        # Base score from activity
        if ip_data['event_count'] > 100:
            score += 20
        elif ip_data['event_count'] > 50:
            score += 10
        
        # Score from user diversity
        if ip_data['user_count'] > 10:
            score += 15
        elif ip_data['user_count'] > 5:
            score += 10
        
        # Score from blacklist
        if ip_data.get('is_blacklisted'):
            score += 50
        
        # Score from threat intelligence
        score += ip_data.get('threat_matches', 0) * 10
        
        return min(score, 100)
    
    def _create_vpn_incidents(self, vpn_findings, proxy_findings):
        """Create security incidents for VPN/proxy detections"""
        try:
            # Group by user for incident creation
            user_vpn_data = {}
            
            for finding in vpn_findings + proxy_findings:
                user_key = finding.get('user', 'Anonymous')
                if user_key not in user_vpn_data:
                    user_vpn_data[user_key] = []
                user_vpn_data[user_key].append(finding)
            
            for username, findings in user_vpn_data.items():
                if username == 'Anonymous':
                    continue
                
                try:
                    user = User.objects.get(username=username)
                    
                    incident_data = {
                        'user': user,
                        'incident_type': 'vpn_proxy_detected',
                        'severity': 'medium' if len(findings) < 5 else 'high',
                        'title': f'VPN/Proxy Activity Detected for {username}',
                        'description': f'Detected {len(findings)} instances of VPN/proxy usage',
                        'evidence': {
                            'findings': findings,
                            'total_detections': len(findings),
                            'scan_date': self.scan_start_time.isoformat()
                        }
                    }
                    
                    incident = self.incident_service.create_incident_from_security_event(incident_data)
                    self.results['incidents_created'].append({
                        'incident_id': str(incident.id),
                        'type': 'vpn_proxy',
                        'user': username
                    })
                    
                except User.DoesNotExist:
                    logger.warning(f"User {username} not found for VPN incident creation")
                    continue
            
        except Exception as e:
            logger.error(f"Failed to create VPN incidents: {str(e)}")
    
    def _create_threat_incidents(self, high_risk_ips, threat_matches):
        """Create security incidents for threat intelligence"""
        try:
            # Create incidents for high-risk IPs
            for ip_data in high_risk_ips:
                incident_data = {
                    'incident_type': 'threat_detected',
                    'severity': 'high' if ip_data['risk_score'] > 70 else 'medium',
                    'title': f'High Risk IP Detected: {ip_data["ip_address"]}',
                    'description': f'IP {ip_data["ip_address"]} has risk score {ip_data["risk_score"]}',
                    'evidence': {
                        'ip_data': ip_data,
                        'scan_date': self.scan_start_time.isoformat()
                    }
                }
                
                incident = self.incident_service.create_incident_from_security_event(incident_data)
                self.results['incidents_created'].append({
                    'incident_id': str(incident.id),
                    'type': 'threat_intel',
                    'ip': ip_data['ip_address']
                })
            
            # Create incidents for threat matches
            for threat_data in threat_matches:
                incident_data = {
                    'incident_type': 'threat_match',
                    'severity': 'high',
                    'title': f'Threat Intelligence Match: {threat_data["threat_type"]}',
                    'description': f'Matched {threat_data["matching_events"]} events for known threat',
                    'evidence': {
                        'threat_data': threat_data,
                        'scan_date': self.scan_start_time.isoformat()
                    }
                }
                
                incident = self.incident_service.create_incident_from_security_event(incident_data)
                self.results['incidents_created'].append({
                    'incident_id': str(incident.id),
                    'type': 'threat_match',
                    'threat_id': threat_data['threat_id']
                })
                
        except Exception as e:
            logger.error(f"Failed to create threat incidents: {str(e)}")
    
    def _create_risk_incidents(self, high_risk_users):
        """Create security incidents for high-risk users"""
        try:
            for user_data in high_risk_users:
                user = User.objects.get(id=user_data['user_id'])
                
                incident_data = {
                    'user': user,
                    'incident_type': 'high_risk_user',
                    'severity': 'high',
                    'title': f'High Risk User: {user_data["username"]}',
                    'description': f'User has risk score {user_data["current_score"]}',
                    'evidence': {
                        'user_data': user_data,
                        'scan_date': self.scan_start_time.isoformat()
                    }
                }
                
                incident = self.incident_service.create_incident_from_security_event(incident_data)
                self.results['incidents_created'].append({
                    'incident_id': str(incident.id),
                    'type': 'high_risk_user',
                    'user': user_data['username']
                })
                
        except Exception as e:
            logger.error(f"Failed to create risk incidents: {str(e)}")
    
    def _create_user_incidents(self, suspicious_users):
        """Create security incidents for suspicious users"""
        try:
            for user_data in suspicious_users:
                if 'user_id' not in user_data:
                    continue
                
                user = User.objects.get(id=user_data['user_id'])
                
                incident_data = {
                    'user': user,
                    'incident_type': 'suspicious_activity',
                    'severity': 'medium',
                    'title': f'Suspicious Activity: {user_data["username"]}',
                    'description': f'Detected {user_data["issue_type"]}',
                    'evidence': {
                        'user_data': user_data,
                        'scan_date': self.scan_start_time.isoformat()
                    }
                }
                
                incident = self.incident_service.create_incident_from_security_event(incident_data)
                self.results['incidents_created'].append({
                    'incident_id': str(incident.id),
                    'type': 'suspicious_user',
                    'user': user_data['username']
                })
                
        except Exception as e:
            logger.error(f"Failed to create user incidents: {str(e)}")
    
    def _create_device_incidents(self, suspicious_devices):
        """Create security incidents for suspicious devices"""
        try:
            for device_data in suspicious_devices:
                incident_data = {
                    'incident_type': 'suspicious_device',
                    'severity': 'medium',
                    'title': f'Suspicious Device: {device_data.get("device_fingerprint", "Unknown")}',
                    'description': f'Detected {device_data["issue_type"]}',
                    'evidence': {
                        'device_data': device_data,
                        'scan_date': self.scan_start_time.isoformat()
                    }
                }
                
                incident = self.incident_service.create_incident_from_security_event(incident_data)
                self.results['incidents_created'].append({
                    'incident_id': str(incident.id),
                    'type': 'suspicious_device',
                    'device': device_data.get('device_fingerprint', 'Unknown')
                })
                
        except Exception as e:
            logger.error(f"Failed to create device incidents: {str(e)}")
    
    def _auto_block_vpn_ips(self, vpn_findings, proxy_findings):
        """Automatically block VPN/proxy IPs"""
        if self.options['dry_run']:
            self.stdout.write("DRY RUN: Would block VPN/proxy IPs")
            return
        
        try:
            blocked_count = 0
            
            for finding in vpn_findings + proxy_findings:
                ip_address = finding['ip_address']
                
                # Check if already blocked
                if IPBlacklist.objects.filter(
                    ip_address=ip_address,
                    is_active=True
                ).exists():
                    continue
                
                # Create blacklist entry
                blacklist_entry = IPBlacklist.objects.create(
                    ip_address=ip_address,
                    blacklist_type='vpn_proxy',
                    reason=f'Auto-blocked during security scan: {finding.get("vpn_type", "unknown")}',
                    confidence=finding.get('confidence', 0),
                    source='security_scan',
                    expires_at=timezone.now() + timedelta(days=30)
                )
                
                blocked_count += 1
                self.results['actions_taken'].append({
                    'action': 'ip_blocked',
                    'ip_address': ip_address,
                    'reason': blacklist_entry.reason,
                    'blocked_at': timezone.now().isoformat()
                })
            
            self.stdout.write(
                self.style.SUCCESS(
                    f"Auto-blocked {blocked_count} VPN/proxy IPs"
                )
            )
            
        except Exception as e:
            logger.error(f"Failed to auto-block VPN IPs: {str(e)}")
    
    def _calculate_statistics(self):
        """Calculate scan statistics"""
        self.results['statistics'] = {
            'scan_duration_seconds': (timezone.now() - self.scan_start_time).total_seconds(),
            'total_findings': len(self.results['findings']),
            'total_incidents_created': len(self.results['incidents_created']),
            'total_actions_taken': len(self.results['actions_taken']),
            'scan_completed_at': timezone.now().isoformat()
        }
        
        # Add breakdown by finding type
        finding_types = {}
        for finding in self.results['findings']:
            scan_type = finding.get('scan_type', 'unknown')
            finding_types[scan_type] = finding_types.get(scan_type, 0) + 1
        
        self.results['statistics']['finding_breakdown'] = finding_types
    
    def _output_results(self):
        """Output scan results"""
        format_type = self.options['output_format']
        
        if format_type == 'json':
            self._output_json_results()
        elif format_type == 'csv':
            self._output_csv_results()
        else:
            self._output_text_results()
    
    def _output_text_results(self):
        """Output results in text format"""
        self.stdout.write("\n" + "="*80)
        self.stdout.write(self.style.SUCCESS("SECURITY SCAN RESULTS"))
        self.stdout.write("="*80)
        
        # Scan info
        scan_info = self.results['scan_info']
        self.stdout.write(f"Scan Type: {scan_info['scan_type']}")
        self.stdout.write(f"Started: {scan_info['started_at']}")
        
        # Statistics
        stats = self.results['statistics']
        self.stdout.write(f"\nDuration: {stats['scan_duration_seconds']:.2f} seconds")
        self.stdout.write(f"Total Findings: {stats['total_findings']}")
        self.stdout.write(f"Incidents Created: {stats['total_incidents_created']}")
        self.stdout.write(f"Actions Taken: {stats['total_actions_taken']}")
        
        # Findings
        for finding in self.results['findings']:
            if 'error' in finding:
                self.stdout.write(
                    self.style.ERROR(f"\n{finding['title']} - FAILED")
                )
                self.stdout.write(f"Error: {finding['error']}")
            else:
                self.stdout.write(
                    self.style.WARNING(f"\n{finding['title']}")
                )
                
                if finding['scan_type'] == 'vpn_detection':
                    self.stdout.write(f"VPN Detections: {finding['total_vpn_detections']}")
                    self.stdout.write(f"Proxy Detections: {finding['total_proxy_detections']}")
                elif finding['scan_type'] == 'threat_intelligence':
                    self.stdout.write(f"High Risk IPs: {finding['total_high_risk_ips']}")
                    self.stdout.write(f"Threat Matches: {finding['total_threat_matches']}")
                elif finding['scan_type'] == 'risk_assessment':
                    self.stdout.write(f"High Risk Users: {finding['total_high_risk']}")
                    self.stdout.write(f"Medium Risk Users: {finding['total_medium_risk']}")
                else:
                    for key, value in finding.items():
                        if key.startswith('total_'):
                            self.stdout.write(f"{key.replace('total_', '').title()}: {value}")
        
        # Actions taken
        if self.results['actions_taken']:
            self.stdout.write("\n" + "-"*40)
            self.stdout.write(self.style.WARNING("ACTIONS TAKEN"))
            self.stdout.write("-"*40)
            for action in self.results['actions_taken']:
                self.stdout.write(f"{action['action']}: {action.get('ip_address', action.get('user', 'N/A'))}")
    
    def _output_json_results(self):
        """Output results in JSON format"""
        json_output = json.dumps(self.results, indent=2, default=str)
        self.stdout.write(json_output)
    
    def _output_csv_results(self):
        """Output results in CSV format"""
        import csv
        from io import StringIO
        
        output = StringIO()
        
        # Create CSV for findings
        if self.results['findings']:
            writer = csv.writer(output)
            writer.writerow(['Scan Type', 'Title', 'Total Items', 'Status'])
            
            for finding in self.results['findings']:
                if 'error' in finding:
                    writer.writerow([finding.get('scan_type', 'unknown'), finding.get('title', 'Unknown'), 0, 'FAILED'])
                else:
                    total_items = 0
                    for key, value in finding.items():
                        if key.startswith('total_'):
                            total_items += value
                    
                    writer.writerow([finding.get('scan_type', 'unknown'), finding.get('title', 'Unknown'), total_items, 'SUCCESS'])
        
        self.stdout.write(output.getvalue())
    
    def _send_summary_notification(self):
        """Send summary notification (placeholder for future implementation)"""
        try:
            stats = self.results['statistics']
            
            summary = f"""
Security Scan Summary:
- Type: {self.options['scan_type']}
- Duration: {stats['scan_duration_seconds']:.2f} seconds
- Findings: {stats['total_findings']}
- Incidents: {stats['total_incidents_created']}
- Actions: {stats['total_actions_taken']}
            """.strip()
            
            logger.info(f"Security scan completed:\n{summary}")
            
        except Exception as e:
            logger.error(f"Failed to send summary notification: {str(e)}")


# Import Django models for use in the command
from django.db import models
# DeviceInfo stub — replace with real import if available
try:
    from api.security.models import DeviceInfo
except ImportError:
    class DeviceInfo:
        pass

