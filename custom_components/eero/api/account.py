"""Eero API."""

from __future__ import annotations

from functools import cached_property

from .network import EeroNetwork
from .resource import EeroResource


class EeroAccount(EeroResource):
    """EeroAccount."""

    def __init__(self, api, data) -> None:
        """Initialize."""
        super().__init__(api=api, network=None, data=data)

    @property
    def email(self) -> str | None:
        """Email."""
        return self.data.get("email", {}).get("value")

    @property
    def log_id(self) -> str | None:
        """Log ID."""
        return self.data.get("log_id")

    @property
    def name(self) -> str | None:
        """Name."""
        return self.data.get("name")

    @property
    def phone(self) -> str | None:
        """Phone."""
        return self.data.get("phone", {}).get("value")

    @property
    def premium_status(self) -> str | None:
        """Premium status."""
        return self.data.get("premium_status")

    # An account object is rebuilt on every poll and its data is never changed
    # in place, so the derived objects are built once per poll. Entities read
    # them several times per state write.
    @cached_property
    def networks(self) -> list[EeroNetwork | None]:
        """Networks."""
        return [
            EeroNetwork(self.api, self, network)
            for network in self.data.get("networks", {}).get("data", [])
        ]

    def network_by_id(self, network_id: str) -> EeroNetwork | None:
        """Return the network with this ID, or None if it is not reported."""
        return self._networks_by_id.get(network_id)

    @cached_property
    def _networks_by_id(self) -> dict[str, EeroNetwork]:
        by_id: dict[str, EeroNetwork] = {}
        for network in self.networks:
            by_id.setdefault(network.id, network)
        return by_id
