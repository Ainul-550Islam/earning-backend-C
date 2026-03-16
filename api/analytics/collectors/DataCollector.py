import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from django.db.models import Count, Sum, Avg, F, Q, Max, Min
from django.db.models.functions import TruncDate, TruncHour, TruncDay, TruncMonth
from django.utils import timezone
from django.core.cache import cache
import pandas as pd
import numpy as np
from collections import defaultdict

logger = logging.getLogger(__name__)

class DataCollector:
    """
    Base data collector for analytics
    Handles data collection, aggregation, and caching
    """
    
    def __init__(self, cache_timeout: int = 300):
        """
        Args:
            cache_timeout: Cache timeout in seconds
        """
        self.cache_timeout = cache_timeout
    
    def collect_data(
        self,
        model_class,
        filters: Dict = None,
        group_by: List[str] = None,
        aggregations: Dict = None,
        date_field: str = 'created_at',
        start_date: datetime = None,
        end_date: datetime = None,
        use_cache: bool = True
    ) -> List[Dict]:
        """
        Collect and aggregate data from a model
        
        Args:
            model_class: Django model class
            filters: Query filters
            group_by: Fields to group by
            aggregations: Aggregation functions
            date_field: Date field for filtering
            start_date: Start date for filtering
            end_date: End date for filtering
            use_cache: Whether to use cache
        
        Returns:
            List of aggregated data
        """
        # Generate cache key
        cache_key = self._generate_cache_key(
            model_class.__name__,
            filters,
            group_by,
            aggregations,
            start_date,
            end_date
        )
        
        # Check cache
        if use_cache:
            cached_data = cache.get(cache_key)
            if cached_data:
                logger.debug(f"Cache hit for {cache_key}")
                return cached_data
        
        # Build query
        queryset = model_class.objects.all()
        
        # Apply filters
        if filters:
            queryset = queryset.filter(**filters)
        
        # Apply date range
        if start_date:
            date_filter = {f"{date_field}__gte": start_date}
            queryset = queryset.filter(**date_filter)
        
        if end_date:
            date_filter = {f"{date_field}__lte": end_date}
            queryset = queryset.filter(**date_filter)
        
        # Apply group by
        if group_by:
            # Handle date truncation
            annotate_kwargs = {}
            for field in group_by:
                if field.startswith('trunc_'):
                    # Handle truncation: trunc_day, trunc_hour, etc.
                    trunc_type = field.replace('trunc_', '')
                    if trunc_type == 'day':
                        annotate_kwargs[field] = TruncDate(date_field)
                    elif trunc_type == 'hour':
                        annotate_kwargs[field] = TruncHour(date_field)
                    elif trunc_type == 'month':
                        annotate_kwargs[field] = TruncMonth(date_field)
                else:
                    annotate_kwargs[field] = F(field)
            
            queryset = queryset.annotate(**annotate_kwargs)
        
        # Apply aggregations
        if aggregations:
            aggregation_map = {
                'count': Count('id'),
                'sum': Sum,
                'avg': Avg,
                'max': Max,
                'min': Min
            }
            
            annotation_kwargs = {}
            for agg_field, agg_config in aggregations.items():
                if isinstance(agg_config, dict):
                    # Complex aggregation
                    agg_type = agg_config.get('type', 'count')
                    field = agg_config.get('field', 'id')
                    
                    if agg_type == 'count':
                        annotation_kwargs[agg_field] = Count(field)
                    elif agg_type == 'sum':
                        annotation_kwargs[agg_field] = Sum(field)
                    elif agg_type == 'avg':
                        annotation_kwargs[agg_field] = Avg(field)
                    elif agg_type == 'max':
                        annotation_kwargs[agg_field] = Max(field)
                    elif agg_type == 'min':
                        annotation_kwargs[agg_field] = Min(field)
                else:
                    # Simple count
                    annotation_kwargs[agg_field] = Count(agg_config)
            
            queryset = queryset.annotate(**annotation_kwargs)
        
        # Group by
        if group_by:
            group_by_fields = list(annotate_kwargs.keys())
            values_fields = group_by_fields + list(aggregations.keys()) if aggregations else group_by_fields
            data = list(queryset.values(*values_fields))
        else:
            data = list(queryset.values())
        
        # Cache results
        if use_cache:
            cache.set(cache_key, data, self.cache_timeout)
            logger.debug(f"Cached data for {cache_key}")
        
        return data
    
    def collect_time_series(
        self,
        model_class,
        metric_field: str,
        date_field: str = 'created_at',
        start_date: datetime = None,
        end_date: datetime = None,
        interval: str = 'day',
        aggregation: str = 'count',
        filters: Dict = None
    ) -> List[Dict]:
        """
        Collect time series data
        
        Args:
            model_class: Django model class
            metric_field: Field to aggregate
            date_field: Date field for grouping
            start_date: Start date
            end_date: End date
            interval: Time interval (hour, day, week, month)
            aggregation: Aggregation type (count, sum, avg)
            filters: Additional filters
        
        Returns:
            Time series data
        """
        # Set default dates
        if not start_date:
            start_date = timezone.now() - timedelta(days=30)
        if not end_date:
            end_date = timezone.now()
        
        # Build query
        queryset = model_class.objects.filter(
            **{f"{date_field}__gte": start_date, f"{date_field}__lte": end_date}
        )
        
        if filters:
            queryset = queryset.filter(**filters)
        
        # Truncate date based on interval
        trunc_map = {
            'hour': TruncHour(date_field),
            'day': TruncDate(date_field),
            'week': TruncDate(date_field),  # Would need custom week truncation
            'month': TruncMonth(date_field)
        }
        
        trunc_func = trunc_map.get(interval, TruncDate(date_field))
        
        # Aggregate
        aggregation_map = {
            'count': Count('id'),
            'sum': Sum(metric_field),
            'avg': Avg(metric_field)
        }
        
        agg_func = aggregation_map.get(aggregation, Count('id'))
        
        # Group by truncated date
        time_series = queryset.annotate(
            period=trunc_func
        ).values('period').annotate(
            value=agg_func
        ).order_by('period')
        
        # Fill missing periods
        filled_series = self._fill_time_series_gaps(
            list(time_series),
            start_date,
            end_date,
            interval
        )
        
        return filled_series
    
    def collect_funnel_data(
        self,
        stages: List[Dict],
        user_field: str = 'user_id',
        date_field: str = 'created_at',
        start_date: datetime = None,
        end_date: datetime = None
    ) -> Dict:
        """
        Collect funnel conversion data
        
        Args:
            stages: List of stage definitions
            user_field: User identifier field
            date_field: Date field for filtering
            start_date: Start date
            end_date: End date
        
        Returns:
            Funnel data with conversion rates
        """
        if not stages:
            return {}
        
        # Build date filter
        date_filter = {}
        if start_date:
            date_filter[f'{date_field}__gte'] = start_date
        if end_date:
            date_filter[f'{date_field}__lte'] = end_date
        
        funnel_data = {
            'stages': [],
            'total_entered': 0,
            'total_converted': 0,
            'drop_offs': []
        }
        
        previous_stage_users = set()
        
        for i, stage in enumerate(stages):
            model_class = stage['model']
            filters = stage.get('filters', {})
            
            # Apply date filter
            filters.update(date_filter)
            
            # Get unique users for this stage
            stage_users = set(model_class.objects.filter(
                **filters
            ).values_list(user_field, flat=True).distinct())
            
            # Calculate stage metrics
            stage_count = len(stage_users)
            
            if i == 0:
                # First stage
                entered = stage_count
                conversion_from_previous = 100.0
            else:
                # Calculate conversion from previous stage
                conversion_from_previous = self._calculate_conversion_rate(
                    len(previous_stage_users.intersection(stage_users)),
                    len(previous_stage_users)
                )
                
                # Calculate drop-off
                drop_off = len(previous_stage_users) - len(previous_stage_users.intersection(stage_users))
                funnel_data['drop_offs'].append({
                    'from_stage': stages[i-1]['name'],
                    'to_stage': stage['name'],
                    'drop_off_count': drop_off,
                    'drop_off_rate': 100 - conversion_from_previous
                })
            
            # Calculate overall conversion rate
            overall_conversion = self._calculate_conversion_rate(
                len(stage_users),
                funnel_data['total_entered'] if funnel_data['total_entered'] > 0 else stage_count
            )
            
            funnel_data['stages'].append({
                'name': stage['name'],
                'user_count': stage_count,
                'conversion_from_previous': conversion_from_previous,
                'overall_conversion': overall_conversion,
                'users': list(stage_users)[:100]  # Limit for performance
            })
            
            previous_stage_users = stage_users
            
            # Update totals
            if i == 0:
                funnel_data['total_entered'] = stage_count
            if i == len(stages) - 1:
                funnel_data['total_converted'] = stage_count
        
        return funnel_data
    
    def collect_retention_data(
        self,
        user_model_class,
        activity_model_class,
        cohort_field: str = 'date_joined',
        activity_field: str = 'created_at',
        cohort_period: str = 'month',
        activity_periods: List[int] = [1, 7, 14, 30, 60, 90],
        start_date: datetime = None,
        end_date: datetime = None
    ) -> List[Dict]:
        """
        Collect user retention data
        
        Args:
            user_model_class: User model class
            activity_model_class: Activity model class
            cohort_field: Cohort definition field
            activity_field: Activity date field
            cohort_period: Cohort period (day, week, month)
            activity_periods: Activity periods to measure
            start_date: Start date
            end_date: End date
        
        Returns:
            Retention data by cohort
        """
        if not start_date:
            start_date = timezone.now() - timedelta(days=180)
        if not end_date:
            end_date = timezone.now()
        
        # Get cohorts
        trunc_map = {
            'day': TruncDate(cohort_field),
            'week': TruncDate(cohort_field),  # Would need custom week
            'month': TruncMonth(cohort_field)
        }
        
        trunc_func = trunc_map.get(cohort_period, TruncMonth(cohort_field))
        
        cohorts = user_model_class.objects.filter(
            **{f"{cohort_field}__gte": start_date, f"{cohort_field}__lte": end_date}
        ).annotate(
            cohort=trunc_func
        ).values('cohort').annotate(
            user_count=Count('id'),
            user_ids=ArrayAgg('id')
        ).order_by('cohort')
        
        retention_data = []
        
        for cohort in cohorts:
            cohort_date = cohort['cohort']
            cohort_users = set(cohort['user_ids'])
            
            cohort_retention = {
                'cohort_date': cohort_date,
                'cohort_size': len(cohort_users),
                'retention_rates': {}
            }
            
            # Calculate retention for each period
            for period in activity_periods:
                period_end_date = cohort_date + timedelta(days=period)
                
                # Get active users in this period
                active_users = activity_model_class.objects.filter(
                    user_id__in=cohort_users,
                    **{f"{activity_field}__gte": cohort_date, f"{activity_field}__lte": period_end_date}
                ).values_list('user_id', flat=True).distinct()
                
                retention_rate = self._calculate_conversion_rate(
                    len(active_users),
                    len(cohort_users)
                )
                
                cohort_retention['retention_rates'][f'day_{period}'] = retention_rate
            
            retention_data.append(cohort_retention)
        
        return retention_data
    
    def collect_segmented_data(
        self,
        model_class,
        segment_field: str,
        metric_field: str,
        segmentation_type: str = 'categorical',
        segments: List = None,
        date_field: str = 'created_at',
        start_date: datetime = None,
        end_date: datetime = None,
        aggregation: str = 'count'
    ) -> Dict:
        """
        Collect data segmented by a field
        
        Args:
            model_class: Django model class
            segment_field: Field to segment by
            metric_field: Metric field
            segmentation_type: Type of segmentation
            segments: Predefined segments
            date_field: Date field
            start_date: Start date
            end_date: End date
            aggregation: Aggregation type
        
        Returns:
            Segmented data
        """
        # Build query
        filters = {}
        if start_date:
            filters[f'{date_field}__gte'] = start_date
        if end_date:
            filters[f'{date_field}__lte'] = end_date
        
        queryset = model_class.objects.filter(**filters)
        
        # Define segments if not provided
        if not segments and segmentation_type == 'categorical':
            # Get distinct values for categorical segmentation
            segments = list(queryset.values_list(segment_field, flat=True).distinct())
        elif segmentation_type == 'range':
            # Define ranges for numerical segmentation
            min_val = queryset.aggregate(min=Min(segment_field))['min'] or 0
            max_val = queryset.aggregate(max=Max(segment_field))['max'] or 100
            
            if not segments:
                # Create 10 equal ranges
                range_size = (max_val - min_val) / 10
                segments = [
                    (min_val + i * range_size, min_val + (i + 1) * range_size)
                    for i in range(10)
                ]
        
        segmented_data = {}
        
        if segmentation_type == 'categorical':
            for segment in segments:
                segment_filters = filters.copy()
                segment_filters[segment_field] = segment
                
                segment_query = model_class.objects.filter(**segment_filters)
                
                # Apply aggregation
                if aggregation == 'count':
                    value = segment_query.count()
                elif aggregation == 'sum':
                    value = segment_query.aggregate(sum=Sum(metric_field))['sum'] or 0
                elif aggregation == 'avg':
                    value = segment_query.aggregate(avg=Avg(metric_field))['avg'] or 0
                else:
                    value = segment_query.count()
                
                segmented_data[segment] = value
        
        elif segmentation_type == 'range':
            for range_start, range_end in segments:
                segment_filters = filters.copy()
                segment_filters[f'{segment_field}__gte'] = range_start
                segment_filters[f'{segment_field}__lt'] = range_end
                
                segment_query = model_class.objects.filter(**segment_filters)
                
                # Apply aggregation
                if aggregation == 'count':
                    value = segment_query.count()
                elif aggregation == 'sum':
                    value = segment_query.aggregate(sum=Sum(metric_field))['sum'] or 0
                elif aggregation == 'avg':
                    value = segment_query.aggregate(avg=Avg(metric_field))['avg'] or 0
                else:
                    value = segment_query.count()
                
                segment_name = f"{range_start}-{range_end}"
                segmented_data[segment_name] = value
        
        return segmented_data
    
    # Helper methods
    def _generate_cache_key(
        self,
        model_name: str,
        filters: Dict,
        group_by: List,
        aggregations: Dict,
        start_date: datetime,
        end_date: datetime
    ) -> str:
        """Generate cache key from parameters"""
        key_parts = [
            f"collector:{model_name}",
            f"filters:{hash(str(filters))}",
            f"group:{hash(str(group_by))}",
            f"agg:{hash(str(aggregations))}",
            f"start:{start_date.isoformat() if start_date else 'none'}",
            f"end:{end_date.isoformat() if end_date else 'none'}"
        ]
        return ":".join(key_parts)
    
    def _fill_time_series_gaps(
        self,
        time_series: List[Dict],
        start_date: datetime,
        end_date: datetime,
        interval: str
    ) -> List[Dict]:
        """Fill gaps in time series data"""
        if not time_series:
            return []
        
        # Convert to DataFrame
        df = pd.DataFrame(time_series)
        df['period'] = pd.to_datetime(df['period'])
        df.set_index('period', inplace=True)
        
        # Create date range
        if interval == 'hour':
            freq = 'H'
        elif interval == 'day':
            freq = 'D'
        elif interval == 'week':
            freq = 'W'
        elif interval == 'month':
            freq = 'M'
        else:
            freq = 'D'
        
        date_range = pd.date_range(start=start_date, end=end_date, freq=freq)
        
        # Reindex and fill gaps
        df = df.reindex(date_range, fill_value=0)
        
        # Convert back to list of dicts
        filled_series = []
        for date, row in df.iterrows():
            filled_series.append({
                'period': date.to_pydatetime(),
                'value': row['value'] if 'value' in row else 0
            })
        
        return filled_series
    
    def _calculate_conversion_rate(self, converted: int, total: int) -> float:
        """Calculate conversion rate percentage"""
        if total == 0:
            return 0.0
        return round((converted / total) * 100, 2)
    
    def clear_cache(self, pattern: str = "collector:*"):
        """Clear cached data"""
        from django.core.cache import cache
        cache.delete_pattern(pattern)
        logger.info(f"Cleared cache with pattern: {pattern}")