import json

from click.testing import CliRunner

from mailbox_cleanup.cli import cli


def test_senders_lists_top_n(seeded_mailbox, monkeypatch):
    g = seeded_mailbox
    from mailbox_cleanup import cli as cli_mod
    from mailbox_cleanup.auth import Credentials

    monkeypatch.setattr(
        cli_mod,
        "get_credentials",
        lambda email: Credentials(email=g["user"], password=g["password"], server=g["host"]),
    )
    monkeypatch.setattr(cli_mod, "_DEFAULT_PORT", g["port"])

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
