"""Modbus TCP scanner with optional AWS IoT MQTT publishing.

Credentials, certificate paths, PLC addresses, and MQTT settings are read from
environment variables. Secrets and private keys must remain outside Git.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import signal
import ssl
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
import paho.mqtt.client as mqtt
from pymodbus.client import ModbusTcpClient

load_dotenv(Path(__file__).with_name(".env"))

LOGGER = logging.getLogger("modbus_aws_logger")


class ConfigError(RuntimeError):
    """Raised when required configuration is missing or invalid."""


def env(name: str, default: str | None = None) -> str:
    value = os.getenv(name, default)
    if value is None or not value.strip():
        raise ConfigError(f"Missing required environment variable: {name}")
    return value.strip()


def env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} must be an integer") from exc


def env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} must be a number") from exc


def required_file(name: str) -> Path:
    path = Path(env(name)).expanduser()
    if not path.is_file():
        raise ConfigError(f"{name} does not point to a readable file: {path}")
    return path


def load_config() -> dict[str, Any]:
    return {
        "aws_endpoint": env("AWS_IOT_ENDPOINT"),
        "aws_port": env_int("AWS_IOT_PORT", 8883),
        "aws_topic": env("AWS_IOT_TOPIC"),
        "ca_file": required_file("AWS_IOT_CA_FILE"),
        "client_cert": required_file("AWS_IOT_CLIENT_CERT_FILE"),
        "private_key": required_file("AWS_IOT_PRIVATE_KEY_FILE"),
        "client_id": os.getenv("AWS_IOT_CLIENT_ID", "modbus-aws-logger"),
        "plc_ip": env("PLC_IP"),
        "plc_port": env_int("PLC_PORT", 502),
        "plc_unit": env_int("PLC_UNIT_ID", 1),
        "register_count": env_int("PLC_REGISTER_COUNT", 124),
        "publish_interval": env_float("PUBLISH_INTERVAL_SECONDS", 1.0),
        "reconnect_delay": env_float("RECONNECT_DELAY_SECONDS", 5.0),
        "log_file": Path(os.getenv("LOG_FILE", "iot_gateway.log")).expanduser(),
    }


def configure_logging(log_file: Path) -> None:
    log_file.parent.mkdir(parents=True, exist_ok=True)
    handlers: list[logging.Handler] = [
        logging.FileHandler(log_file, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ]
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=handlers,
        force=True,
    )


def mqtt_client(client_id: str) -> mqtt.Client:
    # CallbackAPIVersion.VERSION2 is available in paho-mqtt 2.x.
    try:
        return mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_id)
    except AttributeError:
        return mqtt.Client(client_id=client_id)


def configure_mqtt_tls(client: mqtt.Client, config: dict[str, Any]) -> None:
    client.tls_set(
        ca_certs=str(config["ca_file"]),
        certfile=str(config["client_cert"]),
        keyfile=str(config["private_key"]),
        tls_version=ssl.PROTOCOL_TLSv1_2,
    )


def connect_mqtt(client: mqtt.Client, config: dict[str, Any], running: bool) -> bool:
    while running:
        try:
            LOGGER.info("Connecting to AWS IoT MQTT endpoint")
            client.connect(config["aws_endpoint"], config["aws_port"], keepalive=60)
            client.loop_start()
            return True
        except Exception:
            LOGGER.exception("AWS MQTT connection failed; retrying")
            time.sleep(config["reconnect_delay"])
    return False


def connect_plc(config: dict[str, Any]) -> ModbusTcpClient | None:
    client = ModbusTcpClient(
        config["plc_ip"],
        port=config["plc_port"],
        timeout=5,
    )
    try:
        if client.connect():
            LOGGER.info("PLC connected")
            return client
        LOGGER.error("PLC connection failed")
    except Exception:
        LOGGER.exception("PLC connection exception")
    return None


def read_plc(client: ModbusTcpClient, config: dict[str, Any]) -> dict[str, Any] | None:
    try:
        kwargs = {"device_id": config["plc_unit"]}
        try:
            result = client.read_holding_registers(
                address=0,
                count=config["register_count"],
                **kwargs,
            )
        except TypeError:
            # Compatibility with older pymodbus releases.
            kwargs = {"slave": config["plc_unit"]}
            result = client.read_holding_registers(
                address=0,
                count=config["register_count"],
                **kwargs,
            )

        if result.isError():
            LOGGER.error("Modbus read error")
            return None

        values = list(getattr(result, "registers", []))
        return {
            "machine": os.getenv("MACHINE_NAME", "Machine_1"),
            "timestamp": int(time.time()),
            "datetime": datetime.now(timezone.utc).isoformat(),
            "registers": {f"R{i}": value for i, value in enumerate(values)},
        }
    except Exception:
        LOGGER.exception("Modbus read exception")
        return None


def publish(client: mqtt.Client, config: dict[str, Any], payload: dict[str, Any]) -> bool:
    try:
        result = client.publish(
            config["aws_topic"],
            json.dumps(payload, separators=(",", ":")),
            qos=1,
        )
        if result.rc == mqtt.MQTT_ERR_SUCCESS:
            LOGGER.info("Data published to AWS IoT topic %s", config["aws_topic"])
            return True
        LOGGER.error("AWS MQTT publish failed with code %s", result.rc)
    except Exception:
        LOGGER.exception("AWS MQTT publish exception")
    return False


def run(config: dict[str, Any], once: bool = False) -> int:
    running = True

    def stop(signum: int, frame: Any) -> None:
        nonlocal running
        LOGGER.info("Shutdown signal received")
        running = False

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)

    cloud = mqtt_client(config["client_id"])
    configure_mqtt_tls(cloud, config)
    plc = connect_plc(config)
    if not connect_mqtt(cloud, config, running):
        return 1

    try:
        while running:
            started = time.time()
            if plc is None or not getattr(plc, "connected", False):
                LOGGER.warning("Reconnecting PLC")
                plc = connect_plc(config)
                time.sleep(config["reconnect_delay"])
                continue

            payload = read_plc(plc, config)
            if payload is not None:
                publish(cloud, config, payload)

            if once:
                break

            elapsed = time.time() - started
            time.sleep(max(0.0, config["publish_interval"] - elapsed))
    finally:
        if plc is not None:
            plc.close()
            LOGGER.info("PLC connection closed")
        cloud.loop_stop()
        cloud.disconnect()
        LOGGER.info("AWS MQTT disconnected")

    return 0


def check_config(config: dict[str, Any]) -> None:
    # Do not print secret values or file contents.
    print("Configuration is valid.")
    print(f"AWS endpoint: {config['aws_endpoint']}")
    print(f"AWS port: {config['aws_port']}")
    print(f"AWS topic: {config['aws_topic']}")
    print(f"PLC: {config['plc_ip']}:{config['plc_port']} (unit {config['plc_unit']})")
    print(f"Registers: {config['register_count']}")
    print(f"Publish interval: {config['publish_interval']} seconds")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check-config",
        action="store_true",
        help="Validate environment and certificate paths without connecting.",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Read and publish one sample, then exit.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        config = load_config()
        configure_logging(config["log_file"])
        if args.check_config:
            check_config(config)
            return 0
        return run(config, once=args.once)
    except ConfigError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
