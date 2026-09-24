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

## Trust boundaries

- The PLC is an untrusted network endpoint. The client uses a bounded timeout.
- AWS certificates are local files and are never committed.
- The repository is private during the preview phase.
- Logs may contain operational values and must remain local unless explicitly
  reviewed for disclosure.

## Failure behavior

- PLC connection failure returns no fabricated measurement.
- MQTT failure is retried without stopping the process.
- A failed cycle is logged and the loop continues.
- `--check-config` never opens a network connection.
- `--demo` returns a safe sample payload without configuration or network access.
- `--once` performs exactly one read/publish cycle and then exits.
