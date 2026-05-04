"""Multi-account configuration: schema, validation, file I/O, resolution, migration."""

from __future__ import annotations

import re
from dataclasses import dataclass, field


def derive_provider(server: str) -> str:
    """Map an IMAP server hostname to a provider label.

    Free-form return; new providers can be added without consumer changes.
    """
    s = server.lower().strip()
    if "ionos." in s:
        return "ionos"
    if s.endswith("gmail.com") or s.endswith("googlemail.com"):
        return "gmail"
    if "mail.me.com" in s or s.endswith("icloud.com"):
        return "icloud"
    return "generic"


_ALIAS_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,31}$")


class ConfigError(Exception):
    """Raised on invalid or unrecoverable config state."""


def derive_alias_from_email(email: str) -> str:
    """Derive a slugified alias from an email's local-part.

    Replaces `.` and `+` with `-`, lowercases, drops other non-alphanumerics,
    and trims leading hyphens/underscores so the result starts with [a-z0-9].
    Falls back to "account" if no usable characters remain.
    Raises ConfigError if the email has no `@`.
    """
    if "@" not in email:
        raise ConfigError(f"Invalid email (no @): {email!r}")
    local = email.split("@", 1)[0].lower()
    slug = re.sub(r"[.+]", "-", local)
    slug = re.sub(r"[^a-z0-9_-]", "", slug)
    slug = slug.lstrip("-_")
    if not slug:
        slug = "account"
    if not _ALIAS_RE.match(slug):  # defensive — should be unreachable
        raise ConfigError(f"Could not derive valid alias from {email!r}")
    return slug


SCHEMA_VERSION = 1


@dataclass(frozen=True)
class Account:
    alias: str
    email: str
    server: str
    port: int = 993
    provider: str = ""

    def __post_init__(self):
        # frozen dataclass: must use object.__setattr__ for derived defaults
        if not self.provider:
            object.__setattr__(self, "provider", derive_provider(self.server))


@dataclass(frozen=True)
class Config:
    default: str | None
    accounts: tuple[Account, ...] = field(default_factory=tuple)
    schema_version: int = SCHEMA_VERSION


def _validate_account_dict(d: dict) -> Account:
    for required in ("alias", "email", "server"):
        if required not in d:
            raise ConfigError(
                f"Account missing required field {required!r}: {d!r}"
            )
    alias = d["alias"]
    if not isinstance(alias, str) or not _ALIAS_RE.match(alias):
        raise ConfigError(
            f"Invalid alias {alias!r}; must match ^[a-z0-9][a-z0-9_-]{{0,31}}$ "
            "(1-32 chars, leading alphanumeric, lowercase)"
        )
    email = d["email"]
    if not isinstance(email, str) or "@" not in email:
        raise ConfigError(f"Invalid email {email!r} for alias {alias!r}")
    return Account(
        alias=alias,
        email=email,
        server=d["server"],
        port=int(d.get("port", 993)),
        provider=d.get("provider", ""),
    )


def validate_config(data: dict) -> Config:
    """Parse and validate a raw config dict. Raises ConfigError on any problem."""
    if not isinstance(data, dict):
        raise ConfigError(
            f"Config root must be an object, got {type(data).__name__}"
        )
    sv = data.get("schema_version")
    if sv != SCHEMA_VERSION:
        raise ConfigError(
            f"Unsupported schema_version: {sv!r} (this CLI knows {SCHEMA_VERSION})"
        )
    accounts_raw = data.get("accounts", [])
    if not isinstance(accounts_raw, list):
        raise ConfigError("'accounts' must be a list")
    accounts = tuple(_validate_account_dict(a) for a in accounts_raw)

    seen_aliases: set[str] = set()
    seen_emails: set[str] = set()
    for a in accounts:
        if a.alias in seen_aliases:
            raise ConfigError(f"duplicate alias: {a.alias!r}")
        if a.email in seen_emails:
            raise ConfigError(f"duplicate email: {a.email!r}")
        seen_aliases.add(a.alias)
        seen_emails.add(a.email)

    default = data.get("default")
    if default is not None and default not in seen_aliases:
        raise ConfigError(
            f"default {default!r} is not an existing alias: "
            f"{sorted(seen_aliases)}"
        )

    return Config(default=default, accounts=accounts, schema_version=SCHEMA_VERSION)
