"""Parse and execute List-Unsubscribe per RFC 2369 / RFC 8058."""

import re
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage

import requests

from .filters import build_imap_search

_LINK_RE = re.compile(r"<([^>]+)>")


@dataclass
class UnsubAction:
    kind: str  # "https" or "mailto"
    target: str  # URL or mail address
    one_click: bool  # only relevant for https


def parse_list_unsubscribe(
    *,
    list_unsubscribe: str,
    list_unsubscribe_post: str | None,
) -> list[UnsubAction]:
    actions: list[UnsubAction] = []
    one_click = bool(
        list_unsubscribe_post and "List-Unsubscribe=One-Click" in list_unsubscribe_post
    )
    for raw in _LINK_RE.findall(list_unsubscribe or ""):
        raw = raw.strip()
        if raw.startswith("mailto:"):
            target = raw[len("mailto:") :].split("?", 1)[0]
            actions.append(UnsubAction(kind="mailto", target=target, one_click=False))
        elif raw.startswith(("http://", "https://")):
            actions.append(UnsubAction(kind="https", target=raw, one_click=one_click))
    # Prefer https first, then mailto
    actions.sort(key=lambda a: 0 if a.kind == "https" else 1)
    return actions


def perform_unsubscribe(
    action: UnsubAction,
    *,
    smtp_sender: str | None,
    smtp_password: str | None = None,
    smtp_host: str = "smtp.ionos.de",
    smtp_port: int = 587,
    timeout: float = 15.0,
) -> tuple[bool, str]:
    if action.kind == "https":
        try:
            if action.one_click:
                resp = requests.post(
                    action.target,
                    data="List-Unsubscribe=One-Click",
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                    timeout=timeout,
                )
            else:
                resp = requests.get(action.target, timeout=timeout)
            return resp.status_code < 400, f"HTTP {resp.status_code}"
        except Exception as e:
            return False, f"HTTPS error: {e}"
    elif action.kind == "mailto":
        if not smtp_sender or not smtp_password:
            return False, "SMTP credentials missing for mailto unsubscribe"
        msg = EmailMessage()
        msg["From"] = smtp_sender
        msg["To"] = action.target
        msg["Subject"] = "unsubscribe"
        msg.set_content("unsubscribe")
        try:
            with smtplib.SMTP(smtp_host, smtp_port, timeout=timeout) as s:
                s.starttls()
                s.login(smtp_sender, smtp_password)
                s.send_message(msg)
            return True, "SMTP sent"
        except Exception as e:
            return False, f"SMTP error: {e}"
    return False, f"Unknown action kind: {action.kind}"


def collect_unsub_targets(mb, *, sender: str, folder: str = "INBOX") -> dict:
    """Find messages from sender, parse their List-Unsubscribe headers, return targets."""
    mb.folder.set(folder)
    msgs = list(
        mb.fetch(
            build_imap_search(sender=sender),
            headers_only=True,
            mark_seen=False,
            bulk=True,
        )
    )
    seen: set[tuple[str, str]] = set()
    out: list[dict] = []
    uids: list[str] = []
    for m in msgs:
        if m.uid:
            uids.append(m.uid)
        headers = m.headers or {}
        lu = headers.get("list-unsubscribe") or headers.get("List-Unsubscribe")
        lup = headers.get("list-unsubscribe-post") or headers.get("List-Unsubscribe-Post")
        if not lu:
            continue
        lu_val = lu[0] if isinstance(lu, tuple) else lu
        lup_val = (lup[0] if isinstance(lup, tuple) else lup) if lup else None
        for action in parse_list_unsubscribe(
            list_unsubscribe=lu_val,
            list_unsubscribe_post=lup_val,
        ):
            key = (action.kind, action.target)
            if key in seen:
                continue
            seen.add(key)
            out.append(
                {
                    "kind": action.kind,
                    "target": action.target,
                    "one_click": action.one_click,
                }
            )
    return {"uids": uids, "actions": out}
