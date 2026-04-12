"""Mock Proxy Server — for testing proxy detection without real proxies."""
import threading
import socket
import logging

logger = logging.getLogger(__name__)


class MockHTTPProxyServer:
    """
    Lightweight mock HTTP proxy server for testing proxy detection.
    Listens on localhost:8080 and responds to CONNECT requests.
    """
    def __init__(self, host="127.0.0.1", port=18080):
        self.host = host
        self.port = port
        self.server = None
        self.thread = None
        self._running = False

    def start(self):
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server.bind((self.host, self.port))
        self.server.listen(5)
        self._running = True
        self.thread = threading.Thread(target=self._accept_loop, daemon=True)
        self.thread.start()
        logger.info(f"Mock proxy started on {self.host}:{self.port}")

    def _accept_loop(self):
        self.server.settimeout(1.0)
        while self._running:
            try:
                conn, addr = self.server.accept()
                conn.send(b"HTTP/1.1 200 Connection established\r\n\r\n")
                conn.close()
            except socket.timeout:
                continue
            except Exception:
                break

    def stop(self):
        self._running = False
        if self.server:
            self.server.close()
        if self.thread:
            self.thread.join(timeout=2)
        logger.info("Mock proxy stopped")

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *args):
        self.stop()
