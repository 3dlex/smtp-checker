# smtp-checker
Python tool for testing SMTP servers for STARTTLS, open relay, and other configurations

# SMTP Checker

This Python script tests SMTP servers for various configurations, including:
- STARTTLS support
- Reverse DNS and hostname validation
- SMTP banner matching
- Connection performance
- Open relay testing

## Features
- Checks if the server supports STARTTLS and performs a secure handshake.
- Tests if the server acts as an open relay.
- Verifies reverse DNS resolution and hostname validity.
- Measures SMTP connection and transaction times.

## Requirements

- Python 3.6 or later
- Required Python packages:
  - `dnspython`

## Installation

1. Clone this repository:
   ```bash
   git clone https://github.com/3dlex/smtp-checker.git
   cd smtp-checker

2. Install required dependencies:
   pip install dnspython

3. Basic usage:
   python3 smtp_check.py

4. Verbose mode with detailed logs:
   python3 smtp_check.py -showerrors

Normal output:
Enter the FQDN, domain name, or IP of the SMTP server: example.com

Testing server: mail.example.com (priority 10)
Reverse DNS Mismatch: OK - mail.example.com resolves to mail.example.com
Valid Hostname: OK - Reverse DNS is a valid Hostname
Connection Time: OK - 0.472 seconds - Good on Connection time
SMTP Banner Check: OK
  Reverse DNS matches SMTP Banner (mail.example.com)
  PIPELINING
  SIZE 152428800
  ETRN
  STARTTLS
  ENHANCEDSTATUSCODES
  8BITMIME
  DSN
  CHUNKING
STARTTLS: OK - STARTTLS supported and handshake successful
Open Relay: OK - Server is not an open relay (RCPT TO refused)

Verbose output:
python3 smtp_check.py -showerrors
...
Connecting to mail.example.com on port 25...
send: 'ehlo example.com\r\n'
reply: ...
