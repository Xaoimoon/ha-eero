"""Derived objects are built once per poll and looked up by ID.

Entities read their network and resource several times per state write; each
read used to rebuild every client, eero and profile object of the network.
"""

from __future__ import annotations

from helpers import build_api, fixture, ok

ACCOUNT = "/2.2/account"
NETWORK = "/2.2/networks/1234567"


def routes(devices=None) -> dict:
    """Return routes for one network."""
    return {
        ACCOUNT: ok(fixture("account")),
        NETWORK: ok(fixture("network")),
        f"{NETWORK}/thread": ok(fixture("thread")),
        f"{NETWORK}/devices": ok(fixture("devices") if devices is None else devices),
        f"{NETWORK}/profiles": ok([]),
        f"{NETWORK}/backup_access_points": ok([]),
    }


def test_objects_are_built_once_per_poll() -> None:
    """Repeated reads return the same objects within one poll."""
    account = build_api(routes()).update()

    assert account.networks is account.networks
    network = account.networks[0]
    assert network.resources is network.resources
    assert network.clients[0] is network.clients[0]


def test_lookup_by_id_matches_the_linear_scan() -> None:
    """network_by_id and resource_by_id find what a scan of the lists finds."""
    account = build_api(routes()).update()
    network = account.network_by_id("1234567")

    assert network is account.networks[0]
    assert account.network_by_id("missing") is None
    for resource in network.resources:
        assert network.resource_by_id(resource.id) is next(
            r for r in network.resources if r.id == resource.id
        )
    assert network.resource_by_id("missing") is None


def test_a_new_poll_sees_new_data() -> None:
    """The cache lives on the account object, so the next poll is not stale."""
    devices = fixture("devices")
    first_poll, second_poll = routes(devices), routes(devices[1:])
    # The fake session serves a list of responses in order, one per request.
    api = build_api({path: [first_poll[path], second_poll[path]] for path in first_poll})
    first = api.update().networks[0]
    gone = first.clients[0].id

    second = api.update().networks[0]

    assert first.resource_by_id(gone) is not None
    assert second.resource_by_id(gone) is None
