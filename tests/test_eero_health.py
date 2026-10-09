"""Mesh health and Ethernet port data of an eero.

The eero below is built from the field names and value formats of the eero
Android app's data models (no captured response yet): verify against a real
response before relying on an exact value.
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
                "neighbor": {"type": "THIRD_PARTY", "metadata": {"name": "Switch bureau", "port": 3}},
            },
            {
                "interfaceNumber": 0,
                "port_name": "1",
                "hasCarrier": False,
                "speed": None,
                "isWanPort": True,
            },
            {"port_name": "no number, ignored"},
        ],
    },
}


def eero(data=None):
    return EeroDevice(api=None, network=None, data=data if data is not None else EERO)


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
    assert lan.neighbor == "Switch bureau"
    assert eero().ethernet_port(1) == lan
    assert eero().ethernet_port(9) is None


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
