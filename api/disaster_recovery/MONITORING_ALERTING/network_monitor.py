"""Network Monitor — Monitors network latency, bandwidth, packet loss."""
import logging, socket, time
logger = logging.getLogger(__name__)

class NetworkMonitor:
    def check_latency(self, host: str, port: int = 443, count: int = 5) -> dict:
        latencies = []
        for _ in range(count):
            start = time.monotonic()
            try:
                with socket.create_connection((host, port), timeout=5):
                    latencies.append((time.monotonic() - start) * 1000)
            except Exception:
                latencies.append(None)
        valid = [l for l in latencies if l is not None]
        loss_pct = ((count - len(valid)) / count) * 100
        return {
            "host": host, "port": port,
            "avg_ms": round(sum(valid) / len(valid), 2) if valid else None,
            "min_ms": round(min(valid), 2) if valid else None,
            "max_ms": round(max(valid), 2) if valid else None,
            "packet_loss_percent": loss_pct,
            "samples": count
        }

    def check_dns(self, hostname: str) -> dict:
        start = time.monotonic()
        try:
            ip = socket.gethostbyname(hostname)
            return {"hostname": hostname, "ip": ip, "resolution_ms": round((time.monotonic()-start)*1000, 2), "status": "ok"}
        except Exception as e:
            return {"hostname": hostname, "error": str(e), "status": "failed"}
