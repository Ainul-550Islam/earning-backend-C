"""
api/ai_engine/AUTOMATION_AGENTS/resource_agent.py
==================================================
Resource Agent — AI/ML infrastructure resource management।
Auto-scaling, GPU allocation, worker management।
Cost optimization ও performance SLA maintain করো।
"""

import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class ResourceAgent:
    """
    Intelligent resource management agent।
    AI workload এর জন্য compute resources optimize করো।
    """

    # Resource tiers
    TIERS = {
        "small":   {"cpu": 2,  "memory_gb": 4,   "workers": 2},
        "medium":  {"cpu": 4,  "memory_gb": 8,   "workers": 4},
        "large":   {"cpu": 8,  "memory_gb": 16,  "workers": 8},
        "xlarge":  {"cpu": 16, "memory_gb": 32,  "workers": 16},
        "gpu":     {"cpu": 8,  "memory_gb": 64,  "workers": 4, "gpu": 1},
    }

    def recommend_resources(self, workload: dict) -> dict:
        """Workload profile অনুযায়ী resources recommend করো।"""
        batch_size       = workload.get("batch_size", 256)
        model_size_mb    = workload.get("model_size_mb", 100)
        requests_per_min = workload.get("rpm", 100)
        training_hours   = workload.get("training_hours_per_week", 10)
        real_time_pct    = workload.get("real_time_pct", 0.80)

        # Inference tier
        if requests_per_min > 5000:    inference_tier = "xlarge"
        elif requests_per_min > 1000:  inference_tier = "large"
        elif requests_per_min > 200:   inference_tier = "medium"
        else:                          inference_tier = "small"

        # Training tier
        if model_size_mb > 1000:       training_tier = "gpu"
        elif training_hours > 20:      training_tier = "xlarge"
        elif training_hours > 10:      training_tier = "large"
        else:                          training_tier = "medium"

        inf_res   = self.TIERS[inference_tier].copy()
        train_res = self.TIERS[training_tier].copy()

        # Auto-scaling config
        auto_scale = {
            "min_replicas": 1,
            "max_replicas": max(2, requests_per_min // 500),
            "target_cpu_pct": 70,
            "scale_up_threshold_ms": 200,
            "scale_down_threshold_ms": 50,
        }

        # Monthly cost estimate
        cost = self._estimate_monthly_cost(inf_res, train_res, training_hours)

        return {
            "inference_tier":    inference_tier,
            "inference":         inf_res,
            "training_tier":     training_tier,
            "training":          train_res,
            "auto_scaling":      auto_scale,
            "celery_workers":    self._recommend_celery_workers(workload),
            "redis_memory_gb":   max(1, requests_per_min // 10000 + 1),
            "estimated_cost":    cost,
            "cost_optimization": self._cost_tips(training_hours, model_size_mb),
        }

    def _estimate_monthly_cost(self, inf_res: dict, train_res: dict,
                                 training_hours: int) -> str:
        """Rough monthly cloud cost estimate।"""
        # Approximate AWS/GCP pricing (USD)
        cpu_hr    = 0.048   # per vCPU per hour
        mem_hr    = 0.006   # per GB per hour
        gpu_hr    = 2.50    # per GPU per hour

        # Inference: 24/7
        inf_cost  = (inf_res["cpu"] * cpu_hr + inf_res["memory_gb"] * mem_hr) * 24 * 30

        # Training: weekly hours * 4
        train_cpu_cost = (train_res["cpu"] * cpu_hr + train_res["memory_gb"] * mem_hr) * training_hours * 4
        train_gpu_cost = gpu_hr * training_hours * 4 if train_res.get("gpu") else 0
        train_cost = train_cpu_cost + train_gpu_cost

        total = inf_cost + train_cost
        return f"~${total:.0f}/month (estimate)"

    def _recommend_celery_workers(self, workload: dict) -> dict:
        """Celery worker allocation।"""
        rpm = workload.get("rpm", 100)
        return {
            "ai_tasks":     max(2, rpm // 500),
            "training":     2,
            "batch_jobs":   max(1, workload.get("batch_jobs_per_day", 5) // 10),
            "notifications": max(1, workload.get("notifications_per_day", 1000) // 10000),
        }

    def _cost_tips(self, training_hours: int, model_size_mb: int) -> List[str]:
        """Cost optimization tips।"""
        tips = []
        if training_hours > 20:
            tips.append("Use spot/preemptible instances for training — save 60-80%")
        if model_size_mb > 500:
            tips.append("Quantize model to reduce size and inference cost")
        if training_hours > 0:
            tips.append("Schedule training during off-peak hours (2-6 AM)")
        tips.append("Use Redis caching to reduce DB load and inference calls")
        return tips

    def monitor_resources(self) -> dict:
        """Current resource utilization monitor করো।"""
        try:
            import psutil
            cpu_pct    = psutil.cpu_percent(interval=1)
            mem        = psutil.virtual_memory()
            mem_pct    = mem.percent
            disk       = psutil.disk_usage("/")
            disk_pct   = disk.percent

            status = "healthy"
            alerts = []

            if cpu_pct > 90:
                status = "critical"; alerts.append(f"CPU critical: {cpu_pct:.1f}%")
            elif cpu_pct > 75:
                status = "warning";  alerts.append(f"CPU high: {cpu_pct:.1f}%")

            if mem_pct > 90:
                status = "critical"; alerts.append(f"Memory critical: {mem_pct:.1f}%")
            elif mem_pct > 80:
                alerts.append(f"Memory high: {mem_pct:.1f}%")

            if disk_pct > 85:
                alerts.append(f"Disk space low: {disk_pct:.1f}% used")

            return {
                "status":       status,
                "cpu_pct":      round(cpu_pct, 1),
                "memory_pct":   round(mem_pct, 1),
                "memory_used_gb": round(mem.used / 1024**3, 2),
                "memory_total_gb": round(mem.total / 1024**3, 2),
                "disk_pct":     round(disk_pct, 1),
                "alerts":       alerts,
            }
        except ImportError:
            return {"status": "unknown", "error": "psutil not installed"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def auto_scale_decision(self, metrics: dict) -> dict:
        """Scale up/down/maintain decision।"""
        cpu_pct   = metrics.get("cpu_pct", 50)
        mem_pct   = metrics.get("memory_pct", 50)
        latency   = metrics.get("avg_latency_ms", 100)
        queue     = metrics.get("celery_queue_depth", 0)
        error_rate = metrics.get("error_rate_pct", 0)

        if cpu_pct > 85 or latency > 500 or queue > 1000 or error_rate > 5:
            action = "scale_up"
            factor = 2.0 if (cpu_pct > 95 or queue > 5000) else 1.5
            reason = f"High load: CPU={cpu_pct}% Latency={latency}ms Queue={queue}"
        elif cpu_pct < 20 and latency < 50 and queue < 10 and error_rate < 1:
            action = "scale_down"
            factor = 0.5
            reason = f"Low utilization: CPU={cpu_pct}% Latency={latency}ms"
        else:
            action = "maintain"
            factor = 1.0
            reason = f"Normal operation: CPU={cpu_pct}% Latency={latency}ms"

        return {
            "action":        action,
            "scale_factor":  factor,
            "reason":        reason,
            "auto_execute":  action in ("scale_up",) and cpu_pct > 90,
            "current_metrics": metrics,
        }

    def optimize_model_cache(self, model_ids: List[str]) -> dict:
        """Which models to keep in RAM vs disk।"""
        recommendations = []
        for i, model_id in enumerate(model_ids):
            priority = "ram" if i < 3 else "disk"  # Top 3 in RAM
            recommendations.append({
                "model_id": model_id,
                "cache":    priority,
                "reason":   "High frequency model" if priority == "ram" else "Low frequency — disk cache",
            })
        return {
            "total_models":       len(model_ids),
            "ram_cached":         min(3, len(model_ids)),
            "disk_cached":        max(0, len(model_ids) - 3),
            "recommendations":    recommendations,
        }
