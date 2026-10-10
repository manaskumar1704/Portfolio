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

    Returned by GET /messages/{id} so the frontend can re-render a draft after a
    page reload. Deliberately excludes the token: if the browser lost it, the
    draft is unapprovable, and reissuing one would let a reload silently extend
    a capability that is meant to expire.
    """

    id: int
    name: str
    email: str
    body: str
    status: str
    created_at: str
    expires_at: str
