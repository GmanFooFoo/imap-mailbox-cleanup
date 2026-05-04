from unittest.mock import MagicMock, patch

from mailbox_cleanup.operations.unsubscribe import (
    UnsubAction,
    parse_list_unsubscribe,
    perform_unsubscribe,
)


def test_parse_https_only():
    actions = parse_list_unsubscribe(
        list_unsubscribe="<https://example.com/unsub?t=abc>",
        list_unsubscribe_post=None,
    )
    assert any(a.kind == "https" and a.target == "https://example.com/unsub?t=abc" for a in actions)


def test_parse_mailto_only():
    actions = parse_list_unsubscribe(
        list_unsubscribe="<mailto:unsub@x.com?subject=unsubscribe>",
        list_unsubscribe_post=None,
    )
    assert any(a.kind == "mailto" and a.target == "unsub@x.com" for a in actions)


def test_parse_both_https_preferred():
    actions = parse_list_unsubscribe(
        list_unsubscribe="<mailto:u@x>, <https://x.com/unsub>",
        list_unsubscribe_post="List-Unsubscribe=One-Click",
    )
    https = [a for a in actions if a.kind == "https"][0]
    assert https.one_click is True


def test_perform_https_one_click_uses_post():
    action = UnsubAction(kind="https", target="https://x.com/unsub", one_click=True)
    with patch("mailbox_cleanup.operations.unsubscribe.requests") as r:
        r.post.return_value = MagicMock(status_code=200)
        ok, info = perform_unsubscribe(action, smtp_sender=None)
    assert ok is True
    r.post.assert_called_once()
    assert "List-Unsubscribe=One-Click" in r.post.call_args.kwargs["data"]


def test_perform_https_get_when_no_one_click():
    action = UnsubAction(kind="https", target="https://x.com/unsub", one_click=False)
    with patch("mailbox_cleanup.operations.unsubscribe.requests") as r:
        r.get.return_value = MagicMock(status_code=200)
        ok, info = perform_unsubscribe(action, smtp_sender=None)
    assert ok is True
    r.get.assert_called_once()
