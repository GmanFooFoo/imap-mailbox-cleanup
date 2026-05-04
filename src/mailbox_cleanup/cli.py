import json
import sys

import click

from . import SCHEMA_VERSION
from .auth import (
    AuthMissingError,
    delete_credentials,
    get_credentials,
    set_credentials,
)
from .imap_client import imap_connect
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
