#!/usr/bin/env python3
"""
SMTP server checker (CLI only, standard library only).

Runs these checks against every MX host for a domain, or against a
single host/IP:

  - Reverse DNS
  - Hostname (reverse DNS valid)
  - EHLO greeting accepted
  - STARTTLS support and handshake
  - Certificate trusted and valid for the MX hostname
  - Open relay

Usage:
  smtp_checker.py example.com
  smtp_checker.py 203.0.113.10 --details
  smtp_checker.py example.com --json
  smtp_checker.py example.com --helo mail.mydomain.com
  smtp_checker.py                  # prompts for the target

EHLO name:
  Many servers reject a greeting that is not a real, resolvable FQDN.
  The name is chosen in this order:
    1. --helo NAME
    2. Postfix's myhostname (postconf -h myhostname), if it is an FQDN
    3. the system FQDN, if it contains a dot
    4. smtplib's default (falls back to an IP literal like [192.0.2.1])

Connections per host:
  One for the greeting, STARTTLS and certificate, one for the open
  relay test. If the greeting is refused, the remaining checks are
  skipped, so a refused greeting costs a single connection. If the
  certificate chain is not trusted, one extra connection is made to
  confirm that the TLS handshake itself works.

Exit codes:
  0  all checks OK
  1  one or more checks FAILED
  2  no target given, or MX lookup failed

Requires: nothing outside the Python standard library.
MX lookups use the nameservers listed in /etc/resolv.conf.
"""

import argparse
import ipaddress
import json
import os
import smtplib
import socket
import ssl
import struct
import subprocess
import sys


SMTP_PORT = 25
SMTP_TIMEOUT = 10


# ---------------------------------------------------------------------------
# Minimal MX resolver (replaces dnspython)
# ---------------------------------------------------------------------------

RESOLV_CONF = "/etc/resolv.conf"
DNS_PORT = 53
DNS_TIMEOUT = 5
DNS_TYPE_MX = 15
DNS_CLASS_IN = 1

DNS_RCODES = {
    1: "FORMERR (format error)",
    2: "SERVFAIL (server failure)",
    3: "NXDOMAIN (domain does not exist)",
    4: "NOTIMP (not implemented)",
    5: "REFUSED (query refused)",
}


def _read_nameservers(path=RESOLV_CONF):
    servers = []
    try:
        with open(path) as handle:
            for line in handle:
                parts = line.split()
                if len(parts) >= 2 and parts[0] == "nameserver":
                    servers.append(parts[1])
    except OSError:
        pass
    return servers or ["127.0.0.1"]


def _encode_qname(domain):
    encoded = b""
    for label in domain.rstrip(".").split("."):
        raw = label.encode("idna")
        if not 1 <= len(raw) <= 63:
            raise ValueError(f"invalid DNS label in '{domain}'")
        encoded += bytes([len(raw)]) + raw
    return encoded + b"\x00"


def _read_name(data, offset):
    """Decode a (possibly compressed) DNS name. Returns (name, next_offset)."""
    labels = []
    next_offset = None
    jumps = 0
    while True:
        length = data[offset]
        if length & 0xC0 == 0xC0:
            # Compression pointer
            if next_offset is None:
                next_offset = offset + 2
            offset = ((length & 0x3F) << 8) | data[offset + 1]
            jumps += 1
            if jumps > 50:
                raise ValueError("DNS compression loop in response")
            continue
        offset += 1
        if length == 0:
            break
        labels.append(data[offset:offset + length].decode("ascii", "replace"))
        offset += length
    if next_offset is None:
        next_offset = offset
    return ".".join(labels), next_offset


def _recv_exact(sock, count):
    data = b""
    while len(data) < count:
        chunk = sock.recv(count - len(data))
        if not chunk:
            raise OSError("DNS server closed the TCP connection early")
        data += chunk
    return data


def _query_tcp(server, family, packet):
    with socket.socket(family, socket.SOCK_STREAM) as sock:
        sock.settimeout(DNS_TIMEOUT)
        sock.connect((server, DNS_PORT))
        sock.sendall(struct.pack("!H", len(packet)) + packet)
        (length,) = struct.unpack("!H", _recv_exact(sock, 2))
        return _recv_exact(sock, length)


def _query_server(server, packet, query_id):
    family = socket.AF_INET6 if ":" in server else socket.AF_INET
    with socket.socket(family, socket.SOCK_DGRAM) as sock:
        sock.settimeout(DNS_TIMEOUT)
        sock.connect((server, DNS_PORT))
        sock.send(packet)
        while True:
            response = sock.recv(4096)
            if len(response) >= 12 and response[:2] == query_id:
                break
    flags = struct.unpack("!H", response[2:4])[0]
    if flags & 0x0200:
        # Truncated over UDP, repeat over TCP
        response = _query_tcp(server, family, packet)
    return response


def _parse_mx_response(response):
    flags, qdcount, ancount = struct.unpack("!HHH", response[2:8])
    rcode = flags & 0x000F
    if rcode != 0:
        return rcode, []

    offset = 12
    for _ in range(qdcount):
        _, offset = _read_name(response, offset)
        offset += 4  # QTYPE + QCLASS

    records = []
    for _ in range(ancount):
        _, offset = _read_name(response, offset)
        rtype, _rclass, _ttl, rdlength = struct.unpack(
            "!HHIH", response[offset:offset + 10]
        )
        offset += 10
        if rtype == DNS_TYPE_MX:
            (preference,) = struct.unpack("!H", response[offset:offset + 2])
            exchange, _ = _read_name(response, offset + 2)
            records.append((preference, exchange))
        offset += rdlength
    return rcode, records


def resolve_mx(domain):
    """Return a list of (preference, exchange) for domain, or raise."""
    query_id = os.urandom(2)
    packet = (
        query_id
        + struct.pack("!HHHHH", 0x0100, 1, 0, 0, 0)  # RD set, one question
        + _encode_qname(domain)
        + struct.pack("!HH", DNS_TYPE_MX, DNS_CLASS_IN)
    )

    last_error = None
    for server in _read_nameservers():
        try:
            response = _query_server(server, packet, query_id)
            rcode, records = _parse_mx_response(response)
        except (OSError, ValueError, IndexError, struct.error) as e:
            last_error = f"nameserver {server}: {e}"
            continue

        if rcode == 3:
            raise LookupError(DNS_RCODES[3])
        if rcode != 0:
            last_error = f"nameserver {server}: {DNS_RCODES.get(rcode, f'rcode {rcode}')}"
            continue
        if not records:
            raise LookupError("no MX records found")
        return records

    raise LookupError(last_error or "no nameservers available")


# ---------------------------------------------------------------------------
# EHLO name
# ---------------------------------------------------------------------------

def default_helo():
    """Pick an FQDN to greet with, or None to use smtplib's default."""
    try:
        name = subprocess.run(
            ["postconf", "-h", "myhostname"],
            capture_output=True, text=True, timeout=5,
        ).stdout.strip()
        if "." in name:
            return name
    except (OSError, subprocess.SubprocessError):
        pass

    name = socket.getfqdn()
    if "." in name:
        return name
    return None


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------

def get_mx_records(domain_or_ip):
    try:
        # Check if input is an IP address
        socket.inet_aton(domain_or_ip)  # Validates IPv4 address
        return [(0, domain_or_ip)]  # Treat IP as a single "MX record" with priority 0
    except socket.error:
        # If not an IP, try to resolve as a domain
        try:
            mx_records = resolve_mx(domain_or_ip)
            return sorted([(pref, exchange.rstrip('.')) for pref, exchange in mx_records])
        except Exception as e:
            return {"error": f"Error retrieving MX records for {domain_or_ip}: {e}"}


def _reply_text(code, message):
    if isinstance(message, bytes):
        message = message.decode("utf-8", "replace")
    return f"{code} {message}".replace("\r", "").replace("\n", " | ")


STARTTLS_OK = "OK - STARTTLS supported and handshake successful"


def _safe_quit(smtp):
    if smtp is None:
        return
    try:
        smtp.quit()
    except Exception:
        pass
    smtp.close()


def _cert_names(cert):
    """Return (dns_names, ip_addresses) a certificate is issued for."""
    san = cert.get("subjectAltName", ())
    dns_names = [value for kind, value in san if kind == "DNS"]
    ip_addresses = [value for kind, value in san if kind == "IP Address"]
    if not dns_names and not ip_addresses:
        # Very old certificates carry the name only in the subject
        for rdn in cert.get("subject", ()):
            for key, value in rdn:
                if key == "commonName":
                    dns_names.append(value)
    return dns_names, ip_addresses


def _name_matches(pattern, host):
    pattern = pattern.lower().rstrip(".")
    host = host.lower().rstrip(".")
    if pattern == host:
        return True
    if pattern.startswith("*."):
        # A wildcard covers exactly one left-most label
        first_label, _, rest = host.partition(".")
        return bool(first_label) and rest == pattern[2:]
    return False


def _certificate_result(host, cert):
    """Hostname check for a certificate whose chain already verified."""
    dns_names, ip_addresses = _cert_names(cert)
    try:
        target_ip = ipaddress.ip_address(host)
    except ValueError:
        target_ip = None

    if target_ip is not None:
        matched = False
        for value in ip_addresses:
            try:
                if ipaddress.ip_address(value) == target_ip:
                    matched = True
            except ValueError:
                continue
    else:
        matched = any(_name_matches(name, host) for name in dns_names)

    if matched:
        return f"OK - Certificate is trusted and valid for {host}"

    names = dns_names + ip_addresses
    shown = ", ".join(names[:8]) or "no names"
    if len(names) > 8:
        shown += f" (+{len(names) - 8} more)"
    return (
        f"FAILED - Certificate is trusted but not valid for {host}; "
        f"it is valid for: {shown}"
    )


def _unverified_handshake(host, helo=None):
    """Confirm STARTTLS works when the certificate cannot be verified."""
    smtp = None
    try:
        smtp = smtplib.SMTP(host, SMTP_PORT, timeout=SMTP_TIMEOUT, local_hostname=helo)
        smtp.ehlo()
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        smtp.starttls(context=context)
        smtp.ehlo()
        return STARTTLS_OK
    except Exception as e:
        return f"FAILED - STARTTLS test failed: {e}"
    finally:
        _safe_quit(smtp)


def test_ehlo_and_tls(host, helo=None):
    """Greeting, STARTTLS and certificate on one connection.

    Returns (ehlo_result, starttls_result, certificate_result).

    The handshake verifies the certificate chain but not the hostname,
    so a working TLS session with a mismatched certificate can be
    reported as two separate results.
    """
    smtp = None
    try:
        try:
            smtp = smtplib.SMTP(host, SMTP_PORT, timeout=SMTP_TIMEOUT, local_hostname=helo)
            code, message = smtp.ehlo()
        except Exception as e:
            return (
                f"FAILED - Could not connect and greet: {e}",
                "SKIPPED - No SMTP session",
                "SKIPPED - No SMTP session",
            )

        if not 200 <= code <= 299:
            return (
                f"FAILED - Greeting as {smtp.local_hostname} rejected: {_reply_text(code, message)}",
                "SKIPPED - Greeting was rejected",
                "SKIPPED - Greeting was rejected",
            )
        ehlo_result = f"OK - Greeting accepted as {smtp.local_hostname}"

        if "starttls" not in smtp.esmtp_features:
            return (
                ehlo_result,
                "FAILED - STARTTLS not supported",
                "SKIPPED - STARTTLS not supported",
            )

        context = ssl.create_default_context()
        context.check_hostname = False  # hostname is checked separately below
        try:
            smtp.starttls(context=context)
            cert = smtp.sock.getpeercert()
            smtp.ehlo()
        except ssl.SSLCertVerificationError as e:
            cert_error = e.verify_message or str(e)
        except Exception as e:
            return (
                ehlo_result,
                f"FAILED - STARTTLS test failed: {e}",
                "SKIPPED - No TLS session",
            )
        else:
            return ehlo_result, STARTTLS_OK, _certificate_result(host, cert)
    finally:
        _safe_quit(smtp)

    # Only reached when the certificate chain is not trusted (self-signed,
    # expired, unknown issuer). Check the handshake on its own.
    return (
        ehlo_result,
        _unverified_handshake(host, helo=helo),
        f"FAILED - Certificate is not trusted: {cert_error}",
    )


def test_open_relay(host, helo=None):
    try:
        with smtplib.SMTP(host, SMTP_PORT, timeout=SMTP_TIMEOUT, local_hostname=helo) as smtp:
            code, message = smtp.ehlo()
            if not 200 <= code <= 299:
                return f"FAILED - Greeting rejected during open relay test: {_reply_text(code, message)}"
            smtp.mail("test@example.com")
            code, message = smtp.rcpt("nonexistent@external-domain.com")
            if code == 250:
                try:
                    smtp.data("Subject: Test Relay\n\nThis is a relay test.")
                    return "FAILED - Server may be an open relay"
                except smtplib.SMTPException:
                    return "OK - Server is not an open relay"
            else:
                return "OK - Server is not an open relay"
    except smtplib.SMTPRecipientsRefused:
        return "OK - Server is not an open relay"
    except Exception as e:
        return f"FAILED - Error during open relay test: {e}"


def check_smtp_server(host, show_errors=False, helo=None):
    results = {}
    details = {}
    try:
        resolved_host = socket.gethostbyaddr(host)
        results["Reverse DNS"] = f"OK - {host} resolves to {resolved_host[0]}"
        results["Hostname"] = "OK - Reverse DNS is valid"
        if show_errors:
            details["Reverse DNS"] = f"{resolved_host[0]} (IP: {resolved_host[2][0]})"
    except (socket.herror, socket.gaierror):
        results["Reverse DNS"] = f"FAILED - Could not resolve {host}"
        results["Hostname"] = "FAILED - Reverse DNS not valid"

    results["EHLO"], results["STARTTLS"], results["Certificate"] = test_ehlo_and_tls(host, helo=helo)

    if results["EHLO"].startswith("OK"):
        results["Open Relay"] = test_open_relay(host, helo=helo)
    else:
        # Do not open a second connection to a server that refused the first
        results["Open Relay"] = "SKIPPED - No accepted SMTP greeting"

    if show_errors:
        details["EHLO"] = "Greeting accepted." if results["EHLO"].startswith("OK") else results["EHLO"]
        details["STARTTLS"] = "STARTTLS handshake successful." if results["STARTTLS"].startswith("OK") else results["STARTTLS"]
        details["Certificate"] = "Certificate trusted and matches hostname." if results["Certificate"].startswith("OK") else results["Certificate"]
        details["Open Relay"] = "Not an open relay." if results["Open Relay"].startswith("OK") else results["Open Relay"]
        results["Details"] = details

    return results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Check SMTP servers for reverse DNS, EHLO, STARTTLS, certificate and open relay."
    )
    parser.add_argument(
        "target",
        nargs="?",
        help="FQDN, domain name, or IPv4 address of the SMTP server "
             "(prompts if omitted)",
    )
    parser.add_argument(
        "-H", "--helo",
        metavar="NAME",
        help="FQDN to send in EHLO (default: Postfix myhostname, "
             "then the system FQDN)",
    )
    parser.add_argument(
        "-d", "--details",
        action="store_true",
        help="include the per-check details block "
             "(same as the old 'show_errors' option)",
    )
    parser.add_argument(
        "-j", "--json",
        action="store_true",
        help="print results as JSON (same shape as the old /check endpoint)",
    )
    return parser.parse_args(argv)


def has_failure(all_results):
    for checks in all_results.values():
        for name, result in checks.items():
            if name == "Details":
                continue
            if str(result).startswith("FAILED"):
                return True
    return False


def print_text(mx_records, all_results):
    for priority, host in mx_records:
        print(f"\nTesting server: {host} (priority {priority})")
        for check, result in all_results[host].items():
            if check == "Details":
                print("Details:")
                for name, detail in result.items():
                    print(f"  {name}: {detail}")
            else:
                print(f"{check}: {result}")


def main(argv=None):
    args = parse_args(argv)

    target = args.target
    if not target:
        target = input("Enter the FQDN, domain name, or IP of the SMTP server: ").strip()
    if not target:
        print("Please enter a domain.", file=sys.stderr)
        return 2

    helo = args.helo or default_helo()
    if not args.json:
        if helo:
            print(f"EHLO name: {helo}")
        else:
            print("EHLO name: none found, using smtplib default "
                  "(use --helo to set one)")

    mx_records = get_mx_records(target)
    if isinstance(mx_records, dict) and "error" in mx_records:
        if args.json:
            print(json.dumps(mx_records, indent=2))
        else:
            print(mx_records["error"], file=sys.stderr)
        return 2

    all_results = {}
    for priority, host in mx_records:
        all_results[host] = check_smtp_server(host, show_errors=args.details, helo=helo)

    if args.json:
        print(json.dumps(all_results, indent=2))
    else:
        print_text(mx_records, all_results)

    return 1 if has_failure(all_results) else 0


if __name__ == "__main__":
    sys.exit(main())
