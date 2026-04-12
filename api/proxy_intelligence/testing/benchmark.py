"""Benchmark — measures performance of individual detection engines."""
import time
import logging

logger = logging.getLogger(__name__)

TEST_IPS = [
    "8.8.8.8",       # Google DNS - clean
    "1.1.1.1",       # Cloudflare - clean
    "10.0.0.1",      # Private
    "185.220.101.45", # Known Tor exit
    "104.16.0.0",    # Cloudflare CDN
]


class DetectionBenchmark:
    """Benchmarks each detection engine for latency and accuracy."""

    @staticmethod
    def benchmark_engine(engine_name: str, func, ip_list: list = None) -> dict:
        ips = ip_list or TEST_IPS
        latencies = []
        results = []

        for ip in ips:
            try:
                start = time.perf_counter()
                result = func(ip)
                elapsed_ms = (time.perf_counter() - start) * 1000
                latencies.append(elapsed_ms)
                results.append({"ip": ip, "result": result, "latency_ms": round(elapsed_ms, 2)})
            except Exception as e:
                results.append({"ip": ip, "error": str(e), "latency_ms": 0})

        valid_latencies = [l for l in latencies if l > 0]
        return {
            "engine": engine_name,
            "ips_tested": len(ips),
            "avg_latency_ms": round(sum(valid_latencies) / max(len(valid_latencies), 1), 2),
            "min_latency_ms": round(min(valid_latencies, default=0), 2),
            "max_latency_ms": round(max(valid_latencies, default=0), 2),
            "results": results,
        }

    @classmethod
    def run_all(cls) -> dict:
        """Run benchmarks on all detection engines."""
        benchmarks = {}

        # VPN Detector
        try:
            from ..detection_engines.vpn_detector import VPNDetector
            benchmarks["vpn_detector"] = cls.benchmark_engine(
                "VPNDetector",
                lambda ip: VPNDetector(ip).detect()
            )
        except Exception as e:
            benchmarks["vpn_detector"] = {"error": str(e)}

        # Tor Detector
        try:
            from ..detection_engines.tor_detector import TorDetector
            benchmarks["tor_detector"] = cls.benchmark_engine(
                "TorDetector",
                lambda ip: TorDetector.detect(ip)
            )
        except Exception as e:
            benchmarks["tor_detector"] = {"error": str(e)}

        # ASN Lookup
        try:
            from ..ip_intelligence.ip_asn_lookup import ASNLookup
            benchmarks["asn_lookup"] = cls.benchmark_engine(
                "ASNLookup",
                lambda ip: ASNLookup.lookup(ip)
            )
        except Exception as e:
            benchmarks["asn_lookup"] = {"error": str(e)}

        # Real-time scorer
        try:
            from ..real_time_processing.real_time_scorer import RealTimeScorer
            benchmarks["realtime_scorer"] = cls.benchmark_engine(
                "RealTimeScorer",
                lambda ip: RealTimeScorer(ip).score_request()
            )
        except Exception as e:
            benchmarks["realtime_scorer"] = {"error": str(e)}

        return benchmarks
