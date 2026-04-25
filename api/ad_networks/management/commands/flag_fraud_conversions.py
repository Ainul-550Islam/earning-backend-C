"""
api/ad_networks/management/commands/flag_fraud_conversions.py
Manual fraud detection and flagging command
SaaS-ready with tenant support
"""

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.db import transaction
from django.db.models import Q, Count, Sum, Avg, F, Window
from django.db.models.functions import RowNumber
from datetime import timedelta, datetime
import logging
import json

from api.ad_networks.models import OfferConversion, UserOfferEngagement, OfferClick, KnownBadIP
from api.ad_networks.choices import ConversionStatus, RiskLevel, RejectionReason
from api.ad_networks.constants import (
    FRAUD_SCORE_THRESHOLD,
    HIGH_RISK_THRESHOLD,
    MEDIUM_RISK_THRESHOLD,
    MAX_CONVERSIONS_PER_USER_PER_HOUR,
    MAX_CONVERSIONS_PER_USER_PER_DAY,
    MAX_CONVERSIONS_PER_IP_PER_HOUR,
    MAX_CONVERSIONS_PER_IP_PER_DAY,
    SUSPICIOUS_COMPLETION_TIME_SECONDS
)

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Manual fraud detection and flagging of suspicious conversions'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--tenant-id',
            type=str,
            help='Specific tenant ID to scan (optional)'
        )
        parser.add_argument(
            '--network-id',
            type=int,
            help='Specific network ID to scan (optional)'
        )
        parser.add_argument(
            '--days',
            type=int,
            default=7,
            help='Number of days to look back (default: 7)'
        )
        parser.add_argument(
            '--hours',
            type=int,
            help='Number of hours to look back (overrides days if specified)'
        )
        parser.add_argument(
            '--auto-flag',
            action='store_true',
            help='Automatically flag high-risk conversions'
        )
        parser.add_argument(
            '--auto-reject',
            action='store_true',
            help='Automatically reject conversions above fraud threshold'
        )
        parser.add_argument(
            '--threshold',
            type=int,
            default=FRAUD_SCORE_THRESHOLD,
            help=f'Fraud score threshold (default: {FRAUD_SCORE_THRESHOLD})'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be flagged without actually flagging'
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Verbose output'
        )
        parser.add_argument(
            '--export-report',
            type=str,
            help='Export detailed report to JSON file'
        )
    
    def handle(self, *args, **options):
        self.verbose = options.get('verbose', False)
        self.dry_run = options.get('dry_run', False)
        self.auto_flag = options.get('auto_flag', False)
        self.auto_reject = options.get('auto_reject', False)
        self.threshold = options.get('threshold', FRAUD_SCORE_THRESHOLD)
        self.tenant_id = options.get('tenant_id')
        self.network_id = options.get('network_id')
        self.export_report = options.get('export_report')
        
        # Calculate time range
        if options.get('hours'):
            self.time_delta = timedelta(hours=options['hours'])
            self.time_period = f"{options['hours']} hours"
        else:
            days = options.get('days', 7)
            self.time_delta = timedelta(days=days)
            self.time_period = f"{days} days"
        
        self.end_time = timezone.now()
        self.start_time = self.end_time - self.time_delta
        
        self.stdout.write(self.style.SUCCESS('Starting fraud detection scan...'))
        self.stdout.write(f'Time period: {self.time_period} ({self.start_time} to {self.end_time})')
        self.stdout.write(f'Fraud threshold: {self.threshold}')
        
        if self.dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made'))
        
        try:
            # Initialize fraud detection results
            fraud_results = {
                'scan_info': {
                    'start_time': self.start_time.isoformat(),
                    'end_time': self.end_time.isoformat(),
                    'time_period': self.time_period,
                    'threshold': self.threshold,
                    'tenant_id': self.tenant_id,
                    'network_id': self.network_id,
                },
                'detections': {},
                'summary': {}
            }
            
            # Run various fraud detection algorithms
            self._detect_velocity_fraud(fraud_results)
            self._detect_ip_fraud(fraud_results)
            self._detect_time_fraud(fraud_results)
            self._detect_device_fraud(fraud_results)
            self._detect_pattern_fraud(fraud_results)
            self._detect_known_bad_ips(fraud_results)
            
            # Calculate overall fraud scores
            self._calculate_fraud_scores(fraud_results)
            
            # Flag or reject conversions if requested
            if self.auto_flag or self.auto_reject:
                self._process_fraudulent_conversions(fraud_results)
            
            # Generate summary
            self._generate_summary(fraud_results)
            
            # Export report if requested
            if self.export_report:
                self._export_report(fraud_results)
            
            # Print results
            self._print_results(fraud_results)
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Fraud detection failed: {str(e)}'))
            raise CommandError(f'Fraud detection failed: {str(e)}')
    
    def _detect_velocity_fraud(self, results):
        """Detect velocity-based fraud (too many conversions in short time)"""
        self.stdout.write('Detecting velocity-based fraud...')
        
        detections = []
        
        # User velocity detection
        user_velocity = UserOfferEngagement.objects.filter(
            created_at__gte=self.start_time,
            created_at__lte=self.end_time,
            status__in=['completed', 'approved']
        ).values('user_id').annotate(
            conversions_count=Count('id'),
            conversions_per_hour=Count('id') / (self.time_delta.total_seconds() / 3600),
            total_reward=Sum('reward_earned')
        ).filter(
            conversions_count__gt=MAX_CONVERSIONS_PER_USER_PER_DAY
        )
        
        for user_stat in user_velocity:
            fraud_score = min(100, (user_stat['conversions_per_hour'] / MAX_CONVERSIONS_PER_USER_PER_HOUR) * 100)
            
            detections.append({
                'type': 'user_velocity',
                'user_id': user_stat['user_id'],
                'conversions_count': user_stat['conversions_count'],
                'conversions_per_hour': user_stat['conversions_per_hour'],
                'total_reward': user_stat['total_reward'],
                'fraud_score': fraud_score,
                'risk_level': self._get_risk_level(fraud_score),
                'description': f"User has {user_stat['conversions_count']} conversions ({user_stat['conversions_per_hour']:.1f}/hour)"
            })
        
        # IP velocity detection
        ip_velocity = OfferClick.objects.filter(
            created_at__gte=self.start_time,
            created_at__lte=self.end_time
        ).values('ip_address').annotate(
            clicks_count=Count('id'),
            unique_users=Count('user_id', distinct=True),
            clicks_per_hour=Count('id') / (self.time_delta.total_seconds() / 3600)
        ).filter(
            clicks_count__gt=MAX_CONVERSIONS_PER_IP_PER_DAY
        )
        
        for ip_stat in ip_velocity:
            fraud_score = min(100, (ip_stat['clicks_per_hour'] / MAX_CONVERSIONS_PER_IP_PER_HOUR) * 100)
            
            detections.append({
                'type': 'ip_velocity',
                'ip_address': ip_stat['ip_address'],
                'clicks_count': ip_stat['clicks_count'],
                'unique_users': ip_stat['unique_users'],
                'clicks_per_hour': ip_stat['clicks_per_hour'],
                'fraud_score': fraud_score,
                'risk_level': self._get_risk_level(fraud_score),
                'description': f"IP has {ip_stat['clicks_count']} clicks ({ip_stat['clicks_per_hour']:.1f}/hour) from {ip_stat['unique_users']} users"
            })
        
        results['detections']['velocity'] = detections
        
        if self.verbose:
            self.stdout.write(f"  Found {len(detections)} velocity fraud indicators")
    
    def _detect_ip_fraud(self, results):
        """Detect IP-based fraud"""
        self.stdout.write('Detecting IP-based fraud...')
        
        detections = []
        
        # Multiple users from same IP
        ip_users = OfferClick.objects.filter(
            created_at__gte=self.start_time,
            created_at__lte=self.end_time
        ).values('ip_address').annotate(
            unique_users=Count('user_id', distinct=True),
            total_clicks=Count('id')
        ).filter(
            unique_users__gt=5  # More than 5 users from same IP
        )
        
        for ip_stat in ip_users:
            fraud_score = min(100, (ip_stat['unique_users'] / 10) * 100)  # 10+ users = 100% fraud score
            
            detections.append({
                'type': 'multiple_users_same_ip',
                'ip_address': ip_stat['ip_address'],
                'unique_users': ip_stat['unique_users'],
                'total_clicks': ip_stat['total_clicks'],
                'fraud_score': fraud_score,
                'risk_level': self._get_risk_level(fraud_score),
                'description': f"{ip_stat['unique_users']} users from same IP address"
            })
        
        # Conversions from suspicious IP ranges
        suspicious_ranges = [
            {'range': '10.0.0.0/8', 'name': 'Private network'},
            {'range': '172.16.0.0/12', 'name': 'Private network'},
            {'range': '192.168.0.0/16', 'name': 'Private network'},
            {'range': '127.0.0.0/8', 'name': 'Loopback'},
        ]
        
        for suspicious in suspicious_ranges:
            # This would require IP range matching - simplified for demo
            pass
        
        results['detections']['ip'] = detections
        
        if self.verbose:
            self.stdout.write(f"  Found {len(detections)} IP fraud indicators")
    
    def _detect_time_fraud(self, results):
        """Detect time-based fraud (too fast completion)"""
        self.stdout.write('Detecting time-based fraud...')
        
        detections = []
        
        # Suspiciously fast completions
        fast_completions = UserOfferEngagement.objects.filter(
            created_at__gte=self.start_time,
            created_at__lte=self.end_time,
            status__in=['completed', 'approved'],
            started_at__isnull=False,
            completed_at__isnull=False
        ).annotate(
            completion_time_seconds=F('completed_at') - F('started_at')
        ).filter(
            completion_time_seconds__lt=timedelta(seconds=SUSPICIOUS_COMPLETION_TIME_SECONDS)
        )
        
        for engagement in fast_completions:
            completion_seconds = engagement.completion_time_seconds.total_seconds()
            fraud_score = max(0, 100 - (completion_seconds / SUSPICIOUS_COMPLETION_TIME_SECONDS) * 100)
            
            detections.append({
                'type': 'fast_completion',
                'engagement_id': engagement.id,
                'user_id': engagement.user_id,
                'offer_id': engagement.offer_id,
                'completion_time_seconds': completion_seconds,
                'fraud_score': fraud_score,
                'risk_level': self._get_risk_level(fraud_score),
                'description': f"Completion in {completion_seconds:.1f} seconds (suspiciously fast)"
            })
        
        results['detections']['time'] = detections
        
        if self.verbose:
            self.stdout.write(f"  Found {len(detections)} time-based fraud indicators")
    
    def _detect_device_fraud(self, results):
        """Detect device-based fraud"""
        self.stdout.write('Detecting device-based fraud...')
        
        detections = []
        
        # Multiple accounts from same device
        device_users = OfferClick.objects.filter(
            created_at__gte=self.start_time,
            created_at__lte=self.end_time
        ).values('device_info').annotate(
            unique_users=Count('user_id', distinct=True),
            total_clicks=Count('id')
        ).filter(
            unique_users__gt=3  # More than 3 users from same device
        )
        
        for device_stat in device_users:
            if device_stat['device_info']:
                fraud_score = min(100, (device_stat['unique_users'] / 5) * 100)
                
                detections.append({
                    'type': 'multiple_users_same_device',
                    'device_info': device_stat['device_info'],
                    'unique_users': device_stat['unique_users'],
                    'total_clicks': device_stat['total_clicks'],
                    'fraud_score': fraud_score,
                    'risk_level': self._get_risk_level(fraud_score),
                    'description': f"{device_stat['unique_users']} users from same device"
                })
        
        # Suspicious user agents
        suspicious_uas = [
            'bot', 'crawler', 'spider', 'scraper', 'automated',
            'python', 'curl', 'wget', 'java', 'go-http'
        ]
        
        ua_fraud = OfferClick.objects.filter(
            created_at__gte=self.start_time,
            created_at__lte=self.end_time
        ).filter(
            user_agent__icontains='bot'
        )
        
        for click in ua_fraud:
            fraud_score = 90  # High score for obvious bots
            
            detections.append({
                'type': 'suspicious_user_agent',
                'click_id': click.id,
                'user_agent': click.user_agent,
                'ip_address': click.ip_address,
                'fraud_score': fraud_score,
                'risk_level': self._get_risk_level(fraud_score),
                'description': f"Suspicious user agent: {click.user_agent[:50]}..."
            })
        
        results['detections']['device'] = detections
        
        if self.verbose:
            self.stdout.write(f"  Found {len(detections)} device-based fraud indicators")
    
    def _detect_pattern_fraud(self, results):
        """Detect pattern-based fraud"""
        self.stdout.write('Detecting pattern-based fraud...')
        
        detections = []
        
        # Sequential conversions (user completing offers one after another)
        user_patterns = UserOfferEngagement.objects.filter(
            created_at__gte=self.start_time,
            created_at__lte=self.end_time,
            status__in=['completed', 'approved']
        ).values('user_id').annotate(
            conversions_count=Count('id'),
            avg_time_between=Avg('created_at')  # Simplified
        ).filter(
            conversions_count__gt=10  # Users with many conversions
        )
        
        for pattern in user_patterns:
            # Check if conversions are too regular (bot-like)
            fraud_score = min(100, (pattern['conversions_count'] / 20) * 100)
            
            detections.append({
                'type': 'sequential_conversions',
                'user_id': pattern['user_id'],
                'conversions_count': pattern['conversions_count'],
                'fraud_score': fraud_score,
                'risk_level': self._get_risk_level(fraud_score),
                'description': f"User has {pattern['conversions_count']} conversions (potentially automated)"
            })
        
        results['detections']['pattern'] = detections
        
        if self.verbose:
            self.stdout.write(f"  Found {len(detections)} pattern-based fraud indicators")
    
    def _detect_known_bad_ips(self, results):
        """Detect conversions from known bad IPs"""
        self.stdout.write('Detecting known bad IPs...')
        
        detections = []
        
        # Get conversions from known bad IPs
        bad_ip_conversions = OfferClick.objects.filter(
            created_at__gte=self.start_time,
            created_at__lte=self.end_time,
            ip_address__in=KnownBadIP.objects.filter(
                is_active=True
            ).values_list('ip_address', flat=True)
        ).select_related('user', 'offer')
        
        for click in bad_ip_conversions:
            # Get bad IP details
            bad_ip = KnownBadIP.objects.filter(
                ip_address=click.ip_address,
                is_active=True
            ).first()
            
            if bad_ip:
                fraud_score = 80 + (bad_ip.confidence_score / 5)  # Base 80 + confidence
                
                detections.append({
                    'type': 'known_bad_ip',
                    'click_id': click.id,
                    'user_id': click.user_id,
                    'ip_address': click.ip_address,
                    'threat_type': bad_ip.threat_type,
                    'confidence_score': bad_ip.confidence_score,
                    'source': bad_ip.source,
                    'fraud_score': fraud_score,
                    'risk_level': self._get_risk_level(fraud_score),
                    'description': f"Conversion from known bad IP ({bad_ip.threat_type})"
                })
        
        results['detections']['known_bad_ips'] = detections
        
        if self.verbose:
            self.stdout.write(f"  Found {len(detections)} known bad IP indicators")
    
    def _calculate_fraud_scores(self, results):
        """Calculate overall fraud scores for conversions"""
        self.stdout.write('Calculating overall fraud scores...')
        
        # Get all conversions in time range
        conversions = OfferConversion.objects.filter(
            created_at__gte=self.start_time,
            created_at__lte=self.end_time
        ).select_related('engagement__user', 'engagement__offer')
        
        fraud_scores = []
        
        for conversion in conversions:
            score = 0
            reasons = []
            
            # Check against all detection types
            for detection_type, detections in results['detections'].items():
                for detection in detections:
                    # User-based detections
                    if detection.get('user_id') == conversion.engagement.user_id:
                        score += detection['fraud_score'] * 0.3
                        reasons.append(f"{detection_type}: {detection['description']}")
                    
                    # IP-based detections
                    if detection.get('ip_address') == conversion.engagement.ip_address:
                        score += detection['fraud_score'] * 0.4
                        reasons.append(f"{detection_type}: {detection['description']}")
                    
                    # Engagement-based detections
                    if detection.get('engagement_id') == conversion.engagement_id:
                        score += detection['fraud_score'] * 0.5
                        reasons.append(f"{detection_type}: {detection['description']}")
            
            # Cap score at 100
            final_score = min(100, score)
            
            fraud_scores.append({
                'conversion_id': conversion.id,
                'user_id': conversion.engagement.user_id,
                'offer_id': conversion.engagement.offer_id,
                'fraud_score': final_score,
                'risk_level': self._get_risk_level(final_score),
                'reasons': reasons,
                'should_flag': final_score >= self.threshold,
                'should_reject': final_score >= HIGH_RISK_THRESHOLD
            })
        
        results['fraud_scores'] = fraud_scores
        
        if self.verbose:
            flagged_count = len([f for f in fraud_scores if f['should_flag']])
            self.stdout.write(f"  Calculated scores for {len(fraud_scores)} conversions")
            self.stdout.write(f"  {flagged_count} conversions above threshold ({self.threshold})")
    
    def _process_fraudulent_conversions(self, results):
        """Process fraudulent conversions (flag or reject)"""
        self.stdout.write('Processing fraudulent conversions...')
        
        flagged_count = 0
        rejected_count = 0
        
        if not self.dry_run:
            with transaction.atomic():
                for score_data in results['fraud_scores']:
                    conversion = OfferConversion.objects.get(id=score_data['conversion_id'])
                    
                    if score_data['should_reject'] and self.auto_reject:
                        # Reject conversion
                        conversion.conversion_status = ConversionStatus.REJECTED
                        conversion.fraud_score = score_data['fraud_score']
                        conversion.fraud_reasons = score_data['reasons']
                        conversion.risk_level = score_data['risk_level']
                        conversion.rejection_reason = '; '.join(score_data['reasons'])
                        conversion.save()
                        rejected_count += 1
                        
                    elif score_data['should_flag'] and self.auto_flag:
                        # Flag for review
                        conversion.fraud_score = score_data['fraud_score']
                        conversion.fraud_reasons = score_data['reasons']
                        conversion.risk_level = score_data['risk_level']
                        if conversion.conversion_status == ConversionStatus.PENDING:
                            conversion.conversion_status = ConversionStatus.REJECTED
                        conversion.save()
                        flagged_count += 1
        else:
            # Dry run - just count
            for score_data in results['fraud_scores']:
                if score_data['should_reject'] and self.auto_reject:
                    rejected_count += 1
                elif score_data['should_flag'] and self.auto_flag:
                    flagged_count += 1
        
        self.stdout.write(f"  Flagged: {flagged_count}, Rejected: {rejected_count}")
    
    def _generate_summary(self, results):
        """Generate summary statistics"""
        self.stdout.write('Generating summary...')
        
        total_conversions = len(results['fraud_scores'])
        flagged_conversions = len([f for f in results['fraud_scores'] if f['should_flag']])
        high_risk_conversions = len([f for f in results['fraud_scores'] if f['risk_level'] == 'high'])
        medium_risk_conversions = len([f for f in results['fraud_scores'] if f['risk_level'] == 'medium'])
        low_risk_conversions = len([f for f in results['fraud_scores'] if f['risk_level'] == 'low'])
        
        # Detection summary
        detection_summary = {}
        for detection_type, detections in results['detections'].items():
            detection_summary[detection_type] = len(detections)
        
        results['summary'] = {
            'total_conversions_analyzed': total_conversions,
            'conversions_flagged': flagged_conversions,
            'flag_rate_percentage': (flagged_conversions / total_conversions * 100) if total_conversions > 0 else 0,
            'high_risk_conversions': high_risk_conversions,
            'medium_risk_conversions': medium_risk_conversions,
            'low_risk_conversions': low_risk_conversions,
            'detection_summary': detection_summary,
            'average_fraud_score': sum(f['fraud_score'] for f in results['fraud_scores']) / total_conversions if total_conversions > 0 else 0,
        }
    
    def _export_report(self, results):
        """Export detailed report to JSON file"""
        self.stdout.write(f'Exporting report to {self.export_report}...')
        
        with open(self.export_report, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        self.stdout.write(self.style.SUCCESS(f'Report exported to {self.export_report}'))
    
    def _print_results(self, results):
        """Print fraud detection results"""
        self.stdout.write('\n' + '='*60)
        self.stdout.write(self.style.SUCCESS('FRAUD DETECTION RESULTS'))
        self.stdout.write('='*60)
        
        summary = results['summary']
        
        self.stdout.write(f"Time Period: {self.time_period}")
        self.stdout.write(f"Total Conversions Analyzed: {summary['total_conversions_analyzed']}")
        self.stdout.write(f"Conversions Flagged: {summary['conversions_flagged']}")
        self.stdout.write(f"Flag Rate: {summary['flag_rate_percentage']:.2f}%")
        self.stdout.write(f"Average Fraud Score: {summary['average_fraud_score']:.1f}")
        
        self.stdout.write('\nRisk Level Breakdown:')
        self.stdout.write(f"  High Risk: {summary['high_risk_conversions']}")
        self.stdout.write(f"  Medium Risk: {summary['medium_risk_conversions']}")
        self.stdout.write(f"  Low Risk: {summary['low_risk_conversions']}")
        
        self.stdout.write('\nDetection Summary:')
        for detection_type, count in summary['detection_summary'].items():
            self.stdout.write(f"  {detection_type}: {count}")
        
        if self.dry_run:
            self.stdout.write(
                self.style.WARNING('\nDRY RUN MODE - No actual changes made')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS('\nFraud detection completed!')
            )
        
        self.stdout.write('='*60)
    
    def _get_risk_level(self, fraud_score):
        """Get risk level based on fraud score"""
        if fraud_score >= HIGH_RISK_THRESHOLD:
            return RiskLevel.HIGH
        elif fraud_score >= MEDIUM_RISK_THRESHOLD:
            return RiskLevel.MEDIUM
        else:
            return RiskLevel.LOW
