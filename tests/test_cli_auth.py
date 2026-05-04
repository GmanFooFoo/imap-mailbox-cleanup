import json
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from mailbox_cleanup.cli import cli


def test_cli_help():
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "auth" in result.output


def test_auth_set_writes_to_keychain():
    runner = CliRunner()
    with patch("mailbox_cleanup.cli.set_credentials") as set_creds:
        result = runner.invoke(
            cli,
            ["auth", "set", "--email", "a@b.de", "--server", "imap.ionos.de"],
            input="my-password\n",
        )
        assert result.exit_code == 0
        set_creds.assert_called_once_with("a@b.de", "my-password", "imap.ionos.de")


def test_auth_test_success_json():
    runner = CliRunner()
    fake_client = MagicMock()
    inbox = MagicMock()
    inbox.name = "INBOX"
    sent = MagicMock()
    sent.name = "Sent"
    fake_client.__enter__.return_value.folder.list.return_value = [inbox, sent]
    with (
        patch("mailbox_cleanup.cli.get_credentials") as get_creds,
        patch("mailbox_cleanup.cli.imap_connect", return_value=fake_client),
    ):
        get_creds.return_value = MagicMock(email="a@b.de", server="imap.ionos.de")
        result = runner.invoke(cli, ["auth", "test", "--email", "a@b.de", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["ok"] is True
        assert data["email"] == "a@b.de"
        assert "folders" in data


def test_auth_test_missing_credentials_exit_3():
    from mailbox_cleanup.auth import AuthMissingError

    runner = CliRunner()
    with patch("mailbox_cleanup.cli.get_credentials", side_effect=AuthMissingError("no creds")):
        result = runner.invoke(cli, ["auth", "test", "--email", "a@b.de", "--json"])
        assert result.exit_code == 3
        data = json.loads(result.output)
        assert data["ok"] is False
        assert data["error_code"] == "auth_missing"
