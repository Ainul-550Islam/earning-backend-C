from .BaseDetector import BaseDetector
from django.db.models import Count, Q, F, Window, Sum, Avg
from django.db.models.functions import TruncHour, TruncDay, TruncWeek
from django.utils import timezone
from datetime import timedelta, datetime
import numpy as np
from scipy import stats
import logging
from typing import Dict, List, Any, Optional, Tuple
import json
import hashlib

logger = logging.getLogger(__name__)

class PatternAnalyzer(BaseDetector):
    """
    Advanced pattern analysis for fraud detection
    Uses statistical analysis, machine learning, and behavioral patterns
    """
    
    def __init__(self, config: Dict = None):
        super().__init__(config)
        
        # Configuration
        self.anomaly_zscore = config.get('anomaly_zscore', 3.0) if config else 3.0
        self.correlation_threshold = config.get('correlation_threshold', 0.8) if config else 0.8
        self.cluster_threshold = config.get('cluster_threshold', 0.7) if config else 0.7
        self.min_samples_for_analysis = config.get('min_samples', 50) if config else 50
        
        # Pattern weights
        self.weights = {
            'temporal': 25,
            'behavioral': 30,
            'transactional': 20,
            'network': 15,
            'social': 10
        }
        
    def get_required_fields(self) -> List[str]:
        return ['user_id', 'activity_type']
    
    def detect(self, data: Dict) -> Dict:
        """
        Detect anomalous patterns in user behavior
        """
        try:
            user_id = data.get('user_id')
            activity_type = data.get('activity_type')
            timeframe = data.get('timeframe', '7d')
            
            if not self.validate_data(data):
                return self.get_detection_result()
            
            # Get user's historical data
            historical_data = self._get_historical_data(user_id, timeframe)
            
            if len(historical_data) < self.min_samples_for_analysis:
                return {
                    'detector': self.detector_name,
                    'is_fraud': False,
                    'fraud_score': 0,
                    'confidence': 0,
                    'warning': 'Insufficient data for analysis'
                }
            
            # Run pattern analysis
            analyses = [
                self._analyze_temporal_patterns(historical_data),
                self._analyze_behavioral_patterns(historical_data),
                self._analyze_transaction_patterns(user_id, timeframe),
                self._analyze_network_patterns(user_id, timeframe),
                self._analyze_social_patterns(user_id, timeframe),
                self._analyze_sequence_patterns(historical_data),
                self._analyze_outlier_patterns(historical_data)
            ]
            
            # Machine learning analysis
            ml_analyses = self._perform_ml_analysis(historical_data)
            analyses.extend(ml_analyses)
            
            # Calculate overall score
            self._calculate_pattern_score(analyses)
            
            # Detect fraud based on patterns
            self.detected_fraud = self._detect_pattern_fraud(analyses)
            
            # Calculate confidence
            self.confidence = self._calculate_pattern_confidence(analyses, len(historical_data))
            
            # Add evidence
            self._compile_pattern_evidence(analyses, historical_data)
            
            # Log detection
            self.log_detection(user_id)
            
            return self.get_detection_result()
            
        except Exception as e:
            logger.error(f"Error in PatternAnalyzer: {str(e)}")
            return {
                'detector': self.detector_name,
                'is_fraud': False,
                'fraud_score': 0,
                'confidence': 0,
                'error': str(e)
            }
    
    def _get_historical_data(self, user_id: int, timeframe: str) -> List[Dict]:
        """
        Get user's historical activity data
        """
        try:
            from engagement.models import UserActivity
            
            # Parse timeframe
            if timeframe.endswith('d'):
                days = int(timeframe[:-1])
            elif timeframe.endswith('h'):
                days = int(timeframe[:-1]) / 24
            else:
                days = 7  # Default to 7 days
            
            start_date = timezone.now() - timedelta(days=days)
            
            activities = UserActivity.objects.filter(
                user_id=user_id,
                timestamp__gte=start_date
            ).order_by('timestamp')
            
            historical_data = []
            for activity in activities:
                historical_data.append({
                    'timestamp': activity.timestamp,
                    'activity_type': activity.activity_type,
                    'duration': activity.duration or 0,
                    'metadata': activity.metadata or {},
                    'ip_address': activity.ip_address,
                    'device_id': activity.device_id
                })
            
            return historical_data
            
        except Exception as e:
            logger.error(f"Error getting historical data: {e}")
            return []
    
    def _analyze_temporal_patterns(self, historical_data: List[Dict]) -> Dict:
        """
        Analyze temporal patterns for anomalies
        """
        result = {
            'analysis': 'temporal_patterns',
            'periodicities': {},
            'anomalies': [],
            'risk_score': 0,
            'metrics': {}
        }
        
        if len(historical_data) < 10:
            result['warning'] = 'Insufficient data for temporal analysis'
            return result
        
        # Extract timestamps and activity types
        timestamps = [d['timestamp'] for d in historical_data]
        activity_types = [d['activity_type'] for d in historical_data]
        
        # Convert timestamps to numerical values (seconds since start)
        start_time = min(timestamps)
        time_deltas = [(ts - start_time).total_seconds() for ts in timestamps]
        
        # 1. Analyze periodicity
        periodicity = self._detect_periodicity(time_deltas)
        result['periodicities'] = periodicity
        
        # Check for robotic periodicity
        if periodicity.get('is_periodic', False):
            if periodicity.get('regularity_score', 0) > 0.9:
                result['anomalies'].append('Highly periodic/robotic activity pattern')
                result['risk_score'] += 25
        
        # 2. Analyze time-of-day patterns
        hour_distribution = {}
        for ts in timestamps:
            hour = ts.hour
            hour_distribution[hour] = hour_distribution.get(hour, 0) + 1
        
        result['metrics']['hour_distribution'] = hour_distribution
        
        # Check for 24/7 activity
        active_hours = len([h for h, count in hour_distribution.items() if count > 0])
        if active_hours >= 20:
            result['anomalies'].append('24/7 activity pattern detected')
            result['risk_score'] += 20
        
        # 3. Analyze day-of-week patterns
        weekday_distribution = {}
        for ts in timestamps:
            weekday = ts.weekday()
            weekday_distribution[weekday] = weekday_distribution.get(weekday, 0) + 1
        
        result['metrics']['weekday_distribution'] = weekday_distribution
        
        # Check for uniform distribution (unnatural)
        if len(weekday_distribution) >= 6:
            counts = list(weekday_distribution.values())
            cv = np.std(counts) / np.mean(counts) if np.mean(counts) > 0 else 0
            if cv < 0.2:
                result['anomalies'].append('Unnaturally uniform weekly distribution')
                result['risk_score'] += 15
        
        # 4. Analyze burst patterns
        burst_analysis = self._analyze_burst_patterns(time_deltas)
        result['metrics']['burst_analysis'] = burst_analysis
        
        if burst_analysis.get('is_bursty', False):
            burst_score = burst_analysis.get('burst_score', 0)
            if burst_score > 0.7:
                result['anomalies'].append('Highly bursty activity pattern')
                result['risk_score'] += min(30, int(burst_score * 30))
        
        result['risk_score'] = min(100, result['risk_score'])
        
        if result['risk_score'] > 0:
            for anomaly in result['anomalies'][:3]:
                self.add_reason(anomaly, result['risk_score'] // len(result['anomalies']))
        
        return result
    
    def _analyze_behavioral_patterns(self, historical_data: List[Dict]) -> Dict:
        """
        Analyze behavioral patterns
        """
        result = {
            'analysis': 'behavioral_patterns',
            'patterns': {},
            'anomalies': [],
            'risk_score': 0,
            'metrics': {}
        }
        
        if len(historical_data) < 15:
            result['warning'] = 'Insufficient data for behavioral analysis'
            return result
        
        # Group activities by type
        activity_counts = {}
        for data in historical_data:
            activity_type = data['activity_type']
            activity_counts[activity_type] = activity_counts.get(activity_type, 0) + 1
        
        result['metrics']['activity_distribution'] = activity_counts
        
        # 1. Analyze activity sequence patterns
        activity_sequence = [d['activity_type'] for d in historical_data]
        sequence_analysis = self._analyze_activity_sequence(activity_sequence)
        result['patterns']['sequence'] = sequence_analysis
        
        if sequence_analysis.get('is_repetitive', False):
            result['anomalies'].append('Repetitive activity sequence pattern')
            result['risk_score'] += 20
        
        # 2. Analyze activity duration patterns
        durations = [d.get('duration', 0) for d in historical_data if d.get('duration')]
        if durations:
            duration_analysis = self._analyze_duration_patterns(durations)
            result['patterns']['duration'] = duration_analysis
            
            # Check for unrealistic durations
            if duration_analysis.get('has_unrealistic_durations', False):
                result['anomalies'].append('Unrealistic activity durations')
                result['risk_score'] += 15
        
        # 3. Analyze metadata patterns
        metadata_patterns = self._analyze_metadata_patterns(historical_data)
        result['patterns']['metadata'] = metadata_patterns
        
        if metadata_patterns.get('is_suspicious', False):
            result['anomalies'].append('Suspicious metadata patterns')
            result['risk_score'] += metadata_patterns.get('suspicion_score', 0)
        
        # 4. Analyze behavioral entropy
        entropy = self._calculate_behavioral_entropy(historical_data)
        result['metrics']['behavioral_entropy'] = entropy
        
        if entropy < 1.5:  # Low entropy (repetitive behavior)
            result['anomalies'].append('Low behavioral entropy (repetitive patterns)')
            result['risk_score'] += 20
        
        result['risk_score'] = min(100, result['risk_score'])
        
        if result['risk_score'] > 0:
            for anomaly in result['anomalies'][:3]:
                self.add_reason(anomaly, result['risk_score'] // len(result['anomalies']))
        
        return result
    
    def _analyze_transaction_patterns(self, user_id: int, timeframe: str) -> Dict:
        """
        Analyze transaction patterns
        """
        result = {
            'analysis': 'transaction_patterns',
            'patterns': {},
            'anomalies': [],
            'risk_score': 0,
            'metrics': {}
        }
        
        try:
            from wallet.models import WalletTransaction
            
            # Parse timeframe
            if timeframe.endswith('d'):
                days = int(timeframe[:-1])
            else:
                days = 7
            
            start_date = timezone.now() - timedelta(days=days)
            
            transactions = WalletTransaction.objects.filter(
                user_id=user_id,
                created_at__gte=start_date
            ).order_by('created_at')
            
            if transactions.count() < 5:
                result['warning'] = 'Insufficient transaction data'
                return result
            
            # Extract transaction data
            tx_data = []
            for tx in transactions:
                tx_data.append({
                    'timestamp': tx.created_at,
                    'amount': float(tx.amount),
                    'type': tx.transaction_type,
                    'status': tx.status,
                    'description': tx.description
                })
            
            # 1. Analyze amount patterns
            amounts = [tx['amount'] for tx in tx_data]
            amount_analysis = self._analyze_amount_patterns(amounts)
            result['patterns']['amount'] = amount_analysis
            
            if amount_analysis.get('is_suspicious', False):
                result['anomalies'].append('Suspicious transaction amount patterns')
                result['risk_score'] += amount_analysis.get('risk_score', 0)
            
            # 2. Analyze timing patterns
            tx_timestamps = [tx['timestamp'] for tx in tx_data]
            timing_analysis = self._analyze_transaction_timing(tx_timestamps)
            result['patterns']['timing'] = timing_analysis
            
            if timing_analysis.get('is_suspicious', False):
                result['anomalies'].append('Suspicious transaction timing')
                result['risk_score'] += timing_analysis.get('risk_score', 0)
            
            # 3. Analyze type distribution
            type_counts = {}
            for tx in tx_data:
                tx_type = tx['type']
                type_counts[tx_type] = type_counts.get(tx_type, 0) + 1
            
            result['metrics']['type_distribution'] = type_counts
            
            # Check for unusual type ratios
            if 'credit' in type_counts and 'debit' in type_counts:
                credit_ratio = type_counts['credit'] / (type_counts['credit'] + type_counts['debit'])
                if credit_ratio > 0.9:  # Mostly credits
                    result['anomalies'].append('Unusually high credit transaction ratio')
                    result['risk_score'] += 15
            
            result['risk_score'] = min(100, result['risk_score'])
            
            if result['risk_score'] > 0:
                for anomaly in result['anomalies'][:3]:
                    self.add_reason(anomaly, result['risk_score'] // len(result['anomalies']))
            
            return result
            
        except Exception as e:
            logger.error(f"Error analyzing transaction patterns: {e}")
            return {'analysis': 'transaction_patterns', 'error': str(e), 'risk_score': 0}
    
    def _analyze_network_patterns(self, user_id: int, timeframe: str) -> Dict:
        """
        Analyze network and IP patterns
        """
        result = {
            'analysis': 'network_patterns',
            'patterns': {},
            'anomalies': [],
            'risk_score': 0,
            'metrics': {}
        }
        
        try:
            from engagement.models import UserActivity
            
            # Parse timeframe
            if timeframe.endswith('d'):
                days = int(timeframe[:-1])
            else:
                days = 7
            
            start_date = timezone.now() - timedelta(days=days)
            
            # Get unique IPs used by user
            ips = UserActivity.objects.filter(
                user_id=user_id,
                timestamp__gte=start_date
            ).exclude(
                ip_address__isnull=True
            ).values_list('ip_address', flat=True).distinct()
            
            ip_list = list(ips)
            result['metrics']['unique_ips'] = len(ip_list)
            result['metrics']['ip_list'] = ip_list
            
            if len(ip_list) < 2:
                return result  # Not enough data
            
            # 1. Analyze IP diversity
            ip_diversity_analysis = self._analyze_ip_diversity(ip_list, user_id, days)
            result['patterns']['ip_diversity'] = ip_diversity_analysis
            
            if ip_diversity_analysis.get('is_suspicious', False):
                result['anomalies'].append('Suspicious IP diversity pattern')
                result['risk_score'] += ip_diversity_analysis.get('risk_score', 0)
            
            # 2. Analyze IP reputation
            ip_reputation_analysis = self._analyze_ip_reputation(ip_list)
            result['patterns']['ip_reputation'] = ip_reputation_analysis
            
            if ip_reputation_analysis.get('high_risk_ips', 0) > 0:
                result['anomalies'].append(f"{ip_reputation_analysis['high_risk_ips']} high-risk IPs detected")
                result['risk_score'] += ip_reputation_analysis.get('risk_score', 0)
            
            # 3. Analyze geographic patterns
            geo_analysis = self._analyze_geographic_patterns(ip_list)
            result['patterns']['geographic'] = geo_analysis
            
            if geo_analysis.get('has_impossible_travel', False):
                result['anomalies'].append('Impossible travel patterns detected')
                result['risk_score'] += 25
            
            result['risk_score'] = min(100, result['risk_score'])
            
            if result['risk_score'] > 0:
                for anomaly in result['anomalies'][:3]:
                    self.add_reason(anomaly, result['risk_score'] // len(result['anomalies']))
            
            return result
            
        except Exception as e:
            logger.error(f"Error analyzing network patterns: {e}")
            return {'analysis': 'network_patterns', 'error': str(e), 'risk_score': 0}
    
    def _analyze_social_patterns(self, user_id: int, timeframe: str) -> Dict:
        """
        Analyze social and referral patterns
        """
        result = {
            'analysis': 'social_patterns',
            'patterns': {},
            'anomalies': [],
            'risk_score': 0,
            'metrics': {}
        }
        
        try:
            from referral.models import Referral
            from engagement.models import UserActivity
            
            # Parse timeframe
            if timeframe.endswith('d'):
                days = int(timeframe[:-1])
            else:
                days = 7
            
            start_date = timezone.now() - timedelta(days=days)
            
            # 1. Analyze referral patterns
            referrals = Referral.objects.filter(
                referrer_id=user_id,
                created_at__gte=start_date
            )
            
            referral_count = referrals.count()
            result['metrics']['referral_count'] = referral_count
            
            if referral_count > 0:
                successful_referrals = referrals.filter(status='completed').count()
                conversion_rate = (successful_referrals / referral_count) * 100
                result['metrics']['referral_conversion_rate'] = conversion_rate
                
                # Check for suspicious conversion rates
                if conversion_rate > 90:
                    result['anomalies'].append(f"Unrealistic referral conversion rate: {conversion_rate:.1f}%")
                    result['risk_score'] += 25
                elif conversion_rate > 70:
                    result['anomalies'].append(f"High referral conversion rate: {conversion_rate:.1f}%")
                    result['risk_score'] += 15
            
            # 2. Analyze social interaction patterns
            social_activities = UserActivity.objects.filter(
                user_id=user_id,
                timestamp__gte=start_date,
                activity_type__in=['social_share', 'social_like', 'social_comment', 'invite_sent']
            )
            
            social_count = social_activities.count()
            result['metrics']['social_activity_count'] = social_count
            
            # Check for robotic social patterns
            if social_count > 20:
                # Analyze timing of social activities
                social_timestamps = [act.timestamp for act in social_activities]
                time_deltas = []
                
                for i in range(1, len(social_timestamps)):
                    delta = (social_timestamps[i] - social_timestamps[i-1]).total_seconds()
                    time_deltas.append(delta)
                
                if time_deltas:
                    avg_delta = np.mean(time_deltas)
                    std_delta = np.std(time_deltas)
                    
                    if std_delta < 10:  # Very consistent timing
                        result['anomalies'].append('Robotic social activity pattern')
                        result['risk_score'] += 20
            
            result['risk_score'] = min(100, result['risk_score'])
            
            if result['risk_score'] > 0:
                for anomaly in result['anomalies'][:3]:
                    self.add_reason(anomaly, result['risk_score'] // len(result['anomalies']))
            
            return result
            
        except Exception as e:
            logger.error(f"Error analyzing social patterns: {e}")
            return {'analysis': 'social_patterns', 'error': str(e), 'risk_score': 0}
    
    def _analyze_sequence_patterns(self, historical_data: List[Dict]) -> Dict:
        """
        Analyze activity sequence patterns
        """
        result = {
            'analysis': 'sequence_patterns',
            'patterns': {},
            'anomalies': [],
            'risk_score': 0,
            'metrics': {}
        }
        
        if len(historical_data) < 20:
            result['warning'] = 'Insufficient data for sequence analysis'
            return result
        
        # Extract activity sequence
        activity_sequence = [d['activity_type'] for d in historical_data]
        
        # 1. Detect repeating sequences
        repeating_sequences = self._detect_repeating_sequences(activity_sequence)
        result['patterns']['repeating_sequences'] = repeating_sequences
        
        if repeating_sequences.get('has_repeating_patterns', False):
            result['anomalies'].append('Repeating activity sequence patterns detected')
            result['risk_score'] += 20
        
        # 2. Analyze Markov chain patterns
        markov_analysis = self._analyze_markov_patterns(activity_sequence)
        result['patterns']['markov_analysis'] = markov_analysis
        
        if markov_analysis.get('low_entropy', False):
            result['anomalies'].append('Low sequence entropy (predictable patterns)')
            result['risk_score'] += 15
        
        # 3. Detect anomalous sequences
        anomaly_sequences = self._detect_anomalous_sequences(activity_sequence)
        result['patterns']['anomalous_sequences'] = anomaly_sequences
        
        if anomaly_sequences.get('anomaly_count', 0) > 0:
            result['anomalies'].append(f"{anomaly_sequences['anomaly_count']} anomalous sequences detected")
            result['risk_score'] += min(25, anomaly_sequences['anomaly_count'] * 5)
        
        result['risk_score'] = min(100, result['risk_score'])
        
        if result['risk_score'] > 0:
            for anomaly in result['anomalies'][:3]:
                self.add_reason(anomaly, result['risk_score'] // len(result['anomalies']))
        
        return result
    
    def _analyze_outlier_patterns(self, historical_data: List[Dict]) -> Dict:
        """
        Analyze outlier patterns using statistical methods
        """
        result = {
            'analysis': 'outlier_patterns',
            'outliers': {},
            'anomalies': [],
            'risk_score': 0,
            'metrics': {}
        }
        
        if len(historical_data) < 30:
            result['warning'] = 'Insufficient data for outlier analysis'
            return result
        
        # 1. Time-based outlier detection
        timestamps = [d['timestamp'] for d in historical_data]
        time_deltas = []
        
        for i in range(1, len(timestamps)):
            delta = (timestamps[i] - timestamps[i-1]).total_seconds()
            time_deltas.append(delta)
        
        if time_deltas:
            time_outliers = self._detect_statistical_outliers(time_deltas)
            result['outliers']['time_based'] = time_outliers
            
            if time_outliers.get('outlier_count', 0) > 0:
                result['anomalies'].append(f"{time_outliers['outlier_count']} time-based outliers detected")
                result['risk_score'] += min(20, time_outliers['outlier_count'] * 3)
        
        # 2. Activity type outlier detection
        activity_counts = {}
        for data in historical_data:
            activity_type = data['activity_type']
            activity_counts[activity_type] = activity_counts.get(activity_type, 0) + 1
        
        if activity_counts:
            count_values = list(activity_counts.values())
            activity_outliers = self._detect_statistical_outliers(count_values)
            result['outliers']['activity_based'] = activity_outliers
            
            if activity_outliers.get('outlier_count', 0) > 0:
                result['anomalies'].append(f"{activity_outliers['outlier_count']} activity-based outliers detected")
                result['risk_score'] += min(15, activity_outliers['outlier_count'] * 2)
        
        # 3. Multivariate outlier detection
        multivariate_data = []
        for data in historical_data:
            multivariate_data.append({
                'timestamp': data['timestamp'].timestamp(),
                'activity_type': hash(data['activity_type']) % 1000,  # Simple hash
                'has_duration': 1 if data.get('duration') else 0
            })
        
        if len(multivariate_data) > 10:
            mv_outliers = self._detect_multivariate_outliers(multivariate_data)
            result['outliers']['multivariate'] = mv_outliers
            
            if mv_outliers.get('outlier_count', 0) > 0:
                result['anomalies'].append(f"{mv_outliers['outlier_count']} multivariate outliers detected")
                result['risk_score'] += min(25, mv_outliers['outlier_count'] * 4)
        
        result['risk_score'] = min(100, result['risk_score'])
        
        if result['risk_score'] > 0:
            for anomaly in result['anomalies'][:3]:
                self.add_reason(anomaly, result['risk_score'] // len(result['anomalies']))
        
        return result
    
    def _perform_ml_analysis(self, historical_data: List[Dict]) -> List[Dict]:
        """
        Perform machine learning based analysis
        """
        results = []
        
        try:
            if len(historical_data) < 50:
                return results
            
            # 1. Clustering analysis
            clustering_result = self._perform_clustering_analysis(historical_data)
            if clustering_result:
                results.append({
                    'analysis': 'ml_clustering',
                    'results': clustering_result,
                    'risk_score': clustering_result.get('risk_score', 0)
                })
            
            # 2. Anomaly detection using isolation forest
            isolation_result = self._perform_isolation_analysis(historical_data)
            if isolation_result:
                results.append({
                    'analysis': 'ml_isolation_forest',
                    'results': isolation_result,
                    'risk_score': isolation_result.get('risk_score', 0)
                })
            
            # 3. Time series forecasting anomaly detection
            forecast_result = self._perform_forecast_analysis(historical_data)
            if forecast_result:
                results.append({
                    'analysis': 'ml_forecasting',
                    'results': forecast_result,
                    'risk_score': forecast_result.get('risk_score', 0)
                })
            
        except Exception as e:
            logger.error(f"Error in ML analysis: {e}")
        
        return results
    
    def _calculate_pattern_score(self, analyses: List[Dict]):
        """
        Calculate overall pattern fraud score
        """
        weighted_scores = []
        
        for analysis in analyses:
            analysis_type = analysis.get('analysis', '')
            risk_score = analysis.get('risk_score', 0)
            
            # Get weight based on analysis type
            weight_key = analysis_type.split('_')[0] if '_' in analysis_type else analysis_type
            weight = self.weights.get(weight_key, 10) / 100
            
            weighted_scores.append(risk_score * weight)
        
        if weighted_scores:
            base_score = sum(weighted_scores) / len(weighted_scores)
            
            # Adjust based on number of anomalies
            total_anomalies = sum(len(analysis.get('anomalies', [])) for analysis in analyses)
            anomaly_boost = min(30, total_anomalies * 3)
            
            self.fraud_score = min(100, int(base_score + anomaly_boost))
    
    def _detect_pattern_fraud(self, analyses: List[Dict]) -> bool:
        """
        Detect fraud based on pattern analysis
        """
        # High risk if multiple analyses show high risk
        high_risk_analyses = [a for a in analyses if a.get('risk_score', 0) >= 60]
        
        if len(high_risk_analyses) >= 2:
            return True
        
        # Or if total risk score is very high
        total_risk = sum(a.get('risk_score', 0) for a in analyses)
        if total_risk >= 120:
            return True
        
        # Or if ML analyses indicate fraud
        ml_analyses = [a for a in analyses if a.get('analysis', '').startswith('ml_')]
        ml_high_risk = [a for a in ml_analyses if a.get('risk_score', 0) >= 70]
        
        if len(ml_high_risk) >= 1:
            return True
        
        return False
    
    def _calculate_pattern_confidence(self, analyses: List[Dict], data_points: int) -> int:
        """
        Calculate confidence in pattern analysis
        """
        confidence_factors = []
        
        # Data volume factor
        if data_points >= 100:
            confidence_factors.append(80)
        elif data_points >= 50:
            confidence_factors.append(60)
        elif data_points >= 20:
            confidence_factors.append(40)
        else:
            confidence_factors.append(20)
        
        # Analysis consistency factor
        consistent_analyses = sum(1 for a in analyses if a.get('risk_score', 0) > 30)
        if consistent_analyses >= 3:
            confidence_factors.append(70)
        elif consistent_analyses >= 2:
            confidence_factors.append(50)
        
        # ML confirmation factor
        ml_analyses = [a for a in analyses if a.get('analysis', '').startswith('ml_')]
        if ml_analyses:
            confidence_factors.append(60)
        
        if confidence_factors:
            return min(100, int(sum(confidence_factors) / len(confidence_factors)))
        
        return 50
    
    def _compile_pattern_evidence(self, analyses: List[Dict], historical_data: List[Dict]):
        """
        Compile pattern evidence
        """
        self.add_evidence('analysis_summary', {
            'total_analyses': len(analyses),
            'total_data_points': len(historical_data),
            'high_risk_analyses': len([a for a in analyses if a.get('risk_score', 0) >= 50])
        })
        
        for analysis in analyses:
            if analysis.get('risk_score', 0) >= 30:
                analysis_type = analysis.get('analysis', 'unknown')
                self.add_evidence(f'{analysis_type}_details', {
                    'risk_score': analysis['risk_score'],
                    'anomalies': analysis.get('anomalies', [])[:3],
                    'key_metrics': {k: v for k, v in analysis.get('metrics', {}).items() 
                                  if not isinstance(v, (list, dict)) or k in ['unique_ips', 'referral_count']}
                })
    
    # Statistical analysis helper methods
    
    def _detect_periodicity(self, time_deltas: List[float]) -> Dict:
        """Detect periodicity in time deltas"""
        if len(time_deltas) < 10:
            return {'is_periodic': False}
        
        try:
            # Calculate autocorrelation
            from statsmodels.tsa.stattools import acf
            
            nlags = min(20, len(time_deltas) - 1)
            autocorr = acf(time_deltas, nlags=nlags, fft=True)
            
            # Find peaks in autocorrelation
            peaks = []
            for i in range(1, len(autocorr) - 1):
                if autocorr[i] > autocorr[i-1] and autocorr[i] > autocorr[i+1]:
                    peaks.append(i)
            
            is_periodic = len(peaks) > 0 and max(autocorr[1:]) > 0.5
            
            return {
                'is_periodic': is_periodic,
                'regularity_score': max(autocorr[1:]) if is_periodic else 0,
                'peak_lags': peaks,
                'max_autocorrelation': float(max(autocorr[1:])) if len(autocorr) > 1 else 0
            }
            
        except Exception as e:
            logger.error(f"Error in periodicity detection: {e}")
            return {'is_periodic': False, 'error': str(e)}
    
    def _analyze_burst_patterns(self, time_deltas: List[float]) -> Dict:
        """Analyze burst patterns in activity"""
        if len(time_deltas) < 5:
            return {'is_bursty': False}
        
        # Calculate burstiness using Gini coefficient
        sorted_deltas = sorted(time_deltas)
        n = len(sorted_deltas)
        
        if n == 0 or sum(sorted_deltas) == 0:
            return {'is_bursty': False}
        
        # Gini coefficient calculation
        cumulative_sum = 0
        for i, value in enumerate(sorted_deltas, 1):
            cumulative_sum += value
        
        gini_numerator = 0
        for i, value in enumerate(sorted_deltas, 1):
            gini_numerator += (2*i - n - 1) * value
        
        gini = gini_numerator / (n * cumulative_sum) if cumulative_sum > 0 else 0
        
        # Burstiness index (simplified)
        mean_delta = np.mean(time_deltas)
        std_delta = np.std(time_deltas)
        
        if mean_delta > 0:
            burstiness = (std_delta - mean_delta) / (std_delta + mean_delta)
        else:
            burstiness = 0
        
        return {
            'is_bursty': burstiness > 0.3 or gini > 0.4,
            'burst_score': float(max(burstiness, gini)),
            'gini_coefficient': float(gini),
            'burstiness_index': float(burstiness)
        }
    
    def _analyze_activity_sequence(self, sequence: List[str]) -> Dict:
        """Analyze activity sequence patterns"""
        if len(sequence) < 10:
            return {'is_repetitive': False}
        
        # Simple repetitive pattern detection
        # Check for exact sequence repetition
        max_pattern_length = min(5, len(sequence) // 2)
        
        for pattern_len in range(2, max_pattern_length + 1):
            for i in range(len(sequence) - pattern_len * 2 + 1):
                pattern = sequence[i:i + pattern_len]
                next_segment = sequence[i + pattern_len:i + pattern_len * 2]
                
                if pattern == next_segment:
                    return {
                        'is_repetitive': True,
                        'pattern_length': pattern_len,
                        'pattern': pattern,
                        'occurrences': 2
                    }
        
        return {'is_repetitive': False}
    
    def _analyze_duration_patterns(self, durations: List[float]) -> Dict:
        """Analyze duration patterns"""
        if len(durations) < 5:
            return {'has_unrealistic_durations': False}
        
        # Check for unrealistic durations
        # Assuming durations are in seconds
        unrealistic_threshold = 3600  # 1 hour
        too_short_threshold = 0.1  # 100ms
        
        unrealistic_count = sum(1 for d in durations if d > unrealistic_threshold or d < too_short_threshold)
        
        return {
            'has_unrealistic_durations': unrealistic_count > len(durations) * 0.3,
            'unrealistic_count': unrealistic_count,
            'unrealistic_percentage': (unrealistic_count / len(durations)) * 100,
            'mean_duration': float(np.mean(durations)),
            'std_duration': float(np.std(durations))
        }
    
    def _analyze_metadata_patterns(self, historical_data: List[Dict]) -> Dict:
        """Analyze metadata patterns"""
        suspicious_patterns = []
        suspicion_score = 0
        
        # Check for empty or missing metadata
        empty_metadata_count = sum(1 for d in historical_data if not d.get('metadata'))
        if empty_metadata_count > len(historical_data) * 0.8:
            suspicious_patterns.append('Most metadata is empty')
            suspicion_score += 15
        
        # Check for identical metadata
        metadata_strings = [str(d.get('metadata', {})) for d in historical_data]
        unique_metadata = len(set(metadata_strings))
        
        if unique_metadata < len(historical_data) * 0.3:
            suspicious_patterns.append('Highly repetitive metadata')
            suspicion_score += 20
        
        return {
            'is_suspicious': suspicion_score > 0,
            'suspicion_score': suspicion_score,
            'suspicious_patterns': suspicious_patterns,
            'unique_metadata_ratio': unique_metadata / len(historical_data) if historical_data else 0
        }
    
    def _calculate_behavioral_entropy(self, historical_data: List[Dict]) -> float:
        """Calculate behavioral entropy"""
        import math
        
        if len(historical_data) < 5:
            return 0
        
        # Count activity types
        activity_counts = {}
        for data in historical_data:
            activity_type = data['activity_type']
            activity_counts[activity_type] = activity_counts.get(activity_type, 0) + 1
        
        # Calculate Shannon entropy
        entropy = 0
        total = sum(activity_counts.values())
        
        for count in activity_counts.values():
            probability = count / total
            entropy -= probability * math.log2(probability)
        
        return entropy
    
    def _analyze_amount_patterns(self, amounts: List[float]) -> Dict:
        """Analyze transaction amount patterns"""
        if len(amounts) < 5:
            return {'is_suspicious': False}
        
        risk_score = 0
        suspicious_patterns = []
        
        # Check for round amounts
        round_amounts = sum(1 for a in amounts if a % 1 == 0 or a % 5 == 0 or a % 10 == 0)
        round_percentage = (round_amounts / len(amounts)) * 100
        
        if round_percentage > 80:
            suspicious_patterns.append(f"High percentage of round amounts: {round_percentage:.1f}%")
            risk_score += 25
        elif round_percentage > 60:
            suspicious_patterns.append(f"Moderate percentage of round amounts: {round_percentage:.1f}%")
            risk_score += 15
        
        # Check for identical amounts
        unique_amounts = len(set(amounts))
        if unique_amounts < len(amounts) * 0.3:
            suspicious_patterns.append(f"Low amount diversity: {unique_amounts} unique amounts")
            risk_score += 20
        
        # Check for unrealistic amounts
        mean_amount = np.mean(amounts)
        std_amount = np.std(amounts)
        
        if std_amount > mean_amount * 3:
            suspicious_patterns.append("Highly variable transaction amounts")
            risk_score += 15
        
        return {
            'is_suspicious': risk_score > 0,
            'risk_score': risk_score,
            'suspicious_patterns': suspicious_patterns,
            'round_percentage': round_percentage,
            'amount_diversity': unique_amounts / len(amounts)
        }
    
    def _analyze_transaction_timing(self, timestamps: List[datetime]) -> Dict:
        """Analyze transaction timing patterns"""
        if len(timestamps) < 5:
            return {'is_suspicious': False}
        
        risk_score = 0
        suspicious_patterns = []
        
        # Calculate time deltas
        time_deltas = []
        for i in range(1, len(timestamps)):
            delta = (timestamps[i] - timestamps[i-1]).total_seconds()
            time_deltas.append(delta)
        
        # Check for robotic timing
        if time_deltas:
            mean_delta = np.mean(time_deltas)
            std_delta = np.std(time_deltas)
            
            if std_delta < mean_delta * 0.1:  # Very consistent timing
                suspicious_patterns.append("Highly consistent transaction timing")
                risk_score += 25
            
            # Check for burst patterns
            burst_threshold = 60  # 1 minute
            burst_count = sum(1 for d in time_deltas if d < burst_threshold)
            burst_percentage = (burst_count / len(time_deltas)) * 100
            
            if burst_percentage > 50:
                suspicious_patterns.append(f"High burst transaction rate: {burst_percentage:.1f}%")
                risk_score += 20
        
        return {
            'is_suspicious': risk_score > 0,
            'risk_score': risk_score,
            'suspicious_patterns': suspicious_patterns
        }
    
    def _analyze_ip_diversity(self, ip_list: List[str], user_id: int, days: int) -> Dict:
        """Analyze IP diversity patterns"""
        risk_score = 0
        suspicious_patterns = []
        
        ip_count = len(ip_list)
        
        # Check for high IP diversity
        if ip_count > 10:
            suspicious_patterns.append(f"High IP diversity: {ip_count} unique IPs")
            risk_score += min(30, ip_count * 2)
        
        # Check for IP class diversity
        ip_classes = set()
        for ip in ip_list:
            if '.' in ip:  # IPv4
                parts = ip.split('.')
                if len(parts) >= 2:
                    ip_classes.add(f"{parts[0]}.{parts[1]}")
            elif ':' in ip:  # IPv6
                # Simplified IPv6 class extraction
                ip_classes.add(ip.split(':')[0])
        
        if len(ip_classes) > 5:
            suspicious_patterns.append(f"Diverse IP classes: {len(ip_classes)} different networks")
            risk_score += 15
        
        return {
            'is_suspicious': risk_score > 0,
            'risk_score': risk_score,
            'suspicious_patterns': suspicious_patterns,
            'ip_count': ip_count,
            'ip_class_count': len(ip_classes)
        }
    
    def _analyze_ip_reputation(self, ip_list: List[str]) -> Dict:
        """Analyze IP reputation"""
        try:
            from ..models import IPReputation
            
            high_risk_ips = 0
            risk_score = 0
            
            for ip in ip_list:
                ip_reputation = IPReputation.objects.filter(ip_address=ip).first()
                if ip_reputation:
                    if ip_reputation.fraud_score >= 70:
                        high_risk_ips += 1
                        risk_score += 25
                    elif ip_reputation.fraud_score >= 50:
                        high_risk_ips += 1
                        risk_score += 15
            
            suspicious_patterns = []
            if high_risk_ips > 0:
                suspicious_patterns.append(f"{high_risk_ips} high-risk IPs detected")
            
            return {
                'is_suspicious': risk_score > 0,
                'risk_score': risk_score,
                'suspicious_patterns': suspicious_patterns,
                'high_risk_ips': high_risk_ips
            }
            
        except Exception as e:
            logger.error(f"Error analyzing IP reputation: {e}")
            return {'is_suspicious': False, 'error': str(e)}
    
    def _analyze_geographic_patterns(self, ip_list: List[str]) -> Dict:
        """Analyze geographic patterns"""
        # This would require GeoIP database
        # For now, return basic analysis
        return {
            'has_impossible_travel': False,
            'country_count': 0,
            'suspicious_patterns': []
        }
    
    def _detect_repeating_sequences(self, sequence: List[str]) -> Dict:
        """Detect repeating sequences in activity"""
        # Implement sequence mining algorithm
        # For now, return basic detection
        return {
            'has_repeating_patterns': False,
            'patterns_found': 0
        }
    
    def _analyze_markov_patterns(self, sequence: List[str]) -> Dict:
        """Analyze Markov chain patterns"""
        if len(sequence) < 10:
            return {'low_entropy': False}
        
        # Simple Markov analysis
        transitions = {}
        
        for i in range(len(sequence) - 1):
            current = sequence[i]
            next_state = sequence[i + 1]
            
            if current not in transitions:
                transitions[current] = {}
            
            transitions[current][next_state] = transitions[current].get(next_state, 0) + 1
        
        # Calculate entropy for each state
        import math
        total_entropy = 0
        state_count = 0
        
        for current_state, next_states in transitions.items():
            total_transitions = sum(next_states.values())
            state_entropy = 0
            
            for count in next_states.values():
                probability = count / total_transitions
                state_entropy -= probability * math.log2(probability)
            
            total_entropy += state_entropy
            state_count += 1
        
        avg_entropy = total_entropy / state_count if state_count > 0 else 0
        
        return {
            'low_entropy': avg_entropy < 1.0,
            'average_entropy': avg_entropy,
            'unique_states': len(set(sequence)),
            'unique_transitions': sum(len(states) for states in transitions.values())
        }
    
    def _detect_anomalous_sequences(self, sequence: List[str]) -> Dict:
        """Detect anomalous sequences"""
        # Implement anomaly sequence detection
        return {
            'anomaly_count': 0,
            'anomalous_sequences': []
        }
    
    def _detect_statistical_outliers(self, data: List[float]) -> Dict:
        """Detect statistical outliers using Z-score"""
        if len(data) < 10:
            return {'outlier_count': 0}
        
        try:
            z_scores = stats.zscore(data)
            outliers = np.where(np.abs(z_scores) > self.anomaly_zscore)[0]
            
            return {
                'outlier_count': len(outliers),
                'outlier_indices': outliers.tolist(),
                'outlier_z_scores': z_scores[outliers].tolist() if len(outliers) > 0 else []
            }
        except:
            return {'outlier_count': 0}
    
    def _detect_multivariate_outliers(self, data: List[Dict]) -> Dict:
        """Detect multivariate outliers"""
        # Implement multivariate outlier detection
        return {
            'outlier_count': 0,
            'outlier_indices': []
        }
    
    def _perform_clustering_analysis(self, historical_data: List[Dict]) -> Dict:
        """Perform clustering analysis"""
        # Implement clustering analysis
        return {
            'risk_score': 0,
            'clusters_found': 0
        }
    
    def _perform_isolation_analysis(self, historical_data: List[Dict]) -> Dict:
        """Perform isolation forest analysis"""
        # Implement isolation forest
        return {
            'risk_score': 0,
            'anomalies_found': 0
        }
    
    def _perform_forecast_analysis(self, historical_data: List[Dict]) -> Dict:
        """Perform time series forecasting analysis"""
        # Implement time series forecasting
        return {
            'risk_score': 0,
            'forecast_errors': []
        }
    
    def get_detector_config(self) -> Dict:
        base_config = super().get_detector_config()
        base_config.update({
            'description': 'Advanced pattern analysis for fraud detection',
            'version': '3.0.0',
            'thresholds': {
                'anomaly_zscore': self.anomaly_zscore,
                'correlation_threshold': self.correlation_threshold,
                'cluster_threshold': self.cluster_threshold,
                'min_samples': self.min_samples_for_analysis
            },
            'weights': self.weights
        })
        return base_config