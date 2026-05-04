import json

from click.testing import CliRunner

from mailbox_cleanup.cli import cli


def _make_runner_env(seeded_mailbox, monkeypatch, tmp_path):
    g = seeded_mailbox
    from mailbox_cleanup import cli as cli_mod
    from mailbox_cleanup.auth import Credentials
    monkeypatch.setattr(
        cli_mod, "get_credentials",
        lambda email: Credentials(email=g["user"], password=g["password"], server=g["host"]),
    )
    monkeypatch.setattr(cli_mod, "_DEFAULT_PORT", g["port"])
    monkeypatch.setenv("MAILBOX_CLEANUP_AUDIT_LOG", str(tmp_path / "audit.log"))


def test_delete_dry_run_does_not_modify(seeded_mailbox, monkeypatch, tmp_path):
    _make_runner_env(seeded_mailbox, monkeypatch, tmp_path)
    runner = CliRunner()
    result = runner.invoke(cli, [
        "delete", "--email", "test",
        "--sender", "newsletter@linkedin.com",
        "--json",
    ])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["dry_run"] is True
    assert data["affected_count"] >= 1
    assert not (tmp_path / "audit.log").exists()


def test_delete_apply_moves_to_trash(seeded_mailbox, monkeypatch, tmp_path):
    _make_runner_env(seeded_mailbox, monkeypatch, tmp_path)
    # Greenmail does not auto-provision a Trash folder. Create one so the
    # SPECIAL-USE / fallback resolver can find it (it matches via literal name).
    from imap_tools import MailBoxUnencrypted
    g = seeded_mailbox
    with MailBoxUnencrypted(g["host"], port=g["port"]).login(g["user"], g["password"]) as mb:
        existing = {f.name for f in mb.folder.list()}
        if "Trash" not in existing:
            mb.folder.create("Trash")
    runner = CliRunner()
    result = runner.invoke(cli, [
        "delete", "--email", "test",
        "--sender", "newsletter@linkedin.com",
        "--apply", "--json",
    ])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["dry_run"] is False
    assert data["affected_count"] >= 1
    assert (tmp_path / "audit.log").exists()
    audit_line = (tmp_path / "audit.log").read_text().strip()
    audit = json.loads(audit_line)
    assert audit["subcommand"] == "delete"
    assert audit["result"] == "success"


def test_delete_without_filter_returns_4(seeded_mailbox, monkeypatch, tmp_path):
    _make_runner_env(seeded_mailbox, monkeypatch, tmp_path)
    runner = CliRunner()
    result = runner.invoke(cli, ["delete", "--email", "test", "--json"])
    assert result.exit_code == 4
