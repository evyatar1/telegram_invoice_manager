import os
import requests
import io
import asyncio
import json
from telegram import Update, Bot
from telegram.ext import Application, MessageHandler, filters, ContextTypes, CommandHandler # Import CommandHandler
from sqlalchemy import create_engine, Table, Column, Integer, String, MetaData, select
from aiokafka import AIOKafkaConsumer
import logging
from jose import jwt, JWTError
from datetime import datetime, timedelta, timezone # Import timezone
from shared.config import JWT_SECRET, JWT_ALGO # NEW: Import JWT_SECRET and JWT_ALGO

# --- Configuration (from .env) ---
TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
API_SERVER_URL = "http://api-server:8000"  # Internal Docker service name
DB_URL = os.getenv("DATABASE_URL")

# Bot's credentials for authenticating with the API server
API_USER_EMAIL = os.getenv("API_USER_EMAIL")
API_USER_PASSWORD = os.getenv("API_USER_PASSWORD")

# Kafka Configuration (NEW)
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS")
KAFKA_TELEGRAM_OTP_TOPIC = os.getenv("KAFKA_TELEGRAM_OTP_TOPIC")

# Global variable to store the JWT token
API_JWT_TOKEN = None

# --- Logging Setup ---
LOG_FILE = "/app/bot/bot.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Database setup
engine = create_engine(DB_URL)
metadata = MetaData()
users = Table(
    "users", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("email", String, unique=True, nullable=False),
    Column("hashed_pw", String, nullable=False),
    Column("phone", String, unique=True),
    Column("telegram_chat_id", String, unique=True),
    Column("otp_code", String),
    Column("otp_expires", String), # Store as TIMESTAMP WITH TIME ZONE
)

def validate_token(token: str) -> bool:
    """Validates the JWT token's expiration."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
        # Check expiration. The 'exp' claim is a Unix timestamp.
        return datetime.fromtimestamp(payload['exp'], tz=timezone.utc) > datetime.now(timezone.utc)
    except JWTError as e:
        logger.warning(f"JWT token validation failed: {e}")
        return False

async def login_to_api_server(force_refresh: bool = False):
    global API_JWT_TOKEN
    # Only attempt login if token is not set or force_refresh is True
    if API_JWT_TOKEN and not force_refresh and validate_token(API_JWT_TOKEN):
        logger.info("Using existing valid API token.")
        return API_JWT_TOKEN

    logger.info("API token missing, expired, or forced refresh. Attempting to log in to API server.")
    if not API_USER_EMAIL or not API_USER_PASSWORD:
        logger.error("API_USER_EMAIL or API_USER_PASSWORD environment variables are not set. Cannot log in.")
        return None

    login_url = f"{API_SERVER_URL}/login"
    try:
        # Use requests for synchronous HTTP call, or aiohttp for async if preferred
        response = requests.post(login_url, json={
            "email": API_USER_EMAIL,
            "password": API_USER_PASSWORD
        })
        response.raise_for_status()  # Raise an exception for HTTP errors (4xx or 5xx)
        token_data = response.json()
        API_JWT_TOKEN = token_data.get("access_token")
        if API_JWT_TOKEN:
            logger.info("Successfully logged in to API server.")
            return API_JWT_TOKEN
        else:
            logger.error(f"Login successful but no access_token received: {token_data}")
            return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to log in to API server at {login_url}: {e}")
        return None
    except json.JSONDecodeError:
        logger.error(f"Failed to decode JSON response from API server at {login_url}. Response: {response.text}")
        return None

async def get_user_chat_id_from_db(user_id: int) -> str | None:
    """Fetches the Telegram chat ID for a given user ID from the database."""
    with engine.connect() as conn:
        stmt = select(users.c.telegram_chat_id).where(users.c.id == user_id)
        result = conn.execute(stmt).scalar_one_or_none()
        return result

async def consume_otp_messages(bot_instance: Bot):
    """Consumes OTP messages from Kafka and sends them to the respective Telegram chat IDs."""
    logger.info("Starting Kafka OTP consumer...")
    consumer = AIOKafkaConsumer(
        KAFKA_TELEGRAM_OTP_TOPIC,
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        group_id="telegram-otp-group",
        auto_offset_reset="latest"
    )
    try:
        await consumer.start()
        logger.info(f"Kafka OTP consumer started for topic: {KAFKA_TELEGRAM_OTP_TOPIC}")
        async for msg in consumer:
            payload_str = msg.value.decode('utf-8')
            logger.info(f"Received OTP Kafka message: {payload_str}")
            try:
                message_data = json.loads(payload_str)
                user_id = message_data.get("user_id")
                otp_code = message_data.get("otp_code")

                if user_id and otp_code:
                    chat_id = await get_user_chat_id_from_db(user_id)
                    if chat_id:
                        text = f"Your OTP code is: {otp_code}. Use this to verify your account."
                        try:
                            await bot_instance.send_message(chat_id=chat_id, text=text)
                            logger.info(f"OTP {otp_code} sent to chat ID {chat_id} for user {user_id}.")
                        except Exception as e:
                            logger.error(f"Failed to send OTP message to Telegram chat ID {chat_id}: {e}")
                    else:
                        logger.warning(f"No Telegram chat ID found for user_id {user_id}. Cannot send OTP.")
                else:
                    logger.warning(f"Malformed OTP Kafka message: {payload_str}. Missing user_id or otp_code.")
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
    """Sends a message when the command /start is issued."""
    user = update.effective_user
    await update.message.reply_html(
        f"Hi {user.mention_html()}! Send me a photo of your invoice, and I will process it for you.",
    )

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles incoming photos, sends them to the API server for processing."""
    logger.info(f"Received photo from user {update.effective_user.id}")
    file_id = update.message.photo[-1].file_id  # Get the largest photo
    file = await context.bot.get_file(file_id)

    # Ensure we have an API token
    current_token = await login_to_api_server()
    if not current_token:
        await update.message.reply_text("I'm having trouble connecting to the invoice processing service. Please try again later.")
        return

    # Download the file to memory
    file_bytes = io.BytesIO()
    await file.download_to_memory(file_bytes)
    file_bytes.seek(0)  # Rewind to the beginning of the BytesIO object

    upload_url = f"{API_SERVER_URL}/upload-invoice"
    headers = {"Authorization": f"Bearer {current_token}"}
    files = {"file": ("invoice.jpg", file_bytes.getvalue(), "image/jpeg")} # Pass bytes, not BytesIO object

    try:
        response = requests.post(upload_url, headers=headers, files=files)
        response.raise_for_status()  # Raise an exception for HTTP errors (4xx or 5xx)
        logger.info(f"Photo sent to API server successfully. Response: {response.json()}")
        await update.message.reply_text("Your invoice has been received and is being processed! You can view it on the web dashboard.")
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to send photo to API server at {upload_url}: {e}")
        # Check if it's an authorization error (e.g., 401 Unauthorized)
        if response.status_code == 401:
            logger.warning("API token expired or invalid. Attempting refresh and retry.")
            current_token = await login_to_api_server(force_refresh=True)
            if current_token:
                # Retry once after refresh
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
            await update.message.reply_text("Failed to send photo for processing. Please try again later.")
    except Exception as e:
        logger.critical(f"An unexpected error occurred during photo handling: {e}", exc_info=True)
        await update.message.reply_text("An unexpected error occurred. Please try again later.")


async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Echoes the user message if it's not a photo or command."""
    if update.message.text:
        await update.message.reply_text("I can only process photos of invoices. Please send an image.")
    else:
        await update.message.reply_text("I received something, but I can only process photos of invoices.")


async def post_startup(application: Application):
    """Attempt to log in to API server and start Kafka consumer on bot startup."""
    global API_JWT_TOKEN
    logger.info("Performing initial login to API server...")
    API_JWT_TOKEN = await login_to_api_server()
    if API_JWT_TOKEN:
        logger.info("Initial API login successful.")
    else:
        logger.error("Initial API login failed. Will retry on first photo.")

    # NEW: Start the Kafka consumer as a background task
    logger.info("Starting Kafka OTP consumer as background task...")
    asyncio.create_task(consume_otp_messages(application.bot))


def main() -> None:
    """Starts the bot."""
    # Create the Application and pass your bot's token.
    application = Application.builder().token(TG_BOT_TOKEN).post_init(post_startup).build()

    # Add handlers
    application.add_handler(MessageHandler(filters.PHOTO & ~filters.COMMAND, handle_photo))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo)) # Handles non-photo messages
    application.add_handler(CommandHandler('start', start)) # Handles /start command

    logger.info("Telegram bot starting polling...")
    # Run the bot until the user presses Ctrl-C
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
