"""Multi-account configuration: schema, validation, file I/O, resolution, migration."""

from __future__ import annotations

import re


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


_ALIAS_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")


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
