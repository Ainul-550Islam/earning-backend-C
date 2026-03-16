import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from decimal import Decimal
import logging
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import StandardScaler
import warnings
warnings.filterwarnings('ignore')

logger = logging.getLogger(__name__)

class DataProcessor:
    """
    Data processing and analysis for analytics
    """
    
    def __init__(self):
        self.scaler = StandardScaler()
    
    def process_time_series(
        self,
        data: List[Dict],
        date_field: str = 'period',
        value_field: str = 'value',
        fill_missing: bool = True
    ) -> pd.DataFrame:
        """
        Process time series data
        
        Args:
            data: Time series data
            date_field: Date field name
            value_field: Value field name
            fill_missing: Whether to fill missing dates
        
        Returns:
            Processed time series DataFrame
        """
        if not data:
            return pd.DataFrame()
        
        # Convert to DataFrame
        df = pd.DataFrame(data)
        
        # Convert date field to datetime
        if date_field in df.columns:
            df[date_field] = pd.to_datetime(df[date_field])
            df.set_index(date_field, inplace=True)
        
        # Fill missing dates if requested
        if fill_missing and not df.empty:
            # Create complete date range
            start_date = df.index.min()
            end_date = df.index.max()
            date_range = pd.date_range(start=start_date, end=end_date, freq='D')
            
            # Reindex and fill missing values
            df = df.reindex(date_range)
            
            # Forward fill for missing values
            df[value_field] = df[value_field].ffill().bfill()
        
        return df
    
    def calculate_statistics(
        self,
        data: List[Dict],
        value_field: str = 'value'
    ) -> Dict[str, Any]:
        """
        Calculate statistics for data
        
        Args:
            data: Data to analyze
            value_field: Value field name
        
        Returns:
            Statistical summary
        """
        if not data:
            return {}
        
        df = pd.DataFrame(data)
        
        if value_field not in df.columns:
            return {}
        
        values = df[value_field].dropna()
        
        if len(values) == 0:
            return {}
        
        # Basic statistics
        stats = {
            'count': len(values),
            'mean': float(values.mean()),
            'median': float(values.median()),
            'std': float(values.std()),
            'min': float(values.min()),
            'max': float(values.max()),
            'q1': float(values.quantile(0.25)),
            'q3': float(values.quantile(0.75)),
            'iqr': float(values.quantile(0.75) - values.quantile(0.25))
        }
        
        # Detect outliers using IQR method
        lower_bound = stats['q1'] - 1.5 * stats['iqr']
        upper_bound = stats['q3'] + 1.5 * stats['iqr']
        
        outliers = values[(values < lower_bound) | (values > upper_bound)]
        stats['outlier_count'] = len(outliers)
        stats['outlier_percentage'] = (len(outliers) / len(values)) * 100
        
        # Trend analysis
        if len(values) >= 2:
            x = np.arange(len(values)).reshape(-1, 1)
            y = values.values.reshape(-1, 1)
            
            model = LinearRegression()
            model.fit(x, y)
            
            stats['trend_slope'] = float(model.coef_[0][0])
            stats['trend_direction'] = 'increasing' if stats['trest_slope'] > 0 else 'decreasing'
            stats['r_squared'] = float(model.score(x, y))
        
        return stats
    
    def detect_anomalies(
        self,
        time_series: pd.DataFrame,
        value_field: str = 'value',
        method: str = 'zscore',
        threshold: float = 3.0
    ) -> pd.DataFrame:
        """
        Detect anomalies in time series data
        
        Args:
            time_series: Time series DataFrame
            value_field: Value field name
            method: Detection method (zscore, iqr, rolling)
            threshold: Detection threshold
        
        Returns:
            DataFrame with anomaly flags
        """
        if time_series.empty:
            return pd.DataFrame()
        
        df = time_series.copy()
        
        if method == 'zscore':
            # Z-score method
            mean = df[value_field].mean()
            std = df[value_field].std()
            
            if std > 0:
                df['zscore'] = (df[value_field] - mean) / std
                df['is_anomaly'] = abs(df['zscore']) > threshold
            else:
                df['is_anomaly'] = False
        
        elif method == 'iqr':
            # IQR method
            q1 = df[value_field].quantile(0.25)
            q3 = df[value_field].quantile(0.75)
            iqr = q3 - q1
            
            lower_bound = q1 - 1.5 * iqr
            upper_bound = q3 + 1.5 * iqr
            
            df['is_anomaly'] = (df[value_field] < lower_bound) | (df[value_field] > upper_bound)
        
        elif method == 'rolling':
            # Rolling standard deviation method
            window = min(30, len(df) // 4)
            if window >= 3:
                rolling_mean = df[value_field].rolling(window=window, center=True).mean()
                rolling_std = df[value_field].rolling(window=window, center=True).std()
                
                df['is_anomaly'] = abs(df[value_field] - rolling_mean) > (threshold * rolling_std)
                df['is_anomaly'] = df['is_anomaly'].fillna(False)
            else:
                df['is_anomaly'] = False
        
        # Add anomaly severity
        df['anomaly_severity'] = 'low'
        if 'zscore' in df.columns:
            df.loc[abs(df['zscore']) > 5, 'anomaly_severity'] = 'high'
            df.loc[(abs(df['zscore']) > 3) & (abs(df['zscore']) <= 5), 'anomaly_severity'] = 'medium'
        
        return df
    
    def forecast_revenue(
        self,
        historical_data: List[Dict],
        periods: int = 30,
        model_type: str = 'linear'
    ) -> Dict[str, Any]:
        """
        Forecast future revenue
        
        Args:
            historical_data: Historical revenue data
            periods: Number of periods to forecast
            model_type: Forecasting model type
        
        Returns:
            Forecast results
        """
        if not historical_data or len(historical_data) < 7:
            return {'error': 'Insufficient historical data'}
        
        # Prepare data
        df = pd.DataFrame(historical_data)
        
        if 'revenue' not in df.columns and 'value' not in df.columns:
            return {'error': 'No revenue data found'}
        
        revenue_field = 'revenue' if 'revenue' in df.columns else 'value'
        date_field = 'date' if 'date' in df.columns else 'period'
        
        df[date_field] = pd.to_datetime(df[date_field])
        df = df.sort_values(date_field)
        
        # Create features
        df['day'] = df[date_field].dt.day
        df['day_of_week'] = df[date_field].dt.dayofweek
        df['month'] = df[date_field].dt.month
        df['day_of_year'] = df[date_field].dt.dayofyear
        
        # Create lag features
        for lag in [1, 7, 30]:
            if len(df) > lag:
                df[f'lag_{lag}'] = df[revenue_field].shift(lag)
        
        # Drop rows with NaN values
        df_clean = df.dropna()
        
        if len(df_clean) < 10:
            return {'error': 'Insufficient data after cleaning'}
        
        # Prepare features and target
        features = ['day', 'day_of_week', 'month', 'day_of_year']
        lag_features = [col for col in df_clean.columns if col.startswith('lag_')]
        features.extend(lag_features)
        
        X = df_clean[features].values
        y = df_clean[revenue_field].values
        
        # Scale features
        X_scaled = self.scaler.fit_transform(X)
        
        # Train model
        if model_type == 'linear':
            model = LinearRegression()
        elif model_type == 'random_forest':
            model = RandomForestRegressor(n_estimators=100, random_state=42)
        else:
            model = LinearRegression()
        
        model.fit(X_scaled, y)
        
        # Generate forecast
        last_date = df[date_field].max()
        forecast_dates = [last_date + timedelta(days=i+1) for i in range(periods)]
        
        forecast_data = []
        last_values = df_clean[revenue_field].values[-30:]  # Last 30 values
        
        for i, forecast_date in enumerate(forecast_dates):
            # Prepare features for this forecast period
            day = forecast_date.day
            day_of_week = forecast_date.dayofweek
            month = forecast_date.month
            day_of_year = forecast_date.dayofyear
            
            # Create lag values (using forecasted values for future periods)
            lag_1 = forecast_data[i-1]['forecast'] if i > 0 else last_values[-1]
            lag_7 = forecast_data[i-7]['forecast'] if i >= 7 else last_values[-7] if len(last_values) >= 7 else last_values[-1]
            lag_30 = forecast_data[i-30]['forecast'] if i >= 30 else last_values[-30] if len(last_values) >= 30 else last_values[-1]
            
            # Create feature vector
            features_vec = np.array([day, day_of_week, month, day_of_year, lag_1, lag_7, lag_30])
            
            # Ensure correct length
            if len(features_vec) > len(features):
                features_vec = features_vec[:len(features)]
            elif len(features_vec) < len(features):
                features_vec = np.pad(features_vec, (0, len(features) - len(features_vec)), 'constant')
            
            # Scale and predict
            features_scaled = self.scaler.transform([features_vec])
            forecast_value = model.predict(features_scaled)[0]
            
            forecast_data.append({
                'date': forecast_date,
                'forecast': float(forecast_value),
                'confidence': max(0, 95 - (i * 2))  # Decreasing confidence
            })
        
        # Calculate model performance metrics
        y_pred = model.predict(X_scaled)
        
        from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
        
        mae = mean_absolute_error(y, y_pred)
        rmse = np.sqrt(mean_squared_error(y, y_pred))
        r2 = r2_score(y, y_pred)
        
        return {
            'forecast': forecast_data,
            'model_performance': {
                'mae': mae,
                'rmse': rmse,
                'r2': r2,
                'model_type': model_type
            },
            'historical_stats': self.calculate_statistics(historical_data, revenue_field),
            'total_forecast': sum(f['forecast'] for f in forecast_data),
            'avg_daily_forecast': sum(f['forecast'] for f in forecast_data) / len(forecast_data)
        }
    
    def segment_users(
        self,
        user_data: List[Dict],
        n_clusters: int = 4,
        features: List[str] = None
    ) -> Dict[str, Any]:
        """
        Segment users using clustering
        
        Args:
            user_data: User analytics data
            n_clusters: Number of clusters
            features: Features to use for clustering
        
        Returns:
            User segments
        """
        if not user_data:
            return {}
        
        df = pd.DataFrame(user_data)
        
        # Default features if not specified
        if not features:
            features = [
                'login_count', 'tasks_completed', 'earnings_total',
                'engagement_score', 'session_duration_avg'
            ]
        
        # Filter available features
        available_features = [f for f in features if f in df.columns]
        
        if len(available_features) < 2:
            return {'error': 'Insufficient features for clustering'}
        
        # Prepare data
        X = df[available_features].fillna(0).values
        
        # Scale data
        from sklearn.preprocessing import StandardScaler
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        
        # Apply clustering
        from sklearn.cluster import KMeans
        kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        df['cluster'] = kmeans.fit_predict(X_scaled)
        
        # Calculate cluster statistics
        cluster_stats = {}
        for cluster_id in range(n_clusters):
            cluster_data = df[df['cluster'] == cluster_id]
            
            if len(cluster_data) > 0:
                stats = {}
                for feature in available_features:
                    stats[feature] = {
                        'mean': float(cluster_data[feature].mean()),
                        'median': float(cluster_data[feature].median()),
                        'std': float(cluster_data[feature].std())
                    }
                
                cluster_stats[f'cluster_{cluster_id}'] = {
                    'size': len(cluster_data),
                    'percentage': (len(cluster_data) / len(df)) * 100,
                    'stats': stats,
                    'user_ids': cluster_data['user_id'].tolist() if 'user_id' in cluster_data.columns else []
                }
        
        # Assign cluster names based on characteristics
        cluster_names = {}
        for cluster_id, stats in cluster_stats.items():
            if 'engagement_score' in stats['stats']:
                engagement = stats['stats']['engagement_score']['mean']
                earnings = stats['stats']['earnings_total']['mean'] if 'earnings_total' in stats['stats'] else 0
                
                if engagement > 70 and earnings > 100:
                    cluster_names[cluster_id] = 'Power Users'
                elif engagement > 50 and earnings > 10:
                    cluster_names[cluster_id] = 'Regular Users'
                elif engagement > 20:
                    cluster_names[cluster_id] = 'Casual Users'
                else:
                    cluster_names[cluster_id] = 'Inactive Users'
            else:
                cluster_names[cluster_id] = f'Segment {cluster_id}'
        
        return {
            'clusters': cluster_stats,
            'cluster_names': cluster_names,
            'total_users': len(df),
            'features_used': available_features,
            'inertia': float(kmeans.inertia_)
        }
    
    def calculate_correlation(
        self,
        data: List[Dict],
        variables: List[str] = None
    ) -> pd.DataFrame:
        """
        Calculate correlation matrix
        
        Args:
            data: Data for correlation analysis
            variables: Variables to include
        
        Returns:
            Correlation matrix
        """
        if not data:
            return pd.DataFrame()
        
        df = pd.DataFrame(data)
        
        # Use all numeric columns if variables not specified
        if not variables:
            variables = df.select_dtypes(include=[np.number]).columns.tolist()
        
        # Filter available variables
        available_vars = [v for v in variables if v in df.columns]
        
        if len(available_vars) < 2:
            return pd.DataFrame()
        
        # Calculate correlation matrix
        correlation_matrix = df[available_vars].corr()
        
        return correlation_matrix
    
    def identify_key_drivers(
        self,
        data: List[Dict],
        target_variable: str,
        feature_variables: List[str] = None
    ) -> List[Dict]:
        """
        Identify key drivers for a target variable
        
        Args:
            data: Data for analysis
            target_variable: Target variable to explain
            feature_variables: Feature variables to consider
        
        Returns:
            Key drivers with importance scores
        """
        if not data:
            return []
        
        df = pd.DataFrame(data)
        
        if target_variable not in df.columns:
            return []
        
        # Use all other numeric columns as features if not specified
        if not feature_variables:
            feature_variables = [
                col for col in df.select_dtypes(include=[np.number]).columns
                if col != target_variable
            ]
        
        # Filter available features
        available_features = [f for f in feature_variables if f in df.columns]
        
        if len(available_features) < 1:
            return []
        
        # Prepare data
        df_clean = df[[target_variable] + available_features].dropna()
        
        if len(df_clean) < 10:
            return []
        
        X = df_clean[available_features].values
        y = df_clean[target_variable].values
        
        # Scale features
        X_scaled = self.scaler.fit_transform(X)
        
        # Train random forest to get feature importance
        from sklearn.ensemble import RandomForestRegressor
        
        model = RandomForestRegressor(n_estimators=100, random_state=42)
        model.fit(X_scaled, y)
        
        # Get feature importance
        importance = model.feature_importances_
        
        # Create results
        drivers = []
        for i, feature in enumerate(available_features):
            drivers.append({
                'feature': feature,
                'importance': float(importance[i]),
                'correlation': float(df_clean[feature].corr(df_clean[target_variable])),
                'impact': 'positive' if df_clean[feature].corr(df_clean[target_variable]) > 0 else 'negative'
            })
        
        # Sort by importance
        drivers.sort(key=lambda x: x['importance'], reverse=True)
        
        return drivers
    
    def test_alert_rule(self, alert_rule) -> Dict:
        """
        Test an alert rule with historical data
        
        Args:
            alert_rule: AlertRule instance
        
        Returns:
            Test results
        """
        from ..models import RealTimeMetric
        
        # Get historical data for the metric
        time_window = timedelta(seconds=alert_rule.time_window)
        start_time = timezone.now() - time_window
        
        metrics = RealTimeMetric.objects.filter(
            metric_type=alert_rule.metric_type,
            metric_time__gte=start_time
        ).order_by('metric_time')
        
        if not metrics:
            return {'status': 'no_data', 'message': 'No historical data found'}
        
        # Test the condition
        test_results = []
        condition_met_count = 0
        
        for metric in metrics:
            value = metric.value
            condition_met = False
            
            if alert_rule.condition == 'greater_than':
                condition_met = value > alert_rule.threshold_value
            elif alert_rule.condition == 'less_than':
                condition_met = value < alert_rule.threshold_value
            elif alert_rule.condition == 'equal_to':
                condition_met = value == alert_rule.threshold_value
            elif alert_rule.condition == 'not_equal':
                condition_met = value != alert_rule.threshold_value
            elif alert_rule.condition == 'in_range':
                condition_met = alert_rule.threshold_value <= value <= alert_rule.threshold_value_2
            elif alert_rule.condition == 'out_of_range':
                condition_met = value < alert_rule.threshold_value or value > alert_rule.threshold_value_2
            
            test_results.append({
                'time': metric.metric_time,
                'value': value,
                'condition_met': condition_met
            })
            
            if condition_met:
                condition_met_count += 1
        
        # Calculate statistics
        total_tests = len(test_results)
        condition_percentage = (condition_met_count / total_tests) * 100 if total_tests > 0 else 0
        
        # Determine if rule would have triggered
        would_trigger = condition_met_count > 0
        
        return {
            'status': 'tested',
            'rule_name': alert_rule.name,
            'metric_type': alert_rule.metric_type,
            'condition': alert_rule.condition,
            'threshold': alert_rule.threshold_value,
            'time_window': alert_rule.time_window,
            'total_tests': total_tests,
            'condition_met_count': condition_met_count,
            'condition_percentage': condition_percentage,
            'would_trigger': would_trigger,
            'test_results': test_results[:10],  # Return first 10 results
            'recommendation': self._generate_alert_recommendation(condition_percentage)
        }
    
    def _generate_alert_recommendation(self, condition_percentage: float) -> str:
        """Generate recommendation for alert rule based on test results"""
        if condition_percentage > 50:
            return "Alert would trigger frequently. Consider adjusting threshold or time window."
        elif condition_percentage > 20:
            return "Alert would trigger occasionally. Threshold seems appropriate."
        elif condition_percentage > 5:
            return "Alert would trigger rarely. Consider lowering threshold if you want more alerts."
        else:
            return "Alert would almost never trigger. Consider adjusting threshold or condition."