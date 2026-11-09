# Modbus AWS Logger — Architecture & Design

## Problem

Industrial sites need to stream PLC data (Modbus TCP) to AWS IoT Core for cloud telemetry, dashboards, and alerting. Challenges:
- Unreliable networks (factory Wi-Fi, 4G)
- OT/IT security boundaries (no direct PLC-to-cloud)
- Device provisioning at scale
- Sales demos without live PLCs

## Solution

A Python service running on Raspberry Pi (or any Linux edge gateway) that:
1. Reads Modbus TCP registers from PLCs
2. Publishes JSON telemetry to AWS IoT Core via MQTT/TLS
3. Handles reconnects, buffering, and backoff automatically
4. Supports mTLS device authentication (X.509 certs)
5. Includes `--demo` mode for safe offline demonstrations

## Architecture

```
┌─────────────┐     Modbus TCP      ┌──────────────────┐     MQTT/TLS      ┌──────────────────┐
│  PLC/RTU    │ ◄─────────────────► │  Edge Gateway    │ ────────────────► │   AWS IoT Core   │
│  (Omron,    │   Register reads    │  (Raspberry Pi   │   JSON telemetry  │  (MQTT broker,   │
│  Siemens,   │   Polling interval  │   5 / CM4 / x86) │   + device shadow │   rules engine)  │
│  A-B)       │                     │                  │                   │                  │
└─────────────┘                     └──────────────────┘                   └────────┬─────────┘
                                                                                   │
                                                                                   ▼
                                                                        ┌──────────────────┐
                                                                        │  Downstream      │
                                                                        │  - IoT Analytics │
                                                                        │  - SiteWise      │
                                                                        │  - Timestream    │
                                                                        │  - Lambda/Rule   │
                                                                        │    actions       │
                                                                        └──────────────────┘
```

## Key Components

### 1. Modbus Client (`modbus_aws_logger.py`)
- `pymodbus` async TCP client with configurable polling interval
- Register map defined in `.env` (address, count, scale, offset, name, unit)
- Automatic reconnect with exponential backoff (1s → 60s max)
- Read timeouts prevent hanging on unresponsive PLCs

### 2. MQTT Publisher
- `awsiotsdk` MQTT connection with mTLS (cert + key + CA)
- QoS 1 for telemetry, QoS 0 for heartbeats
- Automatic reconnect with session persistence
- Offline message buffering (configurable max queue size)

### 3. Configuration (`config.py`)
- All settings via `.env` file (never committed)
- Environment-based: `dev`, `staging`, `prod`
- Validation on startup (`--check-config`)

### 4. Demo Mode (`--demo`)
```bash
python modbus_aws_logger.py --demo
```
- Generates realistic synthetic register values
- No network connections required
- Perfect for sales demos, CI, development

### 5. Systemd Service
```ini
# /etc/systemd/system/modbus-aws-logger.service
[Unit]
Description=Modbus to AWS IoT Logger
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=pi
WorkingDirectory=/opt/modbus-aws-logger
EnvironmentFile=/opt/modbus-aws-logger/.env
ExecStart=/opt/modbus-aws-logger/.venv/bin/python modbus_aws_logger.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

## Security

| Layer | Implementation |
|-------|----------------|
| **Device Auth** | X.509 certs per device (AWS IoT thing certificates) |
| **Transport** | MQTT over TLS 1.2+ (ALPN `x-amzn-mqtt-ca`) |
| **Secrets** | Certs/keys in `/opt/modbus-aws-logger/certs/` (chmod 600) |
| **Network** | Edge gateway in DMZ / separate VLAN; PLC only talks to gateway |
| **Least Privilege** | IoT policy: `iot:Publish` to `dt/<thingname>/telemetry` only |

## Deployment Checklist

- [ ] Provision AWS IoT Thing + certificates
- [ ] Copy certs to edge device (`certs/thing.cert.pem`, `certs/thing.private.key`, `certs/AmazonRootCA1.pem`)
- [ ] Configure `.env` with PLC IPs, register map, AWS endpoint
- [ ] Test with `--check-config` and `--demo`
- [ ] Install systemd service, enable + start
- [ ] Verify in AWS IoT Console → Test → Subscribe to `dt/+/telemetry`
- [ ] Set up CloudWatch alarms on missing heartbeats

## Scaling to 100+ Devices

1. **Fleet Provisioning** — Use AWS IoT Fleet Provisioning with claim certificates
2. **Device Groups** — Tag things by site/line for targeted rule actions
3. **Central Config** — Store register maps in AWS IoT Device Shadow or S3; edge pulls on startup
4. **Monitoring** — CloudWatch metric `aws.iot.ConnectedDevices` + custom `modbus.read.errors`

## Files in This Repo

| File | Purpose |
|------|---------|
| `modbus_aws_logger.py` | Main service (Modbus + MQTT + reconnect logic) |
| `config.py` | Configuration loading & validation |
| `sending_to_aws.py` | Minimal standalone publish example |
| `email_sender.py` | Daily summary reporter (SMTP) |
| `run.ps1` | Windows dev launcher |
| `requirements.txt` | `pymodbus`, `awsiotsdk`, `python-dotenv` |
| `.env.example` | Template for all config variables |
| `docs/ARCHITECTURE.md` | This file |
| `docs/TAILSCALE.md` | Remote access via Tailscale Serve |
| `docs/SMTP.md` | Email reporter setup |

## License

MIT — see [LICENSE](../LICENSE)