# SMTP Checker

A command-line Python script that tests the SMTP servers for a domain. Give it a
domain and it checks every MX host; give it a hostname's IPv4 address and it
checks that one server.

It uses only the Python standard library. There is nothing to `pip install`.

## Checks

| Check | What it tests |
|---|---|
| Reverse DNS | The MX host resolves back to a hostname. |
| Hostname | The reverse DNS lookup succeeded. |
| EHLO | The server accepts the script's EHLO greeting. |
| STARTTLS | The server offers STARTTLS and the TLS handshake completes. |
| Certificate | The certificate chain is trusted and the certificate is valid for the MX hostname. |
| Open Relay | The server refuses to relay mail for an outside sender and recipient. |

STARTTLS and Certificate are reported separately. A server can have working
encryption (STARTTLS OK) while presenting a certificate issued for a different
name (Certificate FAILED). When that happens, the Certificate line lists the
names the certificate does cover.

## Requirements

- Python 3.7 or later
- Outbound access to TCP port 25
- A DNS resolver listed in `/etc/resolv.conf`

No third-party packages are required. Earlier versions needed Flask and
`dnspython`; both have been removed.

## Installation

```bash
git clone https://github.com/3dlex/smtp-checker.git
cd smtp-checker
```

## Usage

Check every MX host for a domain:

```bash
python3 smtp_checker.py example.com
```

Check a single server by IPv4 address:

```bash
python3 smtp_checker.py 203.0.113.10
```

Run with no arguments to be prompted for the target:

```bash
python3 smtp_checker.py
```

### Options

| Option | Description |
|---|---|
| `-H NAME`, `--helo NAME` | Hostname to send in the EHLO greeting. |
| `-d`, `--details` | Add a per-check details block to the output. |
| `-j`, `--json` | Print the results as JSON. |
| `-h`, `--help` | Show the help text. |

### EHLO name

Many mail servers reject a greeting that is not a real hostname resolvable in
public DNS. The script picks the EHLO name in this order:

1. The value of `--helo`, if given.
2. Postfix's `myhostname` (from `postconf -h myhostname`), if it is a fully
   qualified name.
3. The system's fully qualified hostname, if it contains a dot.
4. Python's default, which falls back to an IP literal such as `[192.0.2.1]`.

The name in use is printed at the top of each run. If you see the EHLO check
fail with a "HELO command rejected" reply, pass a name with `--helo` that
matches the reverse DNS of the machine you are running from:

```bash
python3 smtp_checker.py example.com --helo mail.yourdomain.com
```

### Exit codes

| Code | Meaning |
|---|---|
| 0 | Every check passed. |
| 1 | One or more checks failed. |
| 2 | No target was given, or the MX lookup failed. |

Checks marked `SKIPPED` do not count as failures on their own, but they only
appear after an earlier check on the same host has failed.

## Example output

### All checks passing

```plaintext
$ python3 smtp_checker.py example.com
EHLO name: mail.yourdomain.com

Testing server: mx1.example.com (priority 10)
Reverse DNS: OK - mx1.example.com resolves to mx1.example.com
Hostname: OK - Reverse DNS is valid
EHLO: OK - Greeting accepted as mail.yourdomain.com
STARTTLS: OK - STARTTLS supported and handshake successful
Certificate: OK - Certificate is trusted and valid for mx1.example.com
Open Relay: OK - Server is not an open relay
```

### Certificate issued for a different name

```plaintext
Testing server: mx1.example.com (priority 10)
Reverse DNS: OK - mx1.example.com resolves to mx31.provider.example.net
Hostname: OK - Reverse DNS is valid
EHLO: OK - Greeting accepted as mail.yourdomain.com
STARTTLS: OK - STARTTLS supported and handshake successful
Certificate: FAILED - Certificate is trusted but not valid for mx1.example.com; it is valid for: *.provider.example.net, provider.example.net
Open Relay: OK - Server is not an open relay
```

### Greeting rejected

```plaintext
Testing server: mx1.example.com (priority 10)
Reverse DNS: OK - mx1.example.com resolves to mx1.example.com
Hostname: OK - Reverse DNS is valid
EHLO: FAILED - Greeting as [192.0.2.1] rejected: 550 5.7.1 HELO command rejected
STARTTLS: SKIPPED - Greeting was rejected
Certificate: SKIPPED - Greeting was rejected
Open Relay: SKIPPED - No accepted SMTP greeting
```

### With `--details`

```plaintext
$ python3 smtp_checker.py example.com --details
EHLO name: mail.yourdomain.com

Testing server: mx1.example.com (priority 10)
Reverse DNS: OK - mx1.example.com resolves to mx1.example.com
Hostname: OK - Reverse DNS is valid
EHLO: OK - Greeting accepted as mail.yourdomain.com
STARTTLS: OK - STARTTLS supported and handshake successful
Certificate: OK - Certificate is trusted and valid for mx1.example.com
Open Relay: OK - Server is not an open relay
Details:
  Reverse DNS: mx1.example.com (IP: 192.0.2.10)
  EHLO: Greeting accepted.
  STARTTLS: STARTTLS handshake successful.
  Certificate: Certificate trusted and matches hostname.
  Open Relay: Not an open relay.
```

### With `--json`

```plaintext
$ python3 smtp_checker.py example.com --json
{
  "mx1.example.com": {
    "Reverse DNS": "OK - mx1.example.com resolves to mx1.example.com",
    "Hostname": "OK - Reverse DNS is valid",
    "EHLO": "OK - Greeting accepted as mail.yourdomain.com",
    "STARTTLS": "OK - STARTTLS supported and handshake successful",
    "Certificate": "OK - Certificate is trusted and valid for mx1.example.com",
    "Open Relay": "OK - Server is not an open relay"
  }
}
```

## How it behaves on the wire

- **Connections per host.** One connection covers the greeting, STARTTLS and
  the certificate. A second connection runs the open relay test. If the
  greeting is refused or the connection fails, the remaining checks are
  skipped and no second connection is made. If the certificate chain is not
  trusted, one extra connection confirms that the TLS handshake itself works.
- **Open relay test.** The script sends `MAIL FROM:<test@example.com>` and
  `RCPT TO:<nonexistent@external-domain.com>`. If the server accepts that
  recipient, the script goes on to submit a short test message so it can tell
  whether the server would really relay it. Only run this against servers you
  are responsible for or have permission to test.
- **MX lookups.** The script has its own small DNS client. It queries the
  `nameserver` entries in `/etc/resolv.conf` over UDP and retries over TCP if
  the reply is truncated. The `search` and `options` lines are ignored.
- **IP targets.** Only IPv4 addresses are recognised as a direct target.
  Anything else is treated as a domain and looked up for MX records.
- **Timeouts.** 10 seconds per SMTP connection and 5 seconds per DNS query.

## License

This project is licensed under the MIT License.
