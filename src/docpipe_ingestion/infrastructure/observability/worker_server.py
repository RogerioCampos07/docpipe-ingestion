from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from typing import override

from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from docpipe_ingestion.infrastructure.observability.metrics import Metrics


class WorkerMonitoringServer:
    def __init__(
        self,
        host: str,
        port: int,
        metrics: Metrics,
        ready: Callable[[], bool] = lambda: True,
    ) -> None:
        registry = metrics.registry

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                if self.path == '/metrics':
                    body = generate_latest(registry)
                    self.send_response(200)
                    self.send_header('Content-Type', CONTENT_TYPE_LATEST)
                    self.send_header('Content-Length', str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    return
                if self.path == '/health/live':
                    body = b'{"status":"ok"}'
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.send_header('Content-Length', str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    return
                if self.path == '/health/ready':
                    available = ready()
                    body = (
                        b'{"status":"ok"}'
                        if available
                        else b'{"status":"not_ready"}'
                    )
                    self.send_response(200 if available else 503)
                    self.send_header('Content-Type', 'application/json')
                    self.send_header('Content-Length', str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    return
                self.send_response(404)
                self.end_headers()

            @override
            def log_message(self, format: str, *args: object) -> None:
                del format, args

        self._server = ThreadingHTTPServer((host, port), Handler)
        self._thread = Thread(target=self._server.serve_forever, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def close(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=2)
