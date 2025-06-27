# telegram-bot/Dockerfile
FROM python:3.11-slim-buster

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements.txt and install Python dependencies from their path relative to project root
COPY ./telegram-bot/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the bot code (from ./telegram-bot to /app)
COPY ./telegram-bot .

# Copy the shared directory from the project root
COPY ./shared ./shared

# --- ADD THIS LINE ---
ENV PYTHONPATH="/app:${PYTHONPATH}"
# ---------------------

# Copy wait-for-it.sh from the project root
COPY wait-for-it.sh /wait-for-it.sh
RUN chmod +x /wait-for-it.sh

# Command to run the bot, waiting for DB and Kafka
ENTRYPOINT ["/wait-for-it.sh", "db:5432", "broker:9092", "--", "python", "bot/main.py"]

