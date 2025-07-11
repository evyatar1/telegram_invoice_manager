import os
import requests
import io
import asyncio
import json
import logging
from typing import Optional # Import Optional
from telegram import Update, Bot, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, MessageHandler, filters, ContextTypes, CommandHandler
from sqlalchemy import create_engine, Table, Column, Integer, String, MetaData, select
from aiokafka import AIOKafkaConsumer
from jose import jwt, JWTError
from datetime import datetime, timedelta, timezone
from shared.config import JWT_SECRET, JWT_ALGO # Assuming shared.config exists and has these

# --- Configuration (from .env) ---
TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
API_SERVER_URL = "http://api-server:8000"  # Internal Docker service name
DB_URL = os.getenv("DATABASE_URL")

# Bot's credentials for authenticating with the API server
API_USER_EMAIL = os.getenv("API_USER_EMAIL")
API_USER_PASSWORD = os.getenv("API_USER_PASSWORD")

# Kafka Configuration
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS")
KAFKA_TELEGRAM_OTP_TOPIC = os.getenv("KAFKA_TELEGRAM_OTP_TOPIC")
KAFKA_TELEGRAM_MESSAGE_TOPIC = os.getenv("KAFKA_TELEGRAM_MESSAGE_TOPIC")

# Global variable to store the JWT token
API_JWT_TOKEN = None

# --- Logging Setup ---
# Configure logging to output to console (stdout/stderr)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler() # Sends logs to standard output
    ]
)
logger = logging.getLogger(__name__)

# Database setup (from your provided main.py)
engine = create_engine(DB_URL)
metadata = MetaData()
users = Table(
    "users", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("email", String, unique=True, nullable=False),
    Column("hashed_pw", String, nullable=False),
    Column("phone", String, unique=True),
    Column("telegram_chat_id", String, unique=True),
    Column("otp_secret", String),
    Column("otp_expires", String),
    Column("is_verified", Integer, default=0),
)

def validate_token(token: str) -> bool:
    """Validates the JWT token's expiration."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
        return datetime.fromtimestamp(payload['exp'], tz=timezone.utc) > datetime.now(timezone.utc)
    except JWTError as e:
        logger.warning(f"JWT token validation failed: {e}")
        return False

async def login_to_api_server(force_refresh: bool = False):
    """Attempts to log in to the API server and obtain a JWT token."""
    global API_JWT_TOKEN
    if API_JWT_TOKEN and not force_refresh and validate_token(API_JWT_TOKEN):
        logger.info("Using existing valid API token.")
        return API_JWT_TOKEN

    logger.info("API token missing, expired, or forced refresh. Attempting to log in to API server.")
    if not API_USER_EMAIL or not API_USER_PASSWORD:
        logger.error("API_USER_EMAIL or API_USER_PASSWORD environment variables are not set. Cannot log in.")
        return None

    login_url = f"{API_SERVER_URL}/login"
    try:
        response = requests.post(login_url, json={
            "email": API_USER_EMAIL,
            "password": API_USER_PASSWORD
        })
        response.raise_for_status() # This will raise an exception for 4xx/5xx responses
        token_data = response.json()
        API_JWT_TOKEN = token_data.get("access_token")
        if API_JWT_TOKEN:
            logger.info("Successfully logged in to API server.")
            return API_JWT_TOKEN
        else:
            logger.error(f"Login successful but no access_token received: {token_data}")
            return None
    except requests.exceptions.RequestException as e:
        error_message = f"Failed to log in to API server at {login_url}: {e}"
        if e.response is not None:
            # IMPORTANT: Print the actual response content from the API server
            logger.error(f"{error_message}\nAPI Response Content: {e.response.text}")
        else:
            logger.error(error_message)
        return None
    except json.JSONDecodeError:
        logger.error(f"Failed to decode JSON response from API server at {login_url}. Response: {response.text}")
        return None

async def get_user_chat_id_from_db(user_id: int) -> Optional[str]: # Changed str | None to Optional[str]
    """Fetches the Telegram chat ID for a given user ID from the database."""
    with engine.connect() as conn:
        stmt = select(users.c.telegram_chat_id).where(users.c.id == user_id)
        result = conn.execute(stmt).scalar_one_or_none()
        return result

async def consume_otp_messages(bot_instance: Bot):
    """Consumes OTP messages from Kafka and sends them to the respective Telegram chat IDs."""
    consumer = AIOKafkaConsumer(
        KAFKA_TELEGRAM_OTP_TOPIC,
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        group_id="telegram-otp-group",
        auto_offset_reset="latest"
    )
    logger.info("Starting Kafka OTP consumer...")
    try:
        await consumer.start()
        logger.info(f"Kafka OTP consumer started for topic: {KAFKA_TELEGRAM_OTP_TOPIC}")
        async for msg in consumer:
            payload_str = msg.value.decode('utf-8')
            logger.info(f"Received OTP Kafka message: {payload_str}")
            try:
                message_data = json.loads(payload_str)
                user_id = message_data.get("user_id")
                otp_secret = message_data.get("otp_secret")
                chat_id_from_kafka = message_data.get("chat_id")

                if user_id and otp_secret:
                    chat_id = chat_id_from_kafka if chat_id_from_kafka else await get_user_chat_id_from_db(user_id)
                    if chat_id:
                        text = f"Your OTP code is: {otp_secret}. Use this to verify your account on the web app."
                        try:
                            await bot_instance.send_message(chat_id=chat_id, text=text)
                            logger.info(f"OTP {otp_secret} sent to chat ID {chat_id} for user {user_id}.")
                        except Exception as e:
                            logger.error(f"Failed to send OTP message to Telegram chat ID {chat_id}: {e}")
                    else:
                        logger.warning(f"No Telegram chat ID found for user_id {user_id}. Cannot send OTP.")
                else:
                    logger.warning(f"Malformed OTP Kafka message: {payload_str}. Missing user_id or otp_secret.")
            except json.JSONDecodeError:
                logger.error(f"Failed to decode JSON from Kafka message: {payload_str}")
            except Exception as e:
                logger.error(f"Error processing Kafka OTP message: {e}", exc_info=True)
    except Exception as e:
        logger.critical(f"Critical error in Kafka OTP consumer loop: {e}", exc_info=True)
    finally:
        logger.info("Kafka OTP consumer stopping.")
        await consumer.stop()

# --- Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a message when the command /start is issued, prompting to link account."""
    user_name = update.effective_user.mention_html()
    keyboard = [[KeyboardButton("Share My Phone Number", request_contact=True)]]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_html(
        f"Hi {user_name}! To link your account and receive OTPs, please share your phone number using the button below. Make sure it's the same number you used to register on the web app.",
        reply_markup=reply_markup
    )

async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles incoming contact (phone number) from Telegram, links it to a user."""
    user_chat_id = update.message.chat_id
    phone_number_from_telegram = update.message.contact.phone_number
    logger.info(f"Received contact from chat_id: {user_chat_id}, raw phone: {phone_number_from_telegram}")

    # Normalize phone number: remove non-digit characters, then apply Israeli specific logic
    # This aims to convert +972541234567 or 972541234567 to 0541234567
    cleaned_phone_number = ''.join(filter(str.isdigit, phone_number_from_telegram))

    normalized_phone_number = cleaned_phone_number
    if cleaned_phone_number.startswith('972'):
        # If it starts with 972, replace it with 0 (e.g., 972541234567 -> 0541234567)
        normalized_phone_number = '0' + cleaned_phone_number[3:]
    elif not cleaned_phone_number.startswith('0') and len(cleaned_phone_number) == 9:
        # If it's a 9-digit number and doesn't start with 0, assume it's missing the leading 0
        # (e.g., 541234567 -> 0541234567)
        normalized_phone_number = '0' + cleaned_phone_number

    logger.info(f"Normalized phone number for API: {normalized_phone_number}")

    current_token = await login_to_api_server()
    if not current_token:
        await update.message.reply_text("I'm having trouble connecting to the service. Please try again later.")
        return

    link_url = f"{API_SERVER_URL}/link-telegram-account"
    headers = {"Authorization": f"Bearer {current_token}", "Content-Type": "application/json"}
    payload = {"phone": normalized_phone_number, "telegram_chat_id": str(user_chat_id)}

    try:
        response = requests.post(link_url, headers=headers, json=payload)
        response.raise_for_status()
        response_data = response.json()
        logger.info(f"Telegram link request sent to API server. Response: {response_data}")
        await update.message.reply_text(response_data.get("message", "Account linking request sent. Please check the web app for OTP."))
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to send Telegram link request to API server: {e}")
        error_detail = "Failed to link account. Please ensure your phone number is registered on the web app."
        if e.response is not None and e.response.status_code == 400: # Check for response before accessing it
            try:
                error_detail = e.response.json().get("detail", error_detail)
            except json.JSONDecodeError:
                pass
        await update.message.reply_text(error_detail)
    except Exception as e:
        logger.critical(f"An unexpected error occurred during contact handling: {e}", exc_info=True)
        await update.message.reply_text("An unexpected error occurred during linking. Please try again later.")


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles incoming photos, sends them to the API server for processing."""
    logger.info(f"Received photo from user {update.effective_user.id}")
    file_id = update.message.photo[-1].file_id
    file = await context.bot.get_file(file_id)

    current_token = await login_to_api_server()
    if not current_token:
        await update.message.reply_text("I'm having trouble connecting to the invoice processing service. Please try again later.")
        return

    file_bytes = io.BytesIO()
    await file.download_to_memory(file_bytes)
    file_bytes.seek(0)

    upload_url = f"{API_SERVER_URL}/upload-invoice"
    headers = {"Authorization": f"Bearer {current_token}"}
    files = {"file": ("invoice.jpg", file_bytes.getvalue(), "image/jpeg")}

    try:
        # Corrected: Use files=files for multipart/form-data upload, not json=payload
        response = requests.post(upload_url, headers=headers, files=files)
        response.raise_for_status()
        logger.info(f"Photo sent to API server successfully. Response: {response.json()}")
        await update.message.reply_text("Your invoice has been received and is being processed! You can view it on the web dashboard.")
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to send photo to API server at {upload_url}: {e}")
        if e.response is not None and e.response.status_code == 401:
            logger.warning("API token expired or invalid. Attempting refresh and retry.")
            current_token = await login_to_api_server(force_refresh=True)
            if current_token:
                headers = {"Authorization": f"Bearer {current_token}"}
                try:
                    response = requests.post(upload_url, headers=headers, files=files)
                    response.raise_for_status()
                    logger.info(f"Photo sent to API server successfully on retry. Response: {response.json()}")
                    await update.message.reply_text("Your invoice has been received and is being processed! You can view it on the web dashboard.")
                except requests.exceptions.RequestException as retry_e:
                    logger.error(f"Failed to send photo to API server on retry: {retry_e}")
                    await update.message.reply_text("Failed to send photo for processing after retry. Please try again later.")
            else:
                await update.message.reply_text("Failed to re-authenticate with invoice processing service. Please try again later.")
        else:
            logger.error(f"Failed to send photo for processing. API Response Content: {e.response.text if e.response is not None else 'No response content'}")
            await update.message.reply_text("Failed to send photo for processing. Please try again later.")
    except Exception as e:
        logger.critical(f"An unexpected error occurred during photo handling: {e}", exc_info=True)
        await update.message.reply_text("An unexpected error occurred. Please try again later.")

async def post_startup(application: Application):
    """Attempt to log in to API server and start Kafka consumer on bot startup."""
    global API_JWT_TOKEN
    logger.info("Performing initial login to API server...")
    API_JWT_TOKEN = await login_to_api_server()
    if API_JWT_TOKEN:
        logger.info("Initial API login successful.")
    else:
        logger.error("Initial API login failed. Will retry on first photo.")

    logger.info("Starting Kafka OTP consumer as background task...")
    asyncio.create_task(consume_otp_messages(application.bot))


def main() -> None:
    """Starts the bot."""
    application = Application.builder().token(TG_BOT_TOKEN).post_init(post_startup).build()

    application.add_handler(CommandHandler('start', start))
    application.add_handler(MessageHandler(filters.PHOTO & ~filters.COMMAND, handle_photo))
    application.add_handler(MessageHandler(filters.CONTACT, handle_contact))
    # Removed generic text handler to force users to use specific commands/buttons

    logger.info("Telegram bot starting polling...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
