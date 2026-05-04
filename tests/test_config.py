from mailbox_cleanup.config import derive_alias_from_email, derive_provider


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


def test_derive_alias_simple():
    assert derive_alias_from_email("german@rauhut.com") == "german"


def test_derive_alias_with_dot():
    assert derive_alias_from_email("first.last@example.com") == "first-last"


def test_derive_alias_with_plus():
    assert derive_alias_from_email("user+tag@example.com") == "user-tag"


def test_derive_alias_with_underscore():
    assert derive_alias_from_email("a_b@example.com") == "a_b"


def test_derive_alias_uppercase():
    assert derive_alias_from_email("Germ4N@RAUHUT.com") == "germ4n"


def test_derive_alias_invalid_email_raises():
    import pytest

    from mailbox_cleanup.config import ConfigError

    with pytest.raises(ConfigError):
        derive_alias_from_email("no-at-sign")


def test_derive_alias_strips_leading_non_alnum():
    assert derive_alias_from_email("-foo@x.de") == "foo"
