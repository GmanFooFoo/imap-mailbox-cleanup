import pytest

from mailbox_cleanup.auth import Credentials
from mailbox_cleanup.imap_client import IMAPConnectionError, imap_connect

pytestmark = pytest.mark.integration


def test_connect_to_greenmail_lists_inbox(seeded_mailbox):
    g = seeded_mailbox
    creds = Credentials(email=g["user"], password=g["password"], server=g["host"])
    with imap_connect(creds, port=g["port"]) as mb:
        folders = [f.name for f in mb.folder.list()]
        assert "INBOX" in folders


def test_connect_with_wrong_password_raises(greenmail):
    creds = Credentials(email=greenmail["user"], password="WRONG", server=greenmail["host"])
    with pytest.raises(IMAPConnectionError):
        with imap_connect(creds, port=greenmail["port"], max_retries=0):
            pass


def test_seeded_mailbox_has_four_messages(seeded_mailbox):
    g = seeded_mailbox
    creds = Credentials(email=g["user"], password=g["password"], server=g["host"])
    with imap_connect(creds, port=g["port"]) as mb:
        msgs = list(mb.fetch())
        assert len(msgs) == 4
