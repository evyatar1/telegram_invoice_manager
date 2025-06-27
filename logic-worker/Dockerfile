FROM python:3.11-slim-buster

WORKDIR /worker

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    make \
    swig \
    python3-dev \
    tesseract-ocr \
    tesseract-ocr-eng \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY ./logic-worker/requirements.txt ./
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY ./logic-worker ./logic-worker
COPY ./shared ./shared
COPY wait-for-it.sh /wait-for-it.sh
RUN chmod +x /wait-for-it.sh

# Set PYTHONPATH to include /worker so shared is visible
ENV PYTHONPATH="${PYTHONPATH}:/worker"

# Keep working directory at /worker to avoid import issues
WORKDIR /worker

# Start the application
ENTRYPOINT ["/wait-for-it.sh", "broker:9092", "--", "python", "-m", "logic-worker.worker.main"]
