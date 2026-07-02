"""WebUI runtime route handlers.

Exposes stable runtime endpoints for run status, event replay, and controls.
Delegates to ``api/runtime_journal.py`` for persistence and
``api/runtime_adapter.py`` for adapter-mode detection.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from urllib.parse import parse_qs

from api.runtime_adapter import runtime_adapter_enabled, runtime_adapter_mode
from api.runtime_journal import RuntimeJournal

_RUNTIME_JOURNAL = None


def _journal() -> RuntimeJournal:
    global _RUNTIME_JOURNAL
    if _RUNTIME_JOURNAL is None:
        _RUNTIME_JOURNAL = RuntimeJournal()
    return _RUNTIME_JOURNAL


def _reset_journal_for_test():
    global _RUNTIME_JOURNAL
    _RUNTIME_JOURNAL = None


def handle_runtime_capabilities(handler, parsed):
    """GET /api/runtime/capabilities"""
    from api.helpers import j as json_response

    mode = runtime_adapter_mode()
    is_journal = runtime_adapter_enabled()
    payload = {
        "api_version": "2026-07-02",
        "runtime_adapter": mode,
        "supports": {
            "resumable_events": is_journal,
            "last_event_id": is_journal,
            "cancel": is_journal,
            "approval": False,
            "clarify": False,
        },
    }
    return json_response(handler, payload)


def handle_active_run(handler, parsed):
    """GET /api/sessions/{session_id}/active-run"""
    from api.helpers import j as json_response

    path = str(parsed.path)
    prefix = "/api/sessions/"
    suffix = "/active-run"
    if not path.startswith(prefix) or not path.endswith(suffix):
        from api.helpers import bad

        return bad(handler, "invalid route", 404)
    session_id = path[len(prefix) : -len(suffix)]
    if not session_id:
        from api.helpers import bad

        return bad(handler, "session_id is required", 400)
    jrn = _journal()
    active = jrn.get_active_run_for_session(session_id)
    if active is None:
        return json_response(handler, {"active": False, "run": None})
    run_dict = {
        "run_id": active.run_id,
        "session_id": active.session_id,
        "status": active.status,
        "last_event_id": active.last_event_id,
        "last_seq": active.last_seq,
        "terminal": active.terminal,
        "controls": ["observe", "cancel"] if not active.terminal else [],
    }
    return json_response(handler, {"active": True, "run": run_dict})


def handle_run_status(handler, parsed):
    """GET /api/runs/{run_id}"""
    from api.helpers import j as json_response, bad

    path = str(parsed.path)
    prefix = "/api/runs/"
    if not path.startswith(prefix):
        return bad(handler, "invalid route", 404)
    run_id = path[len(prefix) :]
    if not run_id:
        return bad(handler, "run_id is required", 400)
    if "/" in run_id or "\\" in run_id:
        return bad(handler, "invalid run_id", 400)
    jrn = _journal()
    status = jrn.get_status(run_id)
    if status is None:
        return json_response(handler, {"error": "not_found"}, status=404)
    d = status.to_dict()
    d.setdefault("controls", ["observe"] if not status.terminal else [])
    return json_response(handler, d)


def handle_run_events(handler, parsed):
    """GET /api/runs/{run_id}/events"""
    from api.helpers import j as json_response, bad

    path = str(parsed.path)
    prefix = "/api/runs/"
    suffix = "/events"
    if not path.startswith(prefix) or not path.endswith(suffix):
        return bad(handler, "invalid route", 404)
    run_id = path[len(prefix) : -len(suffix)]
    if not run_id:
        return bad(handler, "run_id is required", 400)
    if "/" in run_id or "\\" in run_id:
        return bad(handler, "invalid run_id", 400)
    jrn = _journal()
    events = jrn.read_events(run_id)
    if events is None:
        return json_response(handler, {"error": "not_found"}, status=404)
    params = parse_qs(parsed.query)
    after_seq_raw = params.get("after_seq", [None])[0]
    limit_raw = params.get("limit", [None])[0]
    events = jrn.read_events(run_id, after_seq=_parse_int(after_seq_raw), limit=_parse_int(limit_raw))
    accept_header = (handler.headers.get("Accept") or "").lower()
    if "text/event-stream" in accept_header:
        return _sse_stream_run_events(handler, run_id, events)
    return json_response(
        handler,
        {
            "run_id": run_id,
            "events": [e.to_dict() for e in (events or [])],
        },
    )


def _parse_int(value):
    if value is None:
        return None
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None


def _sse_stream_run_events(handler, run_id, events):
    from api.sse_chunked import end_sse_headers as _end_sse_headers

    _end_sse_headers(handler)
    try:
        for ev in events:
            d = ev.to_dict()
            handler.wfile.write(f"id: {ev.event_id}\r\n".encode("utf-8"))
            handler.wfile.write(f"event: {ev.type}\r\n".encode("utf-8"))
            handler.wfile.write(f"data: {json.dumps(d)}\r\n\r\n".encode("utf-8"))
            handler.wfile.flush()
    except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
        pass
    return True


def handle_run_cancel(handler, body):
    """POST /api/runs/{run_id}/cancel"""
    from api.helpers import j as json_response, bad

    run_id = str(body.get("run_id") or "").strip()
    if not run_id:
        return bad(handler, "run_id is required", 400)
    if not runtime_adapter_enabled():
        return json_response(
            handler,
            {
                "error": "not_supported",
                "message": "Cancel is not supported by the current runtime adapter.",
            },
            501,
        )
    try:
        from api.streaming import cancel_stream

        result = cancel_stream(run_id)
        return json_response(handler, {"ok": True, "cancelled": result, "run_id": run_id})
    except Exception as exc:
        return json_response(
            handler,
            {
                "error": "not_supported",
                "message": str(exc) or "Cancel is not supported by the current runtime adapter.",
            },
            501,
        )


def handle_run_approval(handler, body):
    """POST /api/runs/{run_id}/approval"""
    from api.helpers import j as json_response

    return json_response(
        handler,
        {
            "error": "not_supported",
            "message": "Approval is not supported by the current runtime adapter.",
        },
        501,
    )


def handle_run_clarify(handler, body):
    """POST /api/runs/{run_id}/clarify"""
    from api.helpers import j as json_response

    return json_response(
        handler,
        {
            "error": "not_supported",
            "message": "Clarify is not supported by the current runtime adapter.",
        },
        501,
    )
