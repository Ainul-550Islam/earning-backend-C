"""
Enhanced Suspicious IP Blocking Management Command
Automatically block high-risk IPs based on risk scores and threat intelligence
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
from datetime import datetime, timedelta
from collections import defaultdict

from ...models import (
    SecurityLog, SecurityIncident, IPBlacklist, 
    ThreatIntelligence, RiskScore, DeviceInfo
)
from ...vpn_detector import VPNDetector, VPNServiceError

User = get_user_model()

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Automatically block high-risk IPs based on risk scores and threat intelligence'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--risk-threshold',
            type=int,
            default=70,
            help='Risk score threshold for automatic blocking (default: 70)'
        )
        parser.add_argument(
            '--days',
            type=int,
            default=7,
            help='Number of days to look back for IP activity (default: 7)'
        )
        parser.add_argument(
            '--min-events',
            type=int,
            default=5,
            help='Minimum number of events required for blocking (default: 5)'
        )
        parser.add_argument(
            '--block-duration',
            type=int,
            default=30,
            help='Duration of IP block in days (default: 30)'
        )
        parser.add_argument(
            '--include-vpn',
            action='store_true',
            help='Include VPN/proxy IPs in blocking'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be blocked without actually blocking'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force block even if IP is already blocked'
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=100,
            help='Batch size for processing (default: 100)'
        )
        parser.add_argument(
            '--exclude-ips',
            type=str,
            help='Comma-separated list of IPs to exclude from blocking'
        )
        parser.add_argument(
            '--whitelist-file',
            type=str,
            help='Path to file containing whitelisted IPs'
        )
        parser.add_argument(
            '--notify-admins',
            action='store_true',
            help='Send notification to admins about blocked IPs'
        )
        parser.add_argument(
            '--create-incidents',
            action='store_true',
            help='Create security incidents for blocked IPs'
        )
    
    def handle(self, *args, **options):
        """Execute the IP blocking command"""
        self.options = options
        self.block_start_time = timezone.now()
        
        try:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Starting suspicious IP blocking process at {self.block_start_time}"
                )
            )
            
            # Initialize data structures
            self.blocked_ips = []
            self.skipped_ips = []
            self.error_ips = []
            self.whitelist = self._load_whitelist()
            
            # Analyze IP activity and risk scores
            ip_analysis = self._analyze_ip_activity()
            
            # Filter IPs for blocking
            ips_to_block = self._filter_ips_for_blocking(ip_analysis)
            
            # Block IPs
            self._block_ips(ips_to_block)
            
            # Create incidents if requested
            if options['create_incidents']:
                self._create_incidents()
            
            # Send notifications if requested
            if options['notify_admins']:
                self._send_admin_notifications()
            
            # Generate summary
            self._generate_summary()
            
            self.stdout.write(
                self.style.SUCCESS(
                    f"IP blocking process completed successfully"
                )
            )
            
        except Exception as e:
            logger.error(f"Suspicious IP blocking failed: {str(e)}")
            raise CommandError(f"Suspicious IP blocking failed: {str(e)}")
    
    def _load_whitelist(self):
        """Load whitelist from file and command line options"""
        whitelist = set()
        
        # Load from command line options
        if self.options['exclude_ips']:
            exclude_ips = [ip.strip() for ip in self.options['exclude_ips'].split(',')]
            whitelist.update(exclude_ips)
        
        # Load from whitelist file
        if self.options['whitelist_file']:
            try:
                with open(self.options['whitelist_file'], 'r') as f:
                    for line in f:
                        ip = line.strip()
                        if ip and not ip.startswith('#'):
                            whitelist.add(ip)
                self.stdout.write(f"Loaded {len(whitelist)} IPs from whitelist file")
            except FileNotFoundError:
                self.stdout.write(
                    self.style.WARNING(f"Whitelist file not found: {self.options['whitelist_file']}")
                )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"Error loading whitelist file: {str(e)}")
                )
        
        return whitelist
    
    def _analyze_ip_activity(self):
        """Analyze IP activity and calculate risk scores"""
        self.stdout.write("Analyzing IP activity...")
        
        cutoff_date = timezone.now() - timedelta(days=self.options['days'])
        
        # Get IP activity data
        ip_activity = SecurityLog.objects.filter(
            created_at__gte=cutoff_date,
            ip_address__isnull=False
        ).values('ip_address').annotate(
            event_count=models.Count('id'),
            user_count=models.Count('user_id', distinct=True),
            failure_count=models.Count('id', filter=models.Q(event_type='login_failure')),
            security_event_count=models.Count('id', filter=models.Q(severity__in=['warning', 'error', 'critical', 'security'])),
            unique_event_types=models.Count('event_type', distinct=True)
        ).order_by('-event_count')
        
        ip_analysis = {}
        
        for ip_data in ip_activity:
            ip_address = ip_data['ip_address']
            
            # Skip whitelisted IPs
            if ip_address in self.whitelist:
                self.skipped_ips.append({
                    'ip_address': ip_address,
                    'reason': 'whitelisted'
                })
                continue
            
            # Calculate risk score
            risk_score = self._calculate_ip_risk_score(ip_data)
            
            # Check if IP is already blacklisted
            is_blacklisted = IPBlacklist.objects.filter(
                ip_address=ip_address,
                is_active=True
            ).exists()
            
            # Check threat intelligence
            threat_matches = ThreatIntelligence.objects.filter(
                indicators__contains=[ip_address],
                is_active=True
            ).count()
            
            # Check for VPN/proxy
            is_vpn = False
            is_proxy = False
            if self.options['include_vpn']:
                try:
                    vpn_detector = VPNDetector()
                    vpn_result = vpn_detector.is_vpn(ip_address)
                    is_vpn = vpn_result.get('is_vpn', False)
                    is_proxy = vpn_result.get('is_proxy', False)
                except VPNServiceError:
                    pass
            
            ip_analysis[ip_address] = {
                'ip_address': ip_address,
                'risk_score': risk_score,
                'event_count': ip_data['event_count'],
                'user_count': ip_data['user_count'],
                'failure_count': ip_data['failure_count'],
                'security_event_count': ip_data['security_event_count'],
                'unique_event_types': ip_data['unique_event_types'],
                'is_blacklisted': is_blacklisted,
                'threat_matches': threat_matches,
                'is_vpn': is_vpn,
                'is_proxy': is_proxy,
                'last_activity': SecurityLog.objects.filter(
                    ip_address=ip_address
                ).order_by('-created_at').first().created_at
            }
        
        self.stdout.write(f"Analyzed {len(ip_analysis)} unique IP addresses")
        return ip_analysis
    
    def _calculate_ip_risk_score(self, ip_data):
        """Calculate risk score for IP address"""
        score = 0
        
        # Base score from event volume
        if ip_data['event_count'] > 1000:
            score += 30
        elif ip_data['event_count'] > 500:
            score += 20
        elif ip_data['event_count'] > 100:
            score += 10
        elif ip_data['event_count'] > 50:
            score += 5
        
        # Score from user diversity (suspicious if too many users)
        if ip_data['user_count'] > 50:
            score += 25
        elif ip_data['user_count'] > 20:
            score += 15
        elif ip_data['user_count'] > 10:
            score += 10
        elif ip_data['user_count'] > 5:
            score += 5
        
        # Score from failed login attempts
        if ip_data['failure_count'] > 50:
            score += 20
        elif ip_data['failure_count'] > 20:
            score += 15
        elif ip_data['failure_count'] > 10:
            score += 10
        elif ip_data['failure_count'] > 5:
            score += 5
        
        # Score from security events
        if ip_data['security_event_count'] > 20:
            score += 25
        elif ip_data['security_event_count'] > 10:
            score += 15
        elif ip_data['security_event_count'] > 5:
            score += 10
        elif ip_data['security_event_count'] > 2:
            score += 5
        
        # Score from event type diversity
        if ip_data['unique_event_types'] > 10:
            score += 10
        elif ip_data['unique_event_types'] > 5:
            score += 5
        
        return min(score, 100)
    
    def _filter_ips_for_blocking(self, ip_analysis):
        """Filter IPs that should be blocked"""
        self.stdout.write("Filtering IPs for blocking...")
        
        ips_to_block = []
        risk_threshold = self.options['risk_threshold']
        min_events = self.options['min_events']
        
        for ip_address, analysis in ip_analysis.items():
            # Skip if already blacklisted (unless force option is used)
            if analysis['is_blacklisted'] and not self.options['force']:
                self.skipped_ips.append({
                    'ip_address': ip_address,
                    'reason': 'already_blacklisted'
                })
                continue
            
            # Check if meets blocking criteria
            should_block = False
            block_reasons = []
            
            # High risk score
            if analysis['risk_score'] >= risk_threshold:
                should_block = True
                block_reasons.append(f'high_risk_score_{analysis["risk_score"]}')
            
            # High failure rate
            if analysis['event_count'] >= min_events:
                failure_rate = analysis['failure_count'] / analysis['event_count']
                if failure_rate > 0.5:  # More than 50% failures
                    should_block = True
                    block_reasons.append(f'high_failure_rate_{failure_rate:.2f}')
            
            # Threat intelligence matches
            if analysis['threat_matches'] > 0:
                should_block = True
                block_reasons.append(f'threat_matches_{analysis["threat_matches"]}')
            
            # VPN/Proxy usage
            if self.options['include_vpn'] and (analysis['is_vpn'] or analysis['is_proxy']):
                should_block = True
                if analysis['is_vpn']:
                    block_reasons.append('vpn_detected')
                if analysis['is_proxy']:
                    block_reasons.append('proxy_detected')
            
            if should_block:
                analysis['block_reasons'] = block_reasons
                ips_to_block.append(analysis)
        
        self.stdout.write(f"Identified {len(ips_to_block)} IPs for blocking")
        return ips_to_block
    
    def _block_ips(self, ips_to_block):
        """Block the identified IPs"""
        self.stdout.write(f"Blocking {len(ips_to_block)} IPs...")
        
        if self.options['dry_run']:
            self.stdout.write("DRY RUN - Would block the following IPs:")
            for ip_data in ips_to_block:
                self.stdout.write(
                    f"  {ip_data['ip_address']} - Risk: {ip_data['risk_score']} - Reasons: {', '.join(ip_data['block_reasons'])}"
                )
            return
        
        block_duration = timedelta(days=self.options['block_duration'])
        batch_size = self.options['batch_size']
        
        for i in range(0, len(ips_to_block), batch_size):
            batch = ips_to_block[i:i + batch_size]
            
            with transaction.atomic():
                for ip_data in batch:
                    try:
                        # Create or update blacklist entry
                        blacklist_entry, created = IPBlacklist.objects.update_or_create(
                            ip_address=ip_data['ip_address'],
                            defaults={
                                'blacklist_type': 'auto_block',
                                'reason': f"Auto-blocked: {', '.join(ip_data['block_reasons'])}",
                                'confidence': min(ip_data['risk_score'] / 100, 1.0),
                                'source': 'suspicious_ip_blocking_command',
                                'expires_at': timezone.now() + block_duration,
                                'is_active': True,
                                'metadata': {
                                    'risk_score': ip_data['risk_score'],
                                    'event_count': ip_data['event_count'],
                                    'user_count': ip_data['user_count'],
                                    'block_reasons': ip_data['block_reasons'],
                                    'blocked_at': timezone.now().isoformat(),
                                    'command_options': self.options
                                }
                            }
                        )
                        
                        self.blocked_ips.append({
                            'ip_address': ip_data['ip_address'],
                            'blacklist_id': str(blacklist_entry.id),
                            'reason': blacklist_entry.reason,
                            'expires_at': blacklist_entry.expires_at.isoformat(),
                            'risk_score': ip_data['risk_score'],
                            'is_new': created
                        })
                        
                    except Exception as e:
                        logger.error(f"Failed to block IP {ip_data['ip_address']}: {str(e)}")
                        self.error_ips.append({
                            'ip_address': ip_data['ip_address'],
                            'error': str(e)
                        })
            
            self.stdout.write(f"Processed batch {i//batch_size + 1}/{(len(ips_to_block) + batch_size - 1)//batch_size}")
    
    def _create_incidents(self):
        """Create security incidents for blocked IPs"""
        self.stdout.write("Creating security incidents for blocked IPs...")
        
        incidents_created = 0
        
        for ip_data in self.blocked_ips:
            try:
                # Get recent security logs for this IP
                recent_logs = SecurityLog.objects.filter(
                    ip_address=ip_data['ip_address']
                ).order_by('-created_at')[:10]
                
                # Create incident
                incident = SecurityIncident.objects.create(
                    incident_type='ip_auto_blocked',
                    severity='high',
                    title=f'IP Auto-Blocked: {ip_data["ip_address"]}',
                    description=f'IP {ip_data["ip_address"]} was automatically blocked due to suspicious activity',
                    evidence={
                        'ip_address': ip_data['ip_address'],
                        'risk_score': ip_data['risk_score'],
                        'block_reason': ip_data['reason'],
                        'recent_logs': [
                            {
                                'event_type': log.event_type,
                                'severity': log.severity,
                                'created_at': log.created_at.isoformat(),
                                'user': log.user.username if log.user else None
                            }
                            for log in recent_logs
                        ],
                        'blocked_at': timezone.now().isoformat()
                    },
                    status='open'
                )
                
                incidents_created += 1
                
            except Exception as e:
                logger.error(f"Failed to create incident for IP {ip_data['ip_address']}: {str(e)}")
        
        self.stdout.write(f"Created {incidents_created} security incidents")
    
    def _send_admin_notifications(self):
        """Send notifications to administrators"""
        self.stdout.write("Sending admin notifications...")
        
        try:
            from django.core.mail import mail_admins
            
            subject = f"Suspicious IP Blocking Report - {len(self.blocked_ips)} IPs Blocked"
            
            message = f"""
Suspicious IP Blocking Report
============================

Execution Time: {self.block_start_time.strftime('%Y-%m-%d %H:%M:%S')}

Summary:
- IPs Blocked: {len(self.blocked_ips)}
- IPs Skipped: {len(self.skipped_ips)}
- Errors: {len(self.error_ips)}

Configuration:
- Risk Threshold: {self.options['risk_threshold']}
- Days Analyzed: {self.options['days']}
- Min Events: {self.options['min_events']}
- Block Duration: {self.options['block_duration']} days
- Include VPN/Proxy: {self.options['include_vpn']}

Blocked IPs:
{chr(10).join([f"- {ip['ip_address']} (Risk: {ip['risk_score']}) - {ip['reason']}" for ip in self.blocked_ips[:10]])}
{f"... and {len(self.blocked_ips) - 10} more" if len(self.blocked_ips) > 10 else ""}

Skipped IPs:
{chr(10).join([f"- {ip['ip_address']} - {ip['reason']}" for ip in self.skipped_ips[:5]])}
{f"... and {len(self.skipped_ips) - 5} more" if len(self.skipped_ips) > 5 else ""}

Errors:
{chr(10).join([f"- {ip['ip_address']}: {ip['error']}" for ip in self.error_ips])}

This is an automated message from the Suspicious IP Blocking command.
            """.strip()
            
            mail_admins(subject, message)
            self.stdout.write("Admin notifications sent successfully")
            
        except Exception as e:
            logger.error(f"Failed to send admin notifications: {str(e)}")
            self.stdout.write(
                self.style.WARNING(f"Failed to send admin notifications: {str(e)}")
            )
    
    def _generate_summary(self):
        """Generate and display summary of blocking operation"""
        self.stdout.write("\n" + "="*80)
        self.stdout.write(self.style.SUCCESS("SUSPICIOUS IP BLOCKING SUMMARY"))
        self.stdout.write("="*80)
        
        # Configuration
        self.stdout.write(f"Configuration:")
        self.stdout.write(f"  Risk Threshold: {self.options['risk_threshold']}")
        self.stdout.write(f"  Days Analyzed: {self.options['days']}")
        self.stdout.write(f"  Min Events: {self.options['min_events']}")
        self.stdout.write(f"  Block Duration: {self.options['block_duration']} days")
        self.stdout.write(f"  Include VPN/Proxy: {self.options['include_vpn']}")
        self.stdout.write(f"  Dry Run: {self.options['dry_run']}")
        self.stdout.write(f"  Force: {self.options['force']}")
        
        # Results
        self.stdout.write(f"\nResults:")
        self.stdout.write(f"  IPs Blocked: {len(self.blocked_ips)}")
        self.stdout.write(f"  IPs Skipped: {len(self.skipped_ips)}")
        self.stdout.write(f"  Errors: {len(self.error_ips)}")
        
        # Blocked IPs details
        if self.blocked_ips:
            self.stdout.write(f"\nBlocked IPs:")
            for ip in self.blocked_ips[:10]:
                self.stdout.write(
                    f"  {ip['ip_address']} - Risk: {ip['risk_score']} - {ip['reason'][:50]}..."
                )
            if len(self.blocked_ips) > 10:
                self.stdout.write(f"  ... and {len(self.blocked_ips) - 10} more")
        
        # Skipped IPs details
        if self.skipped_ips:
            self.stdout.write(f"\nSkipped IPs:")
            for ip in self.skipped_ips[:5]:
                self.stdout.write(f"  {ip['ip_address']} - {ip['reason']}")
            if len(self.skipped_ips) > 5:
                self.stdout.write(f"  ... and {len(self.skipped_ips) - 5} more")
        
        # Errors
        if self.error_ips:
            self.stdout.write(f"\nErrors:")
            for ip in self.error_ips:
                self.stdout.write(f"  {ip['ip_address']}: {ip['error']}")
        
        # Statistics
        if self.blocked_ips:
            risk_scores = [ip['risk_score'] for ip in self.blocked_ips]
            avg_risk = sum(risk_scores) / len(risk_scores)
            max_risk = max(risk_scores)
            min_risk = min(risk_scores)
            
            self.stdout.write(f"\nStatistics:")
            self.stdout.write(f"  Average Risk Score: {avg_risk:.2f}")
            self.stdout.write(f"  Max Risk Score: {max_risk}")
            self.stdout.write(f"  Min Risk Score: {min_risk}")
            
            # Block reasons
            reason_counts = defaultdict(int)
            for ip in self.blocked_ips:
                for reason in ip['reason'].split(', '):
                    if ':' in reason:
                        reason_type = reason.split(':')[0]
                        reason_counts[reason_type] += 1
            
            self.stdout.write(f"\nBlock Reasons:")
            for reason, count in sorted(reason_counts.items(), key=lambda x: x[1], reverse=True):
                self.stdout.write(f"  {reason}: {count}")
        
        self.stdout.write("="*80)


# Import required modules for the command
from django.db import models
# DeviceInfo stub — replace with real import if available
try:
    from api.security.models import DeviceInfo
except ImportError:
    class DeviceInfo:
        pass

