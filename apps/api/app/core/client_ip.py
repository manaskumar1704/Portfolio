"""Working out which visitor is making a request, without being lied to.

## The problem

The send route requires three things: a token, a matching IP, and an unexpired
row. The token is unguessable. The IP is the awkward one, because the app does
not talk to visitors directly — Vercel and Render sit in between, and by default
both of them hide who the caller actually is.

## `X-Forwarded-For` is a claim, not a fact

Every proxy appends to `X-Forwarded-For`, so the header reads:

```
X-Forwarded-For: <original client>, <proxy 1>, <proxy 2>
```

which makes the **leftmost** entry the original client. Anyone can send that
header with anything in it. So it is honoured only when the connection itself
arrived from a peer in `TRUSTED_PROXY_CIDRS`; from anyone else it is discarded
and the socket address is used, which is the truth and cannot be forged.

This is the mistake that fails quietly. Trust the header unconditionally and
everything still appears to work — the IP check passes, the email arrives, and
the only symptom is that a visitor can claim any address they like. Nothing
errors. `test_an_empty_trust_list_trusts_nobody` covers the safe default, which
is "trust nobody".

A forwarded value that claims to be private or loopback is refused even from a
trusted peer. A header that lands the approval check on `127.0.0.1` would let a
visitor forge the appearance of being on the same network.

## IPv6 is normalised to its /64

A visitor's IPv6 address rotates within their /64 for privacy. The full address
is therefore not a stable identity: comparing it exactly would fail on a
harmless rotation and reject a legitimate approval.

IPv6 truncates to /64. IPv4 stays whole at /32, which is its entire address.

The consequence is a real limitation. A carrier that assigns a *new* /64
mid-session will fail the check, and there is no way to keep both "stable" and
"exact". That is why the send route's refusal explains itself rather than
returning a bare 403 — see `app/api/messages.py`.

## What is stored

`sha256(salt + normalised_address)`, hex, 64 characters.

The salt is what makes the digest un-reversible by brute force over the IPv4
space, which is small enough to enumerate. A short salt is refused rather than
silently producing something weak.

Losing the salt means existing hashes no longer match an incoming request, so
every outstanding draft becomes unapprovable. That is the intended failure mode:
drafts are abandoned, never sent by someone else.
"""

import hashlib
import ipaddress
from typing import Any

from app.core.config import Settings
from app.core.logging import get_logger

log = get_logger(__name__)

# IPv4 is a single host address; IPv6's meaningful unit for identifying a
# subscriber is the /64, not the full 128 bits.
IPV4_PREFIX_BITS = 32
IPV6_PREFIX_BITS = 64

# Matches the varchar(64) column, like the approval token hash.
IP_HASH_LENGTH = 64

# A salt shorter than this makes the digest brute-forceable. 16 characters of
# printable entropy is the floor, not a recommendation.
MIN_SALT_LENGTH = 16


def normalise_for_hash(address: str | ipaddress._BaseAddress) -> str:
    """Truncate to the unit that identifies a visitor.

    IPv6 to its /64, IPv4 unchanged. Raises `ValueError` on anything unparseable:
    silently hashing garbage would make two different broken inputs collide.
    """
    parsed = (
        address
        if isinstance(address, (ipaddress.IPv4Address, ipaddress.IPv6Address))
        else ipaddress.ip_address(str(address).strip())
    )

    bits = IPV4_PREFIX_BITS if parsed.version == 4 else IPV6_PREFIX_BITS

    # `strict=False` is required. A full address is not on a /64 boundary, and
    # the strict default raises on exactly the input this function exists to
    # handle.
    #
    # `.network_address` rather than the network's string form, which renders as
    # "203.0.113.42/32". The prefix is implied by the version and belongs in the
    # hash as a separator, not in the address that gets stored.
    return str(ipaddress.ip_network(f"{parsed}/{bits}", strict=False).network_address)


def hash_ip(address: str | ipaddress._BaseAddress, salt: str) -> str:
    """Salted SHA-256 of a visitor's normalised address."""
    if not salt or len(salt) < MIN_SALT_LENGTH:
        raise ValueError(
            f"IP_HASH_SALT must be at least {MIN_SALT_LENGTH} characters. A short or "
            f"empty salt makes the digest reversible by brute force over the IPv4 "
            f"space, and an empty one means outstanding drafts can never match."
        )

    normalised = normalise_for_hash(address)
    return hashlib.sha256(f"{salt}{normalised}".encode()).hexdigest()


def is_trusted_proxy(peer: str, settings: Settings) -> bool:
    """Whether `peer` is a proxy allowed to set `X-Forwarded-For`.

    A malformed entry in the list is logged and skipped rather than raising. One
    typo in an environment variable must not silently disable trust for every
    correctly-configured CIDR alongside it.
    """
    try:
        address = ipaddress.ip_address(str(peer).strip())
    except ValueError:
        return False

    for entry in settings.trusted_proxy_cidrs:
        try:
            if address in ipaddress.ip_network(str(entry).strip(), strict=False):
                return True
        except ValueError:
            log.warning("ignoring malformed TRUSTED_PROXY_CIDRS entry: %r", entry)

    return False


def _is_internal(address: ipaddress._BaseAddress) -> bool:
    """Loopback, private, link-local, or unspecified.

    Refused from a forwarded header even when the peer is trusted. The header is
    attacker-controlled; letting it say `127.0.0.1` or `10.0.0.5` would let a
    visitor forge the "same network" appearance the IP factor depends on.
    """
    return bool(
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_reserved
        or address.is_unspecified
    )


def client_ip(peer: str, forwarded: str | None, settings: Settings) -> str:
    """The visitor's address, as far as it can be trusted.

    `peer` is the socket address. `forwarded` is the raw `X-Forwarded-For` value,
    which is only consulted when `peer` is a trusted proxy.

    Returns something usable in every case: a malformed peer falls back rather
    than raising, because a 500 in front of a visitor is worse than an
    approximate address.
    """
    if forwarded and is_trusted_proxy(peer, settings):
        # Leftmost is the original client. Taking the rightmost would take the
        # nearest proxy's address and make every visitor look identical.
        for candidate in (part.strip() for part in forwarded.split(",")):
            if not candidate:
                continue
            try:
                address = ipaddress.ip_address(candidate)
            except ValueError:
                continue
            if _is_internal(address):
                log.info("ignoring forwarded header claiming an internal address")
                break
            return str(address)

    try:
        return str(ipaddress.ip_address(str(peer).strip()))
    except ValueError:
        # Deliberately not the raw string. An unparseable peer is not an
        # address, and storing it verbatim would put attacker-controlled text
        # into a column that is hashed everywhere else.
        log.warning("unparseable peer address; falling back to a sentinel")
        return "unparseable-peer"


def hash_from_settings(address: str, settings: Settings) -> str | None:
    """Hash using the configured salt, or None when there is no usable salt.

    None rather than an exception: a caller deciding whether to create a draft
    should refuse cleanly, not crash.
    """
    if not settings.ip_hashing_enabled:
        return None
    try:
        return hash_ip(address, settings.ip_hash_salt)
    except ValueError:
        log.warning("cannot hash IP: salt is missing or too short")
        return None


def describe(settings: Settings) -> dict[str, Any]:
    """How this deployment resolves IPs. For logs and the probe route."""
    return {
        "trusted_proxy_count": len(settings.trusted_proxy_cidrs),
        "ip_hashing": settings.ip_hashing_enabled,
        "ipv6_prefix_bits": IPV6_PREFIX_BITS,
    }
