"""Which client devices have been away long enough to be removed automatically.

Kept free of Home Assistant imports so it can be tested on its own (the fork's
tests run without Home Assistant installed); the caller collects the registry
and API facts and passes them in.

Why this exists: a client gets a device and its entities when the integration
loads, and nothing ever removes it. A device that changes its MAC address on
every connection (a car head unit was the case that prompted this) leaves a new
device behind each time, hundreds within days.

The rule: a wired or wireless client may be removed when it is not connected now
and was last seen more than `max_age` ago. "Last seen" is the latest of the
`last_active` date reported by the API and the last time the integration itself
saw the client connected. A device the user has customized (renamed, given an
area or a label, or an entity with its own name, icon or label) is never
removed: someone cared about it. The network, the eeros, backup networks and
profiles are never removed either.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass(frozen=True)
class ClientDevice:
    """What the rule needs to know about one device of the config entry."""

    device_id: str
    name: str | None
    client_ids: frozenset[str]
    is_client: bool
    customized: bool


@dataclass(frozen=True)
class StaleDevice:
    """A device selected for removal, and why."""

    device_id: str
    name: str | None
    last_seen: datetime | None


def last_seen(
    client_ids: Iterable[str],
    api_last_active: Mapping[str, datetime | None],
    seen: Mapping[str, datetime],
) -> datetime | None:
    """Return the latest known sighting of any of these client IDs, or None."""
    dates = [
        date
        for client_id in client_ids
        for date in (api_last_active.get(client_id), seen.get(client_id))
        if date is not None
    ]
    return max(dates) if dates else None


def select_stale_devices(
    devices: Iterable[ClientDevice],
    now: datetime,
    max_age: timedelta,
    connected_ids: Iterable[str],
    api_last_active: Mapping[str, datetime | None],
    seen: Mapping[str, datetime],
    remove_unknown: bool = False,
    stamped: Iterable[str] = (),
) -> list[StaleDevice]:
    """Return the devices to remove, oldest first.

    `stamped` lists the records that are only the placeholder date set by
    `update_seen` for a client met without any date, not a real sighting. They
    keep such a device for `max_age`, unless `remove_unknown` is set: then a
    device with no API date and nothing but placeholders counts as undated and
    is selected whatever its age. That is how a backlog of dead devices (all
    stamped the day this feature first ran) is cleared without waiting.
    """
    connected = set(connected_ids)
    placeholders = set(stamped)
    real_seen = {k: v for k, v in seen.items() if k not in placeholders}
    stale: list[StaleDevice] = []
    for device in devices:
        if not device.is_client or device.customized or not device.client_ids:
            continue
        if not device.client_ids.isdisjoint(connected):
            continue
        if remove_unknown and last_seen(device.client_ids, api_last_active, real_seen) is None:
            stale.append(StaleDevice(device.device_id, device.name, None))
            continue
        seen_at = last_seen(device.client_ids, api_last_active, seen)
        if seen_at is not None and now - seen_at > max_age:
            stale.append(StaleDevice(device.device_id, device.name, seen_at))
    return sorted(stale, key=lambda d: (d.last_seen is not None, d.last_seen or now))


def update_seen(
    seen: dict[str, datetime],
    now: datetime,
    connected_ids: Iterable[str],
    known_ids: Iterable[str],
    api_last_active: Mapping[str, datetime | None],
    stamped: set[str] | None = None,
) -> bool:
    """Record sightings; return True if anything changed.

    Connected clients are seen now (a real sighting: dropped from `stamped`).
    A known client with no record and no `last_active` from the API (a device
    already in the registry the first time this runs, that the API no longer
    reports) gets a placeholder date, now, added to `stamped`: it is not removed
    automatically before it has really been away for `max_age`. One the API
    dates is left alone: its own date is the better answer.
    """
    if stamped is None:
        stamped = set()
    changed = False
    for client_id in connected_ids:
        seen[client_id] = now
        stamped.discard(client_id)
        changed = True
    for client_id in known_ids:
        if client_id not in seen and api_last_active.get(client_id) is None:
            seen[client_id] = now
            stamped.add(client_id)
            changed = True
    return changed


def forget(
    seen: dict[str, datetime], client_ids: Iterable[str], stamped: set[str] | None = None
) -> None:
    """Drop the records of removed clients."""
    for client_id in client_ids:
        seen.pop(client_id, None)
        if stamped is not None:
            stamped.discard(client_id)
