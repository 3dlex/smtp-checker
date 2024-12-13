### Updated `README.md`

```markdown
# SMTP Checker

SMTP Checker is a Python tool for testing SMTP servers for STARTTLS support, open relay vulnerability, and other configurations. This application can be run either from the command line or as a Flask web application, and it is now containerized for ease of deployment with Docker.

---

## Features

- Checks if the server supports STARTTLS and performs a secure handshake.
- Tests if the server acts as an open relay.
- Verifies reverse DNS resolution and hostname validity.
- Measures SMTP connection and transaction times.
- Provides both a command-line interface (CLI) and a web-based interface.

---

## Requirements

- **Python 3.9+** (for non-Docker usage)
- **Required Python packages**:
  - `dnspython`

- **Docker** (for containerized usage)

---

## Installation

### Using Docker

1. Clone the repository:
   ```bash
   git clone https://github.com/<your-username>/<your-repo>.git
   cd <your-repo>
   ```

2. Build the Docker image:
   ```bash
   docker build -t smtp-checker .
   ```

3. Run the container:
   ```bash
   docker run -d --dns=8.8.8.8 --dns=8.8.4.4 -p 5000:5000 smtp-checker
   ```

4. Access the web interface:
   - Open your browser and go to `http://localhost:5000`.

### Without Docker

1. Install dependencies:
   ```bash
   pip install dnspython
   ```

2. Run the script:
   ```bash
   python3 smtp_check.py
   ```

3. To start the Flask web app:
   ```bash
   python3 smtp_check.py runserver
   ```

---

## Usage

### Command Line
Run the script and enter the domain or IP address when prompted:
```bash
python3 smtp_check.py
```

To display detailed output, use:
```bash
python3 smtp_check.py --showerrors
```

### Web Interface
After starting the Flask app or running the Docker container:
1. Enter the domain in the web form.
2. (Optional) Check the "Show detailed output" box for additional details.

---

## Example Output

### Basic CLI Output:
```plaintext
Enter the FQDN, domain name, or IP of the SMTP server: example.com

Testing server: mail.example.com (priority 10)
Reverse DNS: OK - mail.example.com resolves to mail.example.com
Hostname: OK - Reverse DNS is valid
STARTTLS: OK - STARTTLS supported and handshake successful
Open Relay: OK - Server is not an open relay
```

### Detailed CLI Output:
```plaintext
Enter the FQDN, domain name, or IP of the SMTP server: example.com

Testing server: mail.example.com (priority 10)
Reverse DNS: OK - mail.example.com resolves to mail.example.com
Hostname: OK - Reverse DNS is valid
STARTTLS: OK - STARTTLS supported and handshake successful
Open Relay: OK - Server is not an open relay
Details:
  Reverse DNS: mail.example.com (IP: 123.456.78.90)
  STARTTLS: Handshake successful
  Open Relay: Not an open relay
```

---

## Contributing

To contribute to this project:
1. Create a branch for your feature:
   ```bash
   git checkout -b feature-name
   ```

2. Make your changes and commit them:
   ```bash
   git add .
   git commit -m "Add your message here"
   ```

3. Push your branch and open a pull request:
   ```bash
   git push -u origin feature-name
   ```

---

## License

This project is licensed under the MIT License. See the `LICENSE` file for details.
