import json
import sys
from collections import Counter

import click

from . import SCHEMA_VERSION
from .audit import log_action
from .auth import (
    AuthMissingError,
    delete_credentials,
    get_credentials,
    set_credentials,
)
from .folders import resolve_folder
from .imap_client import imap_connect
from .operations.archive import run_archive
from .operations.attachments import run_attachments
from .operations.dedupe import run_dedupe
from .operations.delete import run_delete
from .operations.move import run_move
from .operations.unsubscribe import (
    UnsubAction,
    collect_unsub_targets,
    perform_unsubscribe,
)
from .scan import build_report

_DEFAULT_PORT = 993


def _emit(payload: dict, json_mode: bool) -> None:
    if json_mode:
        click.echo(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        for k, v in payload.items():
            click.echo(f"{k}: {v}")


def _fail(payload: dict, exit_code: int, json_mode: bool) -> None:
    payload["ok"] = False
    _emit(payload, json_mode)
    sys.exit(exit_code)


@click.group()
@click.version_option()
def cli():
    """Triage and clean up an IONOS IMAP mailbox."""


@cli.group()
def auth():
    """Manage IONOS credentials in macOS Keychain."""


@auth.command("set")
@click.option("--email", required=True, help="IONOS email address.")
@click.option("--server", default="imap.ionos.de", show_default=True)
@click.password_option(confirmation_prompt=False, prompt="IONOS password")
def auth_set(email: str, server: str, password: str):
    """Write IONOS credentials into macOS Keychain."""
    set_credentials(email, password, server)
    click.echo(f"Credentials stored for {email} on {server}.")


@auth.command("test")
@click.option("--email", required=True)
@click.option("--json", "json_mode", is_flag=True)
def auth_test(email: str, json_mode: bool):
    """Connect to IMAP, list folders, disconnect."""
    try:
        creds = get_credentials(email)
    except AuthMissingError as e:
        _fail(
            {"error_code": "auth_missing", "message": str(e)},
            exit_code=3,
            json_mode=json_mode,
        )
        return
    try:
        with imap_connect(creds) as mb:
            folders = [f.name for f in mb.folder.list()]
    except Exception as e:
        _fail(
            {"error_code": "connection_error", "message": str(e)},
            exit_code=2,
            json_mode=json_mode,
        )
        return
    _emit(
        {
            "ok": True,
            "email": email,
            "server": creds.server,
            "folders": folders,
            "schema_version": SCHEMA_VERSION,
        },
        json_mode=json_mode,
    )


@auth.command("delete")
@click.option("--email", required=True)
def auth_delete(email: str):
    """Remove credentials from Keychain."""
    delete_credentials(email)
    click.echo(f"Credentials removed for {email}.")


@cli.command("scan")
@click.option("--email", required=True)
@click.option("--folder", default="INBOX", show_default=True)
@click.option("--json", "json_mode", is_flag=True)
def scan_cmd(email: str, folder: str, json_mode: bool):
    """Scan a folder, classify messages, emit a discovery report."""
    try:
        creds = get_credentials(email)
    except AuthMissingError as e:
        _fail({"error_code": "auth_missing", "message": str(e)}, 3, json_mode)
        return
    try:
        with imap_connect(creds, port=_DEFAULT_PORT) as mb:
            mb.folder.set(folder)
            messages = list(mb.fetch(headers_only=True, mark_seen=False, bulk=True))
    except Exception as e:
        _fail({"error_code": "connection_error", "message": str(e)}, 2, json_mode)
        return
    report = build_report(messages, folder=folder)
    if json_mode:
        click.echo(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        click.echo(f"Folder: {report['folder']}")
        click.echo(f"Total: {report['total_messages']} messages, {report['size_total_mb']} MB")
        for name, data in report["categories"].items():
            count = data.get("count") if isinstance(data, dict) else None
            if count is not None:
                click.echo(f"  {name}: {count}")


@cli.command("senders")
@click.option("--email", required=True)
@click.option("--folder", default="INBOX", show_default=True)
@click.option("--top", default=50, show_default=True, type=int)
@click.option("--json", "json_mode", is_flag=True)
def senders_cmd(email: str, folder: str, top: int, json_mode: bool):
    """List the top-N senders by message count."""
    try:
        creds = get_credentials(email)
    except AuthMissingError as e:
        _fail({"error_code": "auth_missing", "message": str(e)}, 3, json_mode)
        return
    try:
        with imap_connect(creds, port=_DEFAULT_PORT) as mb:
            mb.folder.set(folder)
            counter: Counter[str] = Counter()
            for m in mb.fetch(headers_only=True, mark_seen=False, bulk=True):
                if m.from_:
                    counter[m.from_.strip()] += 1
    except Exception as e:
        _fail({"error_code": "connection_error", "message": str(e)}, 2, json_mode)
        return
    payload = {
        "schema_version": SCHEMA_VERSION,
        "folder": folder,
        "senders": [{"sender": s, "count": c} for s, c in counter.most_common(top)],
    }
    if json_mode:
        click.echo(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        for entry in payload["senders"]:
            click.echo(f"{entry['count']:6d}  {entry['sender']}")


def _require_filter(sender, subject_contains, older_than, json_mode):
    if not any([sender, subject_contains, older_than]):
        _fail(
            {
                "error_code": "bad_args",
                "message": (
                    "At least one filter required "
                    "(--sender / --subject-contains / --older-than)"
                ),
            },
            4, json_mode,
        )


@cli.command("delete")
@click.option("--email", required=True)
@click.option("--folder", default="INBOX", show_default=True)
@click.option("--sender", default=None)
@click.option("--subject-contains", default=None)
@click.option("--older-than", default=None, help="e.g. 30d, 2w, 3m, 1y")
@click.option("--limit", default=None, type=int)
@click.option(
    "--apply",
    is_flag=True,
    help="Actually move to Trash. Without --apply this is a dry-run.",
)
@click.option("--json", "json_mode", is_flag=True)
def delete_cmd(email, folder, sender, subject_contains, older_than, limit, apply, json_mode):
    """Soft-delete messages matching filter (move to Trash)."""
    _require_filter(sender, subject_contains, older_than, json_mode)
    try:
        creds = get_credentials(email)
    except AuthMissingError as e:
        _fail({"error_code": "auth_missing", "message": str(e)}, 3, json_mode)
        return
    try:
        with imap_connect(creds, port=_DEFAULT_PORT) as mb:
            res = run_delete(
                mb,
                folder=folder,
                sender=sender,
                subject_contains=subject_contains,
                older_than=older_than,
                apply=apply,
                limit=limit,
            )
    except Exception as e:
        _fail({"error_code": "operation_error", "message": str(e)}, 2, json_mode)
        return
    payload = {
        "ok": True,
        "schema_version": SCHEMA_VERSION,
        "subcommand": "delete",
        "dry_run": res.dry_run,
        "folder": res.folder,
        "target_folder": res.target_folder,
        "affected_count": len(res.affected_uids),
        "affected_uids": res.affected_uids,
        "sample": res.sample,
    }
    if apply:
        log_action(
            subcommand="delete",
            args={
                "sender": sender,
                "subject_contains": subject_contains,
                "older_than": older_than,
                "limit": limit,
            },
            folder=folder,
            affected_uids=res.affected_uids,
            result="success",
        )
    if json_mode:
        click.echo(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        verb = "Moved" if apply else "Would move"
        click.echo(f"{verb} {len(res.affected_uids)} messages to {res.target_folder!r}")


@cli.command("move")
@click.option("--email", required=True)
@click.option("--folder", default="INBOX", show_default=True)
@click.option("--to", "target", required=True, help="Destination folder.")
@click.option("--sender", default=None)
@click.option("--subject-contains", default=None)
@click.option("--older-than", default=None)
@click.option("--limit", default=None, type=int)
@click.option("--apply", is_flag=True)
@click.option("--json", "json_mode", is_flag=True)
def move_cmd(email, folder, target, sender, subject_contains, older_than, limit, apply, json_mode):
    """Move messages matching filter to target folder."""
    _require_filter(sender, subject_contains, older_than, json_mode)
    try:
        creds = get_credentials(email)
    except AuthMissingError as e:
        _fail({"error_code": "auth_missing", "message": str(e)}, 3, json_mode)
        return
    try:
        with imap_connect(creds, port=_DEFAULT_PORT) as mb:
            res = run_move(
                mb, folder=folder, target=target,
                sender=sender, subject_contains=subject_contains,
                older_than=older_than, apply=apply, limit=limit,
            )
    except Exception as e:
        _fail({"error_code": "operation_error", "message": str(e)}, 2, json_mode)
        return
    payload = {
        "ok": True,
        "schema_version": SCHEMA_VERSION,
        "subcommand": "move",
        "dry_run": res.dry_run,
        "folder": res.folder,
        "target_folder": res.target_folder,
        "affected_count": len(res.affected_uids),
        "affected_uids": res.affected_uids,
        "sample": res.sample,
    }
    if apply:
        log_action(
            subcommand="move",
            args={"to": target, "sender": sender, "subject_contains": subject_contains,
                  "older_than": older_than, "limit": limit},
            folder=folder,
            affected_uids=res.affected_uids,
            result="success",
        )
    if json_mode:
        click.echo(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        verb = "Moved" if apply else "Would move"
        click.echo(f"{verb} {len(res.affected_uids)} messages to {target!r}")


@cli.command("archive")
@click.option("--email", required=True)
@click.option("--folder", default="INBOX", show_default=True)
@click.option("--older-than", required=True, help="e.g. 12m, 2y")
@click.option("--apply", is_flag=True)
@click.option("--json", "json_mode", is_flag=True)
def archive_cmd(email, folder, older_than, apply, json_mode):
    """Bulk-move messages older than N into Archive/YYYY subfolders."""
    try:
        creds = get_credentials(email)
    except AuthMissingError as e:
        _fail({"error_code": "auth_missing", "message": str(e)}, 3, json_mode)
        return
    try:
        with imap_connect(creds, port=_DEFAULT_PORT) as mb:
            res = run_archive(mb, folder=folder, older_than=older_than, apply=apply)
    except Exception as e:
        _fail({"error_code": "operation_error", "message": str(e)}, 2, json_mode)
        return
    affected = sum(g["count"] for g in res.groups)
    payload = {
        "ok": True,
        "schema_version": SCHEMA_VERSION,
        "subcommand": "archive",
        "dry_run": res.dry_run,
        "folder": res.folder,
        "archive_root": res.archive_root,
        "groups": res.groups,
        "affected_count": affected,
    }
    if apply:
        log_action(
            subcommand="archive",
            args={"older_than": older_than},
            folder=folder,
            affected_uids=[uid for g in res.groups for uid in g["uids"]],
            result="success",
        )
    if json_mode:
        click.echo(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        verb = "Moved" if apply else "Would move"
        click.echo(f"{verb} {affected} messages into {res.archive_root}/<year>")
        for g in res.groups:
            click.echo(f"  {g['year']}: {g['count']} → {g['target']}")


@cli.command("dedupe")
@click.option("--email", required=True)
@click.option("--folder", default="INBOX", show_default=True)
@click.option("--apply", is_flag=True)
@click.option("--json", "json_mode", is_flag=True)
def dedupe_cmd(email, folder, apply, json_mode):
    """Move duplicate-by-Message-ID copies to Trash, keep the oldest."""
    try:
        creds = get_credentials(email)
    except AuthMissingError as e:
        _fail({"error_code": "auth_missing", "message": str(e)}, 3, json_mode)
        return
    try:
        with imap_connect(creds, port=_DEFAULT_PORT) as mb:
            res = run_dedupe(mb, folder=folder, apply=apply)
    except Exception as e:
        _fail({"error_code": "operation_error", "message": str(e)}, 2, json_mode)
        return
    payload = {
        "ok": True,
        "schema_version": SCHEMA_VERSION,
        "subcommand": "dedupe",
        "dry_run": res.dry_run,
        "folder": res.folder,
        "target_folder": res.target_folder,
        "duplicate_count": len(res.duplicate_uids),
        "groups": res.groups,
    }
    if apply:
        log_action(
            subcommand="dedupe", args={}, folder=folder,
            affected_uids=res.duplicate_uids, result="success",
        )
    if json_mode:
        click.echo(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        verb = "Moved" if apply else "Would move"
        click.echo(
            f"{verb} {len(res.duplicate_uids)} duplicates "
            f"from {len(res.groups)} groups to Trash"
        )


@cli.command("attachments")
@click.option("--email", required=True)
@click.option("--folder", default="INBOX", show_default=True)
@click.option("--size-gt", default="10mb", show_default=True)
@click.option("--older-than", default=None)
@click.option("--json", "json_mode", is_flag=True)
def attachments_cmd(email, folder, size_gt, older_than, json_mode):
    """Find large messages. Stripping deferred to v2 — this lists candidates only."""
    try:
        creds = get_credentials(email)
    except AuthMissingError as e:
        _fail({"error_code": "auth_missing", "message": str(e)}, 3, json_mode)
        return
    try:
        with imap_connect(creds, port=_DEFAULT_PORT) as mb:
            res = run_attachments(mb, folder=folder, size_gt=size_gt, older_than=older_than)
    except Exception as e:
        _fail({"error_code": "operation_error", "message": str(e)}, 2, json_mode)
        return
    payload = {
        "ok": True,
        "schema_version": SCHEMA_VERSION,
        "subcommand": "attachments",
        "dry_run": res.dry_run,
        "folder": res.folder,
        "candidate_count": len(res.candidates),
        "candidates": res.candidates,
        "note": (
            "v1 lists candidates only; "
            "pipe to `delete --sender=... --apply` to remove specific senders."
        ),
    }
    if json_mode:
        click.echo(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        click.echo(f"Found {len(res.candidates)} large messages:")
        for c in res.candidates[:20]:
            click.echo(f"  {c['size_mb']:>6.1f} MB  {c['from']}  {c['subject']}")


@cli.command("unsubscribe")
@click.option("--email", required=True)
@click.option("--folder", default="INBOX", show_default=True)
@click.option("--sender", required=True)
@click.option("--apply", is_flag=True)
@click.option("--json", "json_mode", is_flag=True)
def unsubscribe_cmd(email, folder, sender, apply, json_mode):
    """Parse List-Unsubscribe header for sender, optionally execute (HTTPS or mailto)."""
    try:
        creds = get_credentials(email)
    except AuthMissingError as e:
        _fail({"error_code": "auth_missing", "message": str(e)}, 3, json_mode)
        return
    try:
        with imap_connect(creds, port=_DEFAULT_PORT) as mb:
            data = collect_unsub_targets(mb, sender=sender, folder=folder)
            uids = data["uids"]
            actions = data["actions"]
            results: list[dict] = []
            if apply:
                # Take the first (preferred) action — already sorted https-first
                if actions:
                    a = UnsubAction(**{k: actions[0][k] for k in ("kind", "target", "one_click")})
                    ok, info = perform_unsubscribe(
                        a,
                        smtp_sender=creds.email,
                        smtp_password=creds.password,
                    )
                    results.append({"action": actions[0], "ok": ok, "info": info})
                # Move matching messages to Trash regardless of unsubscribe success
                trash = resolve_folder(mb, "trash")
                if trash and uids:
                    mb.move(uids, trash)
    except Exception as e:
        _fail({"error_code": "operation_error", "message": str(e)}, 2, json_mode)
        return
    payload = {
        "ok": True,
        "schema_version": SCHEMA_VERSION,
        "subcommand": "unsubscribe",
        "dry_run": not apply,
        "folder": folder,
        "sender": sender,
        "matching_count": len(uids),
        "actions": actions,
        "results": results,
    }
    if apply:
        log_action(
            subcommand="unsubscribe",
            args={"sender": sender},
            folder=folder,
            affected_uids=uids,
            result="success" if not results or results[0]["ok"] else "partial",
        )
    if json_mode:
        click.echo(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        verb = "Performed" if apply else "Would attempt"
        click.echo(
            f"{verb} unsubscribe for {sender}: "
            f"{len(actions)} action(s) found, {len(uids)} matching messages"
        )
