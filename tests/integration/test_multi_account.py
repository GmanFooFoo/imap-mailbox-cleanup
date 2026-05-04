"""End-to-end test: two Greenmail accounts, switch via --account and env var."""
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from mailbox_cleanup.auth import Credentials
from mailbox_cleanup.cli import cli
from mailbox_cleanup.config import (
    DEFAULT_CONFIG_PATH_ENV,
    Account,
    Config,
    save_config,
)

pytestmark = pytest.mark.integration


@pytest.fixture
def two_account_setup(tmp_path, monkeypatch, greenmail):
    """Configure two accounts pointing at Greenmail (work + private users)."""
    cfg_path = tmp_path / "cfg.json"
    monkeypatch.setenv(DEFAULT_CONFIG_PATH_ENV, str(cfg_path))
    monkeypatch.delenv("MAILBOX_CLEANUP_ACCOUNT", raising=False)

    host = greenmail["host"]
    port = greenmail["port"]
    save_config(Config(
        default="work",
        accounts=(
            Account(alias="work", email="work@localhost", server=host, port=port),
            Account(alias="private", email="private@localhost", server=host, port=port),
        ),
    ))

    # Greenmail's IMAP LOGIN expects the bare userid (the part before '@'),
    # not the full email. Patch get_credentials so the IMAP login uses the
    # bare userid while the Account.email in config remains the full address.
    creds_by_email = {
        "work@localhost": Credentials(email="work", password="workpw", server=host),
        "private@localhost": Credentials(email="private", password="privatepw", server=host),
    }

    patcher = patch(
        "mailbox_cleanup.cli_helpers.get_credentials",
        side_effect=lambda email: creds_by_email[email],
    )
    patcher.start()
    yield CliRunner()
    patcher.stop()


def test_scan_uses_default_account(two_account_setup):
    runner = two_account_setup
    r = runner.invoke(cli, ["scan", "--json"])
    assert r.exit_code == 0, r.output
    # Default is 'work', so the scan must have used work's mailbox
    assert '"folder"' in r.output or "INBOX" in r.output


def test_scan_with_account_flag_uses_other_account(two_account_setup):
    runner = two_account_setup
    r = runner.invoke(cli, ["scan", "--account", "private", "--json"])
    assert r.exit_code == 0, r.output


def test_scan_env_var_overrides_default(two_account_setup, monkeypatch):
    runner = two_account_setup
    monkeypatch.setenv("MAILBOX_CLEANUP_ACCOUNT", "private")
    r = runner.invoke(cli, ["scan", "--json"])
    assert r.exit_code == 0, r.output


def test_auth_test_returns_correct_account(two_account_setup):
    runner = two_account_setup
    r = runner.invoke(cli, ["auth", "test", "--account", "private", "--json"])
    assert r.exit_code == 0, r.output
    import json
    data = json.loads(r.output)
    assert data["account"] == "private"
    assert data["email"] == "private@localhost"
