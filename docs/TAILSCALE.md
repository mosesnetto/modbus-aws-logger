# Tailscale connectivity

Tailscale is an optional private-connectivity layer for this project. It is not
an AWS IoT broker and it is not required for local PLC communication.

The recommended topology keeps the cloud and site networks separate:

```text
Remote operator
      |
      | Tailscale / SSH or RDP
      v
Logger host (Tailscale + Modbus AWS Logger)
      |                         \
      | Modbus TCP/502            \ MQTT/TLS/8883
      v                            v
PLC on the private site LAN       AWS IoT Core
```

The logger needs outbound access to the AWS IoT endpoint. Tailscale does not
replace the AWS IoT X.509 certificate, MQTT TLS configuration, topic policy, or
AWS IoT endpoint.

## Reference deployment: Raspberry Pi 5

The reference deployment for this project is a **Raspberry Pi 5 with 4 GB of
RAM** acting as the site edge host. The same Raspberry Pi runs the Modbus AWS
Logger, a separate Flask UI/API, and the open-source xrdp remote-desktop
service. Multiple authorized devices join the same Tailscale network and use
that private connectivity for browser/API access and remote administration.

```text
Authorized laptops/tablets/phones
          |
          | Tailscale VPN
          v
Raspberry Pi 5 (4 GB RAM)
  |- Flask UI/API  ── Tailscale Serve or restricted TCP listener
  |- xrdp          ── Tailscale TCP/3389 for remote desktop
  |- Modbus AWS Logger
  |      |- Modbus TCP/502 ──> PLC on the site LAN
  |      `- MQTT/TLS/8883  ──> AWS IoT Core
  `- local configuration, certificates, and runtime state
```

Tailscale supplies the encrypted private network. xrdp is open-source remote
desktop software with no separate license fee, and Flask supplies the web
interface/API; these are separate services. Hardware, internet, and any cloud
charges are separate from the xrdp license status.
Tailscale is not an xrdp replacement, and xrdp is not an AWS IoT broker. The
repository documents this deployment pattern but does not contain the separate
Flask application or provision the operating-system services automatically.

### Device roles

- **Raspberry Pi:** Runs the logger, Flask companion service, Tailscale, and
  xrdp. Keep AWS certificates, `.env`, and runtime files local to the device.
- **Remote devices:** Join the tailnet and access the Flask service through its
  Tailscale URL. Use the Tailscale address or MagicDNS name for xrdp.
- **PLC:** Remains on the private site network. The Pi reaches it over the LAN
  or through an approved Tailscale subnet route.
- **AWS IoT Core:** Receives MQTT/TLS telemetry from the Pi over its normal
  outbound internet connection.

For a direct xrdp session, the usual client target is the Pi's Tailscale
address and TCP port 3389, for example `100.x.y.z:3389`, or the corresponding
MagicDNS name. The exact address is obtained on the Pi with:

```shell
tailscale ip -4
```

The browser-facing Flask service can instead be published with Tailscale Serve
as described below. This keeps Flask on localhost while allowing multiple
authorized Tailscale devices to reach its tailnet-only HTTPS URL.

On the Raspberry Pi, xrdp is normally managed as an operating-system service.
After the service has been installed and configured, its state can be checked
without changing it:

```shell
systemctl status xrdp --no-pager
sudo ss -lntp | grep 3389
```

The listener should be reachable through the intended Tailscale policy and host
firewall, not necessarily only through the Tailscale interface at the socket
level. Test the actual RDP login from an authorized remote device as a separate
user with appropriate permissions.

## Recommended deployment

### Same site as the PLC

Install Tailscale on the logger host for remote administration. Keep the PLC on
its private LAN and set the normal PLC address:

```dotenv
PLC_IP=192.168.50.10
PLC_PORT=502
```

The PLC does not need Tailscale when the logger and PLC are on the same LAN.
Restrict the Tailscale policy so remote users can reach the logger's
administration service, not every device on the PLC LAN.

### PLC behind a remote site gateway

If the logger is not on the same LAN as the PLC, use a Tailscale subnet router
at the PLC site. The router runs Tailscale and advertises only the PLC subnet.
The logger can then use the PLC's LAN address through the approved route.

Example topology:

```text
Tailscale logger  ──►  Tailscale subnet router  ──►  PLC
                         advertises 192.168.50.0/24
```

For a Linux subnet router, the general setup is:

```shell
# Enable IPv4 and IPv6 forwarding according to the host's firewall policy.
sudo tailscale set --advertise-routes=192.168.50.0/24
```

Then approve the route in the Tailscale admin console and add a least-privilege
access rule. The route approval and the access rule are separate controls.
Linux is often a good subnet-router host for a production site because it can use
kernel-mode forwarding; use the current Tailscale documentation for the target
operating system.

On a Tailscale node that needs to consume an advertised subnet route, Linux may
also need route acceptance enabled:

```shell
sudo tailscale set --accept-routes
```

Do not enable an exit node merely to reach the PLC. An exit node changes the
path for general internet traffic; a subnet route is the narrower solution.
AWS IoT should normally use the logger host's normal outbound internet path.

## Tailscale access policy

Tailscale's current guidance recommends grants for new policy configurations.
Use a restricted policy that allows only the logger to reach the PLC's Modbus
port and only authorized operators to reach the logger's administration port.
The following is an illustrative starting point, not a production policy:

```json
{
  "grants": [
    {
      "src": ["tag:pi5-host"],
      "dst": ["192.168.50.10"],
      "ip": ["tcp:502"]
    },
    {
      "src": ["group:operators"],
      "dst": ["tag:pi5-host"],
      "ip": ["tcp:22"]
    },
    {
      "src": ["group:operators"],
      "dst": ["tag:pi5-host"],
      "ip": ["tcp:3389"]
    },
    {
      "src": ["group:flask-users"],
      "dst": ["tag:pi5-host"],
      "ip": ["tcp:5000"]
    }
  ]
}
```

Here `tag:pi5-host` represents the Raspberry Pi 5 edge host, TCP/502 is the
PLC Modbus route, TCP/3389 is xrdp, and TCP/5000 is direct Flask access. If
Flask is published with Tailscale Serve, use the corresponding tailnet-only
Serve policy instead of exposing port 5000 directly. Adapt the selectors to
the actual tailnet, use a tag for the unattended Pi, and test the policy before
applying it. If Tailscale SSH is used instead of ordinary SSH, add the
corresponding Tailscale SSH rule and follow the Tailscale SSH documentation. Do
not rely on the default allow-all policy for a production logger.

Avoid these practices:

- Do not expose the PLC's entire subnet to every tailnet user.
- Do not use Tailscale Funnel or a public port forward for Modbus TCP, xrdp,
  or the Flask service.
- Restrict the host firewall as well as Tailscale policy: a service bound to
  `0.0.0.0` can still be reachable from the local LAN.
- Do not put Tailscale auth keys, tailnet tokens, or generated device keys in
  this repository, `.env`, or support messages.
- Do not use a user's personal account as the only identity for an unattended
  production logger when tagged, renewable device authentication is available.

## Remote access

A remote administrator can use Tailscale to reach the Raspberry Pi for:

- the Flask UI/API from multiple authorized devices;
- xrdp remote desktop on TCP/3389;
- SSH or Tailscale SSH;
- service status and log inspection;
- configuration updates;
- controlled commissioning with `--once`.

Prefer Tailscale SSH or an existing, tightly restricted administrative service.
Restrict the destination to the logger host and the required port. The logger's
Modbus client does not need to listen on a Tailscale address; it only needs to
reach the configured `PLC_IP` and `PLC_PORT`.

Enable MFA, device approval, key-expiry/offboarding procedures, and audit
logging according to the deployment's requirements. Remove old devices and
users from the tailnet when they are no longer needed.

## Flask application access

A separate Flask UI or API can be made available to multiple authorized devices
over the same Tailscale network. This is a companion service pattern; this
repository does not currently include a Flask application or start one
automatically.

The simplest private setup is to keep Flask bound to localhost and let
Tailscale Serve publish it only inside the tailnet:

```text
Authorized Tailscale devices
          |
          | HTTPS through Tailscale Serve
          v
Flask/Waitress on 127.0.0.1:5000
```

For example, after starting the Flask application on port 5000, the Tailscale
host can run:

```shell
tailscale serve 5000
```

Tailscale Serve provides a tailnet-only HTTPS URL using the node's MagicDNS
name. It does not make the service public; do not use Tailscale Funnel for a
private dashboard. The exact URL is printed by the command and should be shared
only with authorized devices.

If direct TCP access is required instead, bind the Flask service to the
host's Tailscale address (or carefully firewall a listener bound to all
interfaces) and restrict the tailnet policy to the Flask port. Do not use
`127.0.0.1` for a service that remote devices must reach directly, and do not
open the port through a router. An illustrative grant is:

```json
{
  "grants": [
    {
      "src": ["group:flask-users"],
      "dst": ["tag:flask"],
      "ip": ["tcp:5000"]
    }
  ]
}
```

Tailscale's network policy controls which devices can reach the service, but it
is not a replacement for application authentication. Use normal Flask login,
authorization, CSRF protection, and secure secret handling for a dashboard that
can change PLC or logger settings. If the application uses Tailscale Serve,
configure proxy-header handling only for the trusted local proxy and validate
the deployment's host and scheme settings.

For a real deployment, run Flask through a production WSGI server such as
Waitress on Windows or Gunicorn on Linux rather than the Flask development
server. Keep the Flask service separate from the PLC logger process, bind it to
localhost when using Tailscale Serve, and restrict its logs and configuration
files in the same way as the logger's local secrets.

## AWS IoT configuration

The existing AWS IoT settings remain valid when Tailscale is enabled:

- `AWS_IOT_ENDPOINT` is the AWS account's data endpoint.
- `AWS_IOT_PORT` is normally `8883` for MQTT over TLS.
- The CA, client certificate, and private key stay outside Git.
- The AWS IoT policy limits the logger to its required topic actions.
- Tailscale ACLs do not grant or revoke AWS IoT permissions.

Do not replace AWS IoT TLS with a Tailscale-only channel. Tailscale protects
the operator/site-to-logger path; AWS IoT TLS authenticates the logger to AWS
and protects the cloud leg.

## Configuration examples

If the PLC itself is a Tailscale node, its Tailscale address can be used:

```dotenv
PLC_IP=100.x.y.z
PLC_PORT=502
```

If the PLC is behind a site subnet router, use its private LAN address and the
approved route instead:

```dotenv
PLC_IP=192.168.50.10
PLC_PORT=502
```

The application does not need a Tailscale SDK, auth key, or special library.
`PLC_IP` is simply the address reachable from the logger host. Keep Tailscale
routing and authorization configured on the operating system or gateway, not in
the Python process.

## Verification

Run these checks from the appropriate Tailscale nodes, after the site network
and ACLs have been reviewed:

```powershell
tailscale status
tailscale ip -4
tailscale ping <logger-or-gateway>
Test-NetConnection <PLC_IP> -Port 502
```

`Test-NetConnection` is a live network test and should not be run against a PLC
without approval. The application-only configuration check is offline:

```powershell
python modbus_aws_logger.py --check-config
```

Only after connectivity and credentials have been verified should a controlled
one-sample run be considered:

```powershell
python modbus_aws_logger.py --once
```

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Tailscale nodes cannot reach each other | `tailscale status`, device approval, and the tailnet policy. |
| Logger cannot reach the PLC | Subnet route approval, accepted routes, PLC address, firewall, and TCP port 502. |
| `tailscale ping` works but Modbus fails | Confirm the destination is the PLC/subnet address and that TCP/502 is allowed. |
| Remote admin works but the PLC does not | Check that the logger is using the routed LAN address, not an unrelated local address. |
| AWS IoT fails while Tailscale works | Check DNS, outbound TCP/8883, AWS certificate paths, endpoint, and AWS IoT policy; do not debug this through the PLC route. |

## Official references

- [Tailscale subnet routers](https://tailscale.com/kb/1019/subnets)
- [Tailscale access controls and grants](https://tailscale.com/kb/1393/access-control)
- [Tailscale Serve](https://tailscale.com/kb/1242/tailscale-serve)
- [xrdp open-source project](https://github.com/neutrinolabs/xrdp)
- [Tailscale tags for non-user devices](https://tailscale.com/kb/1068/acl-tags)
- [AWS IoT device protocols and ports](https://docs.aws.amazon.com/iot/latest/developerguide/protocols.html)
- [AWS IoT MQTT](https://docs.aws.amazon.com/iot/latest/developerguide/mqtt.html)
