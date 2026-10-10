"""Client IP resolution, trusted proxies, and IPv6 normalisation.

THIS IS A RED TEST FILE. It is written before `app/core/client_ip.py` and fails
with ImportError until that module exists. That failure is the point: the
security properties are written down before the code that has to satisfy them.

## What is being defended

`X-Forwarded-For` is set by whatever proxy sat in front of the app. Anyone can
send that header. Trusting it unconditionally means any visitor can claim any IP
address, which defeats the second factor of the send route's approval check â€” and
it fails silently, because everything still appears to work.

So: the header is honoured only when the *connection itself* arrived from a
peer in `TRUSTED_PROXY_CIDRS`. Otherwise the socket address is used, which is the
truth and cannot be forged.

## IPv6 and the /64

A visitor's IPv6 address rotates within their /64 for privacy. The full address
is therefore not a stable identity, and comparing it exactly would fail on a
harmless rotation. IPv6 is truncated to /64; IPv4 stays whole at /32.

The consequence is real: a carrier that assigns a *new* /64 mid-session breaks
the check, and there is no way to keep both "stable" and "exact". That case is
covered by `test_ipv6_normalises_to_64` and handled with a friendly message
rather than a bare 403.

`ipaddress.ip_network(..., strict=False)` is required â€” a full address is not on
a /64 boundary and raises without it.
"""

import ipaddress

import pytest

from app.core.client_ip import (
    IP_HASH_LENGTH,
    IPV4_PREFIX_BITS,
    IPV6_PREFIX_BITS,
    client_ip,
    hash_ip,
    is_trusted_proxy,
    normalise_for_hash,
)
from app.core.config import Settings

# A Render proxy peer (private, as a real one would be) and a random stranger.
TRUSTED = "10.0.0.5"
STRANGER = "45.33.32.200"

# Real globally-routable-looking visitor addresses.
#
# Not the RFC 5737 documentation ranges (203.0.113.x, 198.51.100.x). Python's
# `ipaddress` correctly reports those as non-global, and the implementation
# refuses any forwarded header claiming a non-global address â€” so a test using
# them would be asserting against a case that cannot occur in production. The
# refusal is covered separately by
# `test_documentation_ranges_are_refused_from_the_header`.
VISITOR = "45.33.32.42"
OTHER_VISITOR = "8.8.8.8"

SALT = "a-sufficiently-long-test-salt"


def make_settings(**overrides) -> Settings:
    base = {
        "ip_hash_salt": SALT,
        "trusted_proxy_cidrs": [f"{TRUSTED}/32"],
    }
    base.update(overrides)
    return Settings(**base)


# --- Trusting the proxy header ---------------------------------------------


def test_a_trusted_proxy_may_set_the_header() -> None:
    """The normal Render path. Without this, nobody could ever approve a draft."""
    resolved = client_ip(TRUSTED, VISITOR, make_settings())

    assert resolved == VISITOR


def test_a_stranger_may_not() -> None:
    """The whole point. A forged header from an untrusted peer is ignored."""
    resolved = client_ip(STRANGER, OTHER_VISITOR, make_settings())

    assert resolved == STRANGER, "forged X-Forwarded-For was trusted"


def test_an_empty_trust_list_trusts_nobody() -> None:
    """The default. Degrades to the socket peer and cannot be spoofed."""
    settings = make_settings(trusted_proxy_cidrs=[])

    resolved = client_ip(TRUSTED, VISITOR, settings)

    assert resolved == TRUSTED


def test_the_leftmost_forwarded_entry_wins() -> None:
    """The first entry is the original client; the rest are intermediaries.

    `X-Forwarded-For: client, proxy1, proxy2` is appended to by each hop, so the
    original client is leftmost. Taking the rightmost would take Render's own
    address and make every visitor look identical.
    """
    resolved = client_ip(TRUSTED, f"{VISITOR}, 172.64.0.1", make_settings())

    assert resolved == VISITOR


def test_a_multi_hop_chain_resolves_to_the_client() -> None:
    resolved = client_ip(TRUSTED, f"{VISITOR}, 172.64.0.1, 10.0.0.1", make_settings())

    assert resolved == VISITOR


def test_documentation_ranges_are_refused_from_the_header() -> None:
    """RFC 5737 and RFC 3849 are never a real visitor, so they are a forgery.

    Worth pinning because the whole test file avoids them for the same reason.
    """
    settings = make_settings()

    for documentation in ("203.0.113.7", "198.51.100.7", "2001:db8::1"):
        assert client_ip(TRUSTED, documentation, settings) == TRUSTED, documentation


def test_a_malformed_forwarded_header_is_ignored() -> None:
    """Garbage from a proxy must not become an address."""
    settings = make_settings()

    assert client_ip(STRANGER, "not-an-ip", settings) == STRANGER
    assert client_ip(STRANGER, "", settings) == STRANGER


def test_a_forwarded_header_claiming_an_internal_address_is_refused() -> None:
    """A header is attacker-controlled, so it must not be able to say 127.0.0.1.

    Landing an approval check on localhost, or on a private address, would let a
    visitor forge the "same network" appearance entirely.
    """
    settings = make_settings()

    for spoofed in ("127.0.0.1", "10.0.0.5", "192.168.1.1", "::1", "fc00::1"):
        assert client_ip(TRUSTED, spoofed, settings) == TRUSTED, spoofed


def test_an_unparseable_peer_falls_back_rather_than_raising() -> None:
    """A 500 in front of a visitor is worse than an approximate address."""
    settings = make_settings()

    resolved = client_ip("garbage", "1.2.3.4", settings)

    assert resolved  # something, not an exception


# --- Trusted proxy matching ------------------------------------------------


def test_exact_address_in_a_cidr_is_trusted() -> None:
    settings = make_settings()

    assert is_trusted_proxy("10.0.0.5", settings) is True


def test_address_outside_the_cidr_is_not_trusted() -> None:
    settings = make_settings()

    assert is_trusted_proxy("10.0.0.6", settings) is False


def test_a_wider_cidr_trusts_a_whole_block() -> None:
    settings = make_settings(trusted_proxy_cidrs=["10.0.0.0/8"])

    assert is_trusted_proxy("10.9.9.9", settings) is True


def test_multiple_cidrs_are_all_honoured() -> None:
    settings = make_settings(trusted_proxy_cidrs=["10.0.0.0/24", "172.64.0.0/16"])

    assert is_trusted_proxy("10.0.0.5", settings) is True
    assert is_trusted_proxy("172.64.1.1", settings) is True
    assert is_trusted_proxy("192.0.2.1", settings) is False


def test_an_unparseable_cidr_does_not_disable_the_others() -> None:
    """One bad entry must not silently disable trust entirely."""
    settings = make_settings(trusted_proxy_cidrs=["not-a-cidr", "10.0.0.5/32"])

    assert is_trusted_proxy("10.0.0.5", settings) is True


# --- IPv6 normalisation ----------------------------------------------------


def test_ipv6_normalises_to_64() -> None:
    """Two addresses in one /64 are the same visitor.

    Uses globally-routable addresses rather than the 2001:db8:: documentation
    prefix, because `normalise_for_hash` itself is version-agnostic and should
    be tested on realistic input.
    """
    a = normalise_for_hash("2606:4700:4700:1111::1")
    b = normalise_for_hash("2606:4700:4700:1111:9abc::dead")

    assert a == b


def test_ipv4_is_not_truncated() -> None:
    """A /32 is the whole address. Truncating to a /64 of IPv4 is meaningless."""
    assert normalise_for_hash(VISITOR) == VISITOR


def test_ipv4_and_ipv6_normalise_to_different_values() -> None:
    assert normalise_for_hash(VISITOR) != normalise_for_hash("2606:4700:4700:1111::1")


def test_the_prefix_constants_are_what_the_docstring_says() -> None:
    assert IPV4_PREFIX_BITS == 32
    assert IPV6_PREFIX_BITS == 64


def test_a_different_ipv6_subnet_is_a_different_visitor() -> None:
    """Truncating must not collapse unrelated addresses into one identity."""
    assert normalise_for_hash("2606:4700:1111::1") != normalise_for_hash("2606:4700:2222::1")


def test_an_invalid_address_raises() -> None:
    """Silently hashing garbage would make two different broken inputs collide."""
    with pytest.raises(ValueError):
        normalise_for_hash("not-an-address")


def test_normalise_accepts_an_ipaddress_object() -> None:
    """Callers often already hold a parsed address."""
    address = ipaddress.ip_address(VISITOR)

    assert normalise_for_hash(address) == VISITOR


# --- Hashing ----------------------------------------------------------------


def test_hashing_is_deterministic() -> None:
    """Two drafts from the same visitor must produce the same hash to be approved."""
    assert hash_ip(VISITOR, SALT) == hash_ip(VISITOR, SALT)


def test_different_addresses_hash_differently() -> None:
    assert hash_ip(VISITOR, SALT) != hash_ip(OTHER_VISITOR, SALT)


def test_a_different_salt_changes_the_hash() -> None:
    """The salt is what makes the digest un-reversible by rainbow table."""
    assert hash_ip(VISITOR, SALT) != hash_ip(VISITOR, "a-different-salt-entirely")


def test_the_hash_is_hex_and_fits_the_column() -> None:
    """Stored in a varchar(64), like the approval token hash."""
    digest = hash_ip(VISITOR, SALT)

    assert len(digest) == IP_HASH_LENGTH == 64
    assert all(character in "0123456789abcdef" for character in digest)


def test_the_raw_address_never_appears_in_the_hash() -> None:
    digest = hash_ip(VISITOR, SALT)

    assert VISITOR not in digest


def test_hashing_normalises_first() -> None:
    """Otherwise an IPv6 rotation would look like a different visitor."""
    a = hash_ip("2606:4700:4700:1111::1", SALT)
    b = hash_ip("2606:4700:4700:1111:9abc::dead", SALT)

    assert a == b


def test_a_short_salt_is_refused() -> None:
    """A weak salt makes the digest brute-forceable over the whole IPv4 space."""
    with pytest.raises(ValueError, match="salt"):
        hash_ip(VISITOR, "short")


def test_an_empty_salt_is_refused() -> None:
    """Without a salt there is nothing to hash with, and drafts can never match."""
    with pytest.raises(ValueError, match="salt"):
        hash_ip(VISITOR, "")
