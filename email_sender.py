"""Optional SMTP daily telemetry reports for Modbus AWS Logger.

SMTP is disabled by default. When enabled, the service sends a small daily
summary (counts and errors, not raw register values) after the next day starts.
Credentials are read only from environment variables and are never logged.
"""
from __future__ import annotations

import json
import logging
import os
import smtplib
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from pathlib import Path
from typing import Any

LOGGER = logging.getLogger("modbus_aws_logger.email")


class SmtpConfigError(RuntimeError):
    """Raised when SMTP is enabled but its configuration is incomplete."""


class SmtpDeliveryError(RuntimeError):
    """Raised when the SMTP server rejects a message or cannot be reached."""


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _bool_env(name: str, default: bool = False) -> bool:
    raw = _env(name)
    if not raw:
        return default
    value = raw.lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    raise SmtpConfigError(f"{name} must be true or false")


def _int_env(name: str, default: int) -> int:
    raw = _env(name)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise SmtpConfigError(f"{name} must be an integer") from exc


def _utc_day(timestamp: str | None = None) -> str:
    """Return a UTC report day, falling back safely for malformed timestamps."""
    if timestamp:
        try:
            parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc).date().isoformat()
        except (TypeError, ValueError):
            pass
    return datetime.now(timezone.utc).date().isoformat()


@dataclass(frozen=True)
class SmtpConfig:
    enabled: bool
    host: str
    port: int
    username: str
    password: str = field(repr=False)
    sender: str
    recipients: tuple[str, ...]
    subject_prefix: str
    use_starttls: bool
    check_interval_seconds: int
    runtime_dir: Path

    @classmethod
    def from_env(cls) -> "SmtpConfig":
        enabled = _bool_env("SMTP_ENABLED", False)
        username = _env("SMTP_USERNAME")
        password = _env("SMTP_PASSWORD")
        sender = _env("SMTP_FROM", username)
        recipients = tuple(
            item.strip()
            for item in _env("SMTP_TO").replace(";", ",").split(",")
            if item.strip()
        )
        host = _env("SMTP_HOST", "smtp.gmail.com")
        port = _int_env("SMTP_PORT", 587)
        use_starttls = _bool_env("SMTP_USE_STARTTLS", True)
        if enabled:
            required = {
                "SMTP_USERNAME": username,
                "SMTP_PASSWORD": password,
                "SMTP_FROM": sender,
            }
            missing = [name for name, value in required.items() if not value]
            if not recipients:
                missing.append("SMTP_TO")
            if missing:
                raise SmtpConfigError(
                    "SMTP is enabled but these settings are missing: "
                    + ", ".join(missing)
                )
            if not host:
                missing.append("SMTP_HOST")
            if not 1 <= port <= 65535:
                missing.append("SMTP_PORT (must be between 1 and 65535)")
            if not use_starttls:
                missing.append("SMTP_USE_STARTTLS (must be true)")
            if missing:
                raise SmtpConfigError(
                    "SMTP configuration is invalid: " + ", ".join(missing)
                )

        return cls(
            enabled=enabled,
            host=host,
            port=port,
            username=username,
            password=password,
            sender=sender,
            recipients=recipients,
            subject_prefix=_env("SMTP_SUBJECT_PREFIX", "Modbus AWS Logger"),
            use_starttls=use_starttls,
            check_interval_seconds=max(60, _int_env("SMTP_CHECK_INTERVAL_SECONDS", 600)),
            runtime_dir=Path(_env("RUNTIME_DIR", "./runtime")).expanduser(),
        )


@dataclass
class DailyStats:
    date: str
    successful_publishes: int = 0
    read_failures: int = 0
    publish_failures: int = 0
    connection_failures: int = 0
    first_sample: str = ""
    last_sample: str = ""
    last_error: str = ""

    def record_success(self, timestamp: str) -> None:
        if not self.first_sample:
            self.first_sample = timestamp
        self.last_sample = timestamp
        self.successful_publishes += 1

    def record_failure(self, kind: str, error: str, timestamp: str) -> None:
        if kind == "read":
            self.read_failures += 1
        elif kind == "publish":
            self.publish_failures += 1
        else:
            self.connection_failures += 1
        normalized_error = " ".join(str(error).split())
        self.last_error = f"{kind}: {normalized_error}"[:500]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class DailyStatsStore:
    def __init__(self, runtime_dir: Path):
        self.runtime_dir = runtime_dir
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def path_for(self, day: str) -> Path:
        return self.runtime_dir / f"telemetry_stats_{day}.json"

    def load(self, day: str) -> DailyStats:
        path = self.path_for(day)
        with self._lock:
            if not path.is_file():
                return DailyStats(date=day)
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                return DailyStats(**data)
            except (OSError, ValueError, TypeError) as exc:
                LOGGER.warning("Could not read telemetry stats %s: %s", path, exc)
                return DailyStats(date=day)

    def save(self, stats: DailyStats) -> None:
        path = self.path_for(stats.date)
        temporary = path.with_name(f".{path.name}.tmp")
        with self._lock:
            temporary.write_text(
                json.dumps(stats.as_dict(), indent=2),
                encoding="utf-8",
            )
            temporary.replace(path)


class SmtpMailer:
    def __init__(self, config: SmtpConfig):
        self.config = config

    def send(self, subject: str, body: str) -> None:
        if not self.config.enabled:
            raise SmtpConfigError("SMTP is disabled")
        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = self.config.sender
        message["To"] = ", ".join(self.config.recipients)
        message.set_content(body)

        try:
            with smtplib.SMTP(
                self.config.host,
                self.config.port,
                timeout=30,
            ) as smtp:
                if self.config.use_starttls:
                    smtp.starttls()
                if self.config.username:
                    smtp.login(self.config.username, self.config.password)
                smtp.send_message(message)
        except (OSError, smtplib.SMTPException) as exc:
            raise SmtpDeliveryError("SMTP delivery failed") from exc


class EmailNotifier:
    """Collect local daily statistics and send deduplicated SMTP reports."""

    def __init__(self, config: SmtpConfig):
        self.config = config
        self.store = DailyStatsStore(config.runtime_dir) if config.enabled else None
        self.mailer = SmtpMailer(config)
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._current_day = _utc_day()
        self._stats = self.store.load(self._current_day) if self.store else None
        self._sent_path = (
            self.config.runtime_dir / "smtp_sent_dates.json"
            if self.config.enabled
            else None
        )

    @property
    def enabled(self) -> bool:
        return self.config.enabled

    def _load_sent(self) -> set[str]:
        if not self._sent_path or not self._sent_path.is_file():
            return set()
        try:
            data = json.loads(self._sent_path.read_text(encoding="utf-8"))
            if not isinstance(data, list):
                return set()
            return {item for item in data if isinstance(item, str)}
        except (OSError, ValueError):
            return set()

    def _save_sent(self, sent: set[str]) -> None:
        if not self._sent_path:
            return
        self._sent_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._sent_path.with_name(f".{self._sent_path.name}.tmp")
        temporary.write_text(json.dumps(sorted(sent), indent=2), encoding="utf-8")
        temporary.replace(self._sent_path)

    def _roll_day(self, current_day: str) -> None:
        if not self.store or not self._stats or self._stats.date == current_day:
            return
        self.store.save(self._stats)
        self._current_day = current_day
        self._stats = self.store.load(current_day)

    def record_success(self, timestamp: str) -> None:
        if not self.store or not self._stats:
            return
        with self._lock:
            day = _utc_day(timestamp)
            self._roll_day(day)
            self._stats.record_success(timestamp)
            self.store.save(self._stats)

    def record_failure(self, kind: str, error: str, timestamp: str) -> None:
        if not self.store or not self._stats:
            return
        safe_error = str(error)
        if self.config.password:
            safe_error = safe_error.replace(self.config.password, "[redacted]")
        with self._lock:
            day = _utc_day(timestamp)
            self._roll_day(day)
            self._stats.record_failure(kind, safe_error, timestamp)
            self.store.save(self._stats)

    def _report_body(self, stats: DailyStats) -> str:
        return (
            f"Project: Modbus AWS Logger\n"
            f"Date: {stats.date}\n\n"
            f"Successful publishes: {stats.successful_publishes}\n"
            f"PLC read failures: {stats.read_failures}\n"
            f"AWS publish failures: {stats.publish_failures}\n"
            f"Connection failures: {stats.connection_failures}\n"
            f"First sample: {stats.first_sample or 'none'}\n"
            f"Last sample: {stats.last_sample or 'none'}\n"
            f"Last error: {stats.last_error or 'none'}\n\n"
            "This report contains operational counts only; raw register values "
            "and credentials are not included."
        )

    def send_report_for(self, day: str) -> bool:
        try:
            datetime.strptime(day, "%Y-%m-%d")
        except (TypeError, ValueError):
            return False
        if not self.store or not self.store.path_for(day).is_file():
            return False
        stats = self.store.load(day)
        sent = self._load_sent()
        if day in sent:
            return False
        subject = f"{self.config.subject_prefix} — daily telemetry report — {day}"
        self.mailer.send(subject, self._report_body(stats))
        sent.add(day)
        self._save_sent(sent)
        LOGGER.info("SMTP daily report sent for %s", day)
        return True

    def send_test(self) -> None:
        subject = f"{self.config.subject_prefix} — SMTP test"
        body = (
            "This is a test message from Modbus AWS Logger.\n\n"
            "If you received this message, SMTP configuration is working."
        )
        self.mailer.send(subject, body)
        LOGGER.info("SMTP test message sent")

    def _send_pending(self) -> None:
        today = datetime.now(timezone.utc).date()
        sent = self._load_sent()
        for days_back in range(1, 8):
            day = (today - timedelta(days=days_back)).isoformat()
            if day in sent or not self.store or not self.store.path_for(day).is_file():
                continue
            try:
                self.send_report_for(day)
            except Exception:
                LOGGER.exception("SMTP daily report failed for %s", day)

    def _loop(self) -> None:
        while not self._stop.is_set():
            self._send_pending()
            self._stop.wait(self.config.check_interval_seconds)

    def start(self) -> None:
        if not self.enabled or self._thread is not None:
            return
        self._thread = threading.Thread(target=self._loop, name="smtp-reporter", daemon=True)
        self._thread.start()
        LOGGER.info("SMTP daily reporter started")

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2)
            self._thread = None
        if self.store and self._stats:
            self.store.save(self._stats)

    def check(self) -> None:
        if not self.enabled:
            print("SMTP: disabled")
            return
        print(f"SMTP: enabled via {self.config.host}:{self.config.port}")
        print(f"SMTP recipients: {len(self.config.recipients)}")
        print(f"SMTP STARTTLS: {self.config.use_starttls}")
        print(f"SMTP report interval: {self.config.check_interval_seconds} seconds")
