from __future__ import annotations

import json
import logging
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Lock
from typing import Any

from .chunking import load_knowledge
from .config import Settings
from .providers import OpenAICompatibleProvider
from .retrieval import BM25Retriever
from .service import RAGService

LOGGER = logging.getLogger("citeguard")


class Application:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._lock = Lock()
        self.chunk_count = 0
        self.service: RAGService
        self.reindex()

    def reindex(self) -> int:
        chunks = load_knowledge(self.settings.knowledge_dir)
        provider = None
        if self.settings.llm_enabled:
            provider = OpenAICompatibleProvider(
                self.settings.llm_base_url or "",
                self.settings.llm_api_key or "",
                self.settings.llm_model or "",
                self.settings.llm_timeout_seconds,
            )
        service = RAGService(
            BM25Retriever(chunks),
            generator=provider,
            min_score=self.settings.min_score,
            redact=self.settings.redact_pii,
        )
        with self._lock:
            self.service = service
            self.chunk_count = len(chunks)
        return len(chunks)

    def query(self, question: str, top_k: int) -> dict[str, Any]:
        with self._lock:
            service = self.service
        return service.query(question, top_k).to_dict()


def make_handler(app: Application):
    class Handler(BaseHTTPRequestHandler):
        server_version = "CiteGuard/1.0"

        def log_message(self, fmt: str, *args: Any) -> None:
            LOGGER.info("%s - %s", self.address_string(), fmt % args)

        def _json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            if self.path != "/health":
                self._json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
                return
            self._json(HTTPStatus.OK, {"status": "ok", "chunks": app.chunk_count})

        def do_POST(self) -> None:
            if self.path == "/v1/reindex":
                try:
                    count = app.reindex()
                    self._json(HTTPStatus.OK, {"status": "ok", "chunks": count})
                except (OSError, ValueError) as exc:
                    self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc)})
                return
            if self.path != "/v1/query":
                self._json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length <= 0 or length > 16_384:
                    raise ValueError("Request body must be between 1 and 16384 bytes")
                payload = json.loads(self.rfile.read(length))
                question = payload.get("question")
                top_k = payload.get("top_k", app.settings.top_k)
                if not isinstance(question, str) or not question.strip():
                    raise ValueError("question must be a non-empty string")
                if len(question) > 2_000:
                    raise ValueError("question must not exceed 2000 characters")
                if not isinstance(top_k, int) or isinstance(top_k, bool) or not 1 <= top_k <= 10:
                    raise ValueError("top_k must be an integer between 1 and 10")
                self._json(HTTPStatus.OK, app.query(question, top_k))
            except (ValueError, json.JSONDecodeError) as exc:
                self._json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})

    return Handler


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    settings = Settings.from_env()
    app = Application(settings)
    server = ThreadingHTTPServer((settings.host, settings.port), make_handler(app))
    LOGGER.info("CiteGuard listening on http://%s:%s with %s chunks", settings.host, settings.port, app.chunk_count)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        LOGGER.info("Shutting down")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()

