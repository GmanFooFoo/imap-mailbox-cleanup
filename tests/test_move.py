import json

from click.testing import CliRunner

from mailbox_cleanup.cli import cli


def test_move_apply_moves_to_named_folder(seeded_mailbox, monkeypatch, tmp_path):
    g = seeded_mailbox
    from imap_tools import MailBoxUnencrypted

    from mailbox_cleanup import cli as cli_mod
    from mailbox_cleanup.auth import Credentials

    # Pre-create target folder
    with MailBoxUnencrypted(g["host"], port=g["port"]).login(g["user"], g["password"]) as mb:
        try:
            mb.folder.create("Triage")
        except Exception:
            pass

    monkeypatch.setattr(
        cli_mod, "get_credentials",
        lambda email: Credentials(email=g["user"], password=g["password"], server=g["host"]),
    )
    monkeypatch.setattr(cli_mod, "_DEFAULT_PORT", g["port"])
    monkeypatch.setenv("MAILBOX_CLEANUP_AUDIT_LOG", str(tmp_path / "audit.log"))

    runner = CliRunner()
    result = runner.invoke(cli, [
        "move", "--email", "test",
        "--sender", "alice@example.com",
        "--to", "Triage",
        "--apply", "--json",
    ])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["dry_run"] is False
    assert data["target_folder"] == "Triage"
    assert data["affected_count"] >= 1
