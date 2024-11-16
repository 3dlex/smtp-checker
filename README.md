Certainly! Below is the complete content for your `README.md` file, formatted correctly:

```markdown
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
   ```

2. Install required dependencies:
   ```bash
   pip install dnspython
   ```

## Usage

Run the script:
```bash
python3 smtp_check.py
```

Verbose mode with detailed logs:
```bash
python3 smtp_check.py -showerrors
```

## Example Output

### Normal Output
```plaintext
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
```

### Verbose Output
```bash
python3 smtp_check.py -showerrors

Connecting to mail.example.com on port 25...
send: 'ehlo example.com\r\n'
reply: ...
STARTTLS supported. Initiating handshake...
```

## License

This project is licensed under the MIT License.
