"""Contact: validation, token handling, and the draft lifecycle.

The database half is in `test_contact_db.py`. This file covers everything that
does not need a database: the token, the email parsing, and the sanitization.

The property that matters most is in `test_token_is_never_in_the_model_output`.
The send token is a capability, and anything that puts it in front of the model
lets a prompt-injected visitor approve their own draft.
"""

import pytest

from app.services import contact
from app.services.contact import (
    DRAFT_TTL,
    DraftError,
    clean_text,
    confirmation_for_model,
    generate_token,
    hash_token,
    normalise_email,
    validate_draft,
)

# --- Tokens -----------------------------------------------------------------


def test_a_token_is_long_enough_to_be_unguessable() -> None:
    """32 bytes from urlsafe base64 is 43 characters of entropy."""
    token = generate_token()

    assert len(token) >= 40
    assert len(set(generate_token() for _ in range(20))) == 20


def test_hashing_is_deterministic_and_not_the_token() -> None:
    """A stored hash must be reproducible but useless as a send capability."""
    token = generate_token()

    assert hash_token(token) == hash_token(token)
    assert hash_token(token) != token
    assert len(hash_token(token)) == 64


def test_different_tokens_hash_differently() -> None:
    assert hash_token(generate_token()) != hash_token(generate_token())


def test_the_hash_is_hex() -> None:
    """Stored in a varchar(64); anything else would be truncated."""
    token_hash = hash_token(generate_token())

    assert all(character in "0123456789abcdef" for character in token_hash)


# --- Email parsing ----------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("a@b.com", "a@b.com"),
        ("  spaced@example.com  ", "spaced@example.com"),
        ("Name <name@example.com>", "name@example.com"),
        ('"Quoted Name" <q@example.com>', "q@example.com"),
        ("UPPER@EXAMPLE.COM", "upper@example.com"),
    ],
)
def test_valid_addresses_are_normalised(raw: str, expected: str) -> None:
    assert normalise_email(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "not-an-email",
        "@example.com",
        "a@",
        "a@b",
        "a b@example.com",
        "a@@example.com",
        "http://example.com",
    ],
)
def test_invalid_addresses_are_refused(raw: str) -> None:
    """Guessing at intent here means mail to an address nobody chose."""
    with pytest.raises(DraftError, match="valid email"):
        normalise_email(raw)


def test_an_over_long_address_is_refused() -> None:
    with pytest.raises(DraftError, match="too long"):
        normalise_email(f"{'a' * 400}@example.com")


def test_the_error_message_is_written_for_a_human() -> None:
    """These are shown to a visitor, not logged for an operator."""
    with pytest.raises(DraftError) as exc:
        normalise_email("nope")

    message = str(exc.value)
    assert "does not look like" in message
    assert "Traceback" not in message


# --- Sanitization -----------------------------------------------------------


def test_control_characters_are_stripped() -> None:
    """A body with a NUL in it is either a bug or an attempt to break something."""
    assert clean_text("hello\x00world\x07") == "helloworld"


def test_tabs_and_newlines_survive() -> None:
    """They are legitimate in a message and are not control characters to strip."""
    assert clean_text("line one\nline\ttwo") == "line one\nline\ttwo"


def test_edges_are_trimmed() -> None:
    assert clean_text("  \n padded \n  ") == "padded"


# --- Draft validation -------------------------------------------------------


def test_a_valid_draft_is_cleaned_and_returned() -> None:
    name, email, body = validate_draft("  Ada Lovelace ", "Ada <ada@example.com>", " Hello there ")

    assert name == "Ada Lovelace"
    assert email == "ada@example.com"
    assert body == "Hello there"


def test_an_empty_name_is_refused() -> None:
    with pytest.raises(DraftError, match="your name"):
        validate_draft("", "a@b.com", "hello")


def test_an_empty_body_is_refused() -> None:
    with pytest.raises(DraftError, match="empty"):
        validate_draft("Ada", "a@b.com", "   ")


def test_an_over_long_body_is_refused_with_the_limit() -> None:
    with pytest.raises(DraftError) as exc:
        validate_draft("Ada", "a@b.com", "x" * 5000)

    assert "too long" in str(exc.value)
    assert str(contact.MAX_BODY) in str(exc.value)


def test_an_over_long_name_is_refused() -> None:
    with pytest.raises(DraftError, match="too long"):
        validate_draft("n" * 300, "a@b.com", "hello")


# --- What the model is told -------------------------------------------------


def make_draft() -> contact.Draft:
    from datetime import UTC, datetime

    return contact.Draft(
        id=42,
        name="Ada Lovelace",
        email="ada@example.com",
        body="I have an offer.",
        created_at=datetime.now(UTC),
        expires_at=datetime.now(UTC) + DRAFT_TTL,
        token="super-secret-token",
    )


def test_the_confirmation_says_it_was_not_sent() -> None:
    """The failure this prevents: a bot saying "I've sent your message"."""
    confirmation = confirmation_for_model(make_draft())

    assert "NOT sent" in confirmation
    assert "Nothing has been emailed" in confirmation
    assert "approve" in confirmation.lower()


def test_the_confirmation_never_contains_the_token() -> None:
    """The model must not be able to read the send capability.

    If it could, a prompt-injected visitor could talk it into approving their own
    draft, which collapses the two-phase design into one phase.
    """
    draft = make_draft()
    confirmation = confirmation_for_model(draft)

    assert draft.token not in confirmation
    assert "super-secret-token" not in confirmation


def test_the_confirmation_never_contains_the_message_body() -> None:
    """A stranger's words do not belong in a prompt."""
    draft = make_draft()

    assert draft.body not in confirmation_for_model(draft)


def test_the_confirmation_warns_against_claiming_it_was_sent() -> None:
    confirmation = confirmation_for_model(make_draft())

    assert "do not claim it" in confirmation.lower()
