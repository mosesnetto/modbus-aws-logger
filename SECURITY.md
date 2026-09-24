# Security notes

- Never commit `.env`, AWS private keys, client certificates, CA files, or logs.
- Keep certificate files outside the repository and restrict them to the user account that runs the logger.
- Use a private GitHub repository unless the AWS endpoint and PLC network details are intentionally public.
- If a private key is ever exposed, revoke/rotate it in AWS IoT immediately.
- Keep SMTP app passwords/provider secrets in local environment configuration only.
- Keep SMTP STARTTLS enabled; the application refuses an enabled, unencrypted
  SMTP configuration.
- Review `.gitignore` before every commit.
- Do not paste credentials, access tokens, or private-key contents into issues or chat.
