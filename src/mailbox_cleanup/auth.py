from dataclasses import dataclass

import keyring

SERVICE_NAME = "mailbox-cleanup"
SERVER_KEY_PREFIX = "imap-server:"


class AuthMissingError(Exception):
    """Raised when credentials are not in Keychain."""


@dataclass(frozen=True)
class Credentials:
    email: str
    password: str
    server: str


def set_credentials(email: str, password: str, server: str) -> None:
    keyring.set_password(SERVICE_NAME, email, password)
    keyring.set_password(SERVICE_NAME, f"{SERVER_KEY_PREFIX}{email}", server)


def get_credentials(email: str) -> Credentials:
    password = keyring.get_password(SERVICE_NAME, email)
    if password is None:
        raise AuthMissingError(
            f"No credentials in Keychain for {email}. Run `mailbox-cleanup auth set`."
        )
    server = keyring.get_password(SERVICE_NAME, f"{SERVER_KEY_PREFIX}{email}") or "imap.ionos.de"
    return Credentials(email=email, password=password, server=server)


def delete_credentials(email: str) -> None:
    try:
        keyring.delete_password(SERVICE_NAME, email)
    except keyring.errors.PasswordDeleteError:
        pass
    try:
        keyring.delete_password(SERVICE_NAME, f"{SERVER_KEY_PREFIX}{email}")
    except keyring.errors.PasswordDeleteError:
        pass
