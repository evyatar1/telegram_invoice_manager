import os
import boto3
from dotenv import load_dotenv

load_dotenv()


def get_config(param_name, env_name, default=None):
    # 1. Try to fetch from AWS Parameter Store (Cloud Environment)
    try:
        # Use region from ENV or default to eu-north-1
        current_region = os.getenv("S3_REGION", "eu-north-1")
        ssm = boto3.client('ssm', region_name=current_region)
        parameter = ssm.get_parameter(Name=param_name, WithDecryption=True)
        return parameter['Parameter']['Value']
    except Exception:
        # 2. Fallback to local environment variables (Local Development)
        return os.getenv(env_name, default)


# --- Database Configuration ---
DB_URL = get_config("/prod/db_url", "DATABASE_URL", "postgresql://postgres:postgres123@db:5432/appdb")


# --- AWS S3 Configuration ---
S3_BUCKET = get_config("/prod/s3_bucket", "S3_BUCKET")
S3_REGION = get_config("/prod/s3_region", "S3_REGION", "eu-north-1")

# --- JWT Configuration ---
JWT_SECRET = get_config("/prod/jwt_secret", "JWT_SECRET")
JWT_ALGO = os.getenv("JWT_ALGO", "HS256")
JWT_EXP_DELTA_SECONDS = int(os.getenv("JWT_EXP_DELTA_SECONDS", 1800))

# --- Kafka Configuration ---
KAFKA_BOOTSTRAP_SERVERS = get_config("/prod/kafka_broker", "KAFKA_BOOTSTRAP_SERVERS", "broker:9092")
KAFKA_TOPIC = get_config("/prod/kafka_topic", "KAFKA_TOPIC", "invoice-processing-requests")
KAFKA_TELEGRAM_OTP_TOPIC = os.getenv("KAFKA_TELEGRAM_OTP_TOPIC", "telegram-otp-messages")
KAFKA_REPORT_REQUEST_TOPIC = os.getenv("KAFKA_REPORT_REQUEST_TOPIC", "report-generation-requests")
KAFKA_TELEGRAM_OUTGOING_MESSAGE_TOPIC = os.getenv("KAFKA_TELEGRAM_OUTGOING_MESSAGE_TOPIC", "telegram-outgoing-messages")

# --- Telegram & AI ---
TG_BOT_TOKEN = get_config("/prod/tg_token", "TG_BOT_TOKEN", "")
OPENAI_API_KEY = get_config("/prod/openai_key", "OPENAI_API_KEY", "")

# --- API Admin User ---
API_USER_EMAIL = get_config("/prod/api_user_email", "API_USER_EMAIL")
API_USER_PASSWORD = get_config("/prod/api_user_password", "API_USER_PASSWORD")
