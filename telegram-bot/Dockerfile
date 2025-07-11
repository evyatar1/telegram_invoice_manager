# Use an official Python runtime as a parent image
FROM python:3.9-slim-buster

# Set the working directory in the container
WORKDIR /app/bot

# Install system dependencies for psycopg2-binary (if not already present)
# This helps with potential issues with database drivers
RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy the shared directory to /app (one level up from /app/bot)
# This makes it accessible as 'shared' when /app is added to PYTHONPATH
COPY ./shared /app/shared

# Copy the bot directory into the container
COPY ./telegram-bot/bot /app/bot

# Install any needed packages specified in requirements.txt
# Assuming requirements.txt is in the bot directory
COPY ./telegram-bot/requirements.txt /app/bot/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Add /app to PYTHONPATH so Python can find the 'shared' module
ENV PYTHONPATH=/app:$PYTHONPATH

# Run main.py when the container launches
# Use 'python -u' for unbuffered output, which helps with real-time logging in Docker
CMD ["python", "-u", "main.py"]
