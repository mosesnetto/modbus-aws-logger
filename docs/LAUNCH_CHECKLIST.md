# Public launch checklist

Do not make the repository public until every applicable item is complete.

- [ ] Confirm ownership and licensing of all source files.
- [ ] Select and add the project license.
- [ ] Remove all live endpoints, PLC addresses, customer names, and credentials.
- [ ] Verify `.env`, `*.pem`, `*.key`, `*.crt`, and logs are ignored.
- [ ] Rotate any credential that has ever appeared in history or chat.
- [ ] Run unit tests and CI from a clean checkout.
- [ ] Test PLC reconnect and AWS reconnect behavior.
- [ ] Test malformed PLC data and broker failure paths.
- [ ] Test SMTP delivery with an app password and verify reports contain no raw
      register values or credentials.
- [ ] Test the Raspberry Pi deployment from multiple authorized Tailscale
      devices, including the Flask service and restricted xrdp/TCP/3389 access.
- [ ] Add a sanitized demo/simulator mode.
- [ ] Publish support and security contact details.
- [ ] Create a release tag and changelog.
- [ ] Have a second person review the public documentation.
