import os
from dotenv import load_dotenv

load_dotenv()

# Database Configuration
DB_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres123@db:5432/appdb")

# AWS S3 Configuration
S3_BUCKET = os.getenv("S3_BUCKET")
S3_REGION = os.getenv("S3_REGION", "us-east-1")

# JWT Configuration
JWT_SECRET = os.getenv("JWT_SECRET")
JWT_ALGO = os.getenv("JWT_ALGO", "HS256")
JWT_EXP_DELTA_SECONDS = int(os.getenv("JWT_EXP_DELTA_SECONDS", 1800)) # 30 minutes

# Kafka Configuration
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "broker:9092")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "invoice-processing-requests") # For invoice uploads
KAFKA_TELEGRAM_OTP_TOPIC = os.getenv("KAFKA_TELEGRAM_OTP_TOPIC", "telegram-otp-messages") # For OTP messages
KAFKA_REPORT_REQUEST_TOPIC = os.getenv("KAFKA_REPORT_REQUEST_TOPIC", "report-generation-requests") # NEW: For Excel/Chart reports
KAFKA_TELEGRAM_OUTGOING_MESSAGE_TOPIC = os.getenv("KAFKA_TELEGRAM_OUTGOING_MESSAGE_TOPIC", "telegram-outgoing-messages") # NEW: For generic outgoing messages from worker to Telegram
# Telegram
TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN", "")
