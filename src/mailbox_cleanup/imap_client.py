"""IMAP client wrapper. Real implementation in Task 4."""
from contextlib import contextmanager
from imap_tools import MailBox
from .auth import Credentials


@contextmanager
def imap_connect(creds: Credentials):
    """Context manager that yields a connected MailBox."""
    with MailBox(creds.server).login(creds.email, creds.password) as mb:
        yield mb
