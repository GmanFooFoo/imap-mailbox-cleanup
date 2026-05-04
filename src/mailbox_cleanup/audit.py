"""Audit log writer. One JSON object per line in ~/.mailbox-cleanup/audit.log."""

import json
import os
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path

AUDIT_LOG_PATH_ENV = "MAILBOX_CLEANUP_AUDIT_LOG"
DEFAULT_AUDIT_LOG = Path.home() / ".mailbox-cleanup" / "audit.log"


def _audit_path() -> Path:
    override = os.environ.get(AUDIT_LOG_PATH_ENV)
    return Path(override) if override else DEFAULT_AUDIT_LOG


def log_action(
    *,
    subcommand: str,
    args: Mapping[str, object],
    folder: str,
    affected_uids: Sequence[str],
    result: str,
    error: str | None = None,
) -> None:
    """Append one JSON-line record describing an applied action."""
    record: dict[str, object] = {
        "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "subcommand": subcommand,
        "args": dict(args),
        "folder": folder,
        "affected_uids": list(affected_uids),
        "result": result,
    }
    if error is not None:
        record["error"] = error
    path = _audit_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
