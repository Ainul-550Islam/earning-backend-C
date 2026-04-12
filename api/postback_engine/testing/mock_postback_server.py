"""
testing/mock_postback_server.py
────────────────────────────────
Mock CPA network postback server for integration testing.
Simulates real network postbacks for E2E tests and local development.
"""
import threading, time, hmac, hashlib, urllib.request, urllib.parse, logging
from http.server import HTTPServer, BaseHTTPRequestHandler

logger = logging.getLogger(__name__)


class MockPostbackHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        logger.debug("MockServer: " + format % args)
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"OK")


class MockPostbackServer:
    """
    Lightweight HTTP server that fires postbacks for testing.

    Usage:
        server = MockPostbackServer(port=9999)
        server.start()
        server.fire_postback("cpalead", lead_id="test_user", payout="0.50")
        server.stop()
    """

    def __init__(self, port=19999):
        self.port = port
        self._server = None
        self._thread = None
        self.base_url = "http://localhost:8000/api/postback_engine/postback"

    def start(self):
        self._server = HTTPServer(("", self.port), MockPostbackHandler)
        self._thread = threading.Thread(target=self._server.serve_forever)
        self._thread.daemon = True
        self._thread.start()
        logger.info("MockPostbackServer started on port %d", self.port)

    def stop(self):
        if self._server:
            self._server.shutdown()

    def fire_postback(
        self, network_key, lead_id="test_lead_001",
        offer_id="offer_test_001", payout="0.50",
        status="1", secret="",
    ):
        """Fire a test postback. Returns (http_status_code, response_body)."""
        adapter_params = {
            "cpalead":   f"sub1={lead_id}&amount={payout}&oid={offer_id}&sid=txn_{int(time.time())}",
            "adgate":    f"user_id={lead_id}&reward={payout}&offer_id={offer_id}&token=tok_{int(time.time())}",
            "offertoro": f"user_id={lead_id}&amount={payout}&oid={offer_id}&trans_id=t_{int(time.time())}",
        }
        qs = adapter_params.get(network_key, f"lead_id={lead_id}&payout={payout}&offer_id={offer_id}")
        if status:
            qs += f"&status={status}"
        if secret:
            ts = str(int(time.time()))
            msg = f"{qs}&ts={ts}"
            sig = hmac.new(secret.encode(), msg.encode(), hashlib.sha256).hexdigest()
            qs += f"&ts={ts}&sig={sig}"
        url = f"{self.base_url}/{network_key}/?{qs}"
        try:
            req = urllib.request.urlopen(url, timeout=10)
            return req.status, req.read().decode("utf-8")
        except Exception as exc:
            return 0, str(exc)

    def fire_batch(self, network_key, count=10, payout="0.10"):
        """Fire multiple postbacks. Returns list of (status, body)."""
        results = []
        for i in range(count):
            results.append(self.fire_postback(
                network_key, lead_id=f"batch_{i:04d}",
                offer_id="offer_batch", payout=payout,
            ))
            time.sleep(0.1)
        return results


mock_postback_server = MockPostbackServer()
