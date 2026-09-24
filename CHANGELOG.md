# Changelog

All notable changes to this project are documented here.

## [Unreleased]

### Added

- Optional SMTP daily summary reports with STARTTLS enforcement, local state,
  duplicate-send protection, and an explicit `--email-test` command.
- Documented the Raspberry Pi 5 (4 GB) edge deployment with Tailscale VPN,
  open-source xrdp remote desktop, and a private Flask service accessed by
  multiple authorized devices.

## [0.1.0] - 2026-09-24

### Added

- Secure environment-based Modbus/AWS configuration.
- Modbus TCP holding-register scanning.
- AWS IoT MQTT/TLS publishing with reconnect handling.
- Offline configuration validation mode.
- Safe demo payload mode with no network access.
- One-sample commissioning mode.
- Unit tests, CI baseline, security notes, and pre-commit protection.

### Security

- No AWS credentials, private keys, certificates, or live endpoints are stored
  in the Git repository.
