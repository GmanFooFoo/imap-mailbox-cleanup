from unittest.mock import patch

from mailbox_cleanup.auth import (
    SERVICE_NAME,
    AuthMissingError,
    Credentials,
    delete_credentials,
    get_credentials,
    set_credentials,
)


def test_credentials_dataclass():
    c = Credentials(email="a@b.com", password="secret", server="imap.ionos.de")
    assert c.email == "a@b.com"
    assert c.password == "secret"
    assert c.server == "imap.ionos.de"


def test_set_and_get_credentials_roundtrip():
    with patch("mailbox_cleanup.auth.keyring") as kr:
        store = {}
        kr.set_password.side_effect = lambda s, a, p: store.__setitem__((s, a), p)
        kr.get_password.side_effect = lambda s, a: store.get((s, a))

        set_credentials("user@x.de", "pw123", "imap.ionos.de")

        creds = get_credentials("user@x.de")
        assert creds.email == "user@x.de"
        assert creds.password == "pw123"
        assert creds.server == "imap.ionos.de"


def test_get_credentials_missing_raises():
    with patch("mailbox_cleanup.auth.keyring") as kr:
        kr.get_password.return_value = None
        try:
            get_credentials("nobody@x.de")
        except AuthMissingError as e:
            assert "nobody@x.de" in str(e)
            return
        raise AssertionError("Expected AuthMissingError")


def test_delete_credentials():
    with patch("mailbox_cleanup.auth.keyring") as kr:
        delete_credentials("user@x.de")
        kr.delete_password.assert_any_call(SERVICE_NAME, "user@x.de")
        kr.delete_password.assert_any_call(SERVICE_NAME, "imap-server:user@x.de")
