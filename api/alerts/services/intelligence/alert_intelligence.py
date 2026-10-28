"""
Alert Intelligence Service - Provides AI-powered alert analysis and predictions
"""
import logging
import json
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple
from django.db import transaction
from django.utils import timezone as django_tz
from django.core.cache import cache
from django.db.models import Count, Avg, StdDev, Q, F, Window
from django.db.models.functions import TruncHour, TruncDay, Lag
from django.contrib.auth import get_user_model

from api.alerts.models.core import AlertLog, AlertRule, Notification
from api.alerts.models.intelligence import (
    AlertPrediction, AnomalyDetectionModel
)

logger = logging.getLogger(__name__)
User = get_user_model()


class AlertIntelligence:
    """Provides AI-powered alert analysis and predictions"""
    
    def __init__(self):
        self.cache_timeout = 3600  # 1 hour
        self.prediction_cache_key = "alert_predictions"
        self.anomaly_cache_key = "anomaly_detections"
    
    def analyze_alert_patterns(self, alert_rule: AlertRule, time_period: int = 30) -> Dict[str, Any]:
        """
        Analyze alert patterns for a specific rule
        
        Args:
            alert_rule: Alert rule to analyze
            time_period: Time period in days
        
        Returns:
            Dictionary with pattern analysis results
        """
        try:
            start_date = django_tz.now() - timedelta(days=time_period)
            
            # Get alert logs for the rule
            alerts = AlertLog.objects.filter(
                rule=alert_rule,
                triggered_at__gte=start_date
            ).order_by('triggered_at')
            
            if not alerts.exists():
                return {
                    'pattern_detected': False,
                    'message': 'Insufficient data for pattern analysis',
                    'data_points': 0
                }
            
            # Analyze temporal patterns
            temporal_analysis = self._analyze_temporal_patterns(alerts)
            
            # Analyze value patterns
            value_analysis = self._analyze_value_patterns(alerts)
            
            # Analyze frequency patterns
            frequency_analysis = self._analyze_frequency_patterns(alerts)
            
            # Detect anomalies
            anomalies = self._detect_anomalies(alerts)
            
            # Generate predictions
            predictions = self._generate_predictions(alert_rule, alerts)
            
            result = {
                'pattern_detected': True,
                'data_points': alerts.count(),
                'time_period_days': time_period,
                'temporal_analysis': temporal_analysis,
                'value_analysis': value_analysis,
                'frequency_analysis': frequency_analysis,
                'anomalies': anomalies,
                'predictions': predictions,
                'analysis_timestamp': django_tz.now().isoformat()
            }
            
            # Cache the analysis
            cache_key = f"pattern_analysis_{alert_rule.id}"
            cache.set(cache_key, result, self.cache_timeout)
            
            return result
            
        except Exception as e:
            logger.error(f"Error analyzing alert patterns for rule {alert_rule.id}: {e}")
            return {
                'pattern_detected': False,
                'error': 'Operation failed',
                'data_points': 0
            }
    
    def predict_alert_probability(self, alert_rule: AlertRule, 
                                time_window: int = 24) -> Dict[str, Any]:
        """
        Predict the probability of an alert occurring in the next time window
        
        Args:
            alert_rule: Alert rule to predict for
            time_window: Time window in hours
        
        Returns:
            Dictionary with prediction results
        """
        try:
            # Get historical data
            historical_data = self._get_historical_alert_data(alert_rule, days=30)
            
            if len(historical_data) < 10:
                return {
                    'prediction_available': False,
                    'message': 'Insufficient historical data for prediction',
                    'data_points': len(historical_data)
                }
            
            # Calculate base probability
            base_probability = self._calculate_base_probability(historical_data, time_window)
            
            # Apply seasonal adjustments
            seasonal_adjustment = self._apply_seasonal_adjustment(
                historical_data, base_probability, time_window
            )
            
            # Apply trend adjustments
            trend_adjustment = self._apply_trend_adjustment(historical_data, seasonal_adjustment)
            
            # Calculate confidence interval
            confidence_interval = self._calculate_confidence_interval(
                historical_data, trend_adjustment
            )
            
            # Create prediction record
            prediction = AlertPrediction.objects.create(
                rule=alert_rule,
                prediction_type='probability',
                predicted_value=trend_adjustment,
                confidence_level=confidence_interval['confidence'],
                confidence_interval_low=confidence_interval['low'],
                confidence_interval_high=confidence_interval['high'],
                time_window_hours=time_window,
                training_status='completed',
                last_trained=django_tz.now(),
                tenant=alert_rule.tenant
            )
            
            result = {
                'prediction_available': True,
                'probability': trend_adjustment,
                'confidence_interval': confidence_interval,
                'time_window_hours': time_window,
                'data_points_used': len(historical_data),
                'prediction_id': prediction.id,
                'created_at': prediction.created_at.isoformat()
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Error predicting alert probability for rule {alert_rule.id}: {e}")
            return {
                'prediction_available': False,
                'error': 'Operation failed'
            }
    
    def detect_anomalies(self, alert_rule: AlertRule, 
                        sensitivity: float = 0.95) -> List[Dict[str, Any]]:
        """
        Detect anomalies in alert patterns
        
        Args:
            alert_rule: Alert rule to analyze
            sensitivity: Sensitivity threshold (0.5-1.0)
        
        Returns:
            List of detected anomalies
        """
        try:
            # Get recent alert data
            recent_alerts = AlertLog.objects.filter(
                rule=alert_rule,
                triggered_at__gte=django_tz.now() - timedelta(days=7)
            ).order_by('triggered_at')
            
            if recent_alerts.count() < 20:
                return []
            
            # Extract values for analysis
            values = [alert.trigger_value for alert in recent_alerts if alert.trigger_value is not None]
            
            if len(values) < 20:
                return []
            
            # Calculate statistical measures
            mean_val = sum(values) / len(values)
            variance = sum((x - mean_val) ** 2 for x in values) / len(values)
            std_dev = variance ** 0.5
            
            # Detect anomalies using statistical methods
            anomalies = []
            threshold = std_dev * sensitivity
            
            for i, alert in enumerate(recent_alerts):
                if alert.trigger_value is not None:
                    z_score = abs(alert.trigger_value - mean_val) / std_dev if std_dev > 0 else 0
                    
                    if z_score > sensitivity:
                        anomalies.append({
                            'alert_id': alert.id,
                            'triggered_at': alert.triggered_at.isoformat(),
                            'trigger_value': alert.trigger_value,
                            'z_score': z_score,
                            'anomaly_type': 'statistical_outlier',
                            'severity': 'high' if z_score > 3 else 'medium'
                        })
            
            # Detect pattern anomalies
            pattern_anomalies = self._detect_pattern_anomalies(recent_alerts)
            anomalies.extend(pattern_anomalies)
            
            # Sort by severity and timestamp
            anomalies.sort(key=lambda x: (x['severity'], x['triggered_at']), reverse=True)
            
            return anomalies
            
        except Exception as e:
            logger.error(f"Error detecting anomalies for rule {alert_rule.id}: {e}")
            return []
    
    def recommend_threshold_adjustment(self, alert_rule: AlertRule) -> Dict[str, Any]:
        """
        Recommend threshold adjustments based on historical data
        
        Args:
            alert_rule: Alert rule to analyze
        
        Returns:
            Dictionary with threshold recommendations
        """
        try:
            # Get alert history
            alerts = AlertLog.objects.filter(
                rule=alert_rule,
                triggered_at__gte=django_tz.now() - timedelta(days=30)
            ).order_by('triggered_at')
            
            if alerts.count() < 20:
                return {
                    'recommendation_available': False,
                    'message': 'Insufficient data for threshold recommendation',
                    'data_points': alerts.count()
                }
            
            # Analyze current threshold performance
            current_threshold = alert_rule.threshold_value
            trigger_values = [alert.trigger_value for alert in alerts if alert.trigger_value is not None]
            
            if not trigger_values:
                return {
                    'recommendation_available': False,
                    'message': 'No trigger values available for analysis',
                    'data_points': 0
                }
            
            # Calculate statistics
            mean_val = sum(trigger_values) / len(trigger_values)
            std_dev = (sum((x - mean_val) ** 2 for x in trigger_values) / len(trigger_values)) ** 0.5
            
            # Calculate false positive rate
            false_positives = alerts.filter(
                trigger_value__lt=current_threshold
            ).count()
            false_positive_rate = false_positives / alerts.count()
            
            # Calculate optimal threshold
            optimal_threshold = self._calculate_optimal_threshold(trigger_values, current_threshold)
            
            # Generate recommendation
            if abs(optimal_threshold - current_threshold) / current_threshold > 0.1:
                recommendation = 'adjust'
                reason = f'Statistical analysis suggests threshold should be adjusted by {abs(optimal_threshold - current_threshold) / current_threshold * 100:.1f}%'
            elif false_positive_rate > 0.3:
                recommendation = 'increase'
                reason = f'High false positive rate ({false_positive_rate * 100:.1f}%) suggests increasing threshold'
            elif false_positive_rate < 0.05:
                recommendation = 'decrease'
                reason = f'Low false positive rate ({false_positive_rate * 100:.1f}%) suggests decreasing threshold for better sensitivity'
            else:
                recommendation = 'maintain'
                reason = 'Current threshold appears optimal'
            
            result = {
                'recommendation_available': True,
                'current_threshold': current_threshold,
                'recommended_threshold': optimal_threshold,
                'recommendation': recommendation,
                'reason': reason,
                'false_positive_rate': false_positive_rate,
                'mean_trigger_value': mean_val,
                'std_deviation': std_dev,
                'data_points_analyzed': len(trigger_values),
                'confidence': self._calculate_recommendation_confidence(len(trigger_values))
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Error generating threshold recommendation for rule {alert_rule.id}: {e}")
            return {
                'recommendation_available': False,
                'error': 'Operation failed'
            }
    
    def create_intelligence_report(self, tenant=None, time_period: int = 30) -> Dict[str, Any]:
        """
        Create a comprehensive intelligence report
        
        Args:
            tenant: Optional tenant filter
            time_period: Time period in days
        
        Returns:
            Dictionary with intelligence report
        """
        try:
            start_date = django_tz.now() - timedelta(days=time_period)
            
            # Get all alert rules
            rules = AlertRule.objects.filter(is_active=True)
            if tenant:
                rules = rules.filter(tenant=tenant)
            
            # Analyze each rule
            rule_analyses = []
            for rule in rules:
                analysis = self.analyze_alert_patterns(rule, time_period)
                if analysis.get('pattern_detected'):
                    rule_analyses.append({
                        'rule_id': rule.id,
                        'rule_name': rule.name,
                        'rule_severity': rule.severity,
                        'analysis': analysis
                    })
            
            # Get overall statistics
            overall_stats = self._get_overall_intelligence_stats(start_date, tenant)
            
            # Get top anomalies
            top_anomalies = self._get_top_anomalies(start_date, tenant)
            
            # Get predictions summary
            predictions_summary = self._get_predictions_summary(time_period, tenant)
            
            report = {
                'report_generated_at': django_tz.now().isoformat(),
                'time_period_days': time_period,
                'tenant': str(tenant) if tenant else 'all',
                'overall_statistics': overall_stats,
                'rule_analyses': rule_analyses,
                'top_anomalies': top_anomalies,
                'predictions_summary': predictions_summary,
                'summary': {
                    'total_rules_analyzed': len(rule_analyses),
                    'patterns_detected': len([r for r in rule_analyses if r['analysis'].get('pattern_detected')]),
                    'anomalies_detected': len(top_anomalies),
                    'predictions_generated': predictions_summary.get('total_predictions', 0)
                }
            }
            
            return report
            
        except Exception as e:
            logger.error(f"Error creating intelligence report: {e}")
            return {
                'error': 'Operation failed',
                'report_generated_at': django_tz.now().isoformat()
            }
    
    def _analyze_temporal_patterns(self, alerts) -> Dict[str, Any]:
        """Analyze temporal patterns in alerts"""
        try:
            # Group by hour of day
            hourly_counts = {}
            for alert in alerts:
                hour = alert.triggered_at.hour
                hourly_counts[hour] = hourly_counts.get(hour, 0) + 1
            
            # Group by day of week
            daily_counts = {}
            for alert in alerts:
                day = alert.triggered_at.weekday()
                daily_counts[day] = daily_counts.get(day, 0) + 1
            
            # Find peak hours and days
            peak_hour = max(hourly_counts, key=hourly_counts.get) if hourly_counts else None
            peak_day = max(daily_counts, key=daily_counts.get) if daily_counts else None
            
            return {
                'hourly_distribution': hourly_counts,
                'daily_distribution': daily_counts,
                'peak_hour': peak_hour,
                'peak_day': peak_day,
                'has_temporal_pattern': len(set(hourly_counts.values())) > 1
            }
        except Exception as e:
            logger.error(f"Error analyzing temporal patterns: {e}")
            return {}
    
    def _analyze_value_patterns(self, alerts) -> Dict[str, Any]:
        """Analyze value patterns in alerts"""
        try:
            values = [alert.trigger_value for alert in alerts if alert.trigger_value is not None]
            
            if not values:
                return {}
            
            mean_val = sum(values) / len(values)
            variance = sum((x - mean_val) ** 2 for x in values) / len(values)
            std_dev = variance ** 0.5
            
            return {
                'mean': mean_val,
                'median': sorted(values)[len(values) // 2],
                'std_deviation': std_dev,
                'min_value': min(values),
                'max_value': max(values),
                'trend': self._calculate_trend(values)
            }
        except Exception as e:
            logger.error(f"Error analyzing value patterns: {e}")
            return {}
    
    def _analyze_frequency_patterns(self, alerts) -> Dict[str, Any]:
        """Analyze frequency patterns in alerts"""
        try:
            # Calculate alerts per day
            daily_counts = {}
            for alert in alerts:
                date = alert.triggered_at.date()
                daily_counts[date] = daily_counts.get(date, 0) + 1
            
            if not daily_counts:
                return {}
            
            avg_frequency = sum(daily_counts.values()) / len(daily_counts)
            max_frequency = max(daily_counts.values())
            
            return {
                'average_daily_frequency': avg_frequency,
                'maximum_daily_frequency': max_frequency,
                'frequency_variance': sum((x - avg_frequency) ** 2 for x in daily_counts.values()) / len(daily_counts),
                'days_with_alerts': len(daily_counts),
                'total_days': (alerts.last().triggered_at.date() - alerts.first().triggered_at.date()).days + 1
            }
        except Exception as e:
            logger.error(f"Error analyzing frequency patterns: {e}")
            return {}
    
    def _detect_anomalies(self, alerts) -> List[Dict[str, Any]]:
        """Detect anomalies in alert data"""
        # This is a simplified anomaly detection
        # In a real implementation, you'd use more sophisticated algorithms
        return []
    
    def _generate_predictions(self, alert_rule: AlertRule, alerts) -> Dict[str, Any]:
        """Generate predictions for future alerts"""
        # This is a simplified prediction
        # In a real implementation, you'd use machine learning models
        return {
            'next_alert_probability': 0.5,
            'confidence': 0.3,
            'prediction_horizon_hours': 24
        }
    
    def _get_historical_alert_data(self, alert_rule: AlertRule, days: int) -> List[float]:
        """Get historical alert data for prediction"""
        try:
            start_date = django_tz.now() - timedelta(days=days)
            alerts = AlertLog.objects.filter(
                rule=alert_rule,
                triggered_at__gte=start_date
            ).order_by('triggered_at')
            
            return [1.0 for _ in alerts]  # Simplified - return occurrence indicators
        except Exception as e:
            logger.error(f"Error getting historical alert data: {e}")
            return []
    
    def _calculate_base_probability(self, historical_data: List[float], time_window: int) -> float:
        """Calculate base probability of alert occurrence"""
        if not historical_data:
            return 0.0
        
        # Simplified calculation
        return sum(historical_data) / len(historical_data)
    
    def _apply_seasonal_adjustment(self, historical_data: List[float], 
                                  base_probability: float, time_window: int) -> float:
        """Apply seasonal adjustments to probability"""
        # Simplified seasonal adjustment
        return base_probability
    
    def _apply_trend_adjustment(self, historical_data: List[float], 
                              adjusted_probability: float) -> float:
        """Apply trend adjustments to probability"""
        # Simplified trend adjustment
        return adjusted_probability
    
    def _calculate_confidence_interval(self, historical_data: List[float], 
                                      probability: float) -> Dict[str, Any]:
        """Calculate confidence interval for predictions"""
        # Simplified confidence interval
        margin = 0.1  # 10% margin
        return {
            'confidence': 0.8,
            'low': max(0.0, probability - margin),
            'high': min(1.0, probability + margin)
        }
    
    def _detect_pattern_anomalies(self, alerts) -> List[Dict[str, Any]]:
        """Detect pattern-based anomalies"""
        # Simplified pattern anomaly detection
        return []
    
    def _calculate_optimal_threshold(self, values: List[float], current_threshold: float) -> float:
        """Calculate optimal threshold based on statistical analysis"""
        if not values:
            return current_threshold
        
        mean_val = sum(values) / len(values)
        std_dev = (sum((x - mean_val) ** 2 for x in values) / len(values)) ** 0.5
        
        # Use mean + 2 standard deviations as optimal threshold
        return mean_val + (2 * std_dev)
    
    def _calculate_recommendation_confidence(self, data_points: int) -> float:
        """Calculate confidence level for recommendations"""
        # More data points = higher confidence
        if data_points < 20:
            return 0.3
        elif data_points < 50:
            return 0.6
        elif data_points < 100:
            return 0.8
        else:
            return 0.9
    
    def _calculate_trend(self, values: List[float]) -> str:
        """Calculate trend in values"""
        if len(values) < 2:
            return 'insufficient_data'
        
        # Simple linear trend calculation
        first_half = values[:len(values)//2]
        second_half = values[len(values)//2:]
        
        first_avg = sum(first_half) / len(first_half)
        second_avg = sum(second_half) / len(second_half)
        
        if second_avg > first_avg * 1.1:
            return 'increasing'
        elif second_avg < first_avg * 0.9:
            return 'decreasing'
        else:
            return 'stable'
    
    def _get_overall_intelligence_stats(self, start_date, tenant) -> Dict[str, Any]:
        """Get overall intelligence statistics"""
        try:
            alerts = AlertLog.objects.filter(triggered_at__gte=start_date)
            if tenant:
                alerts = alerts.filter(tenant=tenant)
            
            return {
                'total_alerts': alerts.count(),
                'unique_rules': alerts.values('rule').distinct().count(),
                'alerts_per_day': alerts.count() / max(1, (django_tz.now() - start_date).days),
                'most_active_rule': self._get_most_active_rule(alerts),
                'average_severity': self._get_average_severity(alerts)
            }
        except Exception as e:
            logger.error(f"Error getting overall intelligence stats: {e}")
            return {}
    
    def _get_top_anomalies(self, start_date, tenant) -> List[Dict[str, Any]]:
        """Get top anomalies detected"""
        # Simplified - return empty list for now
        return []
    
    def _get_predictions_summary(self, time_period: int, tenant) -> Dict[str, Any]:
        """Get predictions summary"""
        try:
            predictions = AlertPrediction.objects.filter(
                created_at__gte=django_tz.now() - timedelta(days=time_period)
            )
            if tenant:
                predictions = predictions.filter(tenant=tenant)
            
            return {
                'total_predictions': predictions.count(),
                'average_confidence': predictions.aggregate(
                    avg_confidence=Avg('confidence_level')
                )['avg_confidence'] or 0.0,
                'prediction_types': predictions.values('prediction_type').annotate(
                    count=Count('id')
                ).order_by('-count')
            }
        except Exception as e:
            logger.error(f"Error getting predictions summary: {e}")
            return {}
    
    def _get_most_active_rule(self, alerts) -> Optional[str]:
        """Get the most active alert rule"""
        try:
            result = alerts.values('rule__name').annotate(
                count=Count('id')
            ).order_by('-count').first()
            return result['rule__name'] if result else None
        except Exception as e:
            logger.error(f"Error getting most active rule: {e}")
            return None
    
    def _get_average_severity(self, alerts) -> Optional[str]:
        """Get average severity of alerts"""
        try:
            severity_counts = alerts.values('rule__severity').annotate(
                count=Count('id')
            ).order_by('-count')
            
            if not severity_counts:
                return None
            
            # Return the most common severity
            return severity_counts[0]['rule__severity']
        except Exception as e:
            logger.error(f"Error getting average severity: {e}")
            return None
