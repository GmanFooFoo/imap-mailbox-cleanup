import json

from click.testing import CliRunner

from mailbox_cleanup.cli import cli


def _env(seeded_mailbox, monkeypatch, tmp_path):
    g = seeded_mailbox
    from mailbox_cleanup import cli as cli_mod
    from mailbox_cleanup.auth import Credentials

    monkeypatch.setattr(
        cli_mod,
        "get_credentials",
        lambda email: Credentials(email=g["user"], password=g["password"], server=g["host"]),
    )
    monkeypatch.setattr(cli_mod, "_DEFAULT_PORT", g["port"])
    monkeypatch.setenv("MAILBOX_CLEANUP_AUDIT_LOG", str(tmp_path / "audit.log"))


def test_bounces_dry_run_finds_mailer_daemon(seeded_mailbox, monkeypatch, tmp_path):
    _env(seeded_mailbox, monkeypatch, tmp_path)
    runner = CliRunner()
    result = runner.invoke(cli, ["bounces", "--email", "test", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["dry_run"] is True
    assert data["affected_count"] >= 1


def test_bounces_apply_moves_to_trash(seeded_mailbox, monkeypatch, tmp_path):
    _env(seeded_mailbox, monkeypatch, tmp_path)
    # Greenmail does not auto-provision a Trash folder. Create one so the
    # SPECIAL-USE / fallback resolver can find it (it matches via literal name).
    from imap_tools import MailBoxUnencrypted

    g = seeded_mailbox
    with MailBoxUnencrypted(g["host"], port=g["port"]).login(g["user"], g["password"]) as mb:
        existing = {f.name for f in mb.folder.list()}
        if "Trash" not in existing:
            mb.folder.create("Trash")
    runner = CliRunner()
    result = runner.invoke(cli, ["bounces", "--email", "test", "--apply", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["dry_run"] is False
    assert data["affected_count"] >= 1
    assert (tmp_path / "audit.log").exists()
