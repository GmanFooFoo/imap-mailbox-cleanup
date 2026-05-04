"""Move operation — same filter set as delete, but explicit target folder."""

from dataclasses import dataclass

from .filters import build_imap_search


@dataclass
class MoveResult:
    affected_uids: list[str]
    dry_run: bool
    target_folder: str
    folder: str
    sample: list[dict]


def run_move(
    mb,
    *,
    folder: str,
    target: str,
    sender: str | None = None,
    subject_contains: str | None = None,
    older_than: str | None = None,
    apply: bool = False,
    limit: int | None = None,
) -> MoveResult:
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
    if apply and uids:
        mb.move(uids, target)
    return MoveResult(
        affected_uids=uids,
        dry_run=not apply,
        target_folder=target,
        folder=folder,
        sample=sample,
    )
