from mailbox_cleanup.classify import (
    Category,
    classify,
    is_automated,
    is_bounce,
    is_newsletter,
)


def test_newsletter_via_unsubscribe_header():
    headers = {"list-unsubscribe": "<https://x.com/unsub>"}
    assert is_newsletter(from_addr="x@y.com", subject="hi", headers=headers)


def test_newsletter_via_sender_pattern():
    assert is_newsletter(from_addr="newsletter@linkedin.com", subject="x", headers={})
    assert is_newsletter(from_addr="noreply@github.com", subject="x", headers={})
    assert is_newsletter(from_addr="no-reply@x.com", subject="x", headers={})
    assert is_newsletter(from_addr="news@medium.com", subject="x", headers={})
    assert is_newsletter(from_addr="marketing@x.com", subject="x", headers={})


def test_not_newsletter_for_personal():
    assert not is_newsletter(from_addr="alice@example.com", subject="hi", headers={})


def test_automated_sender_patterns():
    for local in ["notifications", "bot", "service", "alerts", "system", "daemon", "automation"]:
        assert is_automated(from_addr=f"{local}@x.com", subject="x", headers={})


def test_bounce_via_mailer_daemon():
    assert is_bounce(from_addr="MAILER-DAEMON@ionos.de", subject="x", headers={})
    assert is_bounce(from_addr="postmaster@x.com", subject="x", headers={})


def test_bounce_via_subject_prefix():
    for prefix in [
        "Undelivered Mail",
        "Returned mail: foo",
        "Mail Delivery Failure",
        "Delivery Status Notification (Failure)",
        "Auto-Reply: Out of office",
        "Out of Office: vacation",
        "Abwesenheitsnotiz",
    ]:
        assert is_bounce(from_addr="x@y.de", subject=prefix, headers={})


def test_classify_returns_set_of_categories():
    headers = {"list-unsubscribe": "<https://x>"}
    cats = classify(
        from_addr="newsletter@linkedin.com",
        subject="weekly digest",
        headers=headers,
        size_bytes=15_000_000,
    )
    assert Category.NEWSLETTER in cats
    assert Category.LARGE_ATTACHMENT in cats


def test_classify_plain_message_has_no_category():
    cats = classify(
        from_addr="alice@example.com",
        subject="lunch",
        headers={},
        size_bytes=5000,
    )
    assert cats == set()
