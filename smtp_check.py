import smtplib
import socket
import ssl
import time
import dns.resolver
import sys

# Global flag for detailed output
detailed_output = False


def get_mx_records(domain):
    """
    Resolve MX records for the given domain.
    """
    try:
        mx_records = dns.resolver.resolve(domain, 'MX')
        return sorted([(r.preference, str(r.exchange).rstrip('.')) for r in mx_records])
    except Exception as e:
        if detailed_output:
            print(f"Error retrieving MX records for {domain}: {e}")
        return []


def test_smtp_tls(host):
    """
    Test SMTP server for STARTTLS support.
    """
    try:
        if detailed_output:
            print(f"\nConnecting to {host} on port 25...")
        with smtplib.SMTP(host, 25, timeout=10) as smtp:
            smtp.set_debuglevel(1 if detailed_output else 0)  # Enable detailed debugging if requested
            smtp.ehlo()  # Send EHLO to greet the server
            
            # Check if the server supports STARTTLS
            if "starttls" in smtp.esmtp_features:
                if detailed_output:
                    print("STARTTLS supported. Initiating handshake...")
                context = ssl.create_default_context()
                smtp.starttls(context=context)  # Start TLS encryption
                smtp.ehlo()  # Re-greet the server after STARTTLS
                if detailed_output:
                    print("TLS handshake successful. Server is secure.")
                return "OK - STARTTLS supported and handshake successful"
            else:
                return "FAILED - STARTTLS not supported"
    except Exception as e:
        if detailed_output:
            print(f"Error during STARTTLS test: {e}")
        return "FAILED - STARTTLS test failed"


def test_open_relay(host):
    """
    Test if the SMTP server is an open relay.
    """
    try:
        if detailed_output:
            print(f"\nTesting if {host} is an open relay...")
        with smtplib.SMTP(host, 25, timeout=10) as smtp:
            smtp.ehlo()
            
            # Attempt to relay an email
            smtp.mail("test@example.com")  # Fake sender
            code, message = smtp.rcpt("nonexistent@external-domain.com")  # Fake external recipient
            
            if code == 250:
                if detailed_output:
                    print("RCPT TO accepted. Attempting to send data...")
                try:
                    smtp.data("Subject: Test Relay\n\nThis is a relay test.")
                    return "FAILED - Server may be an open relay (allowed email relay transaction)"
                except smtplib.SMTPException:
                    return "OK - Server is not an open relay (transaction rejected)"
            else:
                return "OK - Server is not an open relay (RCPT TO rejected)"
    except smtplib.SMTPRecipientsRefused:
        return "OK - Server is not an open relay (RCPT TO refused)"
    except Exception as e:
        if detailed_output:
            print(f"Error during open relay test: {e}")
        return "FAILED - Error during open relay test"


def check_smtp_server(host):
    """
    Perform SMTP checks on a given server (IP or FQDN).
    """
    results = {}

    # Check Reverse DNS and Valid Hostname
    try:
        resolved_host = socket.gethostbyaddr(host)
        results["Reverse DNS Mismatch"] = f"OK - {host} resolves to {resolved_host[0]}"
        results["Valid Hostname"] = "OK - Reverse DNS is a valid Hostname"
    except socket.herror:
        results["Reverse DNS Mismatch"] = f"FAILED - Could not resolve {host}"
        results["Valid Hostname"] = "FAILED - Reverse DNS is not valid"

    # Check SMTP Banner and Connection Time
    try:
        start_time = time.time()
        with smtplib.SMTP(host, 25, timeout=10) as smtp:
            smtp.set_debuglevel(0 if not detailed_output else 1)
            banner = smtp.ehlo()[1].decode().replace("\n", "\n  ")  # Format banner for cleaner output
            connection_time = time.time() - start_time
            results["Connection Time"] = f"OK - {connection_time:.3f} seconds - Good on Connection time" if connection_time < 1 else f"WARNING - {connection_time:.3f} seconds - Slow Connection time"
            
            # Check Banner matches Reverse DNS
            if "resolved_host" in locals() and resolved_host[0] in banner:
                results["SMTP Banner Check"] = f"OK\n  Reverse DNS matches SMTP Banner ({resolved_host[0]})\n  {banner.strip()}"
            else:
                results["SMTP Banner Check"] = f"WARNING - Reverse DNS does not match SMTP Banner\n  {banner.strip()}"
    except Exception as e:
        results["Connection"] = f"FAILED - Could not connect to server: {e}"

    # Check STARTTLS
    results["STARTTLS"] = test_smtp_tls(host)

    # Check Open Relay
    results["Open Relay"] = test_open_relay(host)

    # Print results
    for check, result in results.items():
        if detailed_output or "FAILED" in result or "WARNING" in result or not detailed_output:
            print(f"{check}: {result}")


if __name__ == "__main__":
    # Check for the detailed output flag
    if len(sys.argv) > 1 and sys.argv[1] == "-showerrors":
        detailed_output = True

    user_input = input("Enter the FQDN, domain name, or IP of the SMTP server: ").strip()

    # Determine if the input is a domain or IP/FQDN
    try:
        socket.inet_aton(user_input)  # Check if input is an IP address
        servers = [(10, user_input)]  # Assume as a single server with priority 10
    except socket.error:
        # Assume domain name, fetch MX records
        servers = get_mx_records(user_input)

    if not servers:
        print(f"No valid SMTP servers found for {user_input}.")
    else:
        for priority, server in servers:
            print(f"\nTesting server: {server} (priority {priority})")
            check_smtp_server(server)
