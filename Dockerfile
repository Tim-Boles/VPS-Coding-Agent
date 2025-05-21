# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Install system dependencies that might be needed by some Python packages
# (e.g., for cryptography, which can be a dependency of other packages)
# For a simple app like this, it might not be strictly necessary, but good practice.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy the requirements file into the container
COPY requirements.txt .

# Install Python dependencies
# Using --no-cache-dir to reduce image size
# Using --default-timeout to prevent timeouts on slow networks if downloading many packages
RUN pip install --no-cache-dir --default-timeout=100 -r requirements.txt

# Copy the rest of the application code into the container
COPY . .

# Expose the port the app runs on (Gunicorn will bind to this port inside the container)
EXPOSE 5000

# Command to run the application using Gunicorn WSGI server
# Gunicorn is a production-ready WSGI server.
# Bind to 0.0.0.0 to make it accessible from outside the container.
# `app:app` means Gunicorn should look for an object named `app` in a file named `app.py`.
# `workers` can be adjusted based on your VPS's CPU cores (e.g., 2 * num_cores + 1)
CMD ["gunicorn", "--workers", "2", "--bind", "0.0.0.0:5000", "app:app"]