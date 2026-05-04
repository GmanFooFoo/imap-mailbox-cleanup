import json

from click.testing import CliRunner

from mailbox_cleanup.cli import cli


def test_senders_lists_top_n(seeded_mailbox, monkeypatch, tmp_path):
    g = seeded_mailbox
    from mailbox_cleanup import cli_helpers
    from mailbox_cleanup.auth import Credentials
    from mailbox_cleanup.config import (
        DEFAULT_CONFIG_PATH_ENV,
        Account,
        Config,
        save_config,
    )

    cfg_path = tmp_path / "cfg.json"
    monkeypatch.setenv(DEFAULT_CONFIG_PATH_ENV, str(cfg_path))
    monkeypatch.delenv("MAILBOX_CLEANUP_ACCOUNT", raising=False)
    save_config(
        Config(
            default="test",
            accounts=(Account(alias="test", email="test@local", server=g["host"], port=g["port"]),),
        )
    )

    fake_creds = lambda email: Credentials(  # noqa: E731
        email=g["user"], password=g["password"], server=g["host"]
    )
    monkeypatch.setattr(cli_helpers, "get_credentials", fake_creds)

    runner = CliRunner()
    result = runner.invoke(cli, ["senders", "--email", "test", "--top", "5", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "senders" in data
    assert isinstance(data["senders"], list)
    assert len(data["senders"]) <= 5
    if data["senders"]:
        assert "sender" in data["senders"][0]
        assert "count" in data["senders"][0]
