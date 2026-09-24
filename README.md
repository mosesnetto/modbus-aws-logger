# Modbus AWS Logger

Reads Modbus TCP holding registers and publishes JSON data to AWS IoT Core over
MQTT/TLS. The program does not contain AWS credentials or private keys.

## Security model

- Configuration is loaded from environment variables and an ignored `.env` file.
- Keep AWS certificates and private keys outside the repository.
- `.env`, `*.pem`, `*.key`, `*.crt`, and `*.log` are ignored by Git.
- The program never prints certificate contents or private-key contents.
- A Git pre-commit hook blocks common certificate, key, and `.env` files.
- Use a private GitHub repository unless the endpoint and PLC details may be public.

## Windows setup

1. Install Python 3.11 or newer and Git.
2. Open PowerShell in this folder.
3. Create the environment:

   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install --upgrade pip
   pip install -r requirements.txt
   ```

4. Copy `.env.example` to `.env` and fill in the local values.
5. Put the AWS CA, client certificate, and private key in a protected folder
   outside this repository.
6. Validate without connecting:

   ```powershell
   python modbus_aws_logger.py --check-config
   ```

7. Run one live sample:

   ```powershell
   python modbus_aws_logger.py --once
   ```

8. Run continuously:

   ```powershell
   python modbus_aws_logger.py
   ```

Do not run the live mode until the PLC address, AWS endpoint, topic, and
certificate paths have been verified.
