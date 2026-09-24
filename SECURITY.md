# Security notes

- Never commit `.env`, AWS private keys, client certificates, CA files, or logs.
- Keep certificate files outside the repository and restrict them to the user account that runs the logger.
- Use a private GitHub repository unless the AWS endpoint and PLC network details are intentionally public.
- If a private key is ever exposed, revoke/rotate it in AWS IoT immediately.
- Keep SMTP app passwords/provider secrets in local environment configuration only.
- Keep SMTP STARTTLS enabled; the application refuses an enabled, unencrypted
  SMTP configuration.
- Use Tailscale for private operator/site connectivity, restrict its policy to
  required devices and ports, and do not use Funnel or public port forwarding
  for the PLC, xrdp, or Flask service.
- On the Raspberry Pi edge host, restrict xrdp/TCP/3389 and the Flask listener
  with both Tailscale policy and the host firewall; a listener bound to all
  interfaces may also be reachable from the local LAN.
- A Flask UI/API must have its own authentication and authorization; tailnet
  access alone is not application authorization.
- Review `.gitignore` before every commit.
- Do not paste credentials, access tokens, or private-key contents into issues or chat.
