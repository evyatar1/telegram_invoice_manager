# app/telegram_bot.py
import os
import io
import logging
import requests
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
import asyncio
import functools

TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
API_SERVER_URL = os.getenv("API_SERVER_URL", "http://localhost:8000")

logger = logging.getLogger(__name__)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.effective_user.mention_html()
    keyboard = [[KeyboardButton("Share My Phone Number", request_contact=True)]]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    logger.info("/start command received from: %s", update.effective_user.id)
    await update.message.reply_html(
        f"Hi {user_name}! Please share your phone number to link your account.",
        reply_markup=reply_markup,
    )


async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    When user shares phone via Telegram, send a request to API server /link-telegram-account.
    Use requests (blocking) inside a thread so we don't block the asyncio loop.
    """
    try:
        phone_raw = update.message.contact.phone_number
        logger.info("handle_contact received phone_raw: %s from chat_id: %s", phone_raw, update.message.chat_id)

        cleaned = "".join(filter(str.isdigit, phone_raw or ""))
        phone = cleaned
        if cleaned.startswith("972"):
            phone = "0" + cleaned[3:]
        elif not cleaned.startswith("0") and len(cleaned) == 9:
            phone = "0" + cleaned

        payload = {"phone": phone, "telegram_chat_id": str(update.message.chat_id)}
        logger.info("Posting link request to API server: %s", {"phone": phone, "chat_id": update.message.chat_id})

        loop = asyncio.get_running_loop()
        func = functools.partial(requests.post, f"{API_SERVER_URL}/link-telegram-account", json=payload, timeout=10)
        response = await loop.run_in_executor(None, func)
        response.raise_for_status()

        logger.info("Link request responded: %s %s", response.status_code, response.text)
        await update.message.reply_text("Phone linked successfully. Check Telegram for OTP.")
    except Exception as e:
        logger.exception("Failed to link phone: %s", e)
        await update.message.reply_text("Failed to link phone. Please try again later.")


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    User sends a photo: log in automatically, get JWT, then upload to /upload-invoice.
    """
    try:
        file_id = update.message.photo[-1].file_id
        logger.info("handle_photo received file_id: %s from user %s", file_id, update.effective_user.id)
        file = await context.bot.get_file(file_id)

        file_buf = io.BytesIO()
        await file.download_to_memory(file_buf)
        file_buf.seek(0)

        files = {"file": ("invoice.jpg", file_buf.getvalue(), "image/jpeg")}

        # --- Automatic login to get JWT ---
        api_email = os.getenv("API_USER_EMAIL")
        api_password = os.getenv("API_USER_PASSWORD")
        login_payload = {"email": api_email, "password": api_password}

        loop = asyncio.get_running_loop()
        login_func = functools.partial(
            requests.post,
            f"{API_SERVER_URL}/login",
            json=login_payload,
            timeout=10
        )
        login_response = await loop.run_in_executor(None, login_func)
        login_response.raise_for_status()
        jwt_token = login_response.json()["access_token"]

        headers = {"Authorization": f"Bearer {jwt_token}"}

        # --- Upload invoice with JWT ---
        upload_func = functools.partial(
            requests.post,
            f"{API_SERVER_URL}/upload-invoice",
            files=files,
            headers=headers,
            timeout=30
        )
        response = await loop.run_in_executor(None, upload_func)
        response.raise_for_status()

        logger.info("Upload invoice response: %s %s", response.status_code, response.text)
        await update.message.reply_text("Invoice uploaded and submitted for processing.")

    except Exception as e:
        logger.exception("Failed to upload invoice: %s", e)
        await update.message.reply_text("Failed to upload invoice. Please try again later.")


async def debug_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.debug("Debug update: %s", update)


def build_bot_app():
    """
    Build and return an Application instance (not started).
    This function is synchronous and returns the Application object to be
    initialized/started from the running event loop.
    """
    app = Application.builder().token(TG_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(MessageHandler(filters.CONTACT, handle_contact))
    app.add_handler(MessageHandler(filters.PHOTO & ~filters.COMMAND, handle_photo))
    app.add_handler(MessageHandler(filters.ALL, debug_handler))
    return app


async def run_telegram_bot_background():
    """
    Initialize, start and start polling in background. Return the Application instance.
    Sequence (python-telegram-bot v20+):
      - initialize()
      - start()
      - start polling with updater.start_polling() in a background task
    On shutdown caller should stop polling and shutdown the app.
    """
    app = build_bot_app()

    # initialize and start the application (prepares internal components)
    await app.initialize()
    await app.start()
    # start polling in background
    polling_task = asyncio.create_task(app.updater.start_polling())
    logger.info("Telegram bot polling started in background (task id: %s)", id(polling_task))

    # attach the polling task to the app for clean shutdown
    app._background_polling_task = polling_task
    return app


async def stop_telegram_bot_background(app: Application):
    """
    Stop polling and gracefully stop + shutdown the Application.
    """
    try:
        # stop polling if polling task exists
        polling_task = getattr(app, "_background_polling_task", None)
        if polling_task:
            # ask updater to stop polling (this stops fetching updates)
            await app.updater.stop_polling()
            # cancel the background polling task if still running
            if not polling_task.done():
                polling_task.cancel()
                try:
                    await polling_task
                except asyncio.CancelledError:
                    logger.info("Background polling task cancelled")
        # stop and shutdown the application
        await app.stop()
        await app.shutdown()
        logger.info("Telegram Application stopped and shutdown")
    except Exception as e:
        logger.exception("Error while stopping Telegram Application: %s", e)
