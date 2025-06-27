FROM python:3.11-slim-buster

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY ./api-server/requirements.txt .
RUN pip install bcrypt==4.0.1
RUN pip install --no-cache-dir -r requirements.txt

COPY ./api-server/app ./app
COPY ./shared ./shared

COPY wait-for-it.sh /wait-for-it.sh
RUN chmod +x /wait-for-it.sh

EXPOSE 8000

ENTRYPOINT ["/wait-for-it.sh", "db:5432", "broker:9092", "--", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
