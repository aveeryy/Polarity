import pytest

from polarity.utils import redact_emails


@pytest.mark.parametrize(
    "text, expected",
    [
        ("test@gmail.com", "[REDACTED]"),
        ("test.with.dots@protonmail.com", "[REDACTED]"),
        (
            "some text the.email+red@some.provider.com more text",
            "some text [REDACTED] more text",
        ),
    ],
)
def test_redact_mails(text, expected):
    assert redact_emails(text) == expected
