"""Backward-compatible entry point for the secured Modbus/AWS logger."""

from modbus_aws_logger import main


if __name__ == "__main__":
    raise SystemExit(main())
