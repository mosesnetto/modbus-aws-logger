import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import paho.mqtt.client as mqtt

from modbus_aws_logger import ConfigError, load_config, publish, read_plc


class FakeModbusResult:
    isError_value = False
    registers = [12, 34]

    def isError(self):
        return self.isError_value


class FakeModbusClient:
    connected = True

    def __init__(self, error=False):
        self.error = error
        self.calls = []

    def read_holding_registers(self, **kwargs):
        self.calls.append(kwargs)
        result = FakeModbusResult()
        result.isError_value = self.error
        return result


class FakeCloud:
    def __init__(self):
        self.calls = []

    def publish(self, topic, payload, qos):
        self.calls.append((topic, payload, qos))
        return SimpleNamespace(rc=mqtt.MQTT_ERR_SUCCESS)


class ModbusLoggerTests(unittest.TestCase):
    def make_config(self, directory):
        files = {}
        for name in ("ca.pem", "client.crt", "private.key"):
            path = Path(directory) / name
            path.write_text("test", encoding="utf-8")
            files[name] = str(path)
        environment = {
            "AWS_IOT_ENDPOINT": "example.iot.region.amazonaws.com",
            "AWS_IOT_PORT": "8883",
            "AWS_IOT_TOPIC": "test/topic",
            "AWS_IOT_CA_FILE": files["ca.pem"],
            "AWS_IOT_CLIENT_CERT_FILE": files["client.crt"],
            "AWS_IOT_PRIVATE_KEY_FILE": files["private.key"],
            "PLC_IP": "192.0.2.10",
            "PLC_PORT": "502",
            "PLC_UNIT_ID": "1",
            "PLC_REGISTER_COUNT": "2",
        }
        with patch.dict(os.environ, environment, clear=True):
            return load_config()

    def test_config_is_loaded_without_network_access(self):
        with tempfile.TemporaryDirectory() as directory:
            config = self.make_config(directory)
        self.assertEqual(config["aws_port"], 8883)
        self.assertEqual(config["register_count"], 2)
        self.assertEqual(config["plc_unit"], 1)

    def test_read_plc_returns_registers_and_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            config = self.make_config(directory)
        client = FakeModbusClient()
        payload = read_plc(client, config)
        self.assertIsNotNone(payload)
        self.assertEqual(payload["registers"], {"R0": 12, "R1": 34})
        self.assertEqual(client.calls[0]["count"], 2)

    def test_publish_uses_configured_topic_and_qos(self):
        with tempfile.TemporaryDirectory() as directory:
            config = self.make_config(directory)
        cloud = FakeCloud()
        self.assertTrue(publish(cloud, config, {"registers": {"R0": 1}}))
        self.assertEqual(cloud.calls[0][0], "test/topic")
        self.assertEqual(cloud.calls[0][2], 1)

    def test_missing_configuration_is_rejected(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ConfigError):
                load_config()


if __name__ == "__main__":
    unittest.main()
