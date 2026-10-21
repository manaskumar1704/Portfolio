"""TEMPORARY. Delete this file once `TRUSTED_PROXY_CIDRS` is populated.

## What it is for

`client_ip` only honours `X-Forwarded-For` when the socket peer is in
`TRUSTED_PROXY_CIDRS`. That list has to contain the CIDRs Render's proxy actually
connects from, and the obvious approaches to finding them are both wrong:

- **Guessing from documentation.** Render publishes no fixed list, and a wrong
  entry either discards the real header (approval breaks for everyone) or trusts
  a stranger's.
- **Trusting everything.** `0.0.0.0/0` makes the IP factor decorative. Anyone can
  claim any address, and the send route's approval check reduces to "do you have
  the token".

So the route reports what it observes, and the list is filled from that.

## It needs a token, because a boolean flag is not enough

A probe that echoes the peer address is a disclosure: it tells an attacker
exactly what the app sees, which is the one piece of information that says
whether a forged `X-Forwarded-For` is believed. `PROBE_ENABLED=true` is a plan to
remember to turn off; an unguessable token in the URL stays safe even if someone
forgets. Empty means 404 for everyone, including whoever finds the route.

## Delete it afterwards

The route has no reason to exist once the list is populated, and leaving it in is
a way to eventually leave the gate open. The comments here are the record of why
the list looks the way it does.
"""

import hmac

from fastapi import APIRouter, HTTPException, Query, Request, status

from app.core.client_ip import client_ip, describe
from app.core.config import Settings, get_settings

router = APIRouter(tags=["probe"])


@router.get("/_probe/headers")
async def probe_headers(request: Request, token: str = Query(default="")) -> dict:
    """Echo what this deployment actually sees.

    Read as the owner, once:

    - `peer` is what goes in `TRUSTED_PROXY_CIDRS`. Use the /32, or the /64 if
      it is IPv6.
    - `forwarded` is the visitor's address as the proxy reports it. It should
      differ from `peer` — that difference is the whole point, and if the two
      match then the header is not being set and no proxy CIDR will help.
    - `currently_resolves_to` shows what the *current* list produces, which is
      how you tell "populated correctly" from "populated with the wrong thing".
    """
    settings = get_settings()
    _authorise(token, settings)

    forwarded = request.headers.get("x-forwarded-for")
    peer = request.client.host if request.client else "unknown"

    return {
        "peer": peer,
        "peer_is_ipv6": ":" in peer,
        "forwarded": forwarded,
        "currently_resolves_to": client_ip(peer, forwarded, settings),
        **describe(settings),
    }


def _authorise(supplied: str, settings: Settings) -> None:
    """404 unless the token matches. Never 403.

    A 403 confirms the route exists, and the only thing an attacker would do
    with that confirmation is try harder. A 404 is indistinguishable from a
    deployment where the route was already deleted.
    """
    expected = settings.probe_token

    if not expected or not hmac.compare_digest(expected, supplied):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found.")
