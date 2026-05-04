import pytest

from mailbox_cleanup.config import (
    Account,
    Config,
    ConfigError,
    derive_alias_from_email,
    derive_provider,
    validate_config,
)


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


def test_derive_alias_underscores_only_falls_back():
    assert derive_alias_from_email("___@x.de") == "account"


def test_derive_alias_dots_only_falls_back():
    assert derive_alias_from_email("....@x.de") == "account"


def test_derive_alias_digits_preserved():
    assert derive_alias_from_email("0a@x.de") == "0a"


def test_derive_alias_leading_digit_kept():
    assert derive_alias_from_email("123abc@x.de") == "123abc"


def test_derive_alias_unicode_stripped():
    """Non-ASCII is dropped (documented behavior; ASCII-only aliases for v0.2)."""
    assert derive_alias_from_email("müller@x.de") == "mller"


def test_account_dataclass_defaults():
    a = Account(alias="work", email="x@y.de", server="imap.ionos.de")
    assert a.port == 993
    assert a.provider == "ionos"  # auto-derived


def test_account_explicit_provider_wins():
    a = Account(
        alias="weird",
        email="x@y.de",
        server="some.host.tld",
        provider="custom",
    )
    assert a.provider == "custom"


def test_validate_config_happy_path():
    data = {
        "schema_version": 1,
        "default": "work",
        "accounts": [
            {"alias": "work", "email": "a@b.de", "server": "imap.ionos.de"}
        ],
    }
    cfg = validate_config(data)
    assert isinstance(cfg, Config)
    assert cfg.default == "work"
    assert len(cfg.accounts) == 1
    assert cfg.accounts[0].alias == "work"


def test_validate_config_empty_default_null_ok():
    data = {"schema_version": 1, "default": None, "accounts": []}
    cfg = validate_config(data)
    assert cfg.default is None
    assert cfg.accounts == ()


def test_validate_config_unknown_default_raises():
    data = {
        "schema_version": 1,
        "default": "missing",
        "accounts": [{"alias": "work", "email": "a@b.de", "server": "x"}],
    }
    with pytest.raises(ConfigError, match="default"):
        validate_config(data)


def test_validate_config_duplicate_alias_raises():
    data = {
        "schema_version": 1,
        "default": "work",
        "accounts": [
            {"alias": "work", "email": "a@b.de", "server": "x"},
            {"alias": "work", "email": "c@d.de", "server": "y"},
        ],
    }
    with pytest.raises(ConfigError, match="duplicate.*alias"):
        validate_config(data)


def test_validate_config_duplicate_email_raises():
    data = {
        "schema_version": 1,
        "default": "a",
        "accounts": [
            {"alias": "a", "email": "x@y.de", "server": "s"},
            {"alias": "b", "email": "x@y.de", "server": "s"},
        ],
    }
    with pytest.raises(ConfigError, match="duplicate.*email"):
        validate_config(data)


def test_validate_config_bad_alias_regex_raises():
    data = {
        "schema_version": 1,
        "default": "Bad-Alias",
        "accounts": [
            {"alias": "Bad-Alias", "email": "a@b.de", "server": "x"}
        ],
    }
    with pytest.raises(ConfigError, match="alias"):
        validate_config(data)


def test_validate_config_alias_too_long_raises():
    long_alias = "a" * 33  # exceeds 1-32 bound
    data = {
        "schema_version": 1,
        "default": long_alias,
        "accounts": [
            {"alias": long_alias, "email": "a@b.de", "server": "x"}
        ],
    }
    with pytest.raises(ConfigError, match="alias"):
        validate_config(data)


def test_validate_config_alias_max_length_ok():
    max_alias = "a" + ("0" * 31)  # exactly 32 chars
    data = {
        "schema_version": 1,
        "default": max_alias,
        "accounts": [
            {"alias": max_alias, "email": "a@b.de", "server": "x"}
        ],
    }
    cfg = validate_config(data)
    assert cfg.accounts[0].alias == max_alias


def test_validate_config_unsupported_schema_version_raises():
    data = {"schema_version": 99, "default": None, "accounts": []}
    with pytest.raises(ConfigError, match="schema_version"):
        validate_config(data)


def test_validate_config_email_at_required():
    data = {
        "schema_version": 1,
        "default": "a",
        "accounts": [{"alias": "a", "email": "no-at", "server": "x"}],
    }
    with pytest.raises(ConfigError, match="email"):
        validate_config(data)


def test_validate_config_missing_required_account_field_raises():
    data = {
        "schema_version": 1,
        "default": None,
        "accounts": [{"alias": "a", "email": "a@b.de"}],  # no server
    }
    with pytest.raises(ConfigError, match="server"):
        validate_config(data)


def test_validate_config_root_must_be_dict_raises():
    with pytest.raises(ConfigError, match="object|dict"):
        validate_config(["not", "a", "dict"])  # type: ignore[arg-type]


def test_validate_config_accounts_must_be_list_raises():
    data = {"schema_version": 1, "default": None, "accounts": "not-a-list"}
    with pytest.raises(ConfigError, match="accounts"):
        validate_config(data)
