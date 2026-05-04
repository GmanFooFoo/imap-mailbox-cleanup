from mailbox_cleanup.config import derive_provider


def test_derive_provider_ionos():
    assert derive_provider("imap.ionos.de") == "ionos"
    assert derive_provider("imap.ionos.com") == "ionos"


def test_derive_provider_gmail():
    assert derive_provider("imap.gmail.com") == "gmail"
    assert derive_provider("imap.googlemail.com") == "gmail"


def test_derive_provider_icloud():
    assert derive_provider("imap.mail.me.com") == "icloud"
    assert derive_provider("imap.icloud.com") == "icloud"


def test_derive_provider_generic():
    assert derive_provider("mail.example.com") == "generic"
    assert derive_provider("imap.fastmail.com") == "generic"


def test_derive_provider_case_insensitive():
    assert derive_provider("IMAP.IONOS.DE") == "ionos"
