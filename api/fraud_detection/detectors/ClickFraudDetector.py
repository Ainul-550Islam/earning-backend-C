from .BaseDetector import BaseDetector
from django.db.models import Count, Q, F, Window, Sum, Avg
from django.db.models.functions import TruncMinute, TruncHour, TruncDay
from django.utils import timezone
from datetime import timedelta, datetime
import math
import statistics
import logging
from typing import Dict, List, Any, Tuple
import numpy as np
from scipy import stats

logger = logging.getLogger(__name__)

class ClickFraudDetector(BaseDetector):
    """
    Advanced click fraud detection for offerwalls and ad networks
    Detects click farms, bots, and fraudulent click patterns
    """
    
    def __init__(self, config: Dict = None):
        super().__init__(config)
        
        # Configuration
        self.anomaly_threshold = config.get('anomaly_threshold', 3.0) if config else 3.0
        self.velocity_threshold = config.get('velocity_threshold', 100) if config else 100
        self.pattern_similarity_threshold = config.get('pattern_similarity_threshold', 0.8) if config else 0.8
        self.min_clicks_for_analysis = config.get('min_clicks_for_analysis', 10) if config else 10
        
        # Behavioral pattern weights
        self.weights = {
            'velocity': 30,
            'regularity': 25,
            'distribution': 20,
            'conversion': 15,
            'device': 10
        }
        
    def get_required_fields(self) -> List[str]:
        return ['user_id', 'click_data']
    
    def detect(self, data: Dict) -> Dict:
        """
        Detect click fraud patterns
        """
        try:
            user_id = data.get('user_id')
            click_data = data.get('click_data', {})
            offer_id = data.get('offer_id')
            
            if not self.validate_data(data):
                return self.get_detection_result()
            
            # Get user's click history
            click_history = self._get_user_click_history(user_id, offer_id)
            
            # Perform detection checks
            checks = [
                self._check_click_velocity(click_history, click_data),
                self._check_temporal_patterns(click_history),
                self._check_click_distribution(click_history),
                self._check_conversion_patterns(user_id, offer_id),
                self._check_device_patterns(user_id, click_data),
                self._check_geographic_patterns(user_id),
                self._check_bot_patterns(click_history)
            ]
            
            # Calculate overall score
            self._calculate_overall_score(checks)
            
            # Advanced ML detection (if enough data)
            if len(click_history) >= self.min_clicks_for_analysis:
                ml_checks = self._perform_ml_analysis(click_history)
                checks.extend(ml_checks)
                
                # Update score with ML results
                self._update_with_ml_results(ml_checks)
            
            # Set detection result
            self.detected_fraud = self.fraud_score >= 65
            
            # Calculate confidence
            self.confidence = self._calculate_confidence(checks)
            
            # Add evidence
            self._compile_evidence(checks, click_history)
            
            # Log detection
            self.log_detection(user_id)
            
            return self.get_detection_result()
            
        except Exception as e:
            logger.error(f"Error in ClickFraudDetector: {str(e)}")
            return {
                'detector': self.detector_name,
                'is_fraud': False,
                'fraud_score': 0,
                'confidence': 0,
                'error': str(e)
            }
    
    def _get_user_click_history(self, user_id: int, offer_id: str = None) -> List[Dict]:
        """
        Get user's click history from database
        """
        try:
            from offerwall.models import OfferClick
            
            filters = {'user_id': user_id}
            if offer_id:
                filters['offer_id'] = offer_id
            
            # Get clicks from last 30 days
            thirty_days_ago = timezone.now() - timedelta(days=30)
            filters['created_at__gte'] = thirty_days_ago
            
            clicks = OfferClick.objects.filter(**filters).order_by('created_at')
            
            click_history = []
            for click in clicks:
                click_history.append({
                    'id': click.id,
                    'offer_id': click.offer_id,
                    'click_time': click.created_at,
                    'ip_address': click.ip_address,
                    'user_agent': click.user_agent,
                    'device_id': click.device_id,
                    'referrer': click.referrer,
                    'is_converted': click.is_converted,
                    'conversion_time': click.conversion_time,
                    'revenue': float(click.revenue) if click.revenue else 0,
                    'payout': float(click.payout) if click.payout else 0
                })
            
            return click_history
            
        except Exception as e:
            logger.error(f"Error getting click history: {e}")
            return []
    
    def _check_click_velocity(self, click_history: List[Dict], current_click: Dict) -> Dict:
        """
        Check click velocity (clicks per time unit)
        """
        result = {
            'check': 'click_velocity',
            'total_clicks': len(click_history),
            'time_periods': {},
            'velocity_scores': {},
            'anomalies': [],
            'risk_score': 0
        }
        
        if len(click_history) < 5:
            result['insufficient_data'] = True
            return result
        
        # Analyze velocity in different time windows
        time_windows = {
            'per_minute': timedelta(minutes=1),
            'per_hour': timedelta(hours=1),
            'per_day': timedelta(days=1),
            'per_week': timedelta(weeks=1)
        }
        
        for window_name, window_size in time_windows.items():
            # Group clicks by time window
            window_counts = {}
            
            for click in click_history:
                click_time = click['click_time']
                window_start = click_time - (click_time - datetime.min) % window_size
                window_key = window_start.isoformat()
                
                window_counts[window_key] = window_counts.get(window_key, 0) + 1
            
            # Calculate statistics
            if window_counts:
                counts = list(window_counts.values())
                avg_count = statistics.mean(counts)
                max_count = max(counts)
                std_dev = statistics.stdev(counts) if len(counts) > 1 else 0
                
                result['time_periods'][window_name] = {
                    'average': avg_count,
                    'maximum': max_count,
                    'std_dev': std_dev,
                    'count': len(counts)
                }
                
                # Detect anomalies
                z_scores = []
                for count in counts:
                    if std_dev > 0:
                        z_score = (count - avg_count) / std_dev
                        z_scores.append(abs(z_score))
                        
                        if abs(z_score) > self.anomaly_threshold:
                            result['anomalies'].append(f"High {window_name} velocity: {count} clicks (z-score: {z_score:.2f})")
                
                # Calculate velocity risk score
                velocity_risk = 0
                
                # High average velocity
                if avg_count > self.velocity_threshold:
                    velocity_risk += 30
                
                # High maximum velocity
                if max_count > self.velocity_threshold * 3:
                    velocity_risk += 25
                
                # High variance
                if std_dev > avg_count * 0.5:
                    velocity_risk += 15
                
                result['velocity_scores'][window_name] = min(100, velocity_risk)
        
        # Overall velocity risk score
        if result['velocity_scores']:
            result['risk_score'] = max(result['velocity_scores'].values())
        
        # Add reasons for high risk
        if result['risk_score'] >= 30:
            for anomaly in result['anomalies'][:3]:  # Limit to top 3 anomalies
                self.add_reason(anomaly, 10)
        
        return result
    
    def _check_temporal_patterns(self, click_history: List[Dict]) -> Dict:
        """
        Check for unnatural temporal patterns
        """
        result = {
            'check': 'temporal_patterns',
            'hourly_distribution': {},
            'daily_patterns': {},
            'interval_analysis': {},
            'risk_score': 0,
            'patterns_detected': []
        }
        
        if len(click_history) < 10:
            result['insufficient_data'] = True
            return result
        
        # Analyze hourly distribution
        hourly_counts = {}
        for click in click_history:
            hour = click['click_time'].hour
            hourly_counts[hour] = hourly_counts.get(hour, 0) + 1
        
        result['hourly_distribution'] = hourly_counts
        
        # Check for 24/7 activity (unnatural for humans)
        active_hours = len([h for h, count in hourly_counts.items() if count > 0])
        if active_hours >= 20:  # Active 20+ hours per day
            result['risk_score'] += 25
            result['patterns_detected'].append('24/7 activity pattern detected')
            self.add_reason("Unnatural 24/7 click activity", 25)
        
        # Analyze click intervals
        intervals = []
        for i in range(1, len(click_history)):
            interval = (click_history[i]['click_time'] - click_history[i-1]['click_time']).total_seconds()
            intervals.append(interval)
        
        if intervals:
            result['interval_analysis'] = {
                'min': min(intervals),
                'max': max(intervals),
                'mean': statistics.mean(intervals),
                'median': statistics.median(intervals),
                'std_dev': statistics.stdev(intervals) if len(intervals) > 1 else 0
            }
            
            # Check for robotic intervals (too consistent)
            if result['interval_analysis']['std_dev'] < 1.0 and len(intervals) > 5:
                result['risk_score'] += 30
                result['patterns_detected'].append('Robotic interval pattern detected')
                self.add_reason("Highly consistent click intervals (robotic pattern)", 30)
            
            # Check for burst patterns
            burst_threshold = 1.0  # 1 second between clicks
            burst_count = sum(1 for interval in intervals if interval <= burst_threshold)
            burst_percentage = (burst_count / len(intervals)) * 100
            
            if burst_percentage > 30:
                result['risk_score'] += 20
                result['patterns_detected'].append(f"High burst activity: {burst_percentage:.1f}%")
                self.add_reason(f"High burst click activity ({burst_percentage:.1f}%)", 20)
        
        # Analyze day of week patterns
        weekday_counts = {}
        for click in click_history:
            weekday = click['click_time'].weekday()
            weekday_counts[weekday] = weekday_counts.get(weekday, 0) + 1
        
        # Check for uniform distribution (unnatural)
        if len(weekday_counts) >= 6:
            counts = list(weekday_counts.values())
            cv = statistics.stdev(counts) / statistics.mean(counts) if statistics.mean(counts) > 0 else 0
            
            if cv < 0.2:  # Very uniform distribution
                result['risk_score'] += 15
                result['patterns_detected'].append('Unnatural uniform weekly distribution')
                self.add_reason("Unnaturally uniform weekly click pattern", 15)
        
        result['risk_score'] = min(100, result['risk_score'])
        
        return result
    
    def _check_click_distribution(self, click_history: List[Dict]) -> Dict:
        """
        Check distribution of clicks across offers/ads
        """
        result = {
            'check': 'click_distribution',
            'offer_distribution': {},
            'concentration_metrics': {},
            'risk_score': 0,
            'issues': []
        }
        
        if len(click_history) < 5:
            result['insufficient_data'] = True
            return result
        
        # Analyze distribution across offers
        offer_counts = {}
        for click in click_history:
            offer_id = click.get('offer_id', 'unknown')
            offer_counts[offer_id] = offer_counts.get(offer_id, 0) + 1
        
        result['offer_distribution'] = offer_counts
        
        # Calculate concentration metrics
        total_clicks = len(click_history)
        unique_offers = len(offer_counts)
        
        # Herfindahl-Hirschman Index (HHI) for concentration
        hhi = 0
        for count in offer_counts.values():
            share = count / total_clicks
            hhi += share * share
        
        result['concentration_metrics'] = {
            'total_clicks': total_clicks,
            'unique_offers': unique_offers,
            'hhi_index': hhi,
            'max_share': max(offer_counts.values()) / total_clicks if total_clicks > 0 else 0
        }
        
        # Evaluate concentration risk
        risk_score = 0
        
        # High concentration (clicking same offers repeatedly)
        if hhi > 0.5:  # Highly concentrated
            risk_score += 30
            result['issues'].append(f"High click concentration (HHI: {hhi:.3f})")
            self.add_reason(f"Highly concentrated clicks on few offers", 30)
        
        # Too many unique offers (spray pattern)
        if unique_offers > 50 and total_clicks < 100:
            risk_score += 25
            result['issues'].append(f"Suspicious spray pattern: {unique_offers} offers in {total_clicks} clicks")
            self.add_reason("Spray pattern: too many unique offers", 25)
        
        # Check for offer targeting patterns
        low_value_offers = self._identify_low_value_offers(offer_counts)
        if low_value_offers:
            risk_score += 15
            result['issues'].append(f"Focus on low-value offers: {low_value_offers}")
            self.add_reason("Focus on low-value/high-volume offers", 15)
        
        result['risk_score'] = min(100, risk_score)
        
        return result
    
    def _check_conversion_patterns(self, user_id: int, offer_id: str = None) -> Dict:
        """
        Check conversion patterns for fraud
        """
        result = {
            'check': 'conversion_patterns',
            'conversion_rate': 0,
            'conversion_timing': {},
            'revenue_patterns': {},
            'risk_score': 0,
            'anomalies': []
        }
        
        try:
            from offerwall.models import OfferClick, OfferCompletion
            
            # Get conversions
            conversion_filters = {'user_id': user_id, 'status': 'completed'}
            if offer_id:
                conversion_filters['offer_id'] = offer_id
            
            conversions = OfferCompletion.objects.filter(**conversion_filters)
            total_conversions = conversions.count()
            
            # Get clicks for same period
            click_filters = {'user_id': user_id}
            if offer_id:
                click_filters['offer_id'] = offer_id
            
            clicks = OfferClick.objects.filter(**click_filters)
            total_clicks = clicks.count()
            
            # Calculate conversion rate
            conversion_rate = (total_conversions / total_clicks * 100) if total_clicks > 0 else 0
            result['conversion_rate'] = conversion_rate
            
            # Analyze conversion timing
            if conversions.exists():
                conv_times = [conv.completed_at for conv in conversions]
                conv_intervals = []
                
                for i in range(1, len(conv_times)):
                    interval = (conv_times[i] - conv_times[i-1]).total_seconds()
                    conv_intervals.append(interval)
                
                if conv_intervals:
                    result['conversion_timing'] = {
                        'avg_interval': statistics.mean(conv_intervals),
                        'min_interval': min(conv_intervals),
                        'max_interval': max(conv_intervals)
                    }
                    
                    # Check for unnaturally fast conversions
                    fast_conversions = sum(1 for interval in conv_intervals if interval < 60)  # < 1 minute
                    if fast_conversions > 0:
                        result['risk_score'] += 20
                        result['anomalies'].append(f"{fast_conversions} conversions within 1 minute")
                        self.add_reason("Unnaturally fast conversions", 20)
            
            # Check conversion rate anomalies
            if conversion_rate > 80:  # Unrealistically high
                result['risk_score'] += 40
                result['anomalies'].append(f"Unrealistic conversion rate: {conversion_rate:.1f}%")
                self.add_reason(f"Unrealistically high conversion rate: {conversion_rate:.1f}%", 40)
            elif conversion_rate > 50:
                result['risk_score'] += 20
                result['anomalies'].append(f"High conversion rate: {conversion_rate:.1f}%")
                self.add_reason(f"High conversion rate: {conversion_rate:.1f}%", 20)
            
            # Check revenue patterns
            if conversions.exists():
                revenues = [float(conv.payout) for conv in conversions if conv.payout]
                if revenues:
                    result['revenue_patterns'] = {
                        'total': sum(revenues),
                        'average': statistics.mean(revenues),
                        'std_dev': statistics.stdev(revenues) if len(revenues) > 1 else 0
                    }
                    
                    # Check for round amounts (common in fraud)
                    round_revenues = sum(1 for rev in revenues if rev % 1 == 0)
                    round_percentage = (round_revenues / len(revenues)) * 100
                    
                    if round_percentage > 80:
                        result['risk_score'] += 15
                        result['anomalies'].append(f"High percentage of round revenue amounts: {round_percentage:.1f}%")
                        self.add_reason("High percentage of round revenue amounts", 15)
            
            result['risk_score'] = min(100, result['risk_score'])
            
            return result
            
        except Exception as e:
            logger.error(f"Error in conversion pattern check: {e}")
            return {'check': 'conversion_patterns', 'error': str(e), 'risk_score': 0}
    
    def _check_device_patterns(self, user_id: int, click_data: Dict) -> Dict:
        """
        Check device-related fraud patterns
        """
        result = {
            'check': 'device_patterns',
            'device_count': 0,
            'device_changes': 0,
            'user_agent_patterns': {},
            'risk_score': 0,
            'suspicious_patterns': []
        }
        
        try:
            from offerwall.models import OfferClick
            from ..models import DeviceFingerprint
            
            # Get user's devices
            devices = DeviceFingerprint.objects.filter(user_id=user_id)
            result['device_count'] = devices.count()
            
            # Get clicks with device info
            clicks = OfferClick.objects.filter(user_id=user_id).exclude(device_id__isnull=True)
            
            if clicks.exists():
                # Count unique devices
                unique_devices = clicks.values('device_id').distinct().count()
                result['unique_devices_in_clicks'] = unique_devices
                
                # Check for device switching during sessions
                device_switches = 0
                last_device = None
                
                for click in clicks.order_by('created_at'):
                    if last_device and click.device_id != last_device:
                        device_switches += 1
                    last_device = click.device_id
                
                result['device_changes'] = device_switches
                
                # Evaluate risk
                if unique_devices > 3:
                    result['risk_score'] += 25
                    result['suspicious_patterns'].append(f"Multiple devices used: {unique_devices}")
                    self.add_reason(f"Multiple devices used for clicking: {unique_devices}", 25)
                
                if device_switches > 5:
                    result['risk_score'] += 20
                    result['suspicious_patterns'].append(f"Frequent device switching: {device_switches} changes")
                    self.add_reason("Frequent device switching during sessions", 20)
            
            # Analyze user agent patterns
            user_agents = clicks.values('user_agent').annotate(count=Count('id')).order_by('-count')
            
            if user_agents.exists():
                result['user_agent_patterns'] = list(user_agents[:5])  # Top 5
                
                # Check for suspicious user agents
                suspicious_agents = ['headless', 'phantom', 'selenium', 'puppeteer', 'playwright', 'bot', 'crawler']
                
                for ua_data in result['user_agent_patterns']:
                    ua = ua_data['user_agent'].lower()
                    for suspicious in suspicious_agents:
                        if suspicious in ua:
                            result['risk_score'] += 30
                            result['suspicious_patterns'].append(f"Suspicious user agent: {ua[:50]}...")
                            self.add_reason("Suspicious/bot-like user agent detected", 30)
                            break
            
            result['risk_score'] = min(100, result['risk_score'])
            
            return result
            
        except Exception as e:
            logger.error(f"Error in device pattern check: {e}")
            return {'check': 'device_patterns', 'error': str(e), 'risk_score': 0}
    
    def _check_geographic_patterns(self, user_id: int) -> Dict:
        """
        Check geographic patterns for fraud
        """
        result = {
            'check': 'geographic_patterns',
            'ip_count': 0,
            'country_count': 0,
            'location_changes': 0,
            'risk_score': 0,
            'anomalies': []
        }
        
        try:
            from offerwall.models import OfferClick
            
            # Get clicks with IP info
            clicks = OfferClick.objects.filter(user_id=user_id).exclude(ip_address__isnull=True)
            
            if clicks.exists():
                # Count unique IPs
                unique_ips = clicks.values('ip_address').distinct().count()
                result['ip_count'] = unique_ips
                
                # Count unique countries (requires GeoIP lookup)
                # Simplified - in production, use GeoIP database
                
                # Check for impossible travel
                travel_anomalies = self._detect_impossible_travel(clicks)
                if travel_anomalies:
                    result['risk_score'] += 35
                    result['anomalies'].extend(travel_anomalies)
                    for anomaly in travel_anomalies[:2]:
                        self.add_reason(anomaly, 20)
                
                # Check for VPN/Proxy IPs
                vpn_proxy_count = 0
                for click in clicks:
                    # Check if IP is VPN/Proxy (simplified)
                    # In production, use VPNProxyDetector
                    pass
                
                if vpn_proxy_count > 0:
                    result['risk_score'] += 25
                    result['anomalies'].append(f"{vpn_proxy_count} clicks from VPN/Proxy IPs")
                    self.add_reason("Clicks from VPN/Proxy IPs", 25)
                
                # High IP diversity
                if unique_ips > 10:
                    result['risk_score'] += 20
                    result['anomalies'].append(f"High IP diversity: {unique_ips} unique IPs")
                    self.add_reason("Unusually high IP diversity", 20)
            
            result['risk_score'] = min(100, result['risk_score'])
            
            return result
            
        except Exception as e:
            logger.error(f"Error in geographic pattern check: {e}")
            return {'check': 'geographic_patterns', 'error': str(e), 'risk_score': 0}
    
    def _check_bot_patterns(self, click_history: List[Dict]) -> Dict:
        """
        Check for bot-like patterns
        """
        result = {
            'check': 'bot_patterns',
            'bot_indicators': [],
            'bot_score': 0,
            'risk_score': 0
        }
        
        if len(click_history) < 10:
            result['insufficient_data'] = True
            return result
        
        bot_score = 0
        indicators = []
        
        # 1. Check for perfect timing patterns
        if self._has_perfect_timing(click_history):
            bot_score += 30
            indicators.append("Perfect timing patterns detected")
            self.add_reason("Bot-like perfect timing patterns", 30)
        
        # 2. Check for lack of human variance
        if self._lacks_human_variance(click_history):
            bot_score += 25
            indicators.append("Lack of human variance in behavior")
            self.add_reason("Behavior lacks human variance", 25)
        
        # 3. Check for always-on activity
        if self._is_always_active(click_history):
            bot_score += 20
            indicators.append("24/7 activity pattern")
            self.add_reason("24/7 activity (bot-like pattern)", 20)
        
        # 4. Check for cookie-cutter patterns
        if self._has_cookie_cutter_patterns(click_history):
            bot_score += 25
            indicators.append("Cookie-cutter behavior patterns")
            self.add_reason("Repetitive cookie-cutter patterns", 25)
        
        result['bot_indicators'] = indicators
        result['bot_score'] = bot_score
        result['risk_score'] = min(100, bot_score)
        
        return result
    
    def _perform_ml_analysis(self, click_history: List[Dict]) -> List[Dict]:
        """
        Perform machine learning based analysis
        """
        results = []
        
        try:
            # Only perform if we have enough data
            if len(click_history) < self.min_clicks_for_analysis:
                return results
            
            # 1. Time series anomaly detection
            ts_anomalies = self._detect_time_series_anomalies(click_history)
            if ts_anomalies:
                results.append({
                    'check': 'ml_time_series',
                    'anomaly_count': ts_anomalies.get('anomaly_count', 0),
                    'risk_score': ts_anomalies.get('risk_score', 0)
                })
            
            # 2. Pattern clustering
            clusters = self._cluster_behavior_patterns(click_history)
            if clusters:
                results.append({
                    'check': 'ml_clustering',
                    'cluster_count': clusters.get('cluster_count', 0),
                    'risk_score': clusters.get('risk_score', 0)
                })
            
            # 3. Predictive model scoring
            prediction = self._predict_fraud_probability(click_history)
            if prediction:
                results.append({
                    'check': 'ml_prediction',
                    'fraud_probability': prediction.get('probability', 0),
                    'risk_score': prediction.get('risk_score', 0)
                })
            
        except Exception as e:
            logger.error(f"Error in ML analysis: {e}")
        
        return results
    
    def _calculate_overall_score(self, checks: List[Dict]):
        """
        Calculate overall fraud score
        """
        weighted_scores = []
        
        for check in checks:
            check_name = check.get('check', '')
            risk_score = check.get('risk_score', 0)
            
            # Apply weight based on check type
            weight = self.weights.get(check_name.split('_')[0], 10)  # Get base check type
            
            weighted_score = risk_score * (weight / 100)
            weighted_scores.append(weighted_score)
        
        if weighted_scores:
            # Take weighted average
            self.fraud_score = min(100, int(sum(weighted_scores) / len(weighted_scores)))
        
        # Adjust based on number of anomalies
        total_anomalies = sum(len(check.get('anomalies', [])) for check in checks)
        if total_anomalies >= 5:
            self.fraud_score = min(100, self.fraud_score + 15)
        elif total_anomalies >= 3:
            self.fraud_score = min(100, self.fraud_score + 10)
    
    def _update_with_ml_results(self, ml_checks: List[Dict]):
        """
        Update score with ML analysis results
        """
        if not ml_checks:
            return
        
        ml_risk_scores = [check.get('risk_score', 0) for check in ml_checks]
        if ml_risk_scores:
            ml_avg = sum(ml_risk_scores) / len(ml_risk_scores)
            
            # Blend ML score with existing score
            self.fraud_score = int((self.fraud_score * 0.6) + (ml_avg * 0.4))
    
    def _calculate_confidence(self, checks: List[Dict]) -> int:
        """
        Calculate confidence in detection
        """
        confidence_factors = []
        
        # Data volume factor
        total_clicks = sum(check.get('total_clicks', 0) for check in checks)
        if total_clicks >= 100:
            confidence_factors.append(80)
        elif total_clicks >= 50:
            confidence_factors.append(60)
        elif total_clicks >= 20:
            confidence_factors.append(40)
        else:
            confidence_factors.append(20)
        
        # Consistency factor
        high_risk_checks = sum(1 for check in checks if check.get('risk_score', 0) >= 40)
        if high_risk_checks >= 3:
            confidence_factors.append(75)
        elif high_risk_checks >= 2:
            confidence_factors.append(50)
        
        # ML confirmation factor
        ml_checks = [check for check in checks if check.get('check', '').startswith('ml_')]
        if ml_checks:
            confidence_factors.append(65)
        
        if confidence_factors:
            return min(100, int(sum(confidence_factors) / len(confidence_factors)))
        
        return 50
    
    def _compile_evidence(self, checks: List[Dict], click_history: List[Dict]):
        """
        Compile evidence from all checks
        """
        self.add_evidence('total_checks_performed', len(checks))
        self.add_evidence('total_clicks_analyzed', len(click_history))
        
        for check in checks:
            check_name = check.get('check', 'unknown')
            risk_score = check.get('risk_score', 0)
            
            if risk_score > 20:
                self.add_evidence(f'{check_name}_score', risk_score)
                self.add_evidence(f'{check_name}_details', {
                    k: v for k, v in check.items() 
                    if k not in ['check', 'risk_score'] and not isinstance(v, (list, dict)) or k in ['anomalies', 'patterns_detected']
                })
    
    def _identify_low_value_offers(self, offer_counts: Dict) -> List[str]:
        """
        Identify low-value/high-volume offers
        """
        # In production, this would check offer payout values
        # For now, return empty list
        return []
    
    def _detect_impossible_travel(self, clicks) -> List[str]:
        """
        Detect impossible travel between clicks
        """
        # In production, implement GeoIP-based travel detection
        return []
    
    def _has_perfect_timing(self, click_history: List[Dict]) -> bool:
        """
        Check for perfect timing patterns (robotic)
        """
        if len(click_history) < 10:
            return False
        
        intervals = []
        for i in range(1, len(click_history)):
            interval = (click_history[i]['click_time'] - click_history[i-1]['click_time']).total_seconds()
            intervals.append(interval)
        
        if len(intervals) > 5:
            # Check for very low variance
            variance = statistics.variance(intervals) if len(intervals) > 1 else 0
            return variance < 0.1  # Less than 0.1 second variance
        
        return False
    
    def _lacks_human_variance(self, click_history: List[Dict]) -> bool:
        """
        Check if behavior lacks human variance
        """
        if len(click_history) < 15:
            return False
        
        # Analyze multiple dimensions
        metrics = []
        
        # 1. Interval variance
        intervals = []
        for i in range(1, len(click_history)):
            interval = (click_history[i]['click_time'] - click_history[i-1]['click_time']).total_seconds()
            intervals.append(interval)
        
        if intervals:
            interval_cv = statistics.stdev(intervals) / statistics.mean(intervals) if statistics.mean(intervals) > 0 else 0
            metrics.append(interval_cv < 0.1)
        
        # 2. Hourly distribution variance
        hourly_counts = {}
        for click in click_history:
            hour = click['click_time'].hour
            hourly_counts[hour] = hourly_counts.get(hour, 0) + 1
        
        if len(hourly_counts) > 1:
            counts = list(hourly_counts.values())
            hour_cv = statistics.stdev(counts) / statistics.mean(counts) if statistics.mean(counts) > 0 else 0
            metrics.append(hour_cv < 0.2)
        
        # If most metrics indicate lack of variance
        return sum(metrics) >= len(metrics) * 0.7
    
    def _is_always_active(self, click_history: List[Dict]) -> bool:
        """
        Check for 24/7 activity
        """
        if len(click_history) < 24:
            return False
        
        # Check activity across all hours
        active_hours = set()
        for click in click_history:
            active_hours.add(click['click_time'].hour)
        
        return len(active_hours) >= 20  # Active in 20+ different hours
    
    def _has_cookie_cutter_patterns(self, click_history: List[Dict]) -> bool:
        """
        Check for repetitive cookie-cutter patterns
        """
        if len(click_history) < 20:
            return False
        
        # Look for repeating sequences
        # Simplified - in production, use sequence mining
        return False
    
    def _detect_time_series_anomalies(self, click_history: List[Dict]) -> Dict:
        """
        Detect anomalies in time series data
        """
        # Implement time series anomaly detection
        # For now, return empty result
        return {}
    
    def _cluster_behavior_patterns(self, click_history: List[Dict]) -> Dict:
        """
        Cluster behavior patterns
        """
        # Implement clustering analysis
        return {}
    
    def _predict_fraud_probability(self, click_history: List[Dict]) -> Dict:
        """
        Predict fraud probability using ML model
        """
        # Implement ML model prediction
        return {}
    
    def get_detector_config(self) -> Dict:
        base_config = super().get_detector_config()
        base_config.update({
            'description': 'Advanced click fraud detection for offerwalls and ad networks',
            'version': '2.5.0',
            'thresholds': {
                'anomaly': self.anomaly_threshold,
                'velocity': self.velocity_threshold,
                'pattern_similarity': self.pattern_similarity_threshold,
                'min_clicks': self.min_clicks_for_analysis
            },
            'weights': self.weights
        })
        return base_config