# Use the official Python image
FROM python:3.9-slim

# Set the working directory
WORKDIR /app

# Install required packages for debugging
RUN apt update && apt install -y dnsutils iputils-ping

# Copy the application code into the container
COPY smtp_check.py /app/
COPY templates /app/templates/
COPY requirements.txt /app/

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose the Flask app port
EXPOSE 5000

# Command to run the Flask app
CMD ["python", "smtp_check.py", "runserver"]
