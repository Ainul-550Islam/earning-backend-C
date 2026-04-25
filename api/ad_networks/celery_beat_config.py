# api/ad_networks/celery_beat_config.py
# SaaS-Ready Multi-Tenant Celery Beat Configuration with Complete Task Scheduling

from celery.schedules import crontab, schedule
from celery import Celery
from django.conf import settings
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)

# ============================================================================
# CELERY BEAT SCHEDULE CONFIGURATION
# ============================================================================

CELERY_BEAT_SCHEDULE = {
    # ============================================================================
    # HIGH FREQUENCY TASKS (Every few minutes)
    # ============================================================================
    
    'process-pending-rewards': {
        'task': 'api.ad_networks.tasks.process_pending_rewards',
        'schedule': crontab(minute='*/5'),  # Every 5 minutes
        'options': {
            'queue': 'ad_networks_rewards',
            'priority': 8,
            'expires': 300,  # 5 minutes
            'retry': True,
            'retry_policy': {
                'max_retries': 3,
                'interval_start': 60,
                'interval_step': 60,
                'interval_max': 300,
            },
        }
    },
    
    'check-network-health': {
        'task': 'api.ad_networks.tasks.check_network_health',
        'schedule': crontab(minute='*/10'),  # Every 10 minutes
        'options': {
            'queue': 'ad_networks_health',
            'priority': 6,
            'expires': 600,  # 10 minutes
        }
    },
    
    'update-fraud-scores': {
        'task': 'api.ad_networks.tasks.update_fraud_scores',
        'schedule': crontab(minute='*/15'),  # Every 15 minutes
        'options': {
            'queue': 'ad_networks_fraud',
            'priority': 9,  # High priority for fraud detection
            'expires': 900,  # 15 minutes
        }
    },
    
    # ============================================================================
    # HOURLY TASKS
    # ============================================================================
    
    'sync-offers-from-networks': {
        'task': 'api.ad_networks.tasks.sync_offers_from_networks',
        'schedule': crontab(minute='0', hour='*'),  # Every hour at minute 0
        'options': {
            'queue': 'ad_networks_sync',
            'priority': 5,
            'expires': 3600,  # 1 hour
            'retry': True,
            'retry_policy': {
                'max_retries': 2,
                'interval_start': 300,
                'interval_step': 300,
                'interval_max': 1800,
            },
        }
    },
    
    'cleanup-temporary-files': {
        'task': 'api.ad_networks.tasks.cleanup_temporary_files',
        'schedule': crontab(minute='30', hour='*'),  # Every hour at minute 30
        'options': {
            'queue': 'ad_networks_maintenance',
            'priority': 2,
            'expires': 3600,
        }
    },
    
    'update-user-recommendations': {
        'task': 'api.ad_networks.tasks.update_user_recommendations',
        'schedule': crontab(minute='45', hour='*'),  # Every hour at minute 45
        'options': {
            'queue': 'ad_networks_recommendations',
            'priority': 4,
            'expires': 3600,
        }
    },
    
    # ============================================================================
    # DAILY TASKS (Night time for better performance)
    # ============================================================================
    
    'calculate-network-stats': {
        'task': 'api.ad_networks.tasks.calculate_network_stats',
        'schedule': crontab(minute='30', hour='2'),  # 2:30 AM daily
        'options': {
            'queue': 'ad_networks_stats',
            'priority': 3,
            'expires': 86400,  # 24 hours
            'retry': True,
            'retry_policy': {
                'max_retries': 2,
                'interval_start': 1800,
                'interval_step': 1800,
                'interval_max': 7200,
            },
        }
    },
    
    'detect-fraud-conversions': {
        'task': 'api.ad_networks.tasks.detect_fraud_conversions',
        'schedule': crontab(minute='0', hour='3'),  # 3:00 AM daily
        'options': {
            'queue': 'ad_networks_fraud',
            'priority': 8,  # High priority for fraud detection
            'expires': 86400,
            'retry': True,
            'retry_policy': {
                'max_retries': 3,
                'interval_start': 600,
                'interval_step': 600,
                'interval_max': 3600,
            },
        }
    },
    
    'update-offer-performance': {
        'task': 'api.ad_networks.tasks.update_offer_performance',
        'schedule': crontab(minute='15', hour='4'),  # 4:15 AM daily
        'options': {
            'queue': 'ad_networks_analytics',
            'priority': 3,
            'expires': 86400,
        }
    },
    
    'cleanup-expired-blacklist': {
        'task': 'api.ad_networks.tasks.cleanup_expired_blacklist',
        'schedule': crontab(minute='0', hour='5'),  # 5:00 AM daily
        'options': {
            'queue': 'ad_networks_maintenance',
            'priority': 2,
            'expires': 86400,
        }
    },
    
    'generate-daily-reports': {
        'task': 'api.ad_networks.tasks.generate_daily_reports',
        'schedule': crontab(minute='30', hour='6'),  # 6:30 AM daily
        'options': {
            'queue': 'ad_networks_reports',
            'priority': 3,
            'expires': 86400,
        }
    },
    
    'backup-critical-data': {
        'task': 'api.ad_networks.tasks.backup_critical_data',
        'schedule': crontab(minute='0', hour='7'),  # 7:00 AM daily
        'options': {
            'queue': 'ad_networks_backup',
            'priority': 1,
            'expires': 86400,
        }
    },
    
    # ============================================================================
    # WEEKLY TASKS
    # ============================================================================
    
    'weekly-performance-analysis': {
        'task': 'api.ad_networks.tasks.weekly_performance_analysis',
        'schedule': crontab(minute='0', hour='8', day_of_week='monday'),  # Monday 8:00 AM
        'options': {
            'queue': 'ad_networks_analytics',
            'priority': 2,
            'expires': 604800,  # 7 days
        }
    },
    
    'cleanup-old-logs': {
        'task': 'api.ad_networks.tasks.cleanup_old_logs',
        'schedule': crontab(minute='30', hour='2', day_of_week='sunday'),  # Sunday 2:30 AM
        'options': {
            'queue': 'ad_networks_maintenance',
            'priority': 1,
            'expires': 604800,
        }
    },
    
    'update-fraud-rules': {
        'task': 'api.ad_networks.tasks.update_fraud_rules',
        'schedule': crontab(minute='0', hour='4', day_of_week='wednesday'),  # Wednesday 4:00 AM
        'options': {
            'queue': 'ad_networks_fraud',
            'priority': 5,
            'expires': 604800,
        }
    },
    
    'tenant-usage-report': {
        'task': 'api.ad_networks.tasks.generate_tenant_usage_report',
        'schedule': crontab(minute='0', hour='9', day_of_week='friday'),  # Friday 9:00 AM
        'options': {
            'queue': 'ad_networks_reports',
            'priority': 3,
            'expires': 604800,
        }
    },
    
    # ============================================================================
    # MONTHLY TASKS
    # ============================================================================
    
    'monthly-billing-calculation': {
        'task': 'api.ad_networks.tasks.calculate_monthly_billing',
        'schedule': crontab(minute='0', hour='3', day_of_month='1'),  # 1st of month 3:00 AM
        'options': {
            'queue': 'ad_networks_billing',
            'priority': 4,
            'expires': 2592000,  # 30 days
            'retry': True,
            'retry_policy': {
                'max_retries': 3,
                'interval_start': 3600,
                'interval_step': 3600,
                'interval_max': 14400,
            },
        }
    },
    
    'archive-old-data': {
        'task': 'api.ad_networks.tasks.archive_old_data',
        'schedule': crontab(minute='30', hour='2', day_of_month='15'),  # 15th of month 2:30 AM
        'options': {
            'queue': 'ad_networks_maintenance',
            'priority': 1,
            'expires': 2592000,
        }
    },
    
    'security-audit': {
        'task': 'api.ad_networks.tasks.perform_security_audit',
        'schedule': crontab(minute='0', hour='5', day_of_month='20'),  # 20th of month 5:00 AM
        'options': {
            'queue': 'ad_networks_security',
            'priority': 6,
            'expires': 2592000,
        }
    },
    
    # ============================================================================
    # REAL-TIME TASKS (Solar schedules for specific times)
    # ============================================================================
    
    'peak-hour-optimization': {
        'task': 'api.ad_networks.tasks.optimize_for_peak_hours',
        'schedule': crontab(minute='0', hour='9,12,15,18,21'),  # 9 AM, 12 PM, 3 PM, 6 PM, 9 PM
        'options': {
            'queue': 'ad_networks_optimization',
            'priority': 5,
            'expires': 3600,
        }
    },
    
    'midnight-cleanup': {
        'task': 'api.ad_networks.tasks.midnight_cleanup',
        'schedule': crontab(minute='0', hour='0'),  # Midnight daily
        'options': {
            'queue': 'ad_networks_maintenance',
            'priority': 2,
            'expires': 86400,
        }
    },
    
    # ============================================================================
    # TENANT-SPECIFIC TASKS
    # ============================================================================
    
    'tenant-health-check': {
        'task': 'api.ad_networks.tasks.check_tenant_health',
        'schedule': crontab(minute='*/30', hour='*'),  # Every 30 minutes
        'options': {
            'queue': 'ad_networks_tenants',
            'priority': 4,
            'expires': 1800,
        }
    },
    
    'tenant-usage-tracking': {
        'task': 'api.ad_networks.tasks.track_tenant_usage',
        'schedule': crontab(minute='*/20', hour='*'),  # Every 20 minutes
        'options': {
            'queue': 'ad_networks_tenants',
            'priority': 3,
            'expires': 1200,
        }
    },
    
    # ============================================================================
    # SEASONAL TASKS
    # ============================================================================
    
    'holiday-optimization': {
        'task': 'api.ad_networks.tasks.holiday_optimization',
        'schedule': crontab(minute='0', hour='10', day_of_week='friday', month='11,12'),  # Fridays in Nov-Dec 10 AM
        'options': {
            'queue': 'ad_networks_optimization',
            'priority': 3,
            'expires': 86400,
        }
    },
    
    # ============================================================================
    # CONDITIONAL TASKS (Based on system state)
    # ============================================================================
    
    'emergency-fraud-scan': {
        'task': 'api.ad_networks.tasks.emergency_fraud_scan',
        'schedule': schedule(60),  # Every minute, but will only run if triggered
        'options': {
            'queue': 'ad_networks_emergency',
            'priority': 10,  # Highest priority
            'expires': 300,
        }
    },
    
    'system-health-monitor': {
        'task': 'api.ad_networks.tasks.system_health_monitor',
        'schedule': crontab(minute='*/2'),  # Every 2 minutes
        'options': {
            'queue': 'ad_networks_monitoring',
            'priority': 7,
            'expires': 120,
        }
    },
}

# ============================================================================
# TASK QUEUE CONFIGURATION
# ============================================================================

CELERY_TASK_ROUTES = {
    # High priority queues
    'api.ad_networks.tasks.process_pending_rewards': {'queue': 'ad_networks_rewards'},
    'api.ad_networks.tasks.detect_fraud_conversions': {'queue': 'ad_networks_fraud'},
    'api.ad_networks.tasks.update_fraud_scores': {'queue': 'ad_networks_fraud'},
    'api.ad_networks.tasks.emergency_fraud_scan': {'queue': 'ad_networks_emergency'},
    
    # Medium priority queues
    'api.ad_networks.tasks.sync_offers_from_networks': {'queue': 'ad_networks_sync'},
    'api.ad_networks.tasks.update_user_recommendations': {'queue': 'ad_networks_recommendations'},
    'api.ad_networks.tasks.check_network_health': {'queue': 'ad_networks_health'},
    'api.ad_networks.tasks.check_tenant_health': {'queue': 'ad_networks_tenants'},
    
    # Analytics queues
    'api.ad_networks.tasks.calculate_network_stats': {'queue': 'ad_networks_stats'},
    'api.ad_networks.tasks.update_offer_performance': {'queue': 'ad_networks_analytics'},
    'api.ad_networks.tasks.weekly_performance_analysis': {'queue': 'ad_networks_analytics'},
    
    # Maintenance queues
    'api.ad_networks.tasks.cleanup_expired_blacklist': {'queue': 'ad_networks_maintenance'},
    'api.ad_networks.tasks.cleanup_temporary_files': {'queue': 'ad_networks_maintenance'},
    'api.ad_networks.tasks.cleanup_old_logs': {'queue': 'ad_networks_maintenance'},
    'api.ad_networks.tasks.archive_old_data': {'queue': 'ad_networks_maintenance'},
    
    # Report queues
    'api.ad_networks.tasks.generate_daily_reports': {'queue': 'ad_networks_reports'},
    'api.ad_networks.tasks.generate_tenant_usage_report': {'queue': 'ad_networks_reports'},
    
    # Backup queues
    'api.ad_networks.tasks.backup_critical_data': {'queue': 'ad_networks_backup'},
    
    # Billing queues
    'api.ad_networks.tasks.calculate_monthly_billing': {'queue': 'ad_networks_billing'},
    
    # Security queues
    'api.ad_networks.tasks.perform_security_audit': {'queue': 'ad_networks_security'},
    
    # Monitoring queues
    'api.ad_networks.tasks.system_health_monitor': {'queue': 'ad_networks_monitoring'},
    
    # Optimization queues
    'api.ad_networks.tasks.optimize_for_peak_hours': {'queue': 'ad_networks_optimization'},
    'api.ad_networks.tasks.holiday_optimization': {'queue': 'ad_networks_optimization'},
}

# ============================================================================
# TASK PRIORITY CONFIGURATION
# ============================================================================

CELERY_TASK_PRIORITY_ROUTING = {
    'ad_networks_emergency': 10,  # Highest
    'ad_networks_fraud': 9,       # High
    'ad_networks_rewards': 8,     # High
    'ad_networks_monitoring': 7,  # High
    'ad_networks_sync': 6,        # Medium-High
    'ad_networks_health': 6,     # Medium-High
    'ad_networks_tenants': 5,    # Medium
    'ad_networks_recommendations': 5,  # Medium
    'ad_networks_stats': 4,      # Medium
    'ad_networks_analytics': 4,  # Medium
    'ad_networks_reports': 3,    # Medium-Low
    'ad_networks_billing': 4,    # Medium
    'ad_networks_backup': 2,     # Low
    'ad_networks_maintenance': 2, # Low
    'ad_networks_security': 6,   # Medium-High
    'ad_networks_optimization': 3, # Medium-Low
}

# ============================================================================
# TASK TIME LIMITS
# ============================================================================

CELERY_TASK_TIME_LIMITS = {
    # Short tasks (5 minutes)
    'api.ad_networks.tasks.process_pending_rewards': 300,
    'api.ad_networks.tasks.update_fraud_scores': 300,
    'api.ad_networks.tasks.check_network_health': 300,
    'api.ad_networks.tasks.check_tenant_health': 300,
    'api.ad_networks.tasks.track_tenant_usage': 300,
    'api.ad_networks.tasks.system_health_monitor': 300,
    
    # Medium tasks (30 minutes)
    'api.ad_networks.tasks.sync_offers_from_networks': 1800,
    'api.ad_networks.tasks.update_user_recommendations': 1800,
    'api.ad_networks.tasks.cleanup_temporary_files': 1800,
    'api.ad_networks.tasks.generate_daily_reports': 1800,
    'api.ad_networks.tasks.midnight_cleanup': 1800,
    'api.ad_networks.tasks.optimize_for_peak_hours': 1800,
    
    # Long tasks (2 hours)
    'api.ad_networks.tasks.calculate_network_stats': 7200,
    'api.ad_networks.tasks.detect_fraud_conversions': 7200,
    'api.ad_networks.tasks.update_offer_performance': 7200,
    'api.ad_networks.tasks.cleanup_expired_blacklist': 7200,
    'api.ad_networks.tasks.weekly_performance_analysis': 7200,
    'api.ad_networks.tasks.generate_tenant_usage_report': 7200,
    
    # Very long tasks (4 hours)
    'api.ad_networks.tasks.cleanup_old_logs': 14400,
    'api.ad_networks.tasks.backup_critical_data': 14400,
    'api.ad_networks.tasks.calculate_monthly_billing': 14400,
    'api.ad_networks.tasks.archive_old_data': 14400,
    'api.ad_networks.tasks.perform_security_audit': 14400,
}

# ============================================================================
# TASK SOFT TIME LIMITS (grace period before hard timeout)
# ============================================================================

CELERY_TASK_SOFT_TIME_LIMITS = {
    # Short tasks (4 minutes)
    'api.ad_networks.tasks.process_pending_rewards': 240,
    'api.ad_networks.tasks.update_fraud_scores': 240,
    'api.ad_networks.tasks.check_network_health': 240,
    'api.ad_networks.tasks.check_tenant_health': 240,
    'api.ad_networks.tasks.track_tenant_usage': 240,
    'api.ad_networks.tasks.system_health_monitor': 240,
    
    # Medium tasks (25 minutes)
    'api.ad_networks.tasks.sync_offers_from_networks': 1500,
    'api.ad_networks.tasks.update_user_recommendations': 1500,
    'api.ad_networks.tasks.cleanup_temporary_files': 1500,
    'api.ad_networks.tasks.generate_daily_reports': 1500,
    'api.ad_networks.tasks.midnight_cleanup': 1500,
    'api.ad_networks.tasks.optimize_for_peak_hours': 1500,
    
    # Long tasks (1.5 hours)
    'api.ad_networks.tasks.calculate_network_stats': 5400,
    'api.ad_networks.tasks.detect_fraud_conversions': 5400,
    'api.ad_networks.tasks.update_offer_performance': 5400,
    'api.ad_networks.tasks.cleanup_expired_blacklist': 5400,
    'api.ad_networks.tasks.weekly_performance_analysis': 5400,
    'api.ad_networks.tasks.generate_tenant_usage_report': 5400,
    
    # Very long tasks (3.5 hours)
    'api.ad_networks.tasks.cleanup_old_logs': 12600,
    'api.ad_networks.tasks.backup_critical_data': 12600,
    'api.ad_networks.tasks.calculate_monthly_billing': 12600,
    'api.ad_networks.tasks.archive_old_data': 12600,
    'api.ad_networks.tasks.perform_security_audit': 12600,
}

# ============================================================================
# TASK AUTO-RETRY CONFIGURATION
# ============================================================================

CELERY_TASK_AUTORETRY_FOR = {
    # Network-related tasks (retry on network errors)
    'api.ad_networks.tasks.sync_offers_from_networks': (ConnectionError, TimeoutError),
    'api.ad_networks.tasks.check_network_health': (ConnectionError, TimeoutError),
    
    # Database-related tasks (retry on DB errors)
    'api.ad_networks.tasks.calculate_network_stats': (Exception,),
    'api.ad_networks.tasks.update_offer_performance': (Exception,),
    
    # External API tasks (retry on API errors)
    'api.ad_networks.tasks.update_fraud_scores': (ConnectionError, TimeoutError),
    'api.ad_networks.tasks.detect_fraud_conversions': (Exception,),
}

CELERY_TASK_MAX_RETRIES = {
    'api.ad_networks.tasks.sync_offers_from_networks': 3,
    'api.ad_networks.tasks.check_network_health': 5,
    'api.ad_networks.tasks.calculate_network_stats': 2,
    'api.ad_networks.tasks.update_offer_performance': 2,
    'api.ad_networks.tasks.update_fraud_scores': 3,
    'api.ad_networks.tasks.detect_fraud_conversions': 3,
}

# ============================================================================
# BEAT SCHEDULER CONFIGURATION
# ============================================================================

class CeleryBeatConfig:
    """
    Advanced Celery Beat configuration with dynamic scheduling
    """
    
    def __init__(self):
        self.schedule_config = CELERY_BEAT_SCHEDULE
        self.queue_config = CELERY_TASK_ROUTES
        self.priority_config = CELERY_TASK_PRIORITY_ROUTING
    
    def get_schedule_for_tenant(self, tenant_id):
        """
        Get tenant-specific schedule
        """
        tenant_schedule = self.schedule_config.copy()
        
        # Add tenant-specific tasks
        tenant_schedule.update({
            f'tenant-{tenant_id}-cleanup': {
                'task': 'api.ad_networks.tasks.tenant_cleanup',
                'schedule': crontab(minute='0', hour='4'),  # Daily at 4 AM
                'options': {
                    'queue': f'ad_networks_tenant_{tenant_id}',
                    'priority': 3,
                    'expires': 86400,
                }
            }
        })
        
        return tenant_schedule
    
    def add_dynamic_task(self, task_name, task_schedule, options=None):
        """
        Add dynamic task to schedule
        """
        self.schedule_config[task_name] = {
            'task': task_name,
            'schedule': task_schedule,
            'options': options or {}
        }
    
    def remove_task(self, task_name):
        """
        Remove task from schedule
        """
        if task_name in self.schedule_config:
            del self.schedule_config[task_name]
    
    def get_task_queue(self, task_name):
        """
        Get queue for task
        """
        return self.queue_config.get(task_name, {}).get('queue', 'default')
    
    def get_task_priority(self, queue_name):
        """
        Get priority for queue
        """
        return self.priority_config.get(queue_name, 5)
    
    def validate_schedule(self):
        """
        Validate schedule configuration
        """
        errors = []
        
        for task_name, config in self.schedule_config.items():
            if 'task' not in config:
                errors.append(f"Task {task_name} missing 'task' configuration")
            
            if 'schedule' not in config:
                errors.append(f"Task {task_name} missing 'schedule' configuration")
            
            if 'options' in config and not isinstance(config['options'], dict):
                errors.append(f"Task {task_name} 'options' must be a dictionary")
        
        return errors
    
    def get_schedule_summary(self):
        """
        Get summary of scheduled tasks
        """
        summary = {
            'total_tasks': len(self.schedule_config),
            'queues': {},
            'priorities': {},
            'frequencies': {}
        }
        
        for task_name, config in self.schedule_config.items():
            # Count queues
            queue = self.get_task_queue(task_name)
            summary['queues'][queue] = summary['queues'].get(queue, 0) + 1
            
            # Count priorities
            priority = self.get_task_priority(queue)
            summary['priorities'][priority] = summary['priorities'].get(priority, 0) + 1
            
            # Count frequencies
            schedule = config['schedule']
            if hasattr(schedule, '_orig'):
                # Crontab schedule
                summary['frequencies']['crontab'] = summary['frequencies'].get('crontab', 0) + 1
            elif hasattr(schedule, 'seconds'):
                # Solar schedule
                summary['frequencies']['solar'] = summary['frequencies'].get('solar', 0) + 1
            else:
                summary['frequencies']['other'] = summary['frequencies'].get('other', 0) + 1
        
        return summary

# ============================================================================
# TASK MONITORING CONFIGURATION
# ============================================================================

class TaskMonitor:
    """
    Monitor task execution and performance
    """
    
    def __init__(self):
        self.task_stats = {}
        self.error_counts = {}
        self.execution_times = {}
    
    def record_task_start(self, task_name, task_id):
        """Record task start"""
        self.task_stats[task_name] = {
            'last_start': timezone.now(),
            'task_id': task_id,
            'status': 'running'
        }
    
    def record_task_success(self, task_name, execution_time):
        """Record successful task completion"""
        if task_name not in self.execution_times:
            self.execution_times[task_name] = []
        
        self.execution_times[task_name].append(execution_time)
        
        # Keep only last 100 execution times
        if len(self.execution_times[task_name]) > 100:
            self.execution_times[task_name] = self.execution_times[task_name][-100:]
        
        self.task_stats[task_name]['status'] = 'success'
        self.task_stats[task_name]['last_success'] = timezone.now()
    
    def record_task_error(self, task_name, error):
        """Record task error"""
        if task_name not in self.error_counts:
            self.error_counts[task_name] = 0
        
        self.error_counts[task_name] += 1
        self.task_stats[task_name]['status'] = 'error'
        self.task_stats[task_name]['last_error'] = timezone.now()
        self.task_stats[task_name]['error'] = str(error)
    
    def get_task_stats(self, task_name):
        """Get task statistics"""
        stats = self.task_stats.get(task_name, {})
        
        if task_name in self.execution_times:
            times = self.execution_times[task_name]
            stats['avg_execution_time'] = sum(times) / len(times)
            stats['min_execution_time'] = min(times)
            stats['max_execution_time'] = max(times)
            stats['total_executions'] = len(times)
        
        if task_name in self.error_counts:
            stats['error_count'] = self.error_counts[task_name]
        
        return stats
    
    def get_all_stats(self):
        """Get all task statistics"""
        all_stats = {}
        
        for task_name in CELERY_BEAT_SCHEDULE.keys():
            all_stats[task_name] = self.get_task_stats(task_name)
        
        return all_stats

# ============================================================================
# SCHEDULER MANAGEMENT
# ============================================================================

class ScheduleManager:
    """
    Manage dynamic schedule changes
    """
    
    def __init__(self):
        self.config = CeleryBeatConfig()
        self.monitor = TaskMonitor()
    
    def enable_task(self, task_name):
        """Enable a task"""
        if task_name in self.config.schedule_config:
            self.config.schedule_config[task_name]['enabled'] = True
            return True
        return False
    
    def disable_task(self, task_name):
        """Disable a task"""
        if task_name in self.config.schedule_config:
            self.config.schedule_config[task_name]['enabled'] = False
            return True
        return False
    
    def update_task_schedule(self, task_name, new_schedule):
        """Update task schedule"""
        if task_name in self.config.schedule_config:
            self.config.schedule_config[task_name]['schedule'] = new_schedule
            return True
        return False
    
    def get_active_tasks(self):
        """Get list of active tasks"""
        active_tasks = []
        
        for task_name, config in self.config.schedule_config.items():
            if config.get('enabled', True):
                active_tasks.append(task_name)
        
        return active_tasks
    
    def get_disabled_tasks(self):
        """Get list of disabled tasks"""
        disabled_tasks = []
        
        for task_name, config in self.config.schedule_config.items():
            if not config.get('enabled', True):
                disabled_tasks.append(task_name)
        
        return disabled_tasks

# ============================================================================
# EXPORTS
# ============================================================================

# Global instances
beat_config = CeleryBeatConfig()
task_monitor = TaskMonitor()
schedule_manager = ScheduleManager()

__all__ = [
    'CELERY_BEAT_SCHEDULE',
    'CELERY_TASK_ROUTES',
    'CELERY_TASK_PRIORITY_ROUTING',
    'CELERY_TASK_TIME_LIMITS',
    'CELERY_TASK_SOFT_TIME_LIMITS',
    'CELERY_TASK_AUTORETRY_FOR',
    'CELERY_TASK_MAX_RETRIES',
    'CeleryBeatConfig',
    'TaskMonitor',
    'ScheduleManager',
    'beat_config',
    'task_monitor',
    'schedule_manager',
]
