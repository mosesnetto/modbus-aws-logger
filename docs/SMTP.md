# SMTP daily reports

The project has an optional, secure SMTP reporter. It is **disabled by default**
and does not send raw PLC register values or AWS credentials.

## What it sends

After a new UTC day starts, the reporter checks the previous UTC day's local
summary and sends one email containing:

- successful AWS publishes;
- PLC read failures;
- AWS publish failures;
- connection failures;
- first and last sample timestamps;
- the last error category.

A small state file prevents the same day's report from being sent twice. Report
files contain only counts, timestamps, and a short error category. These runtime
files stay under `runtime/` and are ignored by Git.

## Configure

1. Create a local `.env` from `.env.example`.
2. Set `SMTP_ENABLED=true`.
3. Set the SMTP host, port, username, sender, and comma-separated recipients.
4. Use an application password or provider-specific secret, not a normal
   account password where the provider supports app passwords.
5. Keep `SMTP_USE_STARTTLS=true`; the logger rejects an enabled SMTP setup that
   would send credentials without transport encryption.
6. Keep `SMTP_PASSWORD` only in the local `.env` file.

`SMTP_CHECK_INTERVAL_SECONDS` controls how often the reporter checks for a
finished UTC day (minimum 60 seconds). `RUNTIME_DIR` controls where the local
statistics and sent-date state are written; keep it outside source control.

Gmail example:

```dotenv
SMTP_ENABLED=true
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-account@gmail.com
SMTP_PASSWORD=your-16-character-app-password
SMTP_FROM=your-account@gmail.com
SMTP_TO=operations@example.com
SMTP_USE_STARTTLS=true
```

## Test locally

This sends a real test email and does not contact the PLC or AWS:

```powershell
python modbus_aws_logger.py --email-test
```

## Validate without sending

```powershell
python modbus_aws_logger.py --check-config
```

The validation output reports the SMTP host and recipient count, but never the
password, certificate contents, or private-key contents.
