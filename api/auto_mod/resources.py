# =============================================================================
# auto_mod/resources.py
# =============================================================================

"""
Resource management and utilities for auto moderation system.
Provides resource allocation, monitoring, and optimization capabilities.
"""
from typing import Callable

import logging
import threading
import time
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass, field
from enum import Enum
from django.utils import timezone
from django.core.cache import cache
from django.conf import settings
from collections import defaultdict, deque

logger = logging.getLogger(__name__)


class ResourceType(Enum):
    """Types of resources that can be managed."""
    CPU = "cpu"
    MEMORY = "memory"
    DISK = "disk"
    NETWORK = "network"
    DATABASE = "database"
    CACHE = "cache"
    QUEUE = "queue"
    WORKER = "worker"


class ResourceStatus(Enum):
    """Resource status indicators."""
    AVAILABLE = "available"
    BUSY = "busy"
    OVERLOADED = "overloaded"
    ERROR = "error"
    MAINTENANCE = "maintenance"
    OFFLINE = "offline"


@dataclass
class ResourceMetrics:
    """Resource metrics and performance data."""
    resource_type: ResourceType
    resource_id: str
    status: ResourceStatus
    utilization: float = 0.0  # 0.0 to 1.0
    capacity: float = 0.0
    used: float = 0.0
    available: float = 0.0
    response_time: float = 0.0  # in milliseconds
    error_rate: float = 0.0  # 0.0 to 1.0
    last_updated: timezone.datetime = field(default_factory=timezone.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def utilization_percentage(self) -> float:
        """Get utilization as percentage."""
        return self.utilization * 100
    
    @property
    def is_healthy(self) -> bool:
        """Check if resource is healthy."""
        return (
            self.status == ResourceStatus.AVAILABLE and
            self.utilization < 0.8 and
            self.error_rate < 0.05
        )
    
    @property
    def is_critical(self) -> bool:
        """Check if resource is in critical state."""
        return (
            self.utilization >= 0.9 or
            self.error_rate >= 0.1 or
            self.status == ResourceStatus.ERROR
        )


class ResourceMonitor:
    """
    Monitors system resources and collects metrics.
    """
    
    def __init__(self):
        self.resources: Dict[str, ResourceMetrics] = {}
        self.metrics_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self.alerts: List[Dict[str, Any]] = []
        self.thresholds: Dict[ResourceType, Dict[str, float]] = {
            ResourceType.CPU: {'warning': 0.7, 'critical': 0.9},
            ResourceType.MEMORY: {'warning': 0.8, 'critical': 0.95},
            ResourceType.DISK: {'warning': 0.8, 'critical': 0.95},
            ResourceType.DATABASE: {'warning': 0.7, 'critical': 0.85},
            ResourceType.CACHE: {'warning': 0.8, 'critical': 0.9},
            ResourceType.QUEUE: {'warning': 100, 'critical': 500},  # queue length
            ResourceType.WORKER: {'warning': 0.8, 'critical': 0.95},
        }
        self._lock = threading.Lock()
    
    def register_resource(self, resource_id: str, resource_type: ResourceType, 
                         capacity: float = 0.0, metadata: Dict[str, Any] = None) -> None:
        """Register a new resource for monitoring."""
        with self._lock:
            self.resources[resource_id] = ResourceMetrics(
                resource_type=resource_type,
                resource_id=resource_id,
                status=ResourceStatus.AVAILABLE,
                capacity=capacity,
                metadata=metadata or {}
            )
            logger.info(f"ResourceMonitor: registered {resource_type.value} resource {resource_id}")
    
    def update_metrics(self, resource_id: str, utilization: float = None,
                      used: float = None, response_time: float = None,
                      error_rate: float = None, status: ResourceStatus = None) -> None:
        """Update metrics for a resource."""
        with self._lock:
            if resource_id not in self.resources:
                logger.warning(f"ResourceMonitor: resource {resource_id} not found")
                return
            
            resource = self.resources[resource_id]
            
            # Update fields
            if utilization is not None:
                resource.utilization = utilization
                resource.used = utilization * resource.capacity
                resource.available = resource.capacity - resource.used
            
            if used is not None:
                resource.used = used
                resource.available = resource.capacity - used
                if resource.capacity > 0:
                    resource.utilization = used / resource.capacity
            
            if response_time is not None:
                resource.response_time = response_time
            
            if error_rate is not None:
                resource.error_rate = error_rate
            
            if status is not None:
                resource.status = status
            
            resource.last_updated = timezone.now()
            
            # Store in history
            self.metrics_history[resource_id].append({
                'timestamp': resource.last_updated.isoformat(),
                'utilization': resource.utilization,
                'response_time': resource.response_time,
                'error_rate': resource.error_rate,
                'status': resource.status.value
            })
            
            # Check for alerts
            self._check_alerts(resource)
    
    def _check_alerts(self, resource: ResourceMetrics) -> None:
        """Check if resource metrics trigger alerts."""
        thresholds = self.thresholds.get(resource.resource_type, {})
        
        # Check utilization threshold
        warning_threshold = thresholds.get('warning', 0.8)
        critical_threshold = thresholds.get('critical', 0.9)
        
        if resource.utilization >= critical_threshold:
            self._create_alert(resource, 'critical', f"Resource utilization {resource.utilization_percentage:.1f}% exceeds critical threshold")
        elif resource.utilization >= warning_threshold:
            self._create_alert(resource, 'warning', f"Resource utilization {resource.utilization_percentage:.1f}% exceeds warning threshold")
        
        # Check error rate
        if resource.error_rate >= 0.1:
            self._create_alert(resource, 'critical', f"Resource error rate {resource.error_rate:.2%} is critical")
        elif resource.error_rate >= 0.05:
            self._create_alert(resource, 'warning', f"Resource error rate {resource.error_rate:.2%} is elevated")
        
        # Check response time
        if resource.response_time >= 5000:  # 5 seconds
            self._create_alert(resource, 'critical', f"Resource response time {resource.response_time:.0f}ms is critical")
        elif resource.response_time >= 2000:  # 2 seconds
            self._create_alert(resource, 'warning', f"Resource response time {resource.response_time:.0f}ms is elevated")
    
    def _create_alert(self, resource: ResourceMetrics, severity: str, message: str) -> None:
        """Create an alert for a resource."""
        alert = {
            'resource_id': resource.resource_id,
            'resource_type': resource.resource_type.value,
            'severity': severity,
            'message': message,
            'timestamp': timezone.now().isoformat(),
            'utilization': resource.utilization,
            'error_rate': resource.error_rate,
            'response_time': resource.response_time,
            'status': resource.status.value
        }
        
        self.alerts.append(alert)
        logger.warning(f"ResourceMonitor: {severity} alert for {resource.resource_id}: {message}")
    
    def get_resource(self, resource_id: str) -> Optional[ResourceMetrics]:
        """Get resource metrics by ID."""
        with self._lock:
            return self.resources.get(resource_id)
    
    def get_resources_by_type(self, resource_type: ResourceType) -> List[ResourceMetrics]:
        """Get all resources of a specific type."""
        with self._lock:
            return [r for r in self.resources.values() if r.resource_type == resource_type]
    
    def get_healthy_resources(self) -> List[ResourceMetrics]:
        """Get all healthy resources."""
        with self._lock:
            return [r for r in self.resources.values() if r.is_healthy]
    
    def get_critical_resources(self) -> List[ResourceMetrics]:
        """Get all critical resources."""
        with self._lock:
            return [r for r in self.resources.values() if r.is_critical]
    
    def get_resource_history(self, resource_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get metrics history for a resource."""
        with self._lock:
            history = list(self.metrics_history[resource_id])
            return history[-limit:] if history else []
    
    def get_recent_alerts(self, limit: int = 50, severity: str = None) -> List[Dict[str, Any]]:
        """Get recent alerts."""
        with self._lock:
            alerts = self.alerts
            
            if severity:
                alerts = [a for a in alerts if a['severity'] == severity]
            
            return alerts[-limit:] if alerts else []
    
    def get_system_summary(self) -> Dict[str, Any]:
        """Get overall system resource summary."""
        with self._lock:
            total_resources = len(self.resources)
            healthy_resources = len(self.get_healthy_resources())
            critical_resources = len(self.get_critical_resources())
            
            # Calculate average utilization by type
            utilization_by_type = defaultdict(list)
            for resource in self.resources.values():
                utilization_by_type[resource.resource_type.value].append(resource.utilization)
            
            avg_utilization_by_type = {}
            for resource_type, values in utilization_by_type.items():
                if values:
                    avg_utilization_by_type[resource_type] = sum(values) / len(values)
            
            return {
                'total_resources': total_resources,
                'healthy_resources': healthy_resources,
                'critical_resources': critical_resources,
                'health_percentage': (healthy_resources / total_resources * 100) if total_resources > 0 else 0,
                'average_utilization_by_type': avg_utilization_by_type,
                'recent_alerts': len(self.get_recent_alerts(limit=10)),
                'last_updated': timezone.now().isoformat()
            }


class ResourceManager:
    """
    Manages resource allocation and optimization.
    """
    
    def __init__(self):
        self.monitor = ResourceMonitor()
        self.allocations: Dict[str, Dict[str, Any]] = {}
        self.pools: Dict[str, Dict[str, Any]] = {}
        self.optimization_rules: List[Callable] = []
        self._lock = threading.Lock()
    
    def create_resource_pool(self, pool_name: str, resource_type: ResourceType,
                           resources: List[str], min_capacity: float = 0.0,
                           max_capacity: float = None) -> None:
        """Create a pool of similar resources."""
        with self._lock:
            self.pools[pool_name] = {
                'resource_type': resource_type,
                'resources': resources,
                'min_capacity': min_capacity,
                'max_capacity': max_capacity or float('inf'),
                'current_capacity': 0.0,
                'utilization': 0.0,
                'created_at': timezone.now()
            }
            
            # Register resources if not already registered
            for resource_id in resources:
                if resource_id not in self.monitor.resources:
                    self.monitor.register_resource(resource_id, resource_type)
            
            logger.info(f"ResourceManager: created pool {pool_name} with {len(resources)} resources")
    
    def allocate_resource(self, pool_name: str, request_id: str, 
                         required_capacity: float = 0.0, priority: int = 0) -> Optional[str]:
        """Allocate a resource from a pool."""
        with self._lock:
            if pool_name not in self.pools:
                logger.error(f"ResourceManager: pool {pool_name} not found")
                return None
            
            pool = self.pools[pool_name]
            
            # Find best available resource
            best_resource = None
            best_score = -1
            
            for resource_id in pool['resources']:
                resource = self.monitor.get_resource(resource_id)
                if not resource or not resource.is_healthy:
                    continue
                
                # Calculate allocation score
                score = self._calculate_allocation_score(resource, required_capacity, priority)
                if score > best_score:
                    best_score = score
                    best_resource = resource_id
            
            if best_resource:
                # Record allocation
                self.allocations[request_id] = {
                    'resource_id': best_resource,
                    'pool_name': pool_name,
                    'required_capacity': required_capacity,
                    'priority': priority,
                    'allocated_at': timezone.now()
                }
                
                # Update resource metrics
                resource = self.monitor.get_resource(best_resource)
                if resource:
                    new_utilization = min(resource.utilization + (required_capacity / resource.capacity), 1.0)
                    self.monitor.update_metrics(best_resource, utilization=new_utilization)
                
                logger.info(f"ResourceManager: allocated {best_resource} for request {request_id}")
                return best_resource
            
            logger.warning(f"ResourceManager: no available resource for request {request_id}")
            return None
    
    def _calculate_allocation_score(self, resource: ResourceMetrics, 
                                 required_capacity: float, priority: int) -> float:
        """Calculate allocation score for a resource."""
        # Base score from availability
        if resource.utilization + (required_capacity / resource.capacity) > 1.0:
            return -1  # Not enough capacity
        
        availability_score = 1.0 - resource.utilization
        
        # Performance score (lower response time is better)
        performance_score = max(0, 1.0 - (resource.response_time / 1000))  # Normalize to seconds
        
        # Error rate score (lower error rate is better)
        error_score = 1.0 - resource.error_rate
        
        # Combined score
        total_score = (availability_score * 0.5 + 
                       performance_score * 0.3 + 
                       error_score * 0.2)
        
        # Apply priority weighting
        if priority > 0:
            total_score *= (1 + priority * 0.1)
        
        return total_score
    
    def release_resource(self, request_id: str) -> bool:
        """Release an allocated resource."""
        with self._lock:
            if request_id not in self.allocations:
                logger.warning(f"ResourceManager: allocation {request_id} not found")
                return False
            
            allocation = self.allocations.pop(request_id)
            resource_id = allocation['resource_id']
            required_capacity = allocation['required_capacity']
            
            # Update resource metrics
            resource = self.monitor.get_resource(resource_id)
            if resource:
                new_utilization = max(resource.utilization - (required_capacity / resource.capacity), 0.0)
                self.monitor.update_metrics(resource_id, utilization=new_utilization)
            
            logger.info(f"ResourceManager: released {resource_id} for request {request_id}")
            return True
    
    def optimize_allocation(self) -> Dict[str, Any]:
        """Optimize resource allocation based on current metrics."""
        with self._lock:
            optimizations = {
                'rebalanced_allocations': 0,
                'released_resources': 0,
                'consolidated_pools': 0,
                'recommendations': []
            }
            
            # Apply optimization rules
            for rule in self.optimization_rules:
                try:
                    rule_result = rule(self.monitor, self.allocations, self.pools)
                    if rule_result:
                        optimizations.update(rule_result)
                except Exception as exc:
                    logger.error(f"ResourceManager: optimization rule error: {exc}")
            
            # Generate recommendations
            optimizations['recommendations'] = self._generate_recommendations()
            
            return optimizations
    
    def _generate_recommendations(self) -> List[str]:
        """Generate optimization recommendations."""
        recommendations = []
        
        # Check for overloaded resources
        critical_resources = self.monitor.get_critical_resources()
        if critical_resources:
            recommendations.append(f"Scale up resources: {len(critical_resources)} resources are critical")
        
        # Check for underutilized resources
        underutilized = [
            r for r in self.monitor.resources.values() 
            if r.utilization < 0.2 and r.status == ResourceStatus.AVAILABLE
        ]
        if len(underutilized) > len(critical_resources):
            recommendations.append(f"Consider scaling down: {len(underutilized)} resources are underutilized")
        
        # Check recent alerts
        recent_alerts = self.monitor.get_recent_alerts(limit=10)
        critical_alerts = [a for a in recent_alerts if a['severity'] == 'critical']
        if critical_alerts:
            recommendations.append(f"Address critical alerts: {len(critical_alerts)} critical issues detected")
        
        return recommendations
    
    def add_optimization_rule(self, rule: Callable) -> None:
        """Add an optimization rule."""
        self.optimization_rules.append(rule)
        logger.info("ResourceManager: added optimization rule")
    
    def get_allocation_summary(self) -> Dict[str, Any]:
        """Get allocation summary."""
        with self._lock:
            total_allocations = len(self.allocations)
            active_pools = len([p for p in self.pools.values() if p['resources']])
            
            # Calculate total utilization
            total_utilization = 0.0
            total_capacity = 0.0
            
            for resource in self.monitor.resources.values():
                total_utilization += resource.utilization * resource.capacity
                total_capacity += resource.capacity
            
            avg_utilization = (total_utilization / total_capacity) if total_capacity > 0 else 0.0
            
            return {
                'total_allocations': total_allocations,
                'active_pools': active_pools,
                'average_utilization': avg_utilization,
                'total_capacity': total_capacity,
                'total_used': total_utilization,
                'last_optimized': timezone.now().isoformat()
            }


class ResourceScheduler:
    """
    Schedules resource usage and manages workload distribution.
    """
    
    def __init__(self, resource_manager: ResourceManager):
        self.resource_manager = resource_manager
        self.scheduled_tasks: Dict[str, Dict[str, Any]] = {}
        self.task_queue: List[Dict[str, Any]] = []
        self.running_tasks: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()
    
    def schedule_task(self, task_id: str, resource_type: ResourceType,
                     required_capacity: float = 0.0, priority: int = 0,
                     estimated_duration: int = 0, dependencies: List[str] = None) -> bool:
        """Schedule a task that requires resources."""
        with self._lock:
            task = {
                'task_id': task_id,
                'resource_type': resource_type,
                'required_capacity': required_capacity,
                'priority': priority,
                'estimated_duration': estimated_duration,
                'dependencies': dependencies or [],
                'status': 'pending',
                'scheduled_at': timezone.now(),
                'attempts': 0
            }
            
            self.scheduled_tasks[task_id] = task
            self.task_queue.append(task)
            
            # Sort queue by priority
            self.task_queue.sort(key=lambda t: t['priority'], reverse=True)
            
            logger.info(f"ResourceScheduler: scheduled task {task_id}")
            return True
    
    def execute_next_task(self) -> Optional[str]:
        """Execute the next task in the queue."""
        with self._lock:
            if not self.task_queue:
                return None
            
            # Find next executable task
            for i, task in enumerate(self.task_queue):
                if self._can_execute_task(task):
                    # Remove from queue
                    self.task_queue.pop(i)
                    
                    # Find suitable pool
                    pool_name = self._find_suitable_pool(task['resource_type'])
                    if not pool_name:
                        task['status'] = 'failed'
                        task['error'] = 'No suitable resource pool available'
                        continue
                    
                    # Allocate resource
                    resource_id = self.resource_manager.allocate_resource(
                        pool_name, task['task_id'], task['required_capacity'], task['priority']
                    )
                    
                    if resource_id:
                        task['status'] = 'running'
                        task['resource_id'] = resource_id
                        task['started_at'] = timezone.now()
                        task['attempts'] += 1
                        
                        self.running_tasks[task['task_id']] = task
                        
                        logger.info(f"ResourceScheduler: started task {task['task_id']} on {resource_id}")
                        return task['task_id']
                    else:
                        task['status'] = 'failed'
                        task['error'] = 'Resource allocation failed'
            
            return None
    
    def _can_execute_task(self, task: Dict[str, Any]) -> bool:
        """Check if a task can be executed."""
        # Check dependencies
        for dep_id in task['dependencies']:
            if dep_id not in self.scheduled_tasks or self.scheduled_tasks[dep_id]['status'] != 'completed':
                return False
        
        # Check if task hasn't failed too many times
        if task.get('attempts', 0) >= 3:
            return False
        
        return True
    
    def _find_suitable_pool(self, resource_type: ResourceType) -> Optional[str]:
        """Find a suitable pool for a resource type."""
        for pool_name, pool in self.resource_manager.pools.items():
            if pool['resource_type'] == resource_type:
                # Check if pool has healthy resources
                healthy_resources = [
                    r for r in pool['resources']
                    if self.resource_manager.monitor.get_resource(r) and 
                    self.resource_manager.monitor.get_resource(r).is_healthy
                ]
                
                if healthy_resources:
                    return pool_name
        
        return None
    
    def complete_task(self, task_id: str, success: bool = True, error: str = None) -> bool:
        """Mark a task as completed."""
        with self._lock:
            if task_id not in self.running_tasks:
                logger.warning(f"ResourceScheduler: task {task_id} not running")
                return False
            
            task = self.running_tasks.pop(task_id)
            
            # Release resource
            if 'resource_id' in task:
                self.resource_manager.release_resource(task_id)
            
            # Update task status
            task['status'] = 'completed' if success else 'failed'
            task['completed_at'] = timezone.now()
            
            if error:
                task['error'] = error
            
            # Update scheduled task
            if task_id in self.scheduled_tasks:
                self.scheduled_tasks[task_id].update(task)
            
            logger.info(f"ResourceScheduler: completed task {task_id} (success: {success})")
            return True
    
    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a specific task."""
        with self._lock:
            if task_id in self.scheduled_tasks:
                return self.scheduled_tasks[task_id].copy()
            return None
    
    def get_queue_summary(self) -> Dict[str, Any]:
        """Get queue summary."""
        with self._lock:
            pending_tasks = [t for t in self.task_queue if t['status'] == 'pending']
            running_tasks = list(self.running_tasks.values())
            
            return {
                'pending_tasks': len(pending_tasks),
                'running_tasks': len(running_tasks),
                'total_scheduled': len(self.scheduled_tasks),
                'average_priority': sum(t['priority'] for t in pending_tasks) / len(pending_tasks) if pending_tasks else 0,
                'queue_by_priority': {
                    'high': len([t for t in pending_tasks if t['priority'] >= 8]),
                    'medium': len([t for t in pending_tasks if 4 <= t['priority'] < 8]),
                    'low': len([t for t in pending_tasks if t['priority'] < 4])
                }
            }


# Global instances
resource_monitor = ResourceMonitor()
resource_manager = ResourceManager(resource_monitor)
resource_scheduler = ResourceScheduler(resource_manager)


# Resource optimization rules
def cpu_optimization_rule(monitor: ResourceMonitor, allocations: Dict, pools: Dict) -> Dict[str, Any]:
    """Optimization rule for CPU resources."""
    cpu_resources = monitor.get_resources_by_type(ResourceType.CPU)
    overloaded = [r for r in cpu_resources if r.utilization > 0.8]
    underutilized = [r for r in cpu_resources if r.utilization < 0.3]
    
    return {
        'cpu_optimizations': len(overloaded) + len(underutilized),
        'recommendation': 'Consider load balancing CPU resources' if overloaded else None
    }


def memory_optimization_rule(monitor: ResourceMonitor, allocations: Dict, pools: Dict) -> Dict[str, Any]:
    """Optimization rule for memory resources."""
    memory_resources = monitor.get_resources_by_type(ResourceType.MEMORY)
    critical = [r for r in memory_resources if r.utilization > 0.9]
    
    return {
        'memory_optimizations': len(critical),
        'recommendation': 'Scale up memory resources' if critical else None
    }


# Register optimization rules
resource_manager.add_optimization_rule(cpu_optimization_rule)
resource_manager.add_optimization_rule(memory_optimization_rule)


# Auto-registration of common resources
def register_common_resources():
    """Register common system resources."""
    # CPU resources
    import multiprocessing
    cpu_count = multiprocessing.cpu_count()
    for i in range(cpu_count):
        resource_monitor.register_resource(
            f"cpu_{i}", 
            ResourceType.CPU, 
            capacity=100.0,
            metadata={'core': i}
        )
    
    # Memory resources
    import psutil
    memory = psutil.virtual_memory()
    resource_monitor.register_resource(
        "memory_main",
        ResourceType.MEMORY,
        capacity=memory.total / (1024**3),  # Convert to GB
        metadata={'total_gb': memory.total / (1024**3)}
    )
    
    # Database connections
    resource_monitor.register_resource(
        "database_pool",
        ResourceType.DATABASE,
        capacity=100.0,
        metadata={'max_connections': 100}
    )
    
    # Cache resources
    resource_monitor.register_resource(
        "redis_cache",
        ResourceType.CACHE,
        capacity=1000.0,  # MB
        metadata={'max_memory_mb': 1000}
    )
    
    logger.info("ResourceManager: registered common system resources")


# Initialize common resources on import
try:
    register_common_resources()
except ImportError:
    logger.warning("ResourceManager: psutil not available, skipping resource registration")
