"""
api/ai_engine/OPTIMIZATION_ENGINES/resource_allocator.py
=========================================================
Resource Allocator — AI compute resources optimal allocation।
CPU, memory, GPU, worker threads, Celery queues।
Training jobs, inference servers, batch pipelines।
"""

import logging
from typing import List, Dict

logger = logging.getLogger(__name__)


class ResourceAllocator:
    """
    Intelligent resource allocation for AI workloads।
    Priority-based + deadline-aware scheduling।
    """

    def allocate(self, tasks: List[Dict],
                 total_capacity: float,
                 unit: str = "cpu_cores") -> List[Dict]:
        """Tasks এর মধ্যে capacity proportionally allocate করো।"""
        if not tasks or total_capacity <= 0:
            return tasks

        # Priority-weighted allocation
        total_priority = sum(float(t.get("priority", 1)) for t in tasks) or 1
        allocated_sum  = 0.0
        result         = []

        sorted_tasks = sorted(tasks, key=lambda x: float(x.get("priority", 1)), reverse=True)

        for i, task in enumerate(sorted_tasks):
            priority   = float(task.get("priority", 1))
            share      = priority / total_priority
            allocated  = round(total_capacity * share, 2)
            min_req    = float(task.get("min_capacity", 0))
            allocated  = max(allocated, min_req)

            if i == len(sorted_tasks) - 1:
                allocated = round(max(min_req, total_capacity - allocated_sum), 2)

            result.append({
                **task,
                "allocated_capacity": allocated,
                "unit":               unit,
                "share_pct":          round(share * 100, 2),
                "meets_minimum":      allocated >= min_req,
            })
            allocated_sum += allocated

        return result

    def recommend_infrastructure(self, workload_profile: dict) -> dict:
        """Workload profile থেকে infrastructure recommendation।"""
        predictions_per_day  = workload_profile.get("predictions_per_day", 10000)
        model_size_mb        = workload_profile.get("model_size_mb", 100)
        batch_training_hours = workload_profile.get("batch_training_hours_per_week", 10)
        real_time_pct        = workload_profile.get("real_time_prediction_pct", 0.80)

        # Inference servers
        rps          = predictions_per_day / 86400
        workers      = max(2, int(rps / 100) + 1)
        memory_gb    = max(4, int(model_size_mb / 100) * 2 + 2)
        use_gpu      = model_size_mb > 1000

        # Training compute
        train_cpus   = max(4, batch_training_hours // 2)
        train_mem_gb = max(8, int(model_size_mb / 50) + 4)

        return {
            "inference": {
                "workers":        workers,
                "memory_gb":      memory_gb,
                "cpu_cores":      max(2, workers // 2),
                "use_gpu":        use_gpu,
                "load_balancer":  workers > 2,
            },
            "training": {
                "cpu_cores":      train_cpus,
                "memory_gb":      train_mem_gb,
                "gpu_needed":     use_gpu,
                "spot_instances": True,  # Cost saving
            },
            "cache": {
                "redis_memory_gb": max(1, predictions_per_day // 100000),
                "ttl_seconds":     300,
            },
            "estimated_monthly_cost": self._estimate_cost(workers, memory_gb, train_cpus),
        }

    def _estimate_cost(self, inference_workers: int,
                        memory_gb: int, train_cpus: int) -> str:
        """Rough cloud cost estimate।"""
        # Approximate AWS/GCP pricing
        inference_cost = inference_workers * 0.10 * 24 * 30  # $0.10/hr per worker
        training_cost  = train_cpus * 0.05 * 40              # 40hrs/month training
        total          = inference_cost + training_cost
        return f"~${total:.0f}/month (estimate)"

    def celery_queue_allocation(self, queue_loads: Dict[str, int]) -> Dict[str, int]:
        """Celery workers queue অনুযায়ী allocate করো।"""
        total_load    = sum(queue_loads.values()) or 1
        total_workers = sum(queue_loads.values()) // 100 + 4  # Base + load-based

        allocation = {}
        for queue, load in queue_loads.items():
            workers = max(1, int(total_workers * load / total_load))
            allocation[queue] = workers

        return allocation

    def auto_scale_decision(self, current_metrics: dict) -> dict:
        """Auto-scaling decision — scale up/down/maintain।"""
        cpu_pct  = current_metrics.get("cpu_pct", 50)
        mem_pct  = current_metrics.get("memory_pct", 50)
        latency  = current_metrics.get("avg_latency_ms", 100)
        queue_depth = current_metrics.get("celery_queue_depth", 0)

        if cpu_pct > 85 or latency > 500 or queue_depth > 1000:
            action = "scale_up"
            factor = 2 if cpu_pct > 95 or queue_depth > 5000 else 1.5
        elif cpu_pct < 20 and latency < 50 and queue_depth < 10:
            action = "scale_down"
            factor = 0.5
        else:
            action = "maintain"
            factor = 1.0

        return {
            "action":      action,
            "scale_factor": factor,
            "current_cpu": cpu_pct,
            "current_latency": latency,
            "queue_depth": queue_depth,
            "reason":      f"CPU={cpu_pct}% Latency={latency}ms Queue={queue_depth}",
        }
