"""Attachments operation — find large messages (strip deferred to v2)."""

import re
from dataclasses import dataclass
from datetime import UTC, datetime

from .filters import parse_age

_SIZE_RE = re.compile(r"^(\d+)\s*(b|kb|mb|gb)?$", re.IGNORECASE)
_SIZE_MULT = {"b": 1, "kb": 1024, "mb": 1024**2, "gb": 1024**3, None: 1}


def parse_size(spec: str) -> int:
    m = _SIZE_RE.match(spec.strip())
    if not m:
        raise ValueError(f"Bad --size-gt spec: {spec!r}; expected e.g. 10mb, 500kb")
    n = int(m.group(1))
    unit = (m.group(2) or "b").lower()
    return n * _SIZE_MULT[unit]


@dataclass
class AttachmentsResult:
    dry_run: bool
    folder: str
    candidates: list[dict]


def find_large_messages(
    messages,
    *,
    size_gt_bytes: int,
    older_than: str | None = None,
    now: datetime | None = None,
):
    if now is None:
        now = datetime.now(UTC)
    cutoff = None
    if older_than:
        cutoff = now - parse_age(older_than)

    out = []
    for m in messages:
        size = getattr(m, "size", 0) or 0
        if size <= size_gt_bytes:
            continue
        if cutoff is not None and isinstance(m.date, datetime):
            d = m.date if m.date.tzinfo else m.date.replace(tzinfo=UTC)
            if d > cutoff:
                continue
        out.append(m)
    return out


def run_attachments(mb, *, folder: str, size_gt: str, older_than: str | None) -> AttachmentsResult:
    mb.folder.set(folder)
    size_gt_bytes = parse_size(size_gt)
    msgs = list(mb.fetch(headers_only=True, mark_seen=False, bulk=True))
    matches = find_large_messages(msgs, size_gt_bytes=size_gt_bytes, older_than=older_than)
    candidates = [
        {
            "uid": m.uid,
            "from": m.from_,
            "subject": m.subject,
            "size_mb": round((m.size or 0) / 1024 / 1024, 1),
            "date": str(m.date),
        }
        for m in matches
    ]
    return AttachmentsResult(dry_run=True, folder=folder, candidates=candidates)
