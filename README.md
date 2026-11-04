# eero for Home Assistant

[![HACS](https://img.shields.io/badge/HACS-Custom-orange.svg?style=for-the-badge)](https://hacs.xyz/docs/faq/custom_repositories)
[![Release](https://img.shields.io/github/v/release/Xaoimoon/ha-eero?style=for-the-badge)](https://github.com/Xaoimoon/ha-eero/releases)
[![Active installations](https://img.shields.io/badge/dynamic/json?style=for-the-badge&color=41BDF5&label=Active%20installations&cacheSeconds=15600&url=https://analytics.home-assistant.io/custom_integrations.json&query=$.eero.total)](https://analytics.home-assistant.io/)
[![License](https://img.shields.io/badge/license-MIT-green.svg?style=for-the-badge)](https://github.com/Xaoimoon/ha-eero/blob/main/LICENSE)

[![Maintained](https://img.shields.io/badge/maintained-yes-green.svg?style=for-the-badge)](https://github.com/Xaoimoon/ha-eero/commits/main)
[![Activity](https://img.shields.io/github/commit-activity/y/Xaoimoon/ha-eero?style=for-the-badge)](https://github.com/Xaoimoon/ha-eero/commits/main)
[![Discussions](https://img.shields.io/github/discussions/Xaoimoon/ha-eero?style=for-the-badge&logo=github&color=7289DA)](https://github.com/Xaoimoon/ha-eero/discussions)
[![Issues](https://img.shields.io/github/issues/Xaoimoon/ha-eero?style=for-the-badge&logo=github&color=E05D44)](https://github.com/Xaoimoon/ha-eero/issues)
[![Stars](https://img.shields.io/github/stars/Xaoimoon/ha-eero?style=for-the-badge&logo=github&color=DFB317)](https://github.com/Xaoimoon/ha-eero/stargazers)

Unofficial Home Assistant integration for eero mesh Wi-Fi networks. It uses the eero account (cloud API, like the mobile app) to show and control the network, the eero nodes, the profiles and the connected devices.

It is the maintained continuation of [schmittx/home-assistant-eero](https://github.com/schmittx/home-assistant-eero), which has had no new release since 1.8.1 (September 2025), picked up from the audited fork [lpleva/home-assistant-eero](https://github.com/lpleva/home-assistant-eero) 1.9.3. The domain is still `eero`: an existing installation upgrades without any reconfiguration (see [Coming from schmittx's integration](#coming-from-schmittxs-integration)).

## Features

- Several networks per account.
- Network settings: guest network, eero Plus and eero Labs features.
- Pause Internet access per profile or per device, profile content filters, blocked applications (eero Plus).
- Presence of devices and profiles, with the band, channel and channel width of Wi-Fi devices.
- Signal, speed, data usage and activity sensors (eero Plus).
- Mesh health, for each eero: mesh quality (0 to 5 bars), backhaul (wired, PoE, Wi-Fi) and upstream eero, last reboot, connected wired and Wi-Fi devices.
- eero Ethernet ports: negotiated speed of each port (unknown when the cable is unplugged), with the link, the original speed and the reason for a downgrade, the WAN port, the connected equipment and its port as attributes (advertised over LLDP: another eero is named after its location).
- Buttons for the actions that restart the network, eero firmware updates.
- eero Beacon nightlight (mode, schedule, brightness).
- Backup networks (eero Plus).

## Installation

### Via HACS (recommended)

[![Open the repository in HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=Xaoimoon&repository=ha-eero&category=integration)

Click the button above, or add the repository manually:

1. In HACS, open the **⋮ > Custom repositories** menu and add `https://github.com/Xaoimoon/ha-eero` with the **Integration** type.
2. Search for "eero" in HACS, then **Download**.
3. Restart Home Assistant.

HACS will then offer new versions automatically.

### Manual

1. Find the Home Assistant configuration folder (the one that contains `configuration.yaml`).
2. Create a `custom_components` folder in it if it does not exist yet.
3. Copy the `custom_components/eero` folder of this repository into it, to get `<config>/custom_components/eero/`.
4. Restart Home Assistant.

## Configuration

[![Add the integration](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=eero)

Click the button above, or:

1. **Settings > Devices & services > Add integration**, search for "eero".
2. Enter the email address or phone number of the eero account, then the verification code you receive.
3. Choose the networks, then the resources to track (eero nodes, profiles, wired and Wi-Fi devices, backup networks) and the activity measurements.

These choices can be changed later in the integration **options**, along with the polling interval (5 minutes by default, 1 minute minimum) and the timeout.

Home Assistant Core 2026.8 or later is required.

## Good to know

- **Language**: the integration is translated into English and French: configuration, options, actions, entity names, states and attributes. Existing entity IDs do not change. For new entities, Home Assistant (since 2026.9) builds the ID from the displayed name and the device's area, for example `sensor.living_room_living_room_mesh_quality`.
- **Diagnostic sensors**: mesh health and Ethernet ports are filed under diagnostics. Ports are created when the integration loads, based on those each eero reports.
- **Amazon account**: signing in with an Amazon account is not supported. Create a regular eero account and add it as an administrator of the network ([how to](https://github.com/schmittx/home-assistant-eero/issues/77#issuecomment-1960875926)).
- **Expired session**: if eero invalidates the session, Home Assistant offers to re-authenticate with a new verification code, without removing the integration.
- **Devices that disappear**: a device that eero no longer reports becomes "unavailable". It can be deleted from its page in Home Assistant, and it is recreated if it comes back. The network, the eero nodes and the profiles cannot be deleted this way.
- **Automatic cleanup**: the "Remove client devices away for" option (miscellaneous options, set per network, 0 = never) deletes wired and Wi-Fi devices that have not connected for that many days, along with their entities. This is useful when a device changes its MAC address on every connection (some cars, phones using a random address) and leaves a new device behind each time. A device you renamed, assigned to an area or labelled, or with an entity carrying your own name, icon or label, is never deleted. The date used is the most recent of the last activity reported by eero and the last connection seen by the integration; a device that eero no longer reports is counted from the first time the integration finds it without a date.
- **`eero.remove_stale_devices` action**: the same cleanup on demand. By default it is a dry run (`dry_run: true`) that returns the list of affected devices; run it from **Developer tools > Actions** with "Return response":

  ```yaml
  action: eero.remove_stale_devices
  data:
    days: 7
    dry_run: true          # false to actually delete
    remove_unknown: false  # true: include devices with no known date
  ```

  `remove_unknown: true` is meant for the first cleanup: regardless of the delay, it includes the devices that eero no longer reports and that the integration has never seen connected (the backlog accumulated before the feature was enabled). Always run it as a dry run first.
- **New devices**: only the devices present when the integration loads get entities. A device that appears later is only added at the next reload.

## Coming from schmittx's integration

The integration keeps the `eero` domain, the entities' unique IDs and the configuration entry format. Devices, entities, and custom names and icons are preserved.

1. In HACS, open the current eero integration, **⋮ > Remove** menu. This removes its files, not the configuration entry.
2. Add this repository and download it (see [Installation](#via-hacs-recommended)), **before** restarting.
3. Restart Home Assistant.

Visible changes compared to 1.8.1:

- the two QR code image entities (network and guest network) are gone and can be deleted;
- entity names follow the Home Assistant convention (device name + measurement name): displayed names may change, but not the IDs of entities already created;
- the `secondary_wan_deny_access` switch becomes `secondary_wan_allow_access`, with the opposite meaning;
- the polling interval is now at least 1 minute, and 5 minutes by default;
- on an API error, entities become "unavailable" instead of keeping their last value.

The details are in [CHANGELOG.md](https://github.com/Xaoimoon/ha-eero/blob/main/CHANGELOG.md).

## Disclaimer

This project is not affiliated with eero or Amazon. The integration relies on the undocumented cloud API of the eero app, which may change without notice.

## Credits

- [@schmittx](https://github.com/schmittx/home-assistant-eero): the original integration;
- [@lpleva](https://github.com/lpleva/home-assistant-eero): the audit and fixes of 1.9;
- [@343max](https://github.com/343max/eero-client): the API authentication;
- [@jrlucier](https://github.com/jrlucier/eero_tracker): the original idea.

## License

MIT — see [LICENSE](https://github.com/Xaoimoon/ha-eero/blob/main/LICENSE).
