import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from email_sender import (
    EmailNotifier,
    SmtpConfig,
    SmtpConfigError,
)


class FakeSmtp:
    def __init__(self):
        self.started = False
        self.login_args = None
        self.message = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def starttls(self):
        self.started = True

    def login(self, username, password):
        self.login_args = (username, password)

    def send_message(self, message):
        self.message = message


class SmtpConfigTests(unittest.TestCase):
    def test_disabled_configuration_needs_no_credentials(self):
        with patch.dict(os.environ, {}, clear=True):
            config = SmtpConfig.from_env()
        self.assertFalse(config.enabled)
        self.assertEqual(config.recipients, ())
        self.assertTrue(config.use_starttls)

    def test_enabled_configuration_parses_recipients(self):
        environment = {
            "SMTP_ENABLED": "true",
            "SMTP_HOST": "smtp.example.test",
            "SMTP_PORT": "587",
            "SMTP_USERNAME": "sender@example.test",
            "SMTP_PASSWORD": "app-secret",
            "SMTP_FROM": "logger@example.test",
            "SMTP_TO": "ops@example.test; maintenance@example.test",
            "SMTP_USE_STARTTLS": "true",
        }
        with patch.dict(os.environ, environment, clear=True):
            config = SmtpConfig.from_env()
        self.assertTrue(config.enabled)
        self.assertEqual(
            config.recipients,
            ("ops@example.test", "maintenance@example.test"),
        )
        self.assertNotIn("app-secret", repr(config))

    def test_enabled_configuration_rejects_missing_credentials(self):
        with patch.dict(os.environ, {"SMTP_ENABLED": "true"}, clear=True):
            with self.assertRaises(SmtpConfigError):
                SmtpConfig.from_env()

    def test_enabled_configuration_requires_starttls(self):
        environment = {
            "SMTP_ENABLED": "true",
            "SMTP_USERNAME": "sender@example.test",
            "SMTP_PASSWORD": "app-secret",
            "SMTP_FROM": "logger@example.test",
            "SMTP_TO": "ops@example.test",
            "SMTP_USE_STARTTLS": "false",
        }
        with patch.dict(os.environ, environment, clear=True):
            with self.assertRaises(SmtpConfigError):
                SmtpConfig.from_env()


class EmailNotifierTests(unittest.TestCase):
    def make_config(self, directory):
        return SmtpConfig(
            enabled=True,
            host="smtp.example.test",
            port=587,
            username="sender@example.test",
            password="app-secret",
            sender="logger@example.test",
            recipients=("ops@example.test",),
            subject_prefix="Test Logger",
            use_starttls=True,
            check_interval_seconds=600,
            runtime_dir=Path(directory),
        )

    def test_daily_report_is_sent_once_and_contains_counts_only(self):
        with tempfile.TemporaryDirectory() as directory:
            notifier = EmailNotifier(self.make_config(directory))
            day = datetime.now(timezone.utc).date().isoformat()
            timestamp = f"{day}T12:00:00+00:00"
            notifier.record_success(timestamp)
            notifier.record_failure(
                "read",
                "PLC read failed; app-secret must not be retained",
                timestamp,
            )

            smtp = FakeSmtp()
            with patch("email_sender.smtplib.SMTP", return_value=smtp) as factory:
                self.assertTrue(notifier.send_report_for(day))
                self.assertFalse(notifier.send_report_for(day))

            self.assertEqual(factory.call_args.kwargs["timeout"], 30)
            self.assertTrue(smtp.started)
            self.assertEqual(
                smtp.login_args,
                ("sender@example.test", "app-secret"),
            )
            self.assertIsNotNone(smtp.message)
            body = smtp.message.get_content()
            self.assertIn("Successful publishes: 1", body)
            self.assertIn("PLC read failures: 1", body)
            self.assertNotIn("app-secret", body)
            self.assertIn("[redacted]", body)
            self.assertIn(day, smtp.message["Subject"])
            self.assertTrue(
                (Path(directory) / f"telemetry_stats_{day}.json").is_file()
            )
            notifier.stop()

    def test_disabled_notifier_does_not_create_runtime_state(self):
        with tempfile.TemporaryDirectory() as directory:
            config = SmtpConfig(
                enabled=False,
                host="smtp.example.test",
                port=587,
                username="",
                password="",
                sender="",
                recipients=(),
                subject_prefix="Test Logger",
                use_starttls=True,
                check_interval_seconds=600,
                runtime_dir=Path(directory) / "runtime",
            )
            notifier = EmailNotifier(config)
            notifier.record_success("2026-09-24T12:00:00+00:00")
            notifier.stop()
            self.assertFalse(config.runtime_dir.exists())


if __name__ == "__main__":
    unittest.main()
