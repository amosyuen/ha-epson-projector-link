# Espon Projector Link

[![GitHub Release][releases-shield]][releases]
[![GitHub Activity][commits-shield]][commits]
[![License][license-shield]](LICENSE)

[![pre-commit][pre-commit-shield]][pre-commit]
[![Black][black-shield]][black]

[![hacs][hacsbadge]][hacs]
[![Project Maintenance][maintenance-shield]][user_profile]
[![BuyMeCoffee][buymecoffeebadge]][buymecoffee]

[![Community Forum][forum-shield]][forum]

## Functionality

The platform allows you to control an Epson projector from Home Assistant.

This custom component is designed for Epson Home Cinema Projectors which support TCP sockets. It should work with any Epson projector that supports TCP sockets and ESC/VP21 command protocol. However projectors may not support all the features.

### Supported Features

- Get and set state (on, off, warmup, cooldown)
- Get source list
- Get and set source
- Get and set audio mute
- Get and set auto iris mode
- Get and set brightness
- Get and set color mode
- Get filter hours
- Get lamp hours
- Get current error
- Increase or decrease volume
- Play, pause, or stop media
- Next or previous media

All the get features will be exposed as attributes on the `media_player`. Changes are exposed as services. See service documentation at https://github.com/amosyuen/ha-epson-projector-link/blob/main/custom_components/epson_projector_link/services.yaml

### Differences from HA Epson Integration

As of September 2022, the main differences with the built in [Home Assistant Epson Integration](https://www.home-assistant.io/integrations/epson/) are:

#### PROS

- Supports push for power state changes
- Support "warmup" and "cooldown" state for projectors
- Queues requests rather than failing if there is an in-flight request
- Supports lens memory
- Supports picture memory
- Supports auto iris mode
- Supports brightness
- Supports power consumption mode
- Supports source list retrieved from projector instead of static list
- Supports stop media

#### CONS

- Only supports TCP sockets. The HA Epson integration uses HTTP. Developer has mentioned that not all projectors support TCP.

## Installation

### HACS

1. Install [HACS](https://hacs.xyz/)
2. Go to HACS "Integrations >" section
3. In the lower right click "+ Explore & Download repositories"
4. Search for "Epson Projector Link" and add it
   - HA Restart is not needed since it is configured in UI config flow
5. In the Home Assistant (HA) UI go to "Configuration"
6. Click "Integrations"
7. Click "+ Add Integration"
8. Search for "Epson Projector Link"

### Manual

1. Using the tool of choice open the directory (folder) for your [HA configuration](https://www.home-assistant.io/docs/configuration/) (where you find `configuration.yaml`).
2. If you do not have a `custom_components` directory (folder) there, you need to create it.
3. In the `custom_components` directory (folder) create a new folder called `epson_projector_link`.
4. Download _all_ the files from the `custom_components/epson_projector_link/` directory (folder) in this repository.
5. Place the files you downloaded in the new directory (folder) you created.
6. Restart Home Assistant
7. In the Home Assistant (HA) UI go to "Configuration"
8. Click "Integrations"
9. Click "+ Add Integration"
10. Search for "Epson Projector Link"

{% endif %}

## Configuration

Config is done in the HA integrations UI.

Make sure the projector is on if you have not setup your projector to keep network on or are choosing additional properties to poll. Additional properties can only be polled when the projector is on.

### Push State

If you want to get push notifications for power state, you must set projector "Standby Mode" to "Standby Mode: Communication On" or some similar state that keeps the network on when off.

Only power state, warnings, and alerts are pushed. All other properties are polled.

### Setup

## Tested Devices

- Epson Home Cinema 5050UB

## Contributions are welcome!

If you want to contribute to this please read the [Contribution guidelines](https://github.com/amosyuen/ha-epson-projector-link/blob/master/CONTRIBUTING.md)

## Credits

Referred to @pszafer's implementation of epson component https://github.com/pszafer/epson_projector

This project was generated from [@oncleben31](https://github.com/oncleben31)'s [Home Assistant Custom Component Cookiecutter](https://github.com/oncleben31/cookiecutter-homeassistant-custom-component) template.

Code template was mainly taken from [@Ludeeus](https://github.com/ludeeus)'s [integration_blueprint][integration_blueprint] template

---

[integration_blueprint]: https://github.com/custom-components/integration_blueprint
[black]: https://github.com/psf/black
[black-shield]: https://img.shields.io/badge/code%20style-black-000000.svg?style=for-the-badge
[buymecoffee]: https://paypal.me/amosyuen
[buymecoffeebadge]: https://img.shields.io/badge/buy%20me%20a%20coffee-donate-yellow.svg?style=for-the-badge
[commits-shield]: https://img.shields.io/github/commit-activity/y/amosyuen/ha-epson-projector-link.svg?style=for-the-badge
[commits]: https://github.com/amosyuen/ha-epson-projector-link/commits/main
[hacs]: https://hacs.xyz
[hacsbadge]: https://img.shields.io/badge/HACS-Default-orange.svg?style=for-the-badge
[forum-shield]: https://img.shields.io/badge/community-forum-brightgreen.svg?style=for-the-badge
[forum]: https://community.home-assistant.io/
[license-shield]: https://img.shields.io/github/license/amosyuen/ha-epson-projector-link.svg?style=for-the-badge
[maintenance-shield]: https://img.shields.io/badge/maintainer-%40amosyuen-blue.svg?style=for-the-badge
[pre-commit]: https://github.com/pre-commit/pre-commit
[pre-commit-shield]: https://img.shields.io/badge/pre--commit-enabled-brightgreen?style=for-the-badge
[releases-shield]: https://img.shields.io/github/release/amosyuen/ha-epson-projector-link.svg?style=for-the-badge
[releases]: https://github.com/amosyuen/ha-epson-projector-link/releases
[user_profile]: https://github.com/amosyuen
