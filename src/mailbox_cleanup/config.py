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

    Replaces `.` and `+` with `-`, lowercases, trims leading non-alphanumeric.
    Raises ConfigError if the email has no local-part.
    """
    if "@" not in email:
        raise ConfigError(f"Invalid email (no @): {email!r}")
    local = email.split("@", 1)[0].lower()
    slug = re.sub(r"[.+]", "-", local)
    slug = re.sub(r"[^a-z0-9_-]", "", slug)
    slug = slug.lstrip("-_0123456789")
    if not slug:
        # fallback: use cleaned local-part even if it starts with a digit/underscore
        slug = re.sub(r"[^a-z0-9_-]", "", local) or "account"
    if not _ALIAS_RE.match(slug):
        raise ConfigError(f"Could not derive valid alias from {email!r}")
    return slug
