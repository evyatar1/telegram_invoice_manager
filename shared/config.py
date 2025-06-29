import os
# Kafka
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "invoices")
# IMPORTANT: Use 'broker:9092' as the default for Docker Compose internal communication
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "broker:9092")

# S3
S3_BUCKET = os.getenv("S3_BUCKET", "my-invoices-bucket")
S3_REGION = os.getenv("S3_REGION", "us-east-1")

# JWT
JWT_SECRET = os.getenv("JWT_SECRET", "supersecretkey")
JWT_ALGO = "HS256"
JWT_EXP_DELTA_SECONDS = 3600

# Postgres
DB_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@db:5432/appdb")

# Telegram
TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN", "")

# NEW Kafka Topic for Telegram OTPs
KAFKA_TELEGRAM_OTP_TOPIC = os.getenv("KAFKA_TELEGRAM_OTP_TOPIC", "telegram-otp-messages")
