from unittest.mock import MagicMock

from mailbox_cleanup.folders import (
    ARCHIVE_FALLBACKS,  # noqa: F401  (re-export contract)
    TRASH_FALLBACKS,  # noqa: F401  (re-export contract)
    resolve_folder,
)


def _make_folder(name: str, flags=()):
    f = MagicMock()
    f.name = name
    f.flags = flags
    return f


def test_resolve_trash_via_special_use():
    folders = [_make_folder("INBOX"), _make_folder("Müll", flags=("\\Trash",))]
    mb = MagicMock()
    mb.folder.list.return_value = folders
    assert resolve_folder(mb, "trash") == "Müll"


def test_resolve_trash_via_fallback_papierkorb():
    folders = [_make_folder("INBOX"), _make_folder("Papierkorb")]
    mb = MagicMock()
    mb.folder.list.return_value = folders
    assert resolve_folder(mb, "trash") == "Papierkorb"


def test_resolve_trash_via_fallback_trash():
    folders = [_make_folder("INBOX"), _make_folder("Trash")]
    mb = MagicMock()
    mb.folder.list.return_value = folders
    assert resolve_folder(mb, "trash") == "Trash"


def test_resolve_archive_via_special_use():
    folders = [_make_folder("INBOX"), _make_folder("Backup", flags=("\\Archive",))]
    mb = MagicMock()
    mb.folder.list.return_value = folders
    assert resolve_folder(mb, "archive") == "Backup"


def test_resolve_archive_fallback():
    folders = [_make_folder("INBOX"), _make_folder("Archive")]
    mb = MagicMock()
    mb.folder.list.return_value = folders
    assert resolve_folder(mb, "archive") == "Archive"


def test_resolve_unknown_returns_none():
    folders = [_make_folder("INBOX")]
    mb = MagicMock()
    mb.folder.list.return_value = folders
    assert resolve_folder(mb, "trash") is None
