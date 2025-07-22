from flask import Flask, request, jsonify, render_template
import smtplib
import socket
import ssl
import time
import dns.resolver
import os
import sys

# Flask app initialization
app = Flask(__name__)

# Helper functions (same as CLI version)
def get_mx_records(domain_or_ip):
    try:
        # Check if input is an IP address
        socket.inet_aton(domain_or_ip)  # Validates IPv4 address
        return [(0, domain_or_ip)]  # Treat IP as a single "MX record" with priority 0
    except socket.error:
        # If not an IP, try to resolve as a domain
        try:
            mx_records = dns.resolver.resolve(domain_or_ip, 'MX')
            return sorted([(r.preference, str(r.exchange).rstrip('.')) for r in mx_records])
        except Exception as e:
            return {"error": f"Error retrieving MX records for {domain_or_ip}: {e}"}

def test_smtp_tls(host):
    try:
        with smtplib.SMTP(host, 25, timeout=10) as smtp:
            smtp.ehlo()
            if "starttls" in smtp.esmtp_features:
                context = ssl.create_default_context()
                smtp.starttls(context=context)
                smtp.ehlo()
                return "OK - STARTTLS supported and handshake successful"
            else:
                return "FAILED - STARTTLS not supported"
    except Exception as e:
        return f"FAILED - STARTTLS test failed: {e}"

def test_open_relay(host):
    try:
        with smtplib.SMTP(host, 25, timeout=10) as smtp:
            smtp.ehlo()
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

def check_smtp_server(host, show_errors=False):
    results = {}
    details = {}
    try:
        resolved_host = socket.gethostbyaddr(host)
        results["Reverse DNS"] = f"OK - {host} resolves to {resolved_host[0]}"
        results["Hostname"] = "OK - Reverse DNS is valid"
        if show_errors:
            details["Reverse DNS"] = f"{resolved_host[0]} (IP: {resolved_host[2][0]})"
    except socket.herror:
        results["Reverse DNS"] = f"FAILED - Could not resolve {host}"
        results["Hostname"] = "FAILED - Reverse DNS not valid"

    results["STARTTLS"] = test_smtp_tls(host)
    results["Open Relay"] = test_open_relay(host)

    if show_errors:
        details["STARTTLS"] = "STARTTLS handshake successful." if "OK" in results["STARTTLS"] else results["STARTTLS"]
        details["Open Relay"] = "Not an open relay." if "OK" in results["Open Relay"] else results["Open Relay"]

    if show_errors:
        results["Details"] = details

    return results

# Flask routes
@app.route("/", methods=["GET", "POST"])
def home():
    if request.method == "POST":
        domain = request.form.get("domain")
        show_errors = request.form.get("show_errors") == "on"  # Check if checkbox is selected

        if not domain:
            return render_template("index.html", error="Please enter a domain.")
        
        mx_records = get_mx_records(domain)
        if "error" in mx_records:
            return render_template("index.html", error=mx_records["error"])
        
        results = {}
        for priority, host in mx_records:
            results[host] = check_smtp_server(host, show_errors=show_errors)
        
        return render_template("index.html", results=results, domain=domain, show_errors=show_errors)
    
    return render_template("index.html")

@app.route("/check", methods=["GET"])
def check_domain():
    domain = request.args.get("domain")
    show_errors = request.args.get("show_errors") == "true"  # Support for detailed output in API

    if not domain:
        return jsonify({"error": "Please provide a 'domain' parameter"}), 400
    
    mx_records = get_mx_records(domain)
    if "error" in mx_records:
        return jsonify(mx_records), 500

    results = {}
    for priority, host in mx_records:
        results[host] = check_smtp_server(host, show_errors=show_errors)
    return jsonify(results)

# CLI entry point
if __name__ == "__main__":
    script_path = os.path.abspath(__file__)
    script_name = os.path.basename(script_path)

    if len(sys.argv) > 1 and sys.argv[1] == "runserver":
        print(f"Starting Flask server using script: {script_name}")
        print(f"Script located at: {script_path}")
        app.run(host="0.0.0.0", port=5000)
    else:
        print(f"Running SMTP Checker CLI using script: {script_name}")
        domain_or_ip = input("Enter the FQDN, domain name, or IP of the SMTP server: ").strip()
        mx_records = get_mx_records(domain_or_ip)

        if "error" in mx_records:
            print(mx_records["error"])
        else:
            for priority, host in mx_records:
                print(f"\nTesting server: {host} (priority {priority})")
                results = check_smtp_server(host)
                for check, result in results.items():
                    print(f"{check}: {result}")
