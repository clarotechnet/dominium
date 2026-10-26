"""Read-only Atlas session proof through an already confirmed NetTask ID.

An open tab is not authentication evidence. This monitor never submits a QUERY,
changes the report database, downloads attachments or renews SSO credentials.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sqlite3
import uuid
from pathlib import Path

from atlas_query_pipeline import VALID_QUEUE, evaluate_query
from atlas_query_report import AtlasAuthRequired, ChromeAtlas, DB

OUTPUT = Path(r"C:\DominiumRuntime\BrowserHealth-20261022\atlas-service-health.json")


def latest_queue(db_path=DB):
    """Read the newest confirmed ID without creating/migrating the database."""
    path = Path(db_path).resolve()
    if not path.is_file():
        return None
    db = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=3)
    try:
        rows = db.execute("SELECT remote_queue_id FROM query_jobs "
                          "WHERE remote_queue_id IS NOT NULL ORDER BY created_at DESC")
        for (value,) in rows:
            if isinstance(value, str) and VALID_QUEUE.fullmatch(value):
                return value
    finally:
        db.close()
    return None


def inspect_session(remote_id, *, chrome_factory=None, queue_reader=None):
    """Only a fresh, identified queue response proves authentication."""
    result = {"session": "unknown", "authenticated": None,
              "reason": "invalid_queue_id", "attachment_check": "not_performed"}
    if not isinstance(remote_id, str) or not VALID_QUEUE.fullmatch(remote_id):
        return result
    browser = None
    try:
        browser = (chrome_factory or ChromeAtlas)()
        found = (queue_reader or evaluate_query)(browser, remote_id)
        state = found.get("state") if isinstance(found, dict) else None
        if state in ("complete", "processing", "failed"):
            result.update(session="authenticated", authenticated=True,
                          reason="queue_response_confirmed", queue_state=state)
        else:
            result["reason"] = "queue_response_unconfirmed"
    except AtlasAuthRequired:
        result.update(session="login_required", authenticated=False,
                      reason="atlas_auth_required")
    except Exception:
        # No arbitrary exception text: it may contain URLs or session material.
        result["reason"] = "queue_probe_failed"
    finally:
        if browser is not None:
            try:
                browser.close()
            except Exception:
                pass
    return result


def record_health(db_path=DB, output_path=OUTPUT):
    """Replace previous health with a timestamped observation, including failure."""
    result = {"session": "unknown", "authenticated": None,
              "reason": "no_confirmed_queue", "attachment_check": "not_performed"}
    try:
        queue = latest_queue(db_path)
    except (OSError, sqlite3.Error):
        result["reason"] = "database_unavailable"
    else:
        if queue:
            result = inspect_session(queue)
            result["remote_queue_id"] = queue
    result["checked_at"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        temporary.write_text(json.dumps(result, separators=(",", ":")) + "\n", encoding="utf-8")
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)
    return result


if __name__ == "__main__":
    print(json.dumps(record_health()))
