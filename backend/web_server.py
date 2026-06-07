from __future__ import annotations

import json
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

from optimizer_agent import OptimizerAgent


ROOT = Path(__file__).resolve().parents[1]
AGENT = OptimizerAgent(ROOT)


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._redirect("/frontend/index.html")
            return
        if parsed.path == "/api/state":
            self._json(AGENT.dashboard())
            return
        if parsed.path == "/api/ds_monitor":
            self._json(AGENT.deepseek_monitor())
            return
        self._static(parsed.path)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        body = self.rfile.read(int(self.headers.get("Content-Length", "0") or "0"))
        try:
            payload = json.loads(body.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            self._json({"type": "bad_request", "message": "POST body must be JSON."}, status=400)
            return
        runtime = self._runtime_options(payload)
        if parsed.path == "/api/start":
            self._json(AGENT.start(runtime=runtime))
            return
        if parsed.path == "/api/strategy_advice":
            self._json(AGENT.strategy_advice(runtime=runtime))
            return
        if parsed.path == "/api/lab":
            self._json(
                AGENT.lab(
                    iterations=int(payload["iterations"]) if "iterations" in payload else 3,
                    preview_only=bool(payload.get("preview_only", False)),
                    force=bool(payload.get("force", False)),
                    runtime=runtime,
                )
            )
            return
        if parsed.path == "/api/feedback":
            self._json(AGENT.feedback(payload.get("raw_feedback", ""), runtime=runtime))
            return
        if parsed.path == "/api/discard_pending":
            self._json(AGENT.discard_pending())
            return
        self.send_error(404)

    def _json(self, data: object, status: int = 200) -> None:
        raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _redirect(self, target: str) -> None:
        self.send_response(302)
        self.send_header("Location", target)
        self.end_headers()

    def _static(self, request_path: str) -> None:
        rel = unquote(request_path.lstrip("/"))
        path = (ROOT / rel).resolve()
        try:
            path.relative_to(ROOT)
        except ValueError:
            self.send_error(404)
            return
        if not path.exists() or path.is_dir():
            self.send_error(404)
            return
        mime, _ = mimetypes.guess_type(str(path))
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mime or "application/octet-stream")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _runtime_options(self, payload: dict) -> dict:
        api_key = str(payload.get("deepseek_api_key") or "").strip()
        model = str(payload.get("deepseek_model") or "deepseek-v4-flash").strip() or "deepseek-v4-flash"
        runtime = {"deepseek_model": model}
        if api_key:
            runtime["deepseek_api_key"] = api_key
        for key in ("deepseek_timeout_s", "max_tokens", "deepseek_max_tokens", "deepseek_stream", "monitor_kind", "monitor_label"):
            if key in payload and payload.get(key) is not None:
                runtime[key] = str(payload.get(key))
        return runtime

    def log_message(self, fmt: str, *args: object) -> None:
        return


def main() -> int:
    server = ThreadingHTTPServer(("127.0.0.1", 8027), Handler)
    print("AutoSolver Agent Workbench: http://localhost:8027/frontend/index.html")
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
