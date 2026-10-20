"""Request and response models for the message approval route.

The token arrives in the body rather than as a header. It is a one-shot bearer
capability presented by a page the visitor is already looking at, not a
credential a script would attach to a request — and putting it in a header would
make it far more likely to end up in a log line or a referrer.
"""

from pydantic import BaseModel, ConfigDict, Field


class SendMessageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # `min_length` is 1 rather than a guess at the real token length. The
    # constant-time comparison is what makes length uninformative, and a length
    # floor here would be a guess at `secrets.token_urlsafe(32)` that only
    # produces a 422 instead of a 403 for a short attacker-supplied string.
    token: str = Field(
        min_length=1,
        max_length=256,
        description="The approval token from the draft event. Never logged.",
    )


class SendMessageResponse(BaseModel):
    """What the browser gets back. Deliberately thin.

    No token, no body, no visitor details. The frontend already has the draft
    from the `draft` event, and echoing it here would put it in browser history
    for no benefit.
    """

    sent: bool
    message_id: int
    # The owner's inbox is subject to a daily ceiling. Distinct from a failure so
    # the frontend can say "try tomorrow" rather than "something went wrong".
    reason: str | None = None


class DraftSummary(BaseModel):
    """The pending draft, for the approve/discard control.

    Returned by GET /messages/{id} and by PATCH (the edit route), so the
    frontend can re-render a draft after a change. Deliberately excludes the
    token: if the browser lost it, the draft is unapprovable, and reissuing one
    would let a reload silently extend a capability that is meant to expire.

    The visitor's address is `sender_email` on the wire (decision 6): the field
    names who is sending, not what kind of message this is. The `messages`
    table's column stays `email` and the model-facing tool argument stays
    `email`; the database and the provider schema do not change vocabulary.
    """

    id: int
    name: str
    sender_email: str
    body: str
    status: str
    created_at: str
    expires_at: str


class CreateDraftRequest(BaseModel):
    """The contact form. `company`, `role` and `subject` are optional context.

    Lengths mirror the service's own validation (`MAX_NAME`, `MAX_BODY`, …):
    a 422 at the edge is cheaper than a DraftError after a rate-limit spend —
    but the service re-validates whatever arrives, because it already has the
    checks and the tool path skips this model entirely.
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    sender_email: str = Field(min_length=3, max_length=320)
    body: str = Field(min_length=1, max_length=4000)
    company: str | None = Field(default=None, max_length=200)
    role: str | None = Field(default=None, max_length=200)
    subject: str | None = Field(default=None, max_length=200)


class CreateDraftResponse(BaseModel):
    """The created draft plus the only copy of the token that will ever exist.

    Sameshape philosophy as the `draft` SSE event: the token goes to the browser
    and into a ref, never into state or storage.
    """

    id: int
    name: str
    sender_email: str
    body: str
    expires_at: str
    token: str


class EditDraftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str = Field(min_length=1, max_length=256)
    body: str = Field(min_length=1, max_length=4000)


class CancelDraftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str = Field(min_length=1, max_length=256)


class CancelDraftResponse(BaseModel):
    """Thin on purpose: the card disappears locally, nothing else changes."""

    cancelled: bool
    message_id: int
