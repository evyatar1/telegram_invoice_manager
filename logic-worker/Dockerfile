#
## logic-worker/Dockerfile
#FROM python:3.11-slim-buster
#
#WORKDIR /worker
#
## Install system dependencies
## These are often needed by image processing libraries like OpenCV (used by PaddleOCR)
## Removed tesseract-ocr as paddleocr is used for OCR.
#RUN apt-get update && \
#    apt-get install -y --no-install-recommends \
#    build-essential \
#    gcc \
#    make \
#    swig \
#    python3-dev \
#    libgl1-mesa-glx \
#    libglib2.0-0 \
#    libsm6 \
#    libxext6 \
#    libxrender-dev \
#    # Clean up apt cache to reduce image size
#    && rm -rf /var/lib/apt/lists/*
#
## Install Python dependencies from requirements.txt
## Copy requirements.txt first to leverage Docker's caching
#COPY ./logic-worker/requirements.txt .
#RUN pip install --upgrade pip && \
#    pip install --no-cache-dir -r requirements.txt
#
## --- IMPORTANT: Pre-download PaddleOCR models during build time ---
## This step ensures that the large OCR models are downloaded and cached
## within the Docker image itself, preventing repeated downloads at runtime.
## This significantly speeds up the worker's startup and first-time processing.
## The 'lang' parameter should match the language models you intend to use.
#RUN python -c "from paddleocr import PaddleOCR; ocr = PaddleOCR(use_angle_cls=True, lang='en'); print('PaddleOCR models pre-downloaded successfully.');"
#
## Copy source code
#COPY ./logic-worker ./logic-worker
#COPY ./shared ./shared
#COPY wait-for-it.sh /wait-for-it.sh
#RUN chmod +x /wait-for-it.sh
#
## Set PYTHONPATH to include /worker so shared is visible
#ENV PYTHONPATH="${PYTHONPATH}:/worker"
#
## Keep working directory at /worker to avoid import issues
#WORKDIR /worker
#
## Start the application
#ENTRYPOINT ["/wait-for-it.sh", "broker:9092", "--", "python", "-m", "logic-worker.worker.main"]
#





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