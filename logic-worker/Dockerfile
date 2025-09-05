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






## logic-worker/Dockerfile
## Stage 1: Build dependencies
#FROM python:3.10-bullseye as builder
#
## Set the working directory for the builder stage
#WORKDIR /app/builder
#
## Install system dependencies required for PaddleOCR, OpenCV, Matplotlib, and Telegram Bot
## Also install curl and tar for downloading and extracting PaddleOCR models during build
#RUN apt-get update && \
#    apt-get install -y --no-install-recommends \
#    build-essential \
#    gcc \
#    make \
#    swig \
#    python3-dev \
#    tesseract-ocr \
#    tesseract-ocr-eng \
#    libgl1-mesa-glx \
#    libglib2.0-0 \
#    libsm6 \
#    libxext6 \
#    libxrender-dev \
#    libcairo2-dev \
#    libjpeg-dev \
#    libpng-dev \
#    libfreetype6-dev \
#    libglvnd-dev \
#    libxkbcommon-x11-0 \
#    libxcb-randr0 \
#    libxcb-render0 \
#    libxcb-shape0 \
#    libxcb-xfixes0 \
#    libxcomposite1 \
#    libxdamage1 \
#    libxfixes3 \
#    libxrandr2 \
#    libxrender1 \
#    curl \
#    tar \
#    # Clean up APT cache to reduce image size
#    && rm -rf /var/lib/apt/lists/*
#
## Copy only the requirements file for dependency installation
#COPY ./logic-worker/requirements.txt ./requirements.txt
#
#ENV PIP_DEFAULT_TIMEOUT=1000
#
#RUN pip install --upgrade pip && \
#    python3 -m venv /opt/venv && \
#    /opt/venv/bin/pip install --no-cache-dir -r requirements.txt --timeout 300 --retries 10
#
## NEW: Download and extract PaddleOCR models during the build process
## This avoids runtime download issues (NameResolutionError) by ensuring models are present in the image.
#RUN mkdir -p /root/.paddleocr/whl/det/en/en_PP-OCRv3_det_infer && \
#    curl -o /tmp/en_PP-OCRv3_det_infer.tar https://paddleocr.bj.bcebos.com/PP-OCRv3/english/en_PP-OCRv3_det_infer.tar && \
#    tar -xf /tmp/en_PP-OCRv3_det_infer.tar -C /root/.paddleocr/whl/det/en/en_PP-OCRv3_det_infer --strip-components=1 && \
#    rm /tmp/en_PP-OCRv3_det_infer.tar
#
#RUN mkdir -p /root/.paddleocr/whl/rec/en/en_PP-OCRv3_rec_infer && \
#    curl -o /tmp/en_PP-OCRv3_rec_infer.tar https://paddleocr.bj.bcebos.com/PP-OCRv3/english/en_PP-OCRv3_rec_infer.tar && \
#    tar -xf /tmp/en_PP-OCRv3_rec_infer.tar -C /root/.paddleocr/whl/rec/en/en_PP-OCRv3_rec_infer --strip-components=1 && \
#    rm /tmp/en_PP-OCRv3_rec_infer.tar
#
#RUN mkdir -p /root/.paddleocr/whl/cls/ch_ppocr_mobile_v2.0_cls_infer && \
#    curl -o /tmp/ch_ppocr_mobile_v2.0_cls_infer.tar https://paddleocr.bj.bcebos.com/dygraph_v2.0/ch/ch_ppocr_mobile_v2.0_cls_infer.tar && \
#    tar -xf /tmp/ch_ppocr_mobile_v2.0_cls_infer.tar -C /root/.paddleocr/whl/cls/ch_ppocr_mobile_v2.0_cls_infer --strip-components=1 && \
#    rm /tmp/ch_ppocr_mobile_v2.0_cls_infer.tar
#
#
## Stage 2: Final image
#FROM python:3.10-bullseye
#
## Install runtime libraries required by OpenCV (for cv2, PaddleOCR)
#RUN apt-get update && \
#    apt-get install -y --no-install-recommends \
#    libgl1-mesa-glx \
#    libglib2.0-0 \
#    libsm6 \
#    libxext6 \
#    libxrender1 \
#    libglvnd0 \
#    libxkbcommon0 \
#    libxcb-randr0 \
#    libxcb-render0 \
#    libxcb-shape0 \
#    libxcb-xfixes0 \
#    libxcomposite1 \
#    libxdamage1 \
#    libxfixes3 \
#    libxrandr2 \
#    libxrender1 \
#    # Clean up APT cache to reduce image size
#    && rm -rf /var/lib/apt/lists/*
#
#COPY --from=builder /opt/venv /opt/venv
## The PaddleOCR models are already copied into /root/.paddleocr during the builder stage
## because they were extracted directly there. No need for another COPY.
#
#WORKDIR /app
#
#ENV PATH="/opt/venv/bin:$PATH"
#ENV PYTHONPATH="/app:/app/logic-worker:${PYTHONPATH}"
#
## Copy source code
#COPY ./logic-worker ./logic-worker
## Copy shared to /app/shared
#COPY ./shared ./shared
## Copy wait-for-it.sh from the project root to /app/wait-for-it.sh in the container
#COPY wait-for-it.sh /app/wait-for-it.sh
## Make wait-for-it.sh executable in /app
#RUN chmod +x /app/wait-for-it.sh
#
#
## Start the application
#ENTRYPOINT ["/app/wait-for-it.sh", "broker:9092", "--", "python", "-m", "logic-worker.worker.main"]
#



## logic-worker/Dockerfile
## Stage 1: Build dependencies
#FROM python:3.10-bullseye as builder
#
#WORKDIR /app/builder
#
#RUN apt-get update && \
#    apt-get install -y --no-install-recommends \
#    build-essential \
#    gcc \
#    make \
#    swig \
#    python3-dev \
#    tesseract-ocr \
#    tesseract-ocr-eng \
#    libgl1-mesa-glx \
#    libglib2.0-0 \
#    libsm6 \
#    libxext6 \
#    libxrender-dev \
#    libcairo2-dev \
#    libjpeg-dev \
#    libpng-dev \
#    libfreetype6-dev \
#    libglvnd-dev \
#    libxkbcommon-x11-0 \
#    libxcb-randr0 \
#    libxcb-render0 \
#    libxcb-shape0 \
#    libxcb-xfixes0 \
#    libxcomposite1 \
#    libxdamage1 \
#    libxfixes3 \
#    libxrandr2 \
#    libxrender1 && \
#    rm -rf /var/lib/apt/lists/*
#
#COPY ./logic-worker/requirements.txt ./requirements.txt
#
#ENV PIP_DEFAULT_TIMEOUT=1000
#
#RUN pip install --upgrade pip && \
#    python3 -m venv /opt/venv && \
#    /opt/venv/bin/pip install --no-cache-dir -r requirements.txt --timeout 300 --retries 10
#
#
## Stage 2: Final image
#FROM python:3.10-bullseye
#
## Install runtime libraries required by OpenCV (for cv2, PaddleOCR)
#RUN apt-get update && \
#    apt-get install -y --no-install-recommends \
#    libgl1-mesa-glx \
#    libglib2.0-0 \
#    libsm6 \
#    libxext6 \
#    libxrender1 && \
#    rm -rf /var/lib/apt/lists/*
#
#COPY --from=builder /opt/venv /opt/venv
#
#WORKDIR /app
#
#ENV PATH="/opt/venv/bin:$PATH"
#ENV PYTHONPATH="/app:/app/logic-worker:${PYTHONPATH}"
#
#COPY ./logic-worker ./logic-worker
#COPY ./shared ./shared
#COPY wait-for-it.sh /app/wait-for-it.sh
#RUN chmod +x /app/wait-for-it.sh
#
#ENTRYPOINT ["/app/wait-for-it.sh", "broker:9092", "--", "python", "-m", "logic-worker.worker.main"]
#
#
#




#
#
#
## logic-worker/Dockerfile
## Stage 1: Build dependencies
#FROM python:3.10-bullseye as builder
#
## Set the working directory for the builder stage
#WORKDIR /app/builder
#
## Install system dependencies required for PaddleOCR, OpenCV, Matplotlib, and Telegram Bot
## This list is comprehensive for common Python image processing and GUI-related libraries.
#RUN apt-get update && \
#    apt-get install -y --no-install-recommends \
#    build-essential \
#    gcc \
#    make \
#    swig \
#    python3-dev \
#    tesseract-ocr \
#    tesseract-ocr-eng \
#    libgl1-mesa-glx \
#    libglib2.0-0 \
#    libsm6 \
#    libxext6 \
#    libxrender-dev \
#    libcairo2-dev \
#    libjpeg-dev \
#    libpng-dev \
#    libfreetype6-dev \
#    # Additional libraries for libGL.so.1 and other potential runtime issues with OpenCV
#    libglvnd-dev \
#    libxkbcommon-x11-0 \
#    libxcb-randr0 \
#    libxcb-render0 \
#    libxcb-shape0 \
#    libxcb-xfixes0 \
#    libxcomposite1 \
#    libxdamage1 \
#    libxfixes3 \
#    libxrandr2 \
#    libxrender1 \
#    # Clean up APT cache to reduce image size
#    && rm -rf /var/lib/apt/lists/*
#
## Copy only the requirements file for dependency installation
#COPY ./logic-worker/requirements.txt ./requirements.txt
#
## Install Python dependencies into a virtual environment
## Using Alibaba Cloud PyPI mirror to bypass network timeouts with default PyPI or other mirrors
## CRITICAL: Ensure this line is copied exactly as is, including --index-url and --trusted-host
#RUN pip install --upgrade pip && \
#    python3 -m venv /opt/venv && \
#    /opt/venv/bin/pip install --no-cache-dir -r requirements.txt --index-url https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com --default-timeout=1000
#
#
## Stage 2: Final image
#FROM python:3.10-bullseye
#
## Copy the virtual environment from the builder stage
#COPY --from=builder /opt/venv /opt/venv
#
## Set the working directory in the final container
#WORKDIR /app
#
## Set PATH to include the virtual environment's bin directory
#ENV PATH="/opt/venv/bin:$PATH"
## Set PYTHONPATH to include /app and /app/logic-worker for module imports
#ENV PYTHONPATH="/app:/app/logic-worker:${PYTHONPATH}"
#
## Copy source code
#COPY ./logic-worker ./logic-worker
## Copy shared to /app/shared
#COPY ./shared ./shared
## Copy wait-for-it.sh from the project root to /app/wait-for-it.sh in the container
#COPY wait-for-it.sh /app/wait-for-it.sh
## Make wait-for-it.sh executable in /app
#RUN chmod +x /app/wait-for-it.sh
#
## Start the application
#ENTRYPOINT ["/app/wait-for-it.sh", "broker:9092", "--", "python", "-m", "logic-worker.worker.main"]
#




## logic-worker/Dockerfile
## Use an official Python runtime as a parent image
#FROM python:3.10-bullseye
#
## Set the working directory in the container
#WORKDIR /app
#
## Install system dependencies required for PaddleOCR, OpenCV, Matplotlib, and Telegram Bot
#RUN apt-get update && \
#    apt-get install -y --no-install-recommends \
#    build-essential \
#    gcc \
#    make \
#    swig \
#    python3-dev \
#    tesseract-ocr \
#    tesseract-ocr-eng \
#    libgl1-mesa-glx \
#    libglib2.0-0 \
#    libsm6 \
#    libxext6 \
#    libxrender-dev \
#    libcairo2-dev \
#    libjpeg-dev \
#    libpng-dev \
#    libfreetype6-dev \
#    # Clean up APT cache to reduce image size
#    && rm -rf /var/lib/apt/lists/*
#
## Copy the requirements file into the working directory
## The context for build is the project root, so path is relative to root.
#COPY ./logic-worker/requirements.txt ./logic-worker/requirements.txt
#
## Install Python dependencies
#RUN pip install --upgrade pip && \
#    pip install --no-cache-dir -r logic-worker/requirements.txt
#
## Copy source code
## This copies the project_root/logic-worker directory into /app/logic-worker in the container.
## This assumes the structure is project_root/logic-worker/worker/main.py
#COPY ./logic-worker ./logic-worker
## Copy shared to /app/shared
#COPY ./shared ./shared
## Copy wait-for-it.sh from the project root to /app/wait-for-it.sh in the container
#COPY wait-for-it.sh /app/wait-for-it.sh
## Make wait-for-it.sh executable in /app
#RUN chmod +x /app/wait-for-it.sh
#
## Set PYTHONPATH to include /app so Python can find 'logic-worker' and 'shared' as top-level packages
## And also /app/logic-worker/worker for direct imports within the worker module
#ENV PYTHONPATH="/app:/app/logic-worker:${PYTHONPATH}"
#
## Keep working directory at /app
#WORKDIR /app
#
## Start the application
## CRITICAL FIX: Run as a module from the correct path: logic-worker.worker.main
#ENTRYPOINT ["/app/wait-for-it.sh", "broker:9092", "--", "python", "-m", "logic-worker.worker.main"]
#
#







# version 2
## logic-worker/Dockerfile
## Use an official Python runtime as a parent image
#FROM python:3.10-bullseye
#
## Set the working directory in the container
#WORKDIR /app
#
## Install system dependencies required for PaddleOCR, OpenCV, and Matplotlib
## libgl1-mesa-glx, libglib2.0-0, libsm6, libxext6, libxrender-dev are for OpenCV
## tesseract-ocr, tesseract-ocr-eng for Tesseract OCR
## libcairo2-dev, libjpeg-dev, libpng-dev, libfreetype6-dev for Matplotlib
#RUN apt-get update && \
#    apt-get install -y --no-install-recommends \
#    build-essential \
#    gcc \
#    make \
#    swig \
#    python3-dev \
#    tesseract-ocr \
#    tesseract-ocr-eng \
#    libgl1-mesa-glx \
#    libglib2.0-0 \
#    libsm6 \
#    libxext6 \
#    libxrender-dev \
#    libcairo2-dev \
#    libjpeg-dev \
#    libpng-dev \
#    libfreetype6-dev \
#    # Clean up APT cache to reduce image size
#    && rm -rf /var/lib/apt/lists/*
#
## Copy the requirements file into the working directory
## The context for build is the project root, so path is relative to root.
#COPY ./logic-worker/requirements.txt ./logic-worker/requirements.txt
#
## Install Python dependencies
#RUN pip install --upgrade pip && \
#    pip install --no-cache-dir -r logic-worker/requirements.txt
#
## Copy source code
## This copies the project_root/logic-worker directory into /app/logic-worker in the container.
#COPY ./logic-worker ./logic-worker
## Copy shared to /app/shared
#COPY ./shared ./shared
## Copy wait-for-it.sh from the project root to /app/wait-for-it.sh in the container
#COPY wait-for-it.sh /app/wait-for-it.sh
## Make wait-for-it.sh executable in /app
#RUN chmod +x /app/wait-for-it.sh
#
## Set PYTHONPATH to include /app so Python can find 'logic-worker' and 'shared' as top-level packages
## And also /app/logic-worker/worker if main.py is directly in there and imports from it
#ENV PYTHONPATH="/app:${PYTHONPATH}"
#
## Keep working directory at /app
#WORKDIR /app
#
## Start the application
## CHANGE: Run as a module from the top-level package 'logic-worker.worker.main'
## This assumes main.py is at logic-worker/worker/main.py relative to the project root.
#ENTRYPOINT ["/app/wait-for-it.sh", "broker:9092", "--", "python", "-m", "logic-worker.worker.main"]
#
#
#




#
#
#FROM python:3.10-bullseye
## FROM python:3.11-slim-buster
#
#WORKDIR /worker
#
## Install system dependencies
#RUN apt-get update && \
#    apt-get install -y --no-install-recommends \
#    build-essential \
#    gcc \
#    make \
#    swig \
#    python3-dev \
#    tesseract-ocr \
#    tesseract-ocr-eng \
#    libgl1-mesa-glx \
#    libglib2.0-0 \
#    libsm6 \
#    libxext6 \
#    libxrender-dev \
#    && rm -rf /var/lib/apt/lists/*
#
## Install python dependencies
#COPY ./logic-worker/requirements.txt ./
#RUN pip install --upgrade pip && \
#    pip install --no-cache-dir -r requirements.txt
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