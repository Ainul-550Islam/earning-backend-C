"""
Tenant Management Formatters

This module contains formatting utilities for tenant management operations
including data formatting, display formatting, and output formatting.
"""

import json
from datetime import datetime, timedelta
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.contrib.humanize.templatetags.humanize import naturaltime, naturalday


class TenantFormatter:
    """Formatter class for tenant-related data."""
    
    @staticmethod
    def format_tenant_status(status):
        """
        Format tenant status for display.
        
        Args:
            status (str): Tenant status
            
        Returns:
            dict: Formatted status with label and color
        """
        status_map = {
            'active': {
                'label': _('Active'),
                'color': 'green',
                'icon': 'check-circle'
            },
            'inactive': {
                'label': _('Inactive'),
                'color': 'gray',
                'icon': 'pause-circle'
            },
            'suspended': {
                'label': _('Suspended'),
                'color': 'red',
                'icon': 'stop-circle'
            },
            'trial': {
                'label': _('Trial'),
                'color': 'blue',
                'icon': 'clock-circle'
            },
            'expired': {
                'label': _('Expired'),
                'color': 'orange',
                'icon': 'exclamation-circle'
            }
        }
        
        return status_map.get(status, {
            'label': status.title(),
            'color': 'gray',
            'icon': 'question-circle'
        })
    
    @staticmethod
    def format_tenant_tier(tier):
        """
        Format tenant tier for display.
        
        Args:
            tier (str): Tenant tier
            
        Returns:
            dict: Formatted tier with label and color
        """
        tier_map = {
            'basic': {
                'label': _('Basic'),
                'color': 'blue',
                'description': _('Essential features for small teams')
            },
            'professional': {
                'label': _('Professional'),
                'color': 'purple',
                'description': _('Advanced features for growing businesses')
            },
            'enterprise': {
                'label': _('Enterprise'),
                'color': 'gold',
                'description': _('Complete solution for large organizations')
            },
            'custom': {
                'label': _('Custom'),
                'color': 'green',
                'description': _('Tailored solution for specific needs')
            }
        }
        
        return tier_map.get(tier, {
            'label': tier.title(),
            'color': 'gray',
            'description': ''
        })
    
    @staticmethod
    def format_tenant_info(tenant):
        """
        Format comprehensive tenant information.
        
        Args:
            tenant: Tenant instance
            
        Returns:
            dict: Formatted tenant information
        """
        return {
            'id': tenant.id,
            'name': tenant.name,
            'slug': tenant.slug,
            'domain': tenant.domain,
            'admin_email': tenant.admin_email,
            'status': TenantFormatter.format_tenant_status(tenant.status),
            'tier': TenantFormatter.format_tenant_tier(tenant.tier),
            'created_at': TenantFormatter.format_datetime(tenant.created_at),
            'updated_at': TenantFormatter.format_datetime(tenant.updated_at),
            'is_active': tenant.is_active,
            'is_suspended': tenant.is_suspended,
            'trial_info': TenantFormatter.format_trial_info(tenant) if hasattr(tenant, 'trial_ends_at') else None
        }
    
    @staticmethod
    def format_trial_info(tenant):
        """
        Format trial information.
        
        Args:
            tenant: Tenant instance
            
        Returns:
            dict: Formatted trial information
        """
        if not hasattr(tenant, 'trial_ends_at') or not tenant.trial_ends_at:
            return None
        
        now = timezone.now()
        trial_ends = tenant.trial_ends_at
        days_remaining = max(0, (trial_ends - now).days)
        is_expired = now > trial_ends
        
        return {
            'trial_ends_at': TenantFormatter.format_datetime(trial_ends),
            'days_remaining': days_remaining,
            'is_expired': is_expired,
            'status': 'expired' if is_expired else 'active',
            'progress': min(100, max(0, 100 - (days_remaining / 14) * 100))  # Assuming 14-day trial
        }


class BillingFormatter:
    """Formatter class for billing-related data."""
    
    @staticmethod
    def format_billing_status(status):
        """
        Format billing status for display.
        
        Args:
            status (str): Billing status
            
        Returns:
            dict: Formatted status with label and color
        """
        status_map = {
            'active': {
                'label': _('Active'),
                'color': 'green',
                'icon': 'check-circle'
            },
            'trial': {
                'label': _('Trial'),
                'color': 'blue',
                'icon': 'clock-circle'
            },
            'expired': {
                'label': _('Expired'),
                'color': 'red',
                'icon': 'exclamation-circle'
            },
            'cancelled': {
                'label': _('Cancelled'),
                'color': 'orange',
                'icon': 'stop-circle'
            },
            'suspended': {
                'label': _('Suspended'),
                'color': 'purple',
                'icon': 'pause-circle'
            }
        }
        
        return status_map.get(status, {
            'label': status.title(),
            'color': 'gray',
            'icon': 'question-circle'
        })
    
    @staticmethod
    def format_invoice_status(status):
        """
        Format invoice status for display.
        
        Args:
            status (str): Invoice status
            
        Returns:
            dict: Formatted status with label and color
        """
        status_map = {
            'draft': {
                'label': _('Draft'),
                'color': 'gray',
                'icon': 'file-alt'
            },
            'pending': {
                'label': _('Pending'),
                'color': 'blue',
                'icon': 'clock'
            },
            'paid': {
                'label': _('Paid'),
                'color': 'green',
                'icon': 'check-circle'
            },
            'overdue': {
                'label': _('Overdue'),
                'color': 'red',
                'icon': 'exclamation-triangle'
            },
            'cancelled': {
                'label': _('Cancelled'),
                'color': 'orange',
                'icon': 'times-circle'
            },
            'refunded': {
                'label': _('Refunded'),
                'color': 'purple',
                'icon': 'undo'
            }
        }
        
        return status_map.get(status, {
            'label': status.title(),
            'color': 'gray',
            'icon': 'question-circle'
        })
    
    @staticmethod
    def format_payment_method(method):
        """
        Format payment method for display.
        
        Args:
            method (str): Payment method
            
        Returns:
            dict: Formatted payment method with label and icon
        """
        method_map = {
            'credit_card': {
                'label': _('Credit Card'),
                'icon': 'credit-card'
            },
            'bank_transfer': {
                'label': _('Bank Transfer'),
                'icon': 'university'
            },
            'paypal': {
                'label': _('PayPal'),
                'icon': 'paypal'
            },
            'stripe': {
                'label': _('Stripe'),
                'icon': 'stripe'
            },
            'crypto': {
                'label': _('Cryptocurrency'),
                'icon': 'bitcoin'
            }
        }
        
        return method_map.get(method, {
            'label': method.title(),
            'icon': 'credit-card'
        })
    
    @staticmethod
    def format_billing_cycle(cycle):
        """
        Format billing cycle for display.
        
        Args:
            cycle (str): Billing cycle
            
        Returns:
            dict: Formatted billing cycle with label and description
        """
        cycle_map = {
            'monthly': {
                'label': _('Monthly'),
                'description': _('Billed every month')
            },
            'yearly': {
                'label': _('Yearly'),
                'description': _('Billed once per year')
            },
            'quarterly': {
                'label': _('Quarterly'),
                'description': _('Billed every 3 months')
            }
        }
        
        return cycle_map.get(cycle, {
            'label': cycle.title(),
            'description': ''
        })
    
    @staticmethod
    def format_invoice_info(invoice):
        """
        Format comprehensive invoice information.
        
        Args:
            invoice: Invoice instance
            
        Returns:
            dict: Formatted invoice information
        """
        return {
            'id': invoice.id,
            'invoice_number': invoice.invoice_number,
            'status': BillingFormatter.format_invoice_status(invoice.status),
            'type': invoice.type,
            'amount': BillingFormatter.format_currency(invoice.total_amount),
            'subtotal': BillingFormatter.format_currency(invoice.subtotal),
            'tax_amount': BillingFormatter.format_currency(invoice.tax_amount),
            'discount_amount': BillingFormatter.format_currency(invoice.discount_amount),
            'issue_date': BillingFormatter.format_date(invoice.issue_date),
            'due_date': BillingFormatter.format_date(invoice.due_date),
            'paid_date': BillingFormatter.format_date(invoice.paid_date) if invoice.paid_date else None,
            'days_overdue': BillingFormatter.calculate_days_overdue(invoice),
            'payment_method': BillingFormatter.format_payment_method(invoice.payment_method) if invoice.payment_method else None
        }
    
    @staticmethod
    def format_currency(amount, currency='USD'):
        """
        Format currency amount.
        
        Args:
            amount (float): Amount to format
            currency (str): Currency code
            
        Returns:
            dict: Formatted currency with symbol and value
        """
        currency_symbols = {
            'USD': '$',
            'EUR': 'EUR',
            'GBP': '£',
            'JPY': '¥'
        }
        
        symbol = currency_symbols.get(currency, currency)
        
        return {
            'amount': amount,
            'currency': currency,
            'symbol': symbol,
            'formatted': f"{symbol}{amount:,.2f}",
            'raw': f"{amount:.2f}"
        }
    
    @staticmethod
    def calculate_days_overdue(invoice):
        """
        Calculate days overdue for an invoice.
        
        Args:
            invoice: Invoice instance
            
        Returns:
            int: Days overdue (0 if not overdue)
        """
        if invoice.status in ['paid', 'cancelled']:
            return 0
        
        now = timezone.now()
        if now <= invoice.due_date:
            return 0
        
        return (now - invoice.due_date).days


class SecurityFormatter:
    """Formatter class for security-related data."""
    
    @staticmethod
    def format_api_key_status(is_active, last_used=None):
        """
        Format API key status for display.
        
        Args:
            is_active (bool): Whether API key is active
            last_used (datetime): Last used timestamp
            
        Returns:
            dict: Formatted status with label and color
        """
        if not is_active:
            return {
                'label': _('Inactive'),
                'color': 'red',
                'icon': 'stop-circle'
            }
        
        if last_used:
            days_since_use = (timezone.now() - last_used).days
            if days_since_use > 30:
                return {
                    'label': _('Inactive'),
                    'color': 'orange',
                    'icon': 'exclamation-triangle'
                }
            elif days_since_use > 7:
                return {
                    'label': _('Active'),
                    'color': 'yellow',
                    'icon': 'clock'
                }
        
        return {
            'label': _('Active'),
            'color': 'green',
            'icon': 'check-circle'
        }
    
    @staticmethod
    def format_security_level(level):
        """
        Format security level for display.
        
        Args:
            level (str): Security level
            
        Returns:
            dict: Formatted level with label and color
        """
        level_map = {
            'low': {
                'label': _('Low'),
                'color': 'green',
                'description': _('Basic security measures')
            },
            'medium': {
                'label': _('Medium'),
                'color': 'yellow',
                'description': _('Standard security measures')
            },
            'high': {
                'label': _('High'),
                'color': 'orange',
                'description': _('Enhanced security measures')
            },
            'critical': {
                'label': _('Critical'),
                'color': 'red',
                'description': _('Maximum security measures')
            }
        }
        
        return level_map.get(level, {
            'label': level.title(),
            'color': 'gray',
            'description': ''
        })
    
    @staticmethod
    def format_permission_list(permissions):
        """
        Format permission list for display.
        
        Args:
            permissions (list): List of permissions
            
        Returns:
            list: Formatted permissions with labels
        """
        permission_labels = {
            'read': _('Read'),
            'write': _('Write'),
            'delete': _('Delete'),
            'admin': _('Admin'),
            'tenants:read': _('Tenants - Read'),
            'tenants:write': _('Tenants - Write'),
            'tenants:delete': _('Tenants - Delete'),
            'billing:read': _('Billing - Read'),
            'billing:write': _('Billing - Write'),
            'analytics:read': _('Analytics - Read'),
            'security:read': _('Security - Read'),
            'security:write': _('Security - Write')
        }
        
        formatted = []
        for permission in permissions:
            formatted.append({
                'key': permission,
                'label': permission_labels.get(permission, permission.title())
            })
        
        return formatted
    
    @staticmethod
    def mask_sensitive_data(data, visible_chars=4):
        """
        Mask sensitive data for display.
        
        Args:
            data (str): Data to mask
            visible_chars (int): Number of visible characters
            
        Returns:
            str: Masked data
        """
        if not data or len(data) <= visible_chars * 2:
            return '*' * len(data)
        
        start = data[:visible_chars]
        end = data[-visible_chars:]
        middle = '*' * (len(data) - visible_chars * 2)
        
        return f"{start}{middle}{end}"


class AnalyticsFormatter:
    """Formatter class for analytics-related data."""
    
    @staticmethod
    def format_metric_value(value, metric_type):
        """
        Format metric value based on type.
        
        Args:
            value: Metric value
            metric_type (str): Type of metric
            
        Returns:
            dict: Formatted value with unit and display
        """
        if metric_type == 'percentage':
            return {
                'value': value,
                'unit': '%',
                'display': f"{value:.1f}%"
            }
        elif metric_type == 'currency':
            return {
                'value': value,
                'unit': '$',
                'display': f"${value:,.2f}"
            }
        elif metric_type == 'bytes':
            return {
                'value': value,
                'unit': AnalyticsFormatter.format_bytes(value),
                'display': AnalyticsFormatter.format_bytes(value)
            }
        elif metric_type == 'duration':
            return {
                'value': value,
                'unit': 'seconds',
                'display': AnalyticsFormatter.format_duration(value)
            }
        else:
            return {
                'value': value,
                'unit': '',
                'display': str(value)
            }
    
    @staticmethod
    def format_health_score(score):
        """
        Format health score with grade and color.
        
        Args:
            score (float): Health score (0-100)
            
        Returns:
            dict: Formatted health score
        """
        if score >= 90:
            grade = 'A+'
            color = 'green'
            label = _('Excellent')
        elif score >= 85:
            grade = 'A'
            color = 'green'
            label = _('Very Good')
        elif score >= 80:
            grade = 'B+'
            color = 'blue'
            label = _('Good')
        elif score >= 75:
            grade = 'B'
            color = 'blue'
            label = _('Good')
        elif score >= 70:
            grade = 'C+'
            color = 'yellow'
            label = _('Fair')
        elif score >= 65:
            grade = 'C'
            color = 'yellow'
            label = _('Fair')
        elif score >= 60:
            grade = 'D'
            color = 'orange'
            label = _('Poor')
        else:
            grade = 'F'
            color = 'red'
            label = _('Critical')
        
        return {
            'score': score,
            'grade': grade,
            'color': color,
            'label': label,
            'display': f"{score:.1f}% ({grade})"
        }
    
    @staticmethod
    def format_trend_direction(value, previous_value=None):
        """
        Format trend direction with icon and color.
        
        Args:
            value: Current value
            previous_value: Previous value for comparison
            
        Returns:
            dict: Formatted trend information
        """
        if previous_value is None:
            return {
                'direction': 'stable',
                'icon': 'minus',
                'color': 'gray',
                'change': 0,
                'change_percentage': 0
            }
        
        change = value - previous_value
        change_percentage = (change / previous_value * 100) if previous_value != 0 else 0
        
        if change > 0:
            direction = 'up'
            icon = 'arrow-up'
            color = 'green'
        elif change < 0:
            direction = 'down'
            icon = 'arrow-down'
            color = 'red'
        else:
            direction = 'stable'
            icon = 'minus'
            color = 'gray'
        
        return {
            'direction': direction,
            'icon': icon,
            'color': color,
            'change': change,
            'change_percentage': change_percentage,
            'display': f"{change_percentage:+.1f}%"
        }
    
    @staticmethod
    def format_bytes(bytes_value):
        """
        Format bytes in human readable format.
        
        Args:
            bytes_value (int): Bytes value
            
        Returns:
            str: Formatted bytes string
        """
        if bytes_value == 0:
            return "0 B"
        
        units = ['B', 'KB', 'MB', 'GB', 'TB']
        unit_index = 0
        
        while bytes_value >= 1024 and unit_index < len(units) - 1:
            bytes_value /= 1024.0
            unit_index += 1
        
        return f"{bytes_value:.1f} {units[unit_index]}"
    
    @staticmethod
    def format_duration(seconds):
        """
        Format duration in human readable format.
        
        Args:
            seconds (float): Duration in seconds
            
        Returns:
            str: Formatted duration string
        """
        if seconds < 60:
            return f"{seconds:.1f}s"
        elif seconds < 3600:
            minutes = seconds / 60
            return f"{minutes:.1f}m"
        else:
            hours = seconds / 3600
            return f"{hours:.1f}h"


class DateTimeFormatter:
    """Formatter class for date and time operations."""
    
    @staticmethod
    def format_datetime(dt, format_type='full'):
        """
        Format datetime based on type.
        
        Args:
            dt: DateTime instance
            format_type (str): Format type ('full', 'date', 'time', 'relative')
            
        Returns:
            str: Formatted datetime string
        """
        if not dt:
            return ''
        
        if format_type == 'full':
            return dt.strftime('%Y-%m-%d %H:%M:%S')
        elif format_type == 'date':
            return dt.strftime('%Y-%m-%d')
        elif format_type == 'time':
            return dt.strftime('%H:%M:%S')
        elif format_type == 'relative':
            return naturaltime(dt)
        elif format_type == 'natural_day':
            return naturalday(dt)
        else:
            return str(dt)
    
    @staticmethod
    def format_date(date, format_type='full'):
        """
        Format date based on type.
        
        Args:
            date: Date instance
            format_type (str): Format type ('full', 'short', 'relative')
            
        Returns:
            str: Formatted date string
        """
        if not date:
            return ''
        
        if format_type == 'full':
            return date.strftime('%B %d, %Y')
        elif format_type == 'short':
            return date.strftime('%m/%d/%Y')
        elif format_type == 'relative':
            return naturalday(date)
        else:
            return str(date)
    
    @staticmethod
    def format_time_span(start_date, end_date):
        """
        Format time span between two dates.
        
        Args:
            start_date: Start date
            end_date: End date
            
        Returns:
            dict: Formatted time span information
        """
        if not start_date or not end_date:
            return {'days': 0, 'hours': 0, 'minutes': 0, 'display': 'N/A'}
        
        delta = end_date - start_date
        
        days = delta.days
        hours = delta.seconds // 3600
        minutes = (delta.seconds % 3600) // 60
        
        if days > 0:
            display = f"{days}d {hours}h {minutes}m"
        elif hours > 0:
            display = f"{hours}h {minutes}m"
        else:
            display = f"{minutes}m"
        
        return {
            'days': days,
            'hours': hours,
            'minutes': minutes,
            'display': display
        }
    
    @staticmethod
    def format_age(date):
        """
        Format age of a date relative to now.
        
        Args:
            date: Date to calculate age for
            
        Returns:
            dict: Formatted age information
        """
        if not date:
            return {'days': 0, 'display': 'N/A'}
        
        now = timezone.now()
        delta = now - date
        
        days = delta.days
        
        if days < 1:
            display = 'Today'
        elif days == 1:
            display = 'Yesterday'
        elif days < 7:
            display = f"{days} days ago"
        elif days < 30:
            weeks = days // 7
            display = f"{weeks} week{'s' if weeks > 1 else ''} ago"
        elif days < 365:
            months = days // 30
            display = f"{months} month{'s' if months > 1 else ''} ago"
        else:
            years = days // 365
            display = f"{years} year{'s' if years > 1 else ''} ago"
        
        return {
            'days': days,
            'display': display
        }


class TableFormatter:
    """Formatter class for table data display."""
    
    @staticmethod
    def format_table_data(data, columns, title=None):
        """
        Format data for table display.
        
        Args:
            data (list): List of data rows
            columns (list): Column definitions
            title (str): Table title
            
        Returns:
            dict: Formatted table data
        """
        formatted_data = []
        
        for row in data:
            formatted_row = {}
            for column in columns:
                key = column['key']
                value = row.get(key, '')
                
                # Apply column formatting
                if column.get('format') == 'currency':
                    formatted_row[key] = BillingFormatter.format_currency(value)
                elif column.get('format') == 'date':
                    formatted_row[key] = DateTimeFormatter.format_date(value)
                elif column.get('format') == 'datetime':
                    formatted_row[key] = DateTimeFormatter.format_datetime(value)
                elif column.get('format') == 'status':
                    formatted_row[key] = TenantFormatter.format_tenant_status(value)
                elif column.get('format') == 'boolean':
                    formatted_row[key] = {
                        'value': value,
                        'display': 'Yes' if value else 'No',
                        'color': 'green' if value else 'red'
                    }
                else:
                    formatted_row[key] = value
            
            formatted_data.append(formatted_row)
        
        return {
            'title': title,
            'columns': columns,
            'data': formatted_data,
            'total_rows': len(formatted_data)
        }
    
    @staticmethod
    def format_summary_stats(data, stats_config):
        """
        Format summary statistics.
        
        Args:
            data (dict): Data to calculate stats from
            stats_config (list): Statistics configuration
            
        Returns:
            list: Formatted statistics
        """
        formatted_stats = []
        
        for stat in stats_config:
            key = stat['key']
            label = stat['label']
            formatter = stat.get('format', 'default')
            
            value = data.get(key, 0)
            
            if formatter == 'currency':
                formatted_value = BillingFormatter.format_currency(value)
            elif formatter == 'percentage':
                formatted_value = AnalyticsFormatter.format_metric_value(value, 'percentage')
            elif formatter == 'number':
                formatted_value = f"{value:,}"
            else:
                formatted_value = str(value)
            
            formatted_stats.append({
                'key': key,
                'label': label,
                'value': value,
                'formatted_value': formatted_value,
                'color': stat.get('color', 'blue'),
                'icon': stat.get('icon', 'chart-bar')
            })
        
        return formatted_stats
