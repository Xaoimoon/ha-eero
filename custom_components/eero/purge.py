"""Removal of client devices that have been away for a while.

The rule is in stale_devices.py; this module gathers the facts from the device
and entity registries and from the last poll, keeps the integration's own
record of when each client was last seen (a Store under .storage), and removes
devices, either after a poll (per-network option) or from the
`eero.remove_stale_devices` action.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import DOMAIN, MODEL_CLIENT_WIRED, MODEL_CLIENT_WIRELESS
from .stale_devices import (
    ClientDevice,
    StaleDevice,
    forget,
    select_stale_devices,
    update_seen,
)

_LOGGER = logging.getLogger(__name__)

STORE_VERSION = 1
# Sightings change every poll; writing them every 10 minutes is plenty.
SAVE_DELAY = 600
# Automatic removal runs after a successful poll, at most this often.
AUTO_INTERVAL = timedelta(hours=1)


def _aware(value: datetime | None) -> datetime | None:
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=UTC)


class StaleDevicePurger:
    """Tracks client sightings and removes long-gone client devices."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        coordinator: DataUpdateCoordinator,
        max_age_days: dict[str, int],
    ) -> None:
        """Initialize."""
        self.hass = hass
        self.config_entry = config_entry
        self.coordinator = coordinator
        self.max_age_days = {k: v for k, v in max_age_days.items() if v}
        self._store = self._make_store(hass, config_entry)
        self._seen: dict[str, datetime] = {}
        # Records that are only the placeholder date of a client met undated.
        self._stamped: set[str] = set()
        self._last_auto_run: datetime | None = None

    @staticmethod
    def _make_store(hass: HomeAssistant, config_entry: ConfigEntry) -> Store[dict]:
        return Store(hass, STORE_VERSION, f"{DOMAIN}.{config_entry.entry_id}.last_seen")

    @classmethod
    async def async_remove_store_for(
        cls, hass: HomeAssistant, config_entry: ConfigEntry
    ) -> None:
        """Delete the record of a config entry that is being removed."""
        await cls._make_store(hass, config_entry).async_remove()

    async def async_setup(self) -> Callable[[], None]:
        """Load the record and follow the coordinator; return the unsubscribe."""
        stored = await self._store.async_load() or {}
        legacy = "seen" not in stored
        seen = stored if legacy else stored.get("seen", {})
        for client_id, value in seen.items():
            if isinstance(value, str) and (parsed := dt_util.parse_datetime(value)):
                self._seen[client_id] = _aware(parsed)
        if legacy:
            # 2.2.0 wrote a flat {client_id: date} mapping that did not tell
            # placeholders from sightings, and it only ran for hours: treat every
            # date as a placeholder. Connected clients become real sightings
            # again on the next poll; only remove_unknown looks at the difference.
            self._stamped = set(self._seen)
        else:
            self._stamped = set(stored.get("stamped", [])) & set(self._seen)
        self._record_sightings()
        return self.coordinator.async_add_listener(self._handle_update)

    async def async_save(self) -> None:
        """Write the record now (the entry is unloading; a reload reads it back)."""
        await self._store.async_save(self._serialize())

    @callback
    def _handle_update(self) -> None:
        if not self.coordinator.last_update_success:
            return
        self._record_sightings()
        if not self.max_age_days:
            return
        now = dt_util.utcnow()
        if self._last_auto_run and now - self._last_auto_run < AUTO_INTERVAL:
            return
        self._last_auto_run = now
        self.hass.async_create_task(
            self.async_purge(self.max_age_days, dry_run=False),
            name=f"{DOMAIN} stale device removal",
        )

    def _api_facts(self) -> tuple[set[str], dict[str, datetime | None]]:
        """Return connected client IDs and last_active dates from the last poll."""
        connected: set[str] = set()
        last_active: dict[str, datetime | None] = {}
        if self.coordinator.data is None:
            return connected, last_active
        for network in self.coordinator.data.networks:
            if network is None:
                continue
            for client in network.clients:
                if client is None or not client.id:
                    continue
                if client.connected:
                    connected.add(client.id)
                try:
                    last_active[client.id] = _aware(client.last_active)
                except ValueError:
                    last_active[client.id] = None
        return connected, last_active

    def _registry_devices(self) -> dict[str, list[ClientDevice]]:
        """Return this entry's devices, grouped by network ID."""
        device_registry = dr.async_get(self.hass)
        entity_registry = er.async_get(self.hass)
        network_ids = {
            device.id: ident
            for device in dr.async_entries_for_config_entry(
                device_registry, self.config_entry.entry_id
            )
            for dom, ident in device.identifiers
            if dom == DOMAIN and device.model not in (MODEL_CLIENT_WIRED, MODEL_CLIENT_WIRELESS)
        }
        grouped: dict[str, list[ClientDevice]] = {}
        for device in dr.async_entries_for_config_entry(
            device_registry, self.config_entry.entry_id
        ):
            entities = er.async_entries_for_device(
                entity_registry, device.id, include_disabled_entities=True
            )
            # Unique IDs start with the network ID; via_device_id is the fallback.
            network_id = next(
                (e.unique_id.split("-")[0] for e in entities if "-" in e.unique_id),
                network_ids.get(device.via_device_id or ""),
            )
            if network_id is None:
                continue
            customized = bool(
                device.name_by_user
                or device.area_id
                or device.labels
                or any(e.name or e.icon or e.labels for e in entities)
            )
            grouped.setdefault(network_id, []).append(
                ClientDevice(
                    device_id=device.id,
                    name=device.name_by_user or device.name,
                    client_ids=frozenset(
                        ident for dom, ident in device.identifiers if dom == DOMAIN
                    ),
                    is_client=device.model in (MODEL_CLIENT_WIRED, MODEL_CLIENT_WIRELESS),
                    customized=customized,
                )
            )
        return grouped

    @callback
    def _record_sightings(self) -> None:
        connected, last_active = self._api_facts()
        known = {
            client_id
            for devices in self._registry_devices().values()
            for device in devices
            if device.is_client
            for client_id in device.client_ids
        }
        if update_seen(
            self._seen, dt_util.utcnow(), connected, known, last_active, self._stamped
        ):
            self._store.async_delay_save(self._serialize, SAVE_DELAY)

    def _serialize(self) -> dict:
        return {
            "seen": {client_id: date.isoformat() for client_id, date in self._seen.items()},
            "stamped": sorted(self._stamped),
        }

    async def async_purge(
        self,
        max_age_days: dict[str, int] | int,
        dry_run: bool,
        remove_unknown: bool = False,
    ) -> list[StaleDevice]:
        """Select (and unless dry_run, remove) the stale client devices.

        max_age_days is either one value for every network or a value per
        network ID; a network without one is left alone.
        """
        connected, last_active = self._api_facts()
        now = dt_util.utcnow()
        selected: list[StaleDevice] = []
        for network_id, devices in self._registry_devices().items():
            days = (
                max_age_days
                if isinstance(max_age_days, int)
                else max_age_days.get(network_id, 0)
            )
            if not days:
                continue
            selected.extend(
                select_stale_devices(
                    devices,
                    now,
                    timedelta(days=days),
                    connected,
                    last_active,
                    self._seen,
                    remove_unknown=remove_unknown,
                    stamped=self._stamped,
                )
            )
        if dry_run or not selected:
            return selected

        device_registry = dr.async_get(self.hass)
        removed_ids: set[str] = set()
        for stale in selected:
            device = device_registry.async_get(stale.device_id)
            if device is None:
                continue
            removed_ids |= {ident for dom, ident in device.identifiers if dom == DOMAIN}
            device_registry.async_update_device(
                stale.device_id, remove_config_entry_id=self.config_entry.entry_id
            )
        forget(self._seen, removed_ids, self._stamped)
        self._store.async_delay_save(self._serialize, SAVE_DELAY)
        _LOGGER.info(
            "Removed %s client device(s) away for too long: %s",
            len(selected),
            ", ".join(sorted(str(stale.name) for stale in selected)),
        )
        return selected
