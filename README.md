# Modbus AWS Logger

**Industrial telemetry from PLC to cloud, without hardcoded secrets.**

[![Status](https://img.shields.io/badge/status-private%20preview-6c5ce7)](https://github.com/mosesnetto/modbus-aws-logger)
[![Python](https://img.shields.io/badge/python-3.11%2B-3776ab)](https://www.python.org/)
[![AWS IoT](https://img.shields.io/badge/cloud-AWS%20IoT-232f3f)](https://aws.amazon.com/iot-core/)
[![Security](https://img.shields.io/badge/secrets-outside%20Git-2ea44f)](SECURITY.md)

Modbus AWS Logger is a focused telemetry bridge for reading Modbus TCP data and
publishing structured JSON to AWS IoT Core through MQTT/TLS. It is designed for
prototypes, pilot deployments, and the early foundation of a future startup
platform.

> **Private preview:** This repository is intentionally private while the
> deployment model, security controls, and product identity are being validated.

![Modbus AWS Logger architecture](assets/brand.svg)

## Why this exists

Industrial teams often begin with a small Python script that:

- hardcodes PLC addresses, certificates, and cloud endpoints;
- reconnects badly after a network interruption;
- makes every measurement a one-off copy/paste operation;
- has no repeatable validation or deployment story.

This project replaces that fragile script with a small, testable foundation:
**configuration → Modbus read → JSON payload → AWS IoT MQTT publish**.

## What is implemented

- Modbus TCP holding-register scanning with a persistent connection.
- Configurable register count, PLC unit, endpoint, and publish interval.
- AWS IoT MQTT/TLS publishing with QoS 1.
- Optional SMTP daily summary reports with duplicate-send protection.
- Documented Tailscale private connectivity for PLC/site access and an optional
  companion Flask service.
- Reconnect handling for both PLC and MQTT connections.
- UTC timestamps and machine identity in every payload.
- Environment-based configuration with no credentials in source control.
- Offline `--check-config` validation mode.
- Safe `--demo` mode that requires no PLC, AWS account, or certificates.
- One-sample `--once` mode for controlled commissioning.
- Local virtual environment and reproducible pinned dependencies.
- Pre-commit protection against common secret-file types.
- GitHub Actions checks for compilation, tests, and dependency consistency.

## Architecture

```text
             ┌──────────────────────┐
             │  PLC / Modbus TCP    │
             └──────────┬───────────┘
                        │ holding registers
                        v
             ┌──────────────────────┐
             │ Modbus AWS Logger    │
             │ decode + timestamp  │
             │ retry + validation   │
             └──────────┬───────────┘
                        │ JSON / MQTT QoS 1 / TLS
                        v
             ┌──────────────────────┐
             │ AWS IoT Core         │
             └──────────────────────┘
```

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for trust boundaries and
failure behavior.

## Quick start

### 1. Open the project

```powershell
cd C:\Users\dell\Desktop\modbus-aws-logger
code .
```

### 2. Create/use the environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 3. See a safe demo payload

```powershell
python modbus_aws_logger.py --demo
```

This mode does not contact a PLC or AWS.

### 4. Configure locally

```powershell
Copy-Item .env.example .env
```

Edit `.env` with your own endpoint, PLC address, topic, and certificate paths.
The `.env` file is ignored by Git and must never be committed.

### 5. Validate without connecting

```powershell
python modbus_aws_logger.py --check-config
```

### 6. Run one controlled sample

Only after the endpoint, PLC, topic, and certificates have been verified:

```powershell
python modbus_aws_logger.py --once
```

### 7. Run continuously

```powershell
python modbus_aws_logger.py
```

## SMTP daily reports

SMTP is optional and disabled by default. When enabled, the logger sends one
small UTC-day summary for the previous day after the next day starts. It
includes publish/read/connection counts and the last error category; it does not
attach raw register data or credentials.

See [`docs/SMTP.md`](docs/SMTP.md) for Gmail app-password setup and testing.

Test SMTP locally without contacting the PLC or AWS:

```powershell
python modbus_aws_logger.py --email-test
```

## Tailscale and Flask access

The reference deployment uses a **Raspberry Pi 5 with 4 GB RAM** as the site
edge host. It runs the Modbus AWS Logger, a separate Flask UI/API, the
open-source xrdp remote-desktop service, and Tailscale. Multiple authorized
devices join the Tailscale network to access the Flask service and administer
the Pi remotely.

Tailscale provides the private VPN path; xrdp provides remote desktop; Flask
provides the browser UI/API; and AWS IoT MQTT/TLS remains the logger-to-cloud
connection. Tailscale does not replace AWS IoT, and xrdp is not an MQTT broker.

See [`docs/TAILSCALE.md`](docs/TAILSCALE.md) for the Raspberry Pi topology,
subnet routing, Tailscale Serve, xrdp port 3389, access policies, and the
recommended Flask deployment pattern. The repository documents this companion
service but does not include or start the separate Flask application.

## Payload shape

The exact register names depend on the configured PLC block. The payload keeps
the raw register values visible and adds operational metadata:

```json
{
  "machine": "Machine_1",
  "timestamp": 1760000000,
  "datetime": "2026-09-24T12:00:00+00:00",
  "registers": {
    "R0": 12,
    "R1": 34
  }
}
```

## Security model

- `.env`, certificates, private keys, logs, and virtual environments are ignored.
- The repository contains placeholders only; live AWS and PLC values stay local.
- AWS private keys are never printed or uploaded.
- SMTP reports use a local app password/provider secret and contain
  operational counts only, not raw register values.
- Tailscale is used for private site/operator connectivity; any Flask service
  must remain tailnet-only and enforce its own authentication.
- The pre-commit hook blocks common secret and certificate extensions.
- Rotate an AWS IoT certificate immediately if it is ever exposed.
- Keep the repository private until a public-release review is complete.

Read [`SECURITY.md`](SECURITY.md) before handling production credentials.

## Project status and roadmap

Current release: **0.1.0 private preview**

- [x] Secure environment-based configuration
- [x] Modbus TCP read loop
- [x] AWS IoT MQTT/TLS publishing
- [x] Offline configuration validation
- [x] Safe demo mode
- [x] Optional SMTP daily summary
- [x] Unit tests and CI baseline
- [ ] Full Modbus simulator mode
- [ ] Payload schema versioning
- [ ] Metrics and health endpoint
- [ ] Docker/systemd deployment profiles
- [ ] Public release and customer documentation

The roadmap is intentionally concrete rather than promising unverified production
claims. See [`docs/ROADMAP.md`](docs/ROADMAP.md).

## Contributing

Read [`CONTRIBUTING.md`](CONTRIBUTING.md). Run the local checks before opening a
pull request:

```powershell
python -m compileall -q .
python -m unittest discover -s tests -v
python -m pip check
```

## License decision

A public license will be selected before any public launch. Until then, this
private repository is not a substitute for a legal license review.
