"""HTTP gateway that exposes the Python control-loop stubs to the Go operator."""

from __future__ import annotations

import argparse
import json
import logging
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from action_engine.gitops_committer import GitOpsCommitter
from action_engine.patch_generator import build_patch
from interpreter.rule_engine import RuleEngine


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class ControlLoopService:
    """Invoke the rule engine + action stubs to keep the contract lightweight."""

    def __init__(self) -> None:
        self.rule_engine = RuleEngine()
        self.gitops_committer = GitOpsCommitter()

    def execute(self, loop: dict[str, Any], event: dict[str, Any] | None) -> dict[str, Any]:
        if not loop:
            raise ValueError("loop payload is required")
        spec = loop.get("spec")
        if not spec:
            raise ValueError("loop.spec is required")

        event_payload: dict[str, Any] = event or {
            "source": "kineticops-http-gateway",
            "timestamp": _now_iso(),
            "intent": "periodic-tick",
        }

        intent = self.rule_engine.evaluate(event_payload)
        patch = build_patch(intent)
        strategy = (spec.get("remediation") or {}).get("strategy", "Direct")

        metadata = {
            "loop": loop.get("metadata", {}).get("name"),
            "reason": intent.get("reason"),
            "source": intent.get("source", "rule-engine"),
        }
        if strategy == "GitOps":
            self.gitops_committer.commit(patch, metadata)

        drift_detected = intent.get("intent") not in {"noop", "healthy"}
        summary = intent.get("reason", "evaluated intent")
        completed = _now_iso()
        response: dict[str, Any] = {
            "phase": "Drifted" if drift_detected else "Healthy",
            "message": summary,
            "driftDetected": drift_detected,
            "driftSummary": f"intent={intent.get('intent')}",
            "lastRemediation": {
                "startedAt": completed,
                "completedAt": completed,
                "driftSummary": summary,
                "appliedStrategy": strategy,
                "gitOpsCommit": metadata["loop"],
                "verifierSummary": "verification stub",
            },
        }
        return response


class LoopRequestHandler(BaseHTTPRequestHandler):
    service = ControlLoopService()

    def do_POST(self) -> None:  # noqa: N802 (http server API)
        if self.path != "/execute":
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "unknown path"})
            return
        content_length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(content_length)
        try:
            payload = json.loads(raw_body or b"{}")
        except json.JSONDecodeError as exc:  # pragma: no cover - trivial
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": f"invalid json: {exc}"})
            return

        loop = payload.get("loop")
        event = payload.get("event")
        try:
            response = self.service.execute(loop, event)
        except ValueError as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return
        except Exception as exc:  # pragma: no cover - defensive
            logging.exception("loop execution failure")
            self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc)})
            return

        self._send_json(HTTPStatus.OK, response)

    def do_GET(self) -> None:  # noqa: N802 (http server API)
        if self.path in {"/healthz", "/readyz"}:
            self._send_json(HTTPStatus.OK, {"status": "ok"})
            return
        self._send_json(HTTPStatus.NOT_FOUND, {"error": "unknown path"})

    def log_message(self, format: str, *args: Any) -> None:  # noqa: N802
        logging.info("http_gateway: " + format, *args)

    def _send_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def serve(host: str = "0.0.0.0", port: int = 8085) -> None:  # noqa: S104 (intentional allow-list)
    server = ThreadingHTTPServer((host, port), LoopRequestHandler)
    logging.info("starting kineticops http gateway on %s:%s", host, port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:  # pragma: no cover - manual shutdown
        logging.info("http gateway interrupted, shutting down")
    finally:
        server.server_close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the KineticOps HTTP gateway")
    parser.add_argument("--host", default="0.0.0.0", help="interface to bind (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8085, help="port to bind (default: 8085)")
    parser.add_argument("--log-level", default="INFO", help="python logging level")
    args = parser.parse_args()

    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO))
    serve(args.host, args.port)


if __name__ == "__main__":
    main()
