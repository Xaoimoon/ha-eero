"""Eero API."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time
import re

from .const import (
    METHOD_POST,
    METHOD_PUT,
    STATE_AMBIENT,
    STATE_DISABLED,
    STATE_SCHEDULE,
)
from .firmware import EeroFirmware
from .resource import EeroResource


# Field names and value formats below come from the eero Android app's data
# models (Gson, no naming policy): `ethernet_status.statuses[]` per port, link
# speeds as PhyRate names ("P10" ... "P25000", in Mbit/s), `derated_reason` as
# 0 none, 1 speed test, 2 user, 3 thermal.
DERATED_REASONS = {0: "none", 1: "speed_test", 2: "user", 3: "thermal"}
UPLINK_TYPES = ("wired", "wired_poe", "wireless", "cellular", "unknown")
_PHY_RATE = re.compile(r"^P(\d+)$")


def phy_rate_mbps(value: str | None) -> int | None:
    """Return the link speed in Mbit/s of a PhyRate name such as "P1000"."""
    if isinstance(value, str) and (match := _PHY_RATE.match(value)):
        return int(match.group(1))
    return None


def parse_date(value: str | None) -> datetime | None:
    """Parse an ISO 8601 date from the API, or return None."""
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


@dataclass(frozen=True)
class EeroEthernetPort:
    """One Ethernet port of an eero, from `ethernet_status.statuses`."""

    number: int
    name: str
    link: bool | None
    speed_mbps: int | None
    original_speed_mbps: int | None
    derated_reason: str | None
    wan: bool | None
    neighbor: str | None

    @classmethod
    def from_status(cls, status: dict) -> EeroEthernetPort | None:
        """Build a port from one status entry; None without a port number."""
        number = status.get("interfaceNumber")
        if not isinstance(number, int):
            return None
        neighbor = status.get("neighbor") or {}
        metadata = neighbor.get("metadata") or {}
        return cls(
            number=number,
            name=str(status.get("port_name") or number),
            link=status.get("hasCarrier"),
            speed_mbps=phy_rate_mbps(status.get("speed")),
            original_speed_mbps=phy_rate_mbps(status.get("original_speed")),
            derated_reason=DERATED_REASONS.get(status.get("derated_reason")),
            wan=status.get("isWanPort"),
            neighbor=metadata.get("location") or metadata.get("name"),
        )


class EeroDevice(EeroResource):
    """EeroDevice."""

    @property
    def connected_wired_clients_count(self) -> int | None:
        """Wired clients connected to this eero."""
        return self.data.get("connected_wired_clients_count")

    @property
    def connected_wireless_clients_count(self) -> int | None:
        """Wireless clients connected to this eero."""
        return self.data.get("connected_wireless_clients_count")

    @property
    def ethernet_ports(self) -> list[EeroEthernetPort]:
        """Ethernet ports, in port number order (none on a Beacon)."""
        statuses = (self.data.get("ethernet_status") or {}).get("statuses") or []
        ports = [
            port
            for status in statuses
            if isinstance(status, dict)
            and (port := EeroEthernetPort.from_status(status)) is not None
        ]
        return sorted(ports, key=lambda port: port.number)

    def ethernet_port(self, number: int) -> EeroEthernetPort | None:
        """Return the port with this number, or None if not reported."""
        for port in self.ethernet_ports:
            if port.number == number:
                return port
        return None

    @property
    def last_reboot(self) -> datetime | None:
        """Last reboot."""
        return parse_date(self.data.get("last_reboot"))

    @property
    def mesh_quality_bars(self) -> int | None:
        """Mesh quality, 0 to 5 bars as in the app."""
        return self.data.get("mesh_quality_bars")

    @property
    def reboots_last_day(self) -> int | None:
        """Reboots in the last 24 hours."""
        return (self.data.get("reboots") or {}).get("last_day")

    @property
    def reboots_last_week(self) -> int | None:
        """Reboots in the last 7 days."""
        return (self.data.get("reboots") or {}).get("last_week")

    @property
    def upstream_eero(self) -> str | None:
        """Name of the eero this one reaches the mesh through wirelessly."""
        return (self.data.get("wireless_upstream_node") or {}).get("name")

    @property
    def upstream_radio(self) -> str | None:
        """Radio of the wireless link to the upstream eero."""
        return (self.data.get("wireless_upstream_node") or {}).get("primary_mesh_radio")

    @property
    def uplink_type(self) -> str | None:
        """How this eero reaches the mesh: wired, wired_poe, wireless, cellular."""
        value = self.data.get("connection_type")
        if not isinstance(value, str):
            return None
        value = value.lower()
        return value if value in UPLINK_TYPES else "unknown"

    @property
    def connected_clients_count(self) -> int | None:
        """Connected clients counts."""
        return self.data.get("connected_clients_count")

    @property
    def connected_clients_names(self) -> list[str]:
        """Connected clients names."""
        return [
            client.name
            for client in self.network.clients
            if client.source_location == self.name
        ]

    @property
    def current_firmware(self) -> EeroFirmware:
        """Current firmware."""
        if not (os_version := self.os_version):
            return EeroFirmware()
        history = {
            firmware.os_version: firmware for firmware in self.network.firmware_history
        }
        return history.get(os_version.split("-")[0], EeroFirmware())

    @property
    def data_usage_day(self) -> tuple[int | None, int | None]:
        """Data usage day."""
        for eero in (
            self.network.data.get("activity", {})
            .get("eeros", {})
            .get("data_usage_day", [])
        ):
            if eero["url"] == self.url:
                return (eero["download"], eero["upload"])
        return (None, None)

    @property
    def data_usage_month(self) -> tuple[int | None, int | None]:
        """Data usage month."""
        for eero in (
            self.network.data.get("activity", {})
            .get("eeros", {})
            .get("data_usage_month", [])
        ):
            if eero["url"] == self.url:
                return (eero["download"], eero["upload"])
        return (None, None)

    @property
    def data_usage_week(self) -> tuple[int | None, int | None]:
        """Data usage week."""
        for eero in (
            self.network.data.get("activity", {})
            .get("eeros", {})
            .get("data_usage_week", [])
        ):
            if eero["url"] == self.url:
                return (eero["download"], eero["upload"])
        return (None, None)

    @property
    def is_gateway(self) -> bool | None:
        """Is gateway."""
        return self.data.get("gateway")

    @property
    def location(self) -> str | None:
        """Location."""
        return self.data.get("location")

    @property
    def mac_address(self) -> str | None:
        """MAC address."""
        return self.data.get("mac_address")

    @property
    def model(self) -> str | None:
        """Model."""
        return self.data.get("model")

    @property
    def model_number(self) -> str | None:
        """Model number."""
        return self.data.get("model_number")

    @property
    def name(self) -> str | None:
        """Name."""
        return self.location

    @property
    def name_long(self) -> str:
        """Name long."""
        return f"{self.name} Eero"

    @property
    def os_version(self) -> str | None:
        """OS version."""
        return self.data.get("os_version")

    def reboot(self) -> None:
        """Reboot."""
        self.api.call(method=METHOD_POST, url=self.url_reboot)

    @property
    def serial(self) -> str | None:
        """Serial."""
        return self.data.get("serial")

    def set_status_light(self, value: bool) -> None:
        """Set status light."""
        if not isinstance(value, bool):
            return
        self.api.call(
            method=METHOD_PUT,
            url=self.url_led,
            json={"led_on": value},
        )

    def set_status_light_brightness(self, value: int) -> None:
        """Set status light brightness."""
        if not isinstance(value, int):
            return None
        if not value:
            return self.set_status_light_off()
        self.api.call(
            method=METHOD_PUT,
            url=self.url_led,
            json={"led_brightness": value},
        )
        return None

    def set_status_light_off(self) -> None:
        """Set status light off."""
        self.set_status_light(value=False)

    def set_status_light_on(self) -> None:
        """Set status light on."""
        self.set_status_light(value=True)

    @property
    def status(self) -> str | None:
        """Status."""
        return self.data.get("status")

    @property
    def status_light_brightness(self) -> int | None:
        """Status light brightness."""
        return self.data.get("led_brightness")

    @property
    def status_light_enabled(self) -> bool | None:
        """Status light enabled."""
        return self.data.get("led_on")

    @property
    def support_expiration_string(self) -> str | None:
        """Support expiration string."""
        return self.data.get("update_status", {}).get("support_expiration_string")

    @property
    def support_expired(self) -> bool | None:
        """Support expired."""
        return self.data.get("update_status", {}).get("support_expired")

    @property
    def target_firmware(self) -> EeroFirmware:
        """Target firmware."""
        if self.support_expired:
            return self.current_firmware
        return self.network.target_firmware

    @property
    def update_available(self) -> bool | None:
        """Update available."""
        return self.data.get("update_available")

    @property
    def url_led(self) -> str | None:
        """URL led."""
        return self.data.get("resources", {}).get("led_action")

    @property
    def url_reboot(self) -> str | None:
        """URL reboot."""
        return self.data.get("resources", {}).get("reboot")


class EeroDeviceBeacon(EeroDevice):
    """EeroDeviceBeacon."""

    def _format_time(self, value: int) -> str | None:
        if not isinstance(value, int):
            return None
        if value < 10:
            return f"0{value}"
        return str(value)

    @property
    def nightlight_brightness_percentage(self) -> int | None:
        """Nightlight brightness percentage."""
        return self.data.get("nightlight", {}).get("brightness_percentage")

    @nightlight_brightness_percentage.setter
    def nightlight_brightness_percentage(self, value: float) -> None:
        if not isinstance(value, (float, int)):
            return
        self.set_nightlight_brightness(value=int(value))

    @property
    def nightlight_enabled(self) -> bool | None:
        """Nightlight enabled."""
        return self.data.get("nightlight", {}).get("enabled")

    @property
    def nightlight_mode(self) -> str:
        """Nightlight mode."""
        if not self.nightlight_enabled:
            return STATE_DISABLED
        if not self.nightlight_schedule_enabled:
            return STATE_AMBIENT
        return STATE_SCHEDULE

    @nightlight_mode.setter
    def nightlight_mode(self, value: str) -> None:
        if value == STATE_DISABLED:
            self.set_nightlight_disabled()
        if value == STATE_AMBIENT:
            self.set_nightlight_ambient()
        if value == STATE_SCHEDULE:
            self.set_nightlight_schedule()

    @property
    def nightlight_mode_options(self) -> list[str]:
        """Nightlight mode options."""
        return [STATE_AMBIENT, STATE_DISABLED, STATE_SCHEDULE]

    @property
    def nightlight_schedule(self) -> tuple[str | None, str | None]:
        """Nightlight schedule."""
        return (
            self.data.get("nightlight", {}).get("schedule", {}).get("on"),
            self.data.get("nightlight", {}).get("schedule", {}).get("off"),
        )

    @property
    def nightlight_schedule_enabled(self) -> bool | None:
        """Nightlight schedule enabled."""
        return self.data.get("nightlight", {}).get("schedule", {}).get("enabled")

    @property
    def nightlight_schedule_off(self) -> time:
        """Nightlight schedule off."""
        return time(
            hour=int(self.nightlight_schedule_off_hour),
            minute=int(self.nightlight_schedule_off_minute),
        )

    @nightlight_schedule_off.setter
    def nightlight_schedule_off(self, value: time) -> None:
        if not isinstance(value, time):
            return
        self.set_nightlight_schedule(
            time_on=self.nightlight_schedule[0],
            time_off=f"{self._format_time(value.hour)}:{self._format_time(value.minute)}",
        )

    @property
    def nightlight_schedule_off_hour(self) -> str:
        """Nightlight schedule off hour."""
        return self.nightlight_schedule[1].split(":")[0]

    @property
    def nightlight_schedule_off_minute(self) -> str:
        """Nightlight schedule off minute."""
        return self.nightlight_schedule[1].split(":")[1]

    @property
    def nightlight_schedule_on(self) -> time:
        """Nightlight schedule on."""
        return time(
            hour=int(self.nightlight_schedule_on_hour),
            minute=int(self.nightlight_schedule_on_minute),
        )

    @nightlight_schedule_on.setter
    def nightlight_schedule_on(self, value: time) -> None:
        if not isinstance(value, time):
            return
        self.set_nightlight_schedule(
            time_on=f"{self._format_time(value.hour)}:{self._format_time(value.minute)}",
            time_off=self.nightlight_schedule[1],
        )

    @property
    def nightlight_schedule_on_hour(self) -> str:
        """Nightlight schedule on hour."""
        return self.nightlight_schedule[0].split(":")[0]

    @property
    def nightlight_schedule_on_minute(self) -> str:
        """Nightlight schedule on minute."""
        return self.nightlight_schedule[0].split(":")[1]

    def _set_nightlight(self, json: dict) -> None:
        if not isinstance(json, dict):
            return
        self.api.call(
            method=METHOD_PUT,
            url=f"/2.2/eeros/{self.id}/nightlight/settings",
            json=json,
        )

    def set_nightlight_ambient(self) -> None:
        """Set nightlight ambient."""
        self._set_nightlight(
            json={
                "enabled": True,
                "schedule": {
                    "enabled": False,
                },
            },
        )

    def set_nightlight_brightness(self, value: int) -> None:
        """Set nightlight brightness."""
        if not isinstance(value, int):
            return
        self._set_nightlight(
            json={
                "enabled": True,
                "brightness_percentage": value,
                "schedule": {
                    "enabled": True,
                    "on": self.nightlight_schedule[0],
                    "off": self.nightlight_schedule[1],
                },
            },
        )

    def set_nightlight_disabled(self) -> None:
        """Set nightlight disabled."""
        self._set_nightlight(
            json={
                "enabled": False,
            },
        )

    def set_nightlight_schedule(self, time_on: str, time_off: str) -> None:
        """Set nightlight schedule."""
        if not isinstance(time_on, str) or not isinstance(time_off, str):
            return
        self._set_nightlight(
            json={
                "enabled": True,
                "schedule": {
                    "enabled": True,
                    "on": time_on,
                    "off": time_off,
                },
            },
        )
