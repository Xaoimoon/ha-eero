"""Mesh health and Ethernet port data of an eero.

The eero below follows the shape of a real network response (2026-10-16,
three eero Pro 6, anonymized MAC addresses and names): `neighbor` is null and
the device at the other end of a port is in `lldpInfo`; `reboots` is absent
from the eeros embedded in the network and comes from the eero's own
resource (see test_eero_reboots_are_fetched_hourly).
"""

from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path

from helpers import eero_api

EeroDevice = eero_api.eero.EeroDevice

EERO = {
    "url": "/2.2/eeros/111",
    "connection_type": "WIRELESS",
    "mesh_quality_bars": 4,
    "last_reboot": "2026-10-01T03:12:45.000Z",
    "reboots": {"last_day": 0, "last_week": 2},
    "connected_wired_clients_count": 1,
    "connected_wireless_clients_count": 7,
    "wireless_upstream_node": {
        "name": "Salon",
        "primary_mesh_radio": "5GHz",
        "is_proxied_node": False,
        "node_or_proxied_node_id": 222,
    },
    "ethernet_status": {
        "segmentId": "seg",
        "wiredInternet": False,
        "statuses": [
            {
                "interfaceNumber": 1,
                "port_name": "2",
                "hasCarrier": True,
                "speed": "P100",
                "original_speed": "P1000",
                "derated_reason": 1,
                "isWanPort": False,
                "neighbor": None,
                "lldpInfo": [{
                    "chassisId": "00:11:22:33:44:50",
                    "chassisIdType": "MacAddress",
                    "macAddress": "00:11:22:33:44:55",
                    "portId": "5",
                    "portIdType": "LocallyAssigned",
                    "systemName": "Zyxel",
                }],
            },
            {
                "interfaceNumber": 0,
                "port_name": "1",
                "hasCarrier": False,
                "speed": None,
                "isWanPort": True,
                "neighbor": None,
                "lldpInfo": [],
            },
            {"port_name": "no number, ignored"},
        ],
    },
}

# Network seen by an eero (Garage) whose port 2 is cabled to another eero
# (Chambre) port 1: LLDP names it by MAC address and system name "eero" only.
NETWORK = {"eeros": {"data": [
    {"url": "/2.2/eeros/1", "location": "Chambre", "mac_address": "aa:bb:cc:00:00:00",
     "ethernet_addresses": ["aa:bb:cc:00:00:00", "aa:bb:cc:00:00:01"]},
    {"url": "/2.2/eeros/2", "location": "Garage", "mac_address": "aa:bb:cc:00:01:00",
     "ethernet_addresses": ["aa:bb:cc:00:01:00", "aa:bb:cc:00:01:01"]},
]}}


class FakeNetwork:
    def __init__(self, data):
        self.data = data


def eero(data=None, network=None):
    return EeroDevice(api=None, network=network, data=data if data is not None else EERO)


def test_mesh_health():
    device = eero()
    assert device.mesh_quality_bars == 4
    assert device.uplink_type == "wireless"
    assert device.upstream_eero == "Salon"
    assert device.upstream_radio == "5GHz"
    assert device.reboots_last_week == 2
    assert device.reboots_last_day == 0
    assert device.last_reboot == datetime(2026, 10, 1, 3, 12, 45, tzinfo=UTC)
    assert device.connected_wired_clients_count == 1
    assert device.connected_wireless_clients_count == 7


def test_ethernet_ports_are_parsed_and_ordered():
    ports = eero().ethernet_ports
    assert [port.number for port in ports] == [0, 1]
    wan, lan = ports
    assert (wan.name, wan.link, wan.speed_mbps, wan.wan) == ("1", False, None, True)
    assert lan.name == "2"
    assert lan.speed_mbps == 100
    assert lan.original_speed_mbps == 1000
    assert lan.derated_reason == "speed_test"
    assert (lan.neighbor, lan.neighbor_port) == ("Zyxel", "5")
    assert (wan.neighbor, wan.neighbor_port) == (None, None)
    assert eero().ethernet_port(1) == lan
    assert eero().ethernet_port(9) is None


def test_neighbor_eero_is_named_by_its_mac_address():
    garage = eero({"ethernet_status": {"statuses": [{
        "interfaceNumber": 1, "port_name": "2", "hasCarrier": True, "speed": "P1000",
        "neighbor": None,
        "lldpInfo": [{"chassisId": "AA:BB:CC:00:00:00", "macAddress": "aa:bb:cc:00:00:00",
                      "portId": "1", "systemName": "eero"}],
    }]}}, network=FakeNetwork(NETWORK))
    port = garage.ethernet_port(1)
    assert (port.neighbor, port.neighbor_port) == ("Chambre", "1")


def test_neighbor_metadata_is_still_read_first():
    # Shape of the app's data model, never seen filled in a real response.
    device = eero({"ethernet_status": {"statuses": [{
        "interfaceNumber": 1,
        "neighbor": {"type": "THIRD_PARTY", "metadata": {"name": "Switch bureau", "port": 3}},
        "lldpInfo": [{"systemName": "Zyxel", "portId": "5"}],
    }]}})
    port = device.ethernet_port(1)
    assert (port.neighbor, port.neighbor_port) == ("Switch bureau", "3")


def test_eero_reboots_are_fetched_hourly():
    calls = []

    class Api(eero_api.EeroAPI):
        def call(self, method, url, allow_refresh=True, **kwargs):
            calls.append(url)
            if url == "/2.2/eeros/2":
                raise eero_api.EeroException(code=500, message="boom")
            return {"reboots": {"last_day": 0, "last_week": 3}}

    def network():
        return {"eeros": {"data": [{"url": "/2.2/eeros/1"}, {"url": "/2.2/eeros/2"}]}}

    api = Api()
    first = network()
    api.add_eero_reboots(first, now=1000.0)
    assert first["eeros"]["data"][0]["reboots"] == {"last_day": 0, "last_week": 3}
    assert "reboots" not in first["eeros"]["data"][1]  # error: no value, poll goes on
    assert calls == ["/2.2/eeros/1", "/2.2/eeros/2"]

    # Next poll within the hour: cached value, and no call at all, not even
    # for the eero that failed (a lasting error must not cost a call a poll).
    second = network()
    api.add_eero_reboots(second, now=1090.0)
    assert second["eeros"]["data"][0]["reboots"]["last_week"] == 3
    assert calls == ["/2.2/eeros/1", "/2.2/eeros/2"]

    # An hour later both are fetched again.
    api.add_eero_reboots(network(), now=1000.0 + eero_api.REBOOTS_REFRESH_INTERVAL)
    assert calls.count("/2.2/eeros/1") == 2
    assert calls.count("/2.2/eeros/2") == 2


def test_expired_session_while_fetching_reboots_is_raised():
    class Api(eero_api.EeroAPI):
        def call(self, method, url, allow_refresh=True, **kwargs):
            raise eero_api.EeroSessionExpired(message="expired")

    try:
        Api().add_eero_reboots({"eeros": {"data": [{"url": "/2.2/eeros/1"}]}}, now=0.0)
    except eero_api.EeroSessionExpired:
        pass
    else:
        raise AssertionError("EeroSessionExpired was swallowed")


def test_unplugged_port_has_no_speed():
    # Seen live 2026-10-16: an unplugged port still reports "P10".
    device = eero({"ethernet_status": {"statuses": [
        {"interfaceNumber": 1, "hasCarrier": False, "speed": "P10"},
        {"interfaceNumber": 2, "speed": "P1000"},
    ]}})
    unplugged, unknown_link = device.ethernet_ports
    assert (unplugged.link, unplugged.speed_mbps) == (False, None)
    assert (unknown_link.link, unknown_link.speed_mbps) == (None, 1000)


def test_missing_fields_give_none_not_errors():
    device = eero({"url": "/2.2/eeros/333"})
    assert device.mesh_quality_bars is None
    assert device.uplink_type is None
    assert device.upstream_eero is None
    assert device.reboots_last_week is None
    assert device.last_reboot is None
    assert device.ethernet_ports == []


def test_unexpected_values_are_tolerated():
    device = eero({"connection_type": "SATELLITE", "last_reboot": "not a date",
                   "ethernet_status": {"statuses": [{"interfaceNumber": 2, "speed": "fast"}]}})
    assert device.uplink_type == "unknown"
    assert device.last_reboot is None
    assert device.ethernet_ports[0].speed_mbps is None
    assert device.ethernet_ports[0].name == "2"


def test_every_entity_has_a_french_name_where_it_has_an_english_one():
    component = Path(__file__).resolve().parents[1] / "custom_components" / "eero"
    en = json.loads((component / "translations" / "en.json").read_text(encoding="utf-8"))["entity"]
    fr = json.loads((component / "translations" / "fr.json").read_text(encoding="utf-8"))["entity"]
    for platform, entities in en.items():
        for key, entry in entities.items():
            if "name" in entry:
                assert fr[platform][key].get("name"), f"{platform}.{key}"
    assert fr["sensor"]["ethernet_port"]["name"] == "Port {port}"
