# api-server/Dockerfile
# Use an official Python runtime as a parent image
FROM python:3.10-bullseye

# Set the working directory in the container
WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file and install Python dependencies
# The context for build is the project root, so paths are relative to root.
COPY api-server/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY api-server/app ./app
COPY shared ./shared
COPY wait-for-it.sh /wait-for-it.sh

# Make wait-for-it.sh executable
RUN chmod +x /wait-for-it.sh

# Set PYTHONPATH to include the app directory for shared modules
ENV PYTHONPATH=/app

# Command to run the application
ENTRYPOINT ["/wait-for-it.sh", "db:5432", "--", "/wait-for-it.sh", "broker:9092", "--", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
