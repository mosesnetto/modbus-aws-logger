# Architecture

## Design goals

1. Keep credentials and infrastructure details outside source control.
2. Make the PLC and cloud paths independently retryable.
3. Preserve raw values so later analytics can evolve without losing data.
4. Make offline validation possible before touching a production network.

## Data path

```text
Environment / local .env
          │
          ▼
     Configuration
          │
          ▼
  Modbus TCP client ───── failure ──► reconnect/backoff
          │
          ▼
   JSON payload builder
          │
          ▼
 AWS IoT MQTT/TLS client ─ failure ──► reconnect/backoff
          │
          ▼
       AWS IoT topic
```

## Reporting path

Successful publishes and categorized failures are written to small local JSON
state files under `runtime/`. When SMTP is enabled, a background reporter sends
one deduplicated summary for the previous UTC day. The reporting path is
independent of the MQTT payload and never copies raw register values into the
message.

## Companion Flask service

The reference edge host is a Raspberry Pi 5 with 4 GB RAM. A separate Flask
UI/API may listen on localhost and be shared only through Tailscale Serve, or it
may listen on a Tailscale address with a restricted tailnet policy. The same
host may provide xrdp remote desktop on TCP/3389. These services are not part
of the logger process and do not replace AWS IoT MQTT/TLS. The web service must
provide its own authentication, authorization, CSRF protection, and secret
handling.

## Trust boundaries

- The PLC is an untrusted network endpoint. The client uses a bounded timeout.
- AWS certificates are local files and are never committed.
- SMTP credentials are local environment values and are never committed.
- SMTP reports contain counts/status only, not raw register values.
- Tailscale protects private operator/site paths; a companion Flask service is
  still responsible for application authentication and authorization.
- The repository is private during the preview phase.
- Logs may contain operational values and must remain local unless explicitly
  reviewed for disclosure.

## Failure behavior

- PLC connection failure returns no fabricated measurement.
- MQTT failure is retried without stopping the process.
- A failed cycle is logged and the loop continues.
- SMTP delivery failures are logged and retried without stopping telemetry.
- `--check-config` never opens a network connection.
- `--demo` returns a safe sample payload without configuration or network access.
- `--once` performs exactly one read/publish cycle and then exits.
