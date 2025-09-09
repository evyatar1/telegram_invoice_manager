# logic-worker/Dockerfile
# Stage 1: Build dependencies
FROM python:3.10-bullseye as builder

WORKDIR /app/builder

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
    libcairo2-dev \
    libjpeg-dev \
    libpng-dev \
    libfreetype6-dev \
    libglvnd-dev \
    libxkbcommon-x11-0 \
    libxcb-randr0 \
    libxcb-render0 \
    libxcb-shape0 \
    libxcb-xfixes0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libxrender1 && \
    rm -rf /var/lib/apt/lists/*

COPY ./logic-worker/requirements.txt ./requirements.txt

ENV PIP_DEFAULT_TIMEOUT=1000

RUN pip install --upgrade pip && \
    python3 -m venv /opt/venv && \
    /opt/venv/bin/pip install --no-cache-dir -r requirements.txt --timeout 300 --retries 10

# NEW: Add a step to explicitly check the installed python-telegram-bot version
RUN /opt/venv/bin/pip show python-telegram-bot


# Stage 2: Final image
FROM python:3.10-bullseye

# Install runtime libraries required by OpenCV (for cv2, PaddleOCR)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 && \
    rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/venv /opt/venv

WORKDIR /app

ENV PATH="/opt/venv/bin:$PATH"
ENV PYTHONPATH="/app:/app/logic-worker:${PYTHONPATH}"

COPY ./logic-worker ./logic-worker
COPY ./shared ./shared
COPY wait-for-it.sh /app/wait-for-it.sh
RUN chmod +x /app/wait-for-it.sh

ENTRYPOINT ["/app/wait-for-it.sh", "broker:9092", "--", "python", "-m", "logic-worker.worker.main"]
