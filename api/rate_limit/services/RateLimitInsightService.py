"""
RateLimitInsightService.py - Advanced abuse data analysis and insight generation.

This service analyzes daily abuse data, identifies patterns, and saves insights
to the RateLimitInsight model for comprehensive monitoring and reporting.
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from django.utils import timezone
from django.db.models import Q, Count, Avg, Max, Min, Sum, F
from django.core.cache import cache
from collections import defaultdict

from api.rate_limit.models import RateLimitInsight, AbuseReport, IPBlockList, RateLimitLog
from api.rate_limit.services.AbuseDetectionService import AbuseDetectionService

logger = logging.getLogger(__name__)


class RateLimitInsightService:
    """Advanced abuse data analysis and insight generation service."""
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.abuse_detection_service = AbuseDetectionService()
        self.cache_timeout = 3600  # 1 hour cache
    
    def generate_daily_insights(self, analysis_date: datetime = None) -> RateLimitInsight:
        """
        Generate comprehensive daily insights from abuse data.
        
        Args:
            analysis_date: Date to analyze (default: yesterday)
            
        Returns:
            Created RateLimitInsight instance
        """
        if analysis_date is None:
            analysis_date = timezone.now() - timedelta(days=1)
        
        # Ensure we're working with date only
        analysis_date = analysis_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = analysis_date + timedelta(days=1)
        
        self.logger.info(f"Generating insights for {analysis_date.date()}")
        
        try:
            # Collect all data points
            abuse_data = self._collect_abuse_data(analysis_date, end_date)
            block_data = self._collect_block_data(analysis_date, end_date)
            log_data = self._collect_log_data(analysis_date, end_date)
            pattern_data = self._analyze_patterns(abuse_data, block_data, log_data)
            
            # Generate insights
            insights = self._generate_insights(abuse_data, block_data, log_data, pattern_data)
            
            # Calculate risk scores
            risk_assessment = self._calculate_risk_assessment(insights)
            
            # Create insight record
            insight = RateLimitInsight.objects.create(
                analysis_date=analysis_date,
                total_abuse_reports=abuse_data['total_reports'],
                unique_offenders=abuse_data['unique_ips'],
                blocked_ips=block_data['blocked_count'],
                high_risk_ips=pattern_data['high_risk_ips'],
                top_abuse_types=insights['top_abuse_types'],
                risk_score=risk_assessment['overall_risk'],
                severity_distribution=insights['severity_distribution'],
                geographic_data=insights['geographic_data'],
                time_patterns=insights['time_patterns'],
                recommendations=insights['recommendations'],
                metadata={
                    'analysis_period': {
                        'start': analysis_date.isoformat(),
                        'end': end_date.isoformat()
                    },
                    'data_sources': ['abuse_reports', 'ip_blocks', 'rate_limit_logs'],
                    'pattern_analysis': pattern_data,
                    'risk_factors': risk_assessment['factors']
                }
            )
            
            self.logger.info(f"Generated insight ID: {insight.id} for {analysis_date.date()}")
            return insight
            
        except Exception as e:
            self.logger.error(f"Error generating daily insights: {e}")
            raise
    
    def _collect_abuse_data(self, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Collect and analyze abuse report data."""
        reports = AbuseReport.objects.filter(
            created_at__gte=start_date,
            created_at__lt=end_date
        )
        
        # Basic counts
        total_reports = reports.count()
        unique_ips = reports.values('ip_address').distinct().count()
        blocked_reports = reports.filter(is_blocked=True).count()
        
        # By type
        by_type = reports.values('abuse_type').annotate(
            count=Count('id')
        ).order_by('-count')
        
        # By severity
        by_severity = reports.values('severity').annotate(
            count=Count('id')
        ).order_by('severity')
        
        # Top offenders
        top_offenders = reports.values('ip_address').annotate(
            report_count=Count('id'),
            blocked_count=Count('id', filter=Q(is_blocked=True))
        ).order_by('-report_count')[:10]
        
        # Geographic distribution
        geo_data = self._extract_geographic_data(reports)
        
        return {
            'total_reports': total_reports,
            'unique_ips': unique_ips,
            'blocked_reports': blocked_reports,
            'block_rate': (blocked_reports / total_reports * 100) if total_reports > 0 else 0,
            'by_type': list(by_type),
            'by_severity': list(by_severity),
            'top_offenders': list(top_offenders),
            'geographic_data': geo_data
        }
    
    def _collect_block_data(self, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Collect and analyze IP block data."""
        blocks = IPBlockList.objects.filter(
            created_at__gte=start_date,
            created_at__lt=end_date
        )
        
        total_blocks = blocks.count()
        permanent_blocks = blocks.filter(permanent=True).count()
        
        # By reason
        by_reason = blocks.values('reason').annotate(
            count=Count('id')
        ).order_by('-count')
        
        # By type
        by_type = blocks.values('block_type').annotate(
            count=Count('id')
        ).order_by('-count')
        
        # Average duration (for temporary blocks)
        temp_blocks = blocks.filter(permanent=False, expires_at__isnull=False)
        avg_duration = 0
        if temp_blocks.exists():
            durations = [
                (block.expires_at - block.created_at).total_seconds() / 86400  # days
                for block in temp_blocks
            ]
            avg_duration = sum(durations) / len(durations)
        
        return {
            'blocked_count': total_blocks,
            'permanent_blocks': permanent_blocks,
            'temporary_blocks': total_blocks - permanent_blocks,
            'by_reason': list(by_reason),
            'by_type': list(by_type),
            'avg_duration_days': avg_duration
        }
    
    def _collect_log_data(self, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Collect and analyze rate limit log data."""
        logs = RateLimitLog.objects.filter(
            timestamp__gte=start_date,
            timestamp__lt=end_date
        )
        
        total_requests = logs.count()
        blocked_requests = logs.filter(status='blocked').count()
        
        # By endpoint
        by_endpoint = logs.values('endpoint').annotate(
            count=Count('id'),
            blocked_count=Count('id', filter=Q(status='blocked'))
        ).order_by('-count')[:10]
        
        # By hour
        by_hour = logs.extra(
            {'hour': "strftime('%%H', timestamp)"}
        ).values('hour').annotate(
            count=Count('id')
        ).order_by('hour')
        
        # Suspicion scores
        avg_suspicion = logs.aggregate(
            avg_score=Avg('suspicion_score')
        )['avg_score'] or 0
        
        return {
            'total_requests': total_requests,
            'blocked_requests': blocked_requests,
            'block_rate': (blocked_requests / total_requests * 100) if total_requests > 0 else 0,
            'by_endpoint': list(by_endpoint),
            'by_hour': list(by_hour),
            'avg_suspicion_score': avg_suspicion
        }
    
    def _analyze_patterns(self, abuse_data: Dict, block_data: Dict, log_data: Dict) -> Dict[str, Any]:
        """Analyze patterns across all data sources."""
        patterns = {
            'high_risk_ips': [],
            'emerging_threats': [],
            'time_based_patterns': [],
            'geographic_anomalies': []
        }
        
        # Identify high-risk IPs (multiple abuse types or high severity)
        for offender in abuse_data['top_offenders']:
            if offender['report_count'] >= 5 or offender['blocked_count'] >= 3:
                patterns['high_risk_ips'].append({
                    'ip': offender['ip_address'],
                    'report_count': offender['report_count'],
                    'blocked_count': offender['blocked_count'],
                    'risk_level': 'high' if offender['report_count'] >= 10 else 'medium'
                })
        
        # Identify emerging threats (new abuse patterns)
        if abuse_data['by_type']:
            for abuse_type in abuse_data['by_type'][:3]:  # Top 3 types
                if abuse_type['count'] > abuse_data['total_reports'] * 0.3:  # > 30% of reports
                    patterns['emerging_threats'].append({
                        'type': abuse_type['abuse_type'],
                        'count': abuse_type['count'],
                        'percentage': (abuse_type['count'] / abuse_data['total_reports'] * 100)
                    })
        
        # Time-based patterns
        if log_data['by_hour']:
            peak_hour = max(log_data['by_hour'], key=lambda x: x['count'])
            avg_hour = sum(h['count'] for h in log_data['by_hour']) / len(log_data['by_hour'])
            
            if peak_hour['count'] > avg_hour * 2:  # Peak is 2x average
                patterns['time_based_patterns'].append({
                    'type': 'peak_hour',
                    'hour': peak_hour['hour'],
                    'count': peak_hour['count'],
                    'multiplier': peak_hour['count'] / avg_hour
                })
        
        return patterns
    
    def _generate_insights(self, abuse_data: Dict, block_data: Dict, 
                         log_data: Dict, pattern_data: Dict) -> Dict[str, Any]:
        """Generate comprehensive insights from analyzed data."""
        insights = {
            'top_abuse_types': [],
            'severity_distribution': {},
            'geographic_data': {},
            'time_patterns': {},
            'recommendations': []
        }
        
        # Top abuse types
        if abuse_data['by_type']:
            insights['top_abuse_types'] = [
                {
                    'type': item['abuse_type'],
                    'count': item['count'],
                    'percentage': (item['count'] / abuse_data['total_reports'] * 100)
                }
                for item in abuse_data['by_type'][:5]
            ]
        
        # Severity distribution
        if abuse_data['by_severity']:
            insights['severity_distribution'] = {
                str(item['severity']): item['count']
                for item in abuse_data['by_severity']
            }
        
        # Geographic data
        insights['geographic_data'] = abuse_data['geographic_data']
        
        # Time patterns
        insights['time_patterns'] = {
            'hourly_distribution': log_data['by_hour'],
            'peak_hours': [h['hour'] for h in log_data['by_hour'] if h['count'] > 0],
            'patterns_detected': len(pattern_data['time_based_patterns']) > 0
        }
        
        # Generate recommendations
        insights['recommendations'] = self._generate_recommendations(
            abuse_data, block_data, log_data, pattern_data
        )
        
        return insights
    
    def _calculate_risk_assessment(self, insights: Dict) -> Dict[str, Any]:
        """Calculate overall risk assessment."""
        risk_factors = []
        overall_risk = 0
        
        # Factor 1: Volume of abuse reports
        if insights.get('total_reports', 0) > 100:
            risk_factors.append({
                'factor': 'high_volume',
                'weight': 0.3,
                'score': 80
            })
            overall_risk += 24
        elif insights.get('total_reports', 0) > 50:
            risk_factors.append({
                'factor': 'moderate_volume',
                'weight': 0.3,
                'score': 60
            })
            overall_risk += 18
        
        # Factor 2: High-risk IPs
        high_risk_count = len(insights.get('high_risk_ips', []))
        if high_risk_count > 10:
            risk_factors.append({
                'factor': 'many_high_risk_ips',
                'weight': 0.25,
                'score': 85
            })
            overall_risk += 21
        elif high_risk_count > 5:
            risk_factors.append({
                'factor': 'some_high_risk_ips',
                'weight': 0.25,
                'score': 65
            })
            overall_risk += 16
        
        # Factor 3: Block rate
        block_rate = insights.get('block_rate', 0)
        if block_rate > 70:
            risk_factors.append({
                'factor': 'high_block_rate',
                'weight': 0.2,
                'score': 75
            })
            overall_risk += 15
        elif block_rate > 50:
            risk_factors.append({
                'factor': 'moderate_block_rate',
                'weight': 0.2,
                'score': 55
            })
            overall_risk += 11
        
        # Factor 4: Emerging threats
        emerging_count = len(insights.get('emerging_threats', []))
        if emerging_count > 0:
            risk_factors.append({
                'factor': 'emerging_threats',
                'weight': 0.25,
                'score': 70
            })
            overall_risk += 18
        
        return {
            'overall_risk': min(overall_risk, 100),
            'risk_level': self._get_risk_level(overall_risk),
            'factors': risk_factors
        }
    
    def _get_risk_level(self, risk_score: int) -> str:
        """Get risk level based on score."""
        if risk_score >= 80:
            return 'critical'
        elif risk_score >= 60:
            return 'high'
        elif risk_score >= 40:
            return 'medium'
        elif risk_score >= 20:
            return 'low'
        else:
            return 'minimal'
    
    def _generate_recommendations(self, abuse_data: Dict, block_data: Dict, 
                              log_data: Dict, pattern_data: Dict) -> List[Dict[str, Any]]:
        """Generate actionable recommendations."""
        recommendations = []
        
        # High volume recommendations
        if abuse_data['total_reports'] > 100:
            recommendations.append({
                'type': 'increase_monitoring',
                'priority': 'high',
                'title': 'High Abuse Volume Detected',
                'description': f"Abuse reports ({abuse_data['total_reports']}) exceed normal thresholds. Consider increasing monitoring frequency.",
                'action_items': [
                    'Review automated blocking rules',
                    'Increase monitoring staff alerts',
                    'Consider stricter rate limits'
                ]
            })
        
        # High-risk IP recommendations
        high_risk_ips = pattern_data['high_risk_ips']
        if len(high_risk_ips) > 5:
            recommendations.append({
                'type': 'block_high_risk_ips',
                'priority': 'critical',
                'title': 'Multiple High-Risk IPs Detected',
                'description': f"Found {len(high_risk_ips)} high-risk IPs with repeated abuse patterns.",
                'action_items': [
                    'Review and consider permanent blocking',
                    'Implement additional verification for these IPs',
                    'Add to watchlist for extended monitoring'
                ]
            })
        
        # Block rate recommendations
        if abuse_data['block_rate'] > 70:
            recommendations.append({
                'type': 'review_blocking_criteria',
                'priority': 'medium',
                'title': 'High Block Rate',
                'description': f"Block rate ({abuse_data['block_rate']:.1f}%) is very high. Review blocking criteria.",
                'action_items': [
                    'Review false positive rates',
                    'Adjust blocking thresholds',
                    'Consider graduated blocking approach'
                ]
            })
        
        # Emerging threats
        if pattern_data['emerging_threats']:
            recommendations.append({
                'type': 'address_emerging_threats',
                'priority': 'high',
                'title': 'Emerging Threat Patterns',
                'description': 'New abuse patterns detected that require immediate attention.',
                'action_items': [
                    'Update detection rules for new patterns',
                    'Implement targeted countermeasures',
                    'Monitor for pattern evolution'
                ]
            })
        
        # Time-based pattern recommendations
        if pattern_data['time_based_patterns']:
            recommendations.append({
                'type': 'time_based_monitoring',
                'priority': 'medium',
                'title': 'Time-Based Attack Patterns',
                'description': 'Abuse activity shows clear time-based patterns.',
                'action_items': [
                    'Increase monitoring during peak hours',
                    'Implement time-based rate limiting',
                    'Schedule security reviews for peak periods'
                ]
            })
        
        return recommendations
    
    def _extract_geographic_data(self, reports) -> Dict[str, Any]:
        """Extract geographic distribution from abuse reports."""
        geo_data = {
            'countries': {},
            'cities': {},
            'coordinates': []
        }
        
        for report in reports:
            if report.metadata:
                metadata = report.metadata
                if 'country' in metadata:
                    country = metadata['country']
                    geo_data['countries'][country] = geo_data['countries'].get(country, 0) + 1
                
                if 'city' in metadata:
                    city = metadata['city']
                    geo_data['cities'][city] = geo_data['cities'].get(city, 0) + 1
                
                if 'latitude' in metadata and 'longitude' in metadata:
                    geo_data['coordinates'].append({
                        'lat': metadata['latitude'],
                        'lng': metadata['longitude'],
                        'count': 1
                    })
        
        return geo_data
    
    def get_insight_summary(self, days: int = 7) -> Dict[str, Any]:
        """Get summary of recent insights."""
        since = timezone.now() - timedelta(days=days)
        insights = RateLimitInsight.objects.filter(
            analysis_date__gte=since
        ).order_by('-analysis_date')
        
        if not insights:
            return {'message': 'No insights found for the specified period'}
        
        # Calculate averages and trends
        total_reports = sum(insight.total_abuse_reports for insight in insights)
        avg_reports = total_reports / len(insights)
        avg_risk = sum(insight.risk_score for insight in insights) / len(insights)
        
        # Risk trend
        recent_risk = insights.first().risk_score if insights.first() else 0
        older_risk = insights.last().risk_score if insights.last() else 0
        risk_trend = 'increasing' if recent_risk > older_risk else 'decreasing'
        
        return {
            'period_days': days,
            'insight_count': len(insights),
            'total_abuse_reports': total_reports,
            'average_daily_reports': round(avg_reports, 1),
            'average_risk_score': round(avg_risk, 1),
            'current_risk_score': recent_risk,
            'risk_trend': risk_trend,
            'latest_insight_date': insights.first().analysis_date if insights.first() else None,
            'insights': [
                {
                    'date': insight.analysis_date,
                    'total_reports': insight.total_abuse_reports,
                    'risk_score': insight.risk_score,
                    'blocked_ips': insight.blocked_ips,
                    'recommendations_count': len(insight.recommendations or [])
                }
                for insight in insights
            ]
        }
    
    def generate_weekly_report(self, week_start: datetime = None) -> Dict[str, Any]:
        """Generate comprehensive weekly abuse report."""
        if week_start is None:
            # Get start of current week (Monday)
            today = timezone.now().date()
            week_start = datetime.combine(
                today - timedelta(days=today.weekday()),
                datetime.min.time()
            )
        
        week_end = week_start + timedelta(days=7)
        
        # Generate insights for each day
        daily_insights = []
        current_date = week_start
        
        while current_date < week_end:
            try:
                insight = self.generate_daily_insights(current_date)
                daily_insights.append(insight)
            except Exception as e:
                self.logger.error(f"Error generating insight for {current_date}: {e}")
            current_date += timedelta(days=1)
        
        # Calculate weekly aggregates
        weekly_totals = {
            'total_reports': sum(insight.total_abuse_reports for insight in daily_insights),
            'total_blocked_ips': sum(insight.blocked_ips for insight in daily_insights),
            'avg_risk_score': sum(insight.risk_score for insight in daily_insights) / len(daily_insights) if daily_insights else 0,
            'high_risk_days': len([i for i in daily_insights if i.risk_score >= 60])
        }
        
        return {
            'week_start': week_start,
            'week_end': week_end,
            'daily_insights': daily_insights,
            'weekly_totals': weekly_totals,
            'recommendations': self._generate_weekly_recommendations(daily_insights)
        }
    
    def _generate_weekly_recommendations(self, daily_insights: List[RateLimitInsight]) -> List[Dict[str, Any]]:
        """Generate recommendations based on weekly insights."""
        recommendations = []
        
        if not daily_insights:
            return recommendations
        
        # Analyze risk trends
        risk_scores = [insight.risk_score for insight in daily_insights]
        avg_risk = sum(risk_scores) / len(risk_scores)
        
        if avg_risk > 60:
            recommendations.append({
                'type': 'weekly_high_risk',
                'priority': 'high',
                'title': 'High Weekly Risk Average',
                'description': f"Average risk score this week: {avg_risk:.1f}",
                'action_items': [
                    'Review all blocking rules',
                    'Consider increasing monitoring resources',
                    'Schedule security review meeting'
                ]
            })
        
        # Check for persistent offenders
        all_offenders = []
        for insight in daily_insights:
            if insight.metadata and 'pattern_analysis' in insight.metadata:
                all_offenders.extend(insight.metadata['pattern_analysis'].get('high_risk_ips', []))
        
        if len(all_offenders) > 20:
            recommendations.append({
                'type': 'persistent_offenders',
                'priority': 'critical',
                'title': 'High Number of Persistent Offenders',
                'description': f"Found {len(all_offenders)} high-risk IPs this week.",
                'action_items': [
                    'Consider permanent blocking for repeat offenders',
                    'Implement IP reputation checking',
                    'Review authentication mechanisms'
                ]
            })
        
        return recommendations
