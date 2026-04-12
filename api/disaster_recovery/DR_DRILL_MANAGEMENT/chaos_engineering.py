"""Chaos Engineering — Controlled failure injection to test resilience."""
import logging, random, subprocess
from datetime import datetime
logger = logging.getLogger(__name__)

class ChaosEngineering:
    """
    Inspired by Netflix Chaos Monkey.
    Injects controlled failures to verify system resilience.
    """
    EXPERIMENTS = ["network_latency", "cpu_stress", "memory_pressure",
                   "disk_fill", "process_kill", "network_partition"]

    def __init__(self, dry_run: bool = True):
        self.dry_run = dry_run

    def inject_network_latency(self, interface: str = "eth0", latency_ms: int = 200, duration_s: int = 30) -> dict:
        logger.warning(f"CHAOS: Injecting {latency_ms}ms latency on {interface} for {duration_s}s")
        if not self.dry_run:
            subprocess.run(["tc", "qdisc", "add", "dev", interface, "root", "netem", "delay", f"{latency_ms}ms"])
        return {"experiment": "network_latency", "latency_ms": latency_ms, "duration_s": duration_s, "dry_run": self.dry_run}

    def inject_cpu_stress(self, percent: int = 80, duration_s: int = 60) -> dict:
        logger.warning(f"CHAOS: CPU stress {percent}% for {duration_s}s")
        if not self.dry_run:
            subprocess.Popen(["stress-ng", "--cpu", "0", f"--cpu-load", str(percent), "--timeout", str(duration_s)])
        return {"experiment": "cpu_stress", "percent": percent, "duration_s": duration_s, "dry_run": self.dry_run}

    def kill_process(self, process_name: str) -> dict:
        logger.warning(f"CHAOS: Killing process {process_name}")
        if not self.dry_run:
            subprocess.run(["pkill", "-f", process_name])
        return {"experiment": "process_kill", "process": process_name, "dry_run": self.dry_run}

    def random_experiment(self) -> dict:
        exp = random.choice(self.EXPERIMENTS)
        logger.info(f"Random chaos experiment: {exp}")
        return {"selected_experiment": exp, "dry_run": self.dry_run}
