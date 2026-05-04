"""Discovery scan — produces the JSON report defined in spec §7."""

from collections import Counter, defaultdict
from collections.abc import Iterable
from datetime import UTC, datetime

from . import SCHEMA_VERSION
from .classify import (
    Category,
    classify,
)

TOP_N = 10
SAMPLES = 5
OFFENDERS = 10


def _flatten_headers(raw_headers) -> dict[str, str]:
    out: dict[str, str] = {}
    if not raw_headers:
        return out
    for k, v in raw_headers.items():
        if isinstance(v, (tuple, list)) and v:
            out[k.lower()] = str(v[0])
        else:
            out[k.lower()] = str(v)
    return out


def _months_between(now: datetime, then: datetime) -> int:
    delta = now - then
    return delta.days // 30


def build_report(messages: Iterable, *, folder: str, now: datetime | None = None) -> dict:
    if now is None:
        now = datetime.now(UTC)

    msgs = list(messages)
    total = len(msgs)
    total_size = sum(getattr(m, "size", 0) or 0 for m in msgs)

    nl_counter: Counter[str] = Counter()
    nl_unsub: dict[str, bool] = {}
    auto_counter: Counter[str] = Counter()
    bounces: list[dict] = []
    large: list[dict] = []
    large_size = 0
    msg_id_uids: dict[str, list[str]] = defaultdict(list)
    by_year: Counter[int] = Counter()
    older_12 = older_24 = older_60 = 0

    for m in msgs:
        from_addr = (m.from_ or "").strip()
        subject = m.subject or ""
        size = getattr(m, "size", 0) or 0
        headers = _flatten_headers(getattr(m, "headers", None))
        msg_date = getattr(m, "date", None)

        cats = classify(
            from_addr=from_addr,
            subject=subject,
            headers=headers,
            size_bytes=size,
        )

        if Category.NEWSLETTER in cats:
            nl_counter[from_addr] += 1
            nl_unsub[from_addr] = "list-unsubscribe" in headers
        if Category.AUTOMATED in cats:
            auto_counter[from_addr] += 1
        if Category.BOUNCE in cats and len(bounces) < SAMPLES:
            bounces.append({"uid": m.uid, "from": from_addr, "subject": subject})
        if Category.LARGE_ATTACHMENT in cats:
            large_size += size
            large.append({
                "uid": m.uid,
                "subject": subject,
                "size_mb": round(size / 1024 / 1024, 1),
                "from": from_addr,
            })

        # Duplicates by Message-ID
        msg_id = headers.get("message-id")
        if msg_id:
            msg_id_uids[msg_id].append(m.uid)

        # Age buckets
        if isinstance(msg_date, datetime):
            d = msg_date if msg_date.tzinfo else msg_date.replace(tzinfo=UTC)
            by_year[d.year] += 1
            months = _months_between(now, d)
            if months >= 12:
                older_12 += 1
            if months >= 24:
                older_24 += 1
            if months >= 60:
                older_60 += 1

    duplicates = [
        {"message_id": mid, "uids": uids}
        for mid, uids in msg_id_uids.items()
        if len(uids) > 1
    ]
    duplicate_count = sum(len(d["uids"]) - 1 for d in duplicates)

    large_sorted = sorted(large, key=lambda x: x["size_mb"], reverse=True)[:OFFENDERS]

    report = {
        "schema_version": SCHEMA_VERSION,
        "scanned_at": now.isoformat().replace("+00:00", "Z"),
        "folder": folder,
        "total_messages": total,
        "size_total_mb": round(total_size / 1024 / 1024, 1),
        "categories": {
            "newsletters": {
                "count": sum(nl_counter.values()),
                "top_senders": [
                    {"sender": s, "count": c, "has_unsubscribe": nl_unsub.get(s, False)}
                    for s, c in nl_counter.most_common(TOP_N)
                ],
            },
            "automated_notifications": {
                "count": sum(auto_counter.values()),
                "top_senders": [
                    {"sender": s, "count": c}
                    for s, c in auto_counter.most_common(TOP_N)
                ],
            },
            "bounces_and_autoreplies": {
                "count": sum(1 for m in msgs if Category.BOUNCE in classify(
                    from_addr=(m.from_ or "").strip(),
                    subject=m.subject or "",
                    headers=_flatten_headers(getattr(m, "headers", None)),
                    size_bytes=getattr(m, "size", 0) or 0,
                )),
                "samples": bounces,
            },
            "large_attachments": {
                "count": len(large),
                "size_mb": round(large_size / 1024 / 1024, 1),
                "top_offenders": large_sorted,
            },
            "duplicates": {
                "count": duplicate_count,
                "groups": duplicates[:OFFENDERS],
            },
            "old_messages": {
                "older_than_12m": older_12,
                "older_than_24m": older_24,
                "older_than_60m": older_60,
            },
            "by_year": {str(y): c for y, c in sorted(by_year.items())},
        },
        "recommendations": _recommendations(
            nl_counter, nl_unsub, auto_counter, large_sorted, large_size
        ),
    }
    return report


def _recommendations(nl_counter, nl_unsub, auto_counter, large, large_size_bytes) -> list[str]:
    recs: list[str] = []
    for sender, count in nl_counter.most_common(3):
        if nl_unsub.get(sender):
            recs.append(
                f"{count} messages from {sender} with Unsubscribe link → "
                f"'unsubscribe --sender={sender}'"
            )
    for sender, count in auto_counter.most_common(3):
        recs.append(
            f"{count} automated messages from {sender} → "
            f"'delete --sender={sender} --older-than=6m'"
        )
    if large:
        recs.append(
            f"{len(large)} attachments over 10 MB → "
            f"'attachments --size-gt=10mb --older-than=6m'"
        )
    return recs
