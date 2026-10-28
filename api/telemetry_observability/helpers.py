"""
Helper functions for Telemetry Observability.
"""
from typing import Dict, Any, Optional, List
from django.utils import timezone
from datetime import timedelta
import json


def format_metric_value(value: float, metric_type: str = 'counter', unit: str = '') -> str:
    """
    Format a metric value for display.
    
    Args:
        value: Metric value
        metric_type: Type of metric
        unit: Unit of measurement
        
    Returns:
        Formatted value string
    """
    if metric_type == 'counter':
        return f"{int(value)} {unit}" if unit else f"{int(value)}"
    elif metric_type == 'gauge':
        return f"{value:.2f} {unit}" if unit else f"{value:.2f}"
    else:
        return f"{value:.2f} {unit}" if unit else f"{value:.2f}"


def calculate_aggregation(values: List[float], aggregation: str = 'avg') -> float:
    """
    Calculate aggregation of values.
    
    Args:
        values: List of values
        aggregation: Aggregation type (avg, sum, min, max, count)
        
    Returns:
        Aggregated value
    """
    if not values:
        return 0.0
    
    if aggregation == 'avg':
        return round(sum(values) / len(values), 2)
    elif aggregation == 'sum':
        return round(sum(values), 2)
    elif aggregation == 'min':
        return round(min(values), 2)
    elif aggregation == 'max':
        return round(max(values), 2)
    elif aggregation == 'count':
        return float(len(values))
    else:
        return 0.0


def get_time_bucket(timestamp: timezone.datetime, interval: str = 'hour') -> str:
    """
    Get time bucket for aggregation.
    
    Args:
        timestamp: Timestamp to bucket
        interval: Time interval (minute, hour, day, week, month)
        
    Returns:
        Time bucket string
    """
    if interval == 'minute':
        return timestamp.strftime('%Y-%m-%d %H:%M')
    elif interval == 'hour':
        return timestamp.strftime('%Y-%m-%d %H:00')
    elif interval == 'day':
        return timestamp.strftime('%Y-%m-%d')
    elif interval == 'week':
        return timestamp.strftime('%Y-W%W')
    elif interval == 'month':
        return timestamp.strftime('%Y-%m')
    else:
        return timestamp.isoformat()


def parse_time_range(time_range: str) -> tuple:
    """
    Parse a time range string.
    
    Args:
        time_range: Time range string (e.g., "1h", "24h", "7d")
        
    Returns:
        Tuple of (start_time, end_time)
    """
    end_time = timezone.now()
    
    if time_range.endswith('m'):
        minutes = int(time_range[:-1])
        start_time = end_time - timedelta(minutes=minutes)
    elif time_range.endswith('h'):
        hours = int(time_range[:-1])
        start_time = end_time - timedelta(hours=hours)
    elif time_range.endswith('d'):
        days = int(time_range[:-1])
        start_time = end_time - timedelta(days=days)
    elif time_range.endswith('w'):
        weeks = int(time_range[:-1])
        start_time = end_time - timedelta(weeks=weeks)
    else:
        # Default to 1 hour
        start_time = end_time - timedelta(hours=1)
    
    return start_time, end_time


def sanitize_query_string(query: str) -> str:
    """
    Sanitize a query string.
    
    Args:
        query: Query string to sanitize
        
    Returns:
        Sanitized query string
    """
    if not query:
        return ''
    
    # Remove potentially dangerous characters
    sanitized = query.replace('\x00', '').replace('\x1b', '')
    
    # Limit length
    if len(sanitized) > 1000:
        sanitized = sanitized[:1000]
    
    return sanitized


def extract_labels_from_context(context: Dict[str, Any]) -> Dict[str, str]:
    """
    Extract labels from a context dictionary.
    
    Args:
        context: Context dictionary
        
    Returns:
        Labels dictionary
    """
    labels = {}
    
    label_keys = ['service', 'environment', 'source', 'component', 'version']
    for key in label_keys:
        if key in context:
            labels[key] = str(context[key])
    
    return labels


def format_log_context(context: Dict[str, Any]) -> str:
    """
    Format log context for display.
    
    Args:
        context: Context dictionary
        
    Returns:
        Formatted context string
    """
    if not context:
        return ''
    
    formatted = []
    for key, value in context.items():
        if isinstance(value, (dict, list)):
            formatted.append(f"{key}={json.dumps(value)}")
        else:
            formatted.append(f"{key}={value}")
    
    return ' '.join(formatted)


def calculate_trend(values: List[float], window: int = 5) -> float:
    """
    Calculate trend of values.
    
    Args:
        values: List of values
        window: Window size for trend calculation
        
    Returns:
        Trend value (positive = increasing, negative = decreasing)
    """
    if len(values) < 2:
        return 0.0
    
    # Calculate moving average
    if len(values) > window:
        recent_avg = sum(values[-window:]) / window
        older_avg = sum(values[-(window*2):-window]) / window
    else:
        recent_avg = sum(values[-len(values)//2:]) / (len(values)//2)
        older_avg = sum(values[:len(values)//2]) / (len(values)//2)
    
    return round(recent_avg - older_avg, 2)


def detect_anomaly(values: List[float], threshold: float = 2.0) -> bool:
    """
    Detect if the last value is an anomaly.
    
    Args:
        values: List of values
        threshold: Standard deviation threshold
        
    Returns:
        True if anomaly detected
    """
    if len(values) < 3:
        return False
    
    import statistics
    
    mean = statistics.mean(values[:-1])
    std_dev = statistics.stdev(values[:-1]) if len(values) > 2 else 0
    
    if std_dev == 0:
        return False
    
    last_value = values[-1]
    z_score = abs(last_value - mean) / std_dev
    
    return z_score > threshold


def generate_dashboard_title(widget_type: str, data_source: str) -> str:
    """
    Generate a dashboard widget title.
    
    Args:
        widget_type: Type of widget
        data_source: Data source
        
    Returns:
        Generated title
    """
    titles = {
        'line_chart': f'{data_source} Over Time',
        'bar_chart': f'{data_source} Distribution',
        'pie_chart': f'{data_source} Breakdown',
        'gauge': f'{data_source} Status',
        'table': f'{data_source} Table',
        'metric_card': f'{data_source} Summary',
        'log_view': f'{data_source} Logs',
        'trace_view': f'{data_source} Traces',
        'alert_list': f'{data_source} Alerts'
    }
    
    return titles.get(widget_type, f'{data_source} Dashboard')


def validate_widget_config(config: Dict[str, Any]) -> bool:
    """
    Validate widget configuration.
    
    Args:
        config: Widget configuration
        
    Returns:
        True if valid
    """
    required_fields = ['widget_type', 'data_source']
    
    for field in required_fields:
        if field not in config:
            return False
    
    return True


def merge_widget_configs(*configs: Dict[str, Any]) -> Dict[str, Any]:
    """
    Merge multiple widget configurations.
    
    Args:
        *configs: Configuration dictionaries to merge
        
    Returns:
        Merged configuration
    """
    merged = {}
    for config in configs:
        merged.update(config)
    return merged


def get_widget_refresh_rate(widget_type: str) -> int:
    """
    Get recommended refresh rate for a widget type.
    
    Args:
        widget_type: Type of widget
        
    Returns:
        Refresh rate in seconds
    """
    refresh_rates = {
        'line_chart': 30,
        'bar_chart': 60,
        'pie_chart': 300,
        'gauge': 10,
        'table': 60,
        'metric_card': 15,
        'log_view': 5,
        'trace_view': 30,
        'alert_list': 10
    }
    
    return refresh_rates.get(widget_type, 60)


def calculate_dashboard_layout(widgets: List[Dict[str, Any]], max_width: int = 12) -> List[Dict[str, Any]]:
    """
    Calculate dashboard widget layout.
    
    Args:
        widgets: List of widgets
        max_width: Maximum width of dashboard
        
    Returns:
        List of widgets with calculated positions
    """
    layout = []
    current_x = 0
    current_y = 0
    
    for widget in widgets:
        width = widget.get('width', 4)
        height = widget.get('height', 4)
        
        # Check if widget fits in current row
        if current_x + width > max_width:
            current_x = 0
            current_y += 4  # Move to next row
        
        widget['position_x'] = current_x
        widget['position_y'] = current_y
        
        layout.append(widget)
        
        current_x += width
    
    return layout


def export_dashboard_config(dashboard_id: int) -> Dict[str, Any]:
    """
    Export dashboard configuration.
    
    Args:
        dashboard_id: Dashboard ID
        
    Returns:
        Exported configuration
    """
    from .models.dashboard_widget import DashboardWidget
    
    widgets = DashboardWidget.objects.filter(dashboard_id=dashboard_id)
    
    return {
        'dashboard_id': dashboard_id,
        'widgets': [
            {
                'name': widget.name,
                'widget_type': widget.widget_type,
                'data_source': widget.data_source,
                'query': widget.query,
                'config': widget.config,
                'position_x': widget.position_x,
                'position_y': widget.position_y,
                'width': widget.width,
                'height': widget.height,
                'refresh_interval': widget.refresh_interval
            }
            for widget in widgets
        ]
    }


def import_dashboard_config(config: Dict[str, Any]) -> bool:
    """
    Import dashboard configuration.
    
    Args:
        config: Configuration to import
        
    Returns:
        True if successful
    """
    from .models.dashboard_widget import DashboardWidget
    
    try:
        dashboard_id = config.get('dashboard_id')
        widgets = config.get('widgets', [])
        
        for widget_config in widgets:
            DashboardWidget.objects.create(
                dashboard_id=dashboard_id,
                name=widget_config['name'],
                widget_type=widget_config['widget_type'],
                data_source=widget_config['data_source'],
                query=widget_config.get('query', {}),
                config=widget_config.get('config', {}),
                position_x=widget_config.get('position_x', 0),
                position_y=widget_config.get('position_y', 0),
                width=widget_config.get('width', 4),
                height=widget_config.get('height', 4),
                refresh_interval=widget_config.get('refresh_interval', 60)
            )
        
        return True
    except Exception:
        return False
