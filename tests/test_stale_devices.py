"""Which client devices are removed automatically after being away too long."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import importlib.util
from pathlib import Path
import sys

MODULE = Path(__file__).resolve().parents[1] / "custom_components" / "eero" / "stale_devices.py"
spec = importlib.util.spec_from_file_location("eero_stale_devices", MODULE)
sd = importlib.util.module_from_spec(spec)
# dataclasses look their module up in sys.modules.
sys.modules[spec.name] = sd
spec.loader.exec_module(sd)

NOW = datetime(2026, 10, 9, 12, 0, tzinfo=UTC)
WEEK = timedelta(days=7)


def client(device_id, *client_ids, customized=False, is_client=True):
    return sd.ClientDevice(
        device_id=device_id,
        name=device_id,
        client_ids=frozenset(client_ids or (device_id,)),
        is_client=is_client,
        customized=customized,
    )


def ids(stale):
    return [d.device_id for d in stale]


def test_client_away_longer_than_max_age_goes():
    stale = sd.select_stale_devices(
        [client("car")], NOW, WEEK, set(), {"car": NOW - timedelta(days=8)}, {}
    )
    assert ids(stale) == ["car"]
    assert stale[0].last_seen == NOW - timedelta(days=8)


def test_client_seen_recently_stays():
    assert not sd.select_stale_devices(
        [client("phone")], NOW, WEEK, set(), {"phone": NOW - timedelta(days=6)}, {}
    )


def test_connected_client_stays_whatever_its_dates():
    assert not sd.select_stale_devices(
        [client("tv")], NOW, WEEK, {"tv"}, {"tv": NOW - timedelta(days=90)}, {}
    )


def test_customized_device_is_never_removed():
    assert not sd.select_stale_devices(
        [client("nas", customized=True)], NOW, WEEK, set(), {"nas": NOW - timedelta(days=90)}, {}
    )


def test_network_eeros_and_profiles_are_never_removed():
    assert not sd.select_stale_devices(
        [client("eero-1", is_client=False)], NOW, WEEK, set(), {"eero-1": NOW - timedelta(days=90)}, {}
    )


def test_latest_of_api_and_own_sighting_wins():
    # The API's last_active is old, but the integration saw it connected 2 days ago.
    assert not sd.select_stale_devices(
        [client("laptop")],
        NOW,
        WEEK,
        set(),
        {"laptop": NOW - timedelta(days=30)},
        {"laptop": NOW - timedelta(days=2)},
    )


def test_unknown_date_is_kept_unless_asked():
    assert not sd.select_stale_devices([client("ghost")], NOW, WEEK, set(), {}, {})
    stale = sd.select_stale_devices([client("ghost")], NOW, WEEK, set(), {}, {}, remove_unknown=True)
    assert ids(stale) == ["ghost"]
    assert stale[0].last_seen is None


def test_result_is_ordered_unknown_then_oldest_first():
    stale = sd.select_stale_devices(
        [client("b"), client("a"), client("ghost")],
        NOW,
        WEEK,
        set(),
        {"a": NOW - timedelta(days=40), "b": NOW - timedelta(days=10)},
        {},
        remove_unknown=True,
    )
    assert ids(stale) == ["ghost", "a", "b"]


def test_update_seen_stamps_connected_clients_now():
    seen = {"phone": NOW - timedelta(days=3)}
    assert sd.update_seen(seen, NOW, {"phone"}, set(), {})
    assert seen["phone"] == NOW


def test_update_seen_starts_counting_for_undated_known_clients():
    seen = {}
    sd.update_seen(seen, NOW, set(), {"old-device"}, {})
    assert seen == {"old-device": NOW}
    # ...and a later run does not move the date forward.
    assert not sd.update_seen(seen, NOW + timedelta(days=1), set(), {"old-device"}, {})
    assert seen == {"old-device": NOW}


def test_update_seen_leaves_clients_the_api_dates():
    # Stamping it now would postpone a removal the API date already justifies.
    seen = {}
    sd.update_seen(seen, NOW, set(), {"car"}, {"car": NOW - timedelta(days=20)})
    assert seen == {}
    assert ids(sd.select_stale_devices([client("car")], NOW, WEEK, set(), {"car": NOW - timedelta(days=20)}, seen)) == ["car"]


def test_forget_drops_records():
    seen = {"a": NOW, "b": NOW}
    sd.forget(seen, {"a", "missing"})
    assert seen == {"b": NOW}


def test_placeholder_keeps_device_in_automatic_mode():
    # Met undated on the first run: stamped now, kept for max_age.
    seen, stamped = {}, set()
    sd.update_seen(seen, NOW - timedelta(hours=2), set(), {"car-old-mac"}, {}, stamped)
    assert stamped == {"car-old-mac"}
    assert not sd.select_stale_devices([client("car-old-mac")], NOW, WEEK, set(), {}, seen, stamped=stamped)


def test_remove_unknown_sees_through_placeholders():
    # The backlog case: devices the API no longer reports, stamped on the first run.
    seen, stamped = {}, set()
    sd.update_seen(seen, NOW - timedelta(hours=2), set(), {"car-old-mac", "laptop"}, {}, stamped)
    sd.update_seen(seen, NOW - timedelta(hours=1), {"laptop"}, set(), {}, stamped)  # laptop really seen
    stale = sd.select_stale_devices(
        [client("car-old-mac"), client("laptop")], NOW, WEEK, set(), {}, seen,
        remove_unknown=True, stamped=stamped,
    )
    assert ids(stale) == ["car-old-mac"]
    assert stale[0].last_seen is None


def test_remove_unknown_keeps_devices_the_api_dates_recently():
    seen, stamped = {}, set()
    stale = sd.select_stale_devices(
        [client("phone")], NOW, WEEK, set(), {"phone": NOW - timedelta(days=1)}, seen,
        remove_unknown=True, stamped=stamped,
    )
    assert not stale


def test_connection_turns_a_placeholder_into_a_sighting():
    seen, stamped = {}, set()
    sd.update_seen(seen, NOW, set(), {"tv"}, {}, stamped)
    sd.update_seen(seen, NOW, {"tv"}, set(), {}, stamped)
    assert stamped == set()


def test_forget_drops_placeholders_too():
    seen, stamped = {"a": NOW}, {"a"}
    sd.forget(seen, {"a"}, stamped)
    assert seen == {} and stamped == set()
