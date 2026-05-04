"""Delete operation — soft-delete (move to Trash) with dry-run by default."""

from dataclasses import dataclass

from ..folders import resolve_folder
from .filters import build_imap_search


@dataclass
class DeleteResult:
    affected_uids: list[str]
    dry_run: bool
    target_folder: str | None
    folder: str
    sample: list[dict]


def run_delete(
    mb,
    *,
    folder: str = "INBOX",
    sender: str | None = None,
    subject_contains: str | None = None,
    older_than: str | None = None,
    apply: bool = False,
    limit: int | None = None,
) -> DeleteResult:
    """Find matching messages, move to Trash if apply=True. Otherwise dry-run."""
    mb.folder.set(folder)
    criteria = build_imap_search(
        sender=sender,
        subject_contains=subject_contains,
        older_than=older_than,
    )
    msgs = list(mb.fetch(criteria, headers_only=True, mark_seen=False, limit=limit, bulk=True))
    uids = [m.uid for m in msgs if m.uid]
    sample = [
        {"uid": m.uid, "from": m.from_, "subject": m.subject, "date": str(m.date)}
        for m in msgs[:5]
    ]
    target = resolve_folder(mb, "trash")
    if apply and uids:
        if not target:
            raise RuntimeError(
                "Could not resolve Trash folder on server "
                "(no SPECIAL-USE, no fallback match)."
            )
        mb.move(uids, target)
    return DeleteResult(
        affected_uids=uids,
        dry_run=not apply,
        target_folder=target,
        folder=folder,
        sample=sample,
    )
