from PIL import Image, ImageFilter, ImageOps, ImageEnhance
import io
import pytesseract
import openai
import re
import logging
from datetime import datetime, timezone
from sqlalchemy import create_engine, MetaData, Table, update, Column, Integer, String, DateTime, JSON, ForeignKey, \
    select
from paddleocr import PaddleOCR
import cv2, boto3
import numpy as np
import xlsxwriter
import matplotlib.pyplot as plt
from telegram import Bot, InputFile
import uuid
import os
import json
from shared.config import DB_URL, S3_BUCKET, S3_REGION, TG_BOT_TOKEN
from .config import OPENAI_API_KEY  # Assuming this config is for worker's OpenAI key

# Logging setup
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# OpenAI API key
openai.api_key = OPENAI_API_KEY

# Database setup
engine = create_engine(DB_URL)
metadata = MetaData()

# DB Tables
users = Table("users", metadata,
              Column("id", Integer, primary_key=True, autoincrement=True),
              Column("email", String, unique=True, nullable=False),
              Column("hashed_pw", String, nullable=False),
              Column("phone", String, unique=True, nullable=True),
              Column("is_verified", Integer, default=0),
              Column("otp_secret", String, nullable=True),
              Column("otp_expires", DateTime, nullable=True),
              Column("telegram_chat_id", String, unique=True, nullable=True)
              )

invoices = Table(
    "invoices",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("user_id", Integer, ForeignKey("users.id"), nullable=False),
    Column("s3_key", String, nullable=False, unique=True),
    Column("created_at", DateTime, default=datetime.utcnow),
    Column("status", String, default="pending"),
    Column("extracted_data", JSON),
    Column("category", String),
)
metadata.create_all(engine)

ocr = PaddleOCR(use_angle_cls=True, lang='en')

# S3 client for uploading processed images and generating presigned URLs
s3_client = boto3.client("s3", region_name=S3_REGION)

# Telegram bot instance for sending outgoing messages
telegram_bot_instance = None
if TG_BOT_TOKEN:
    telegram_bot_instance = Bot(token=TG_BOT_TOKEN)
else:
    logger.warning("TG_BOT_TOKEN not set in worker. Telegram outgoing messages will be disabled.")


# --- Corrected OCR and Preprocessing Functions ---

def preprocess_image(img_bytes: bytes) -> Image.Image:
    """
    Refined preprocessing:
    - Upscale for better OCR accuracy.
    - Enhance contrast without over-processing.
    - Apply a slight blur to smooth out noise without destroying text detail.
    This version is safer and less aggressive than the previous attempt.
    """
    try:
        image = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    except Exception as e:
        logger.error(f"Failed to open image from bytes: {e}")
        raise

    # Upscale the image to help with small or low-res text
    upscale_factor = 2.0
    new_size = tuple([int(dim * upscale_factor) for dim in image.size])
    image = image.resize(new_size, Image.LANCZOS)

    # Convert to grayscale
    image = ImageOps.grayscale(image)

    # Enhance contrast to make text stand out
    enhancer = ImageEnhance.Contrast(image)
    image = enhancer.enhance(1.5)

    # Apply a slight blur to smooth out noise, a good balance is key
    image = image.filter(ImageFilter.GaussianBlur(radius=0.5))

    return image


def perform_ocr(image_bytes: bytes, invoice_id: int) -> str:
    """
    Performs OCR using PaddleOCR first, with Tesseract fallback if text is too short.
    Cleans and deduplicates results.
    """

    def clean_lines(lines):
        seen = set()
        cleaned = []
        for line in lines:
            line = line.strip()
            if line and line not in seen:
                seen.add(line)
                cleaned.append(line)
        return cleaned

    try:
        # Preprocess using the refined function
        preprocessed_pil = preprocess_image(image_bytes)

        # Convert PIL image to BGR numpy array for PaddleOCR
        image_np = np.array(preprocessed_pil)
        image_cv = cv2.cvtColor(image_np, cv2.COLOR_RGB2BGR)

        ocr_result = ocr.ocr(image_cv, cls=True)
        lines = []

        if ocr_result and ocr_result[0]:
            for line in ocr_result[0]:
                try:
                    text_piece = line[1][0].strip()
                    if text_piece:
                        lines.append(text_piece)
                except Exception:
                    continue

        text = "\n".join(clean_lines(lines))

        # Fallback to Tesseract if PaddleOCR result is too short
        if len(text.strip()) < 20:
            logger.warning(f"OCR text too short for invoice {invoice_id}, falling back to Tesseract.")
            text = pytesseract.image_to_string(preprocessed_pil, lang="eng")
            text = "\n".join(clean_lines(text.splitlines()))

    except Exception as e:
        logger.error(f"Error with OCR for invoice {invoice_id}: {e}", exc_info=True)
        text = ""

    return text.strip()


def extract_date(text: str) -> str:
    """
    Extracts a date from invoice text in YYYY-MM-DD format.
    If regex fails, falls back to GPT.
    """
    date_patterns = [
        r'\b(\d{4}[- /.]\d{2}[- /.]\d{2})\b',  # 2025-08-01
        r'\b(\d{2}[- /.]\d{2}[- /.]\d{4})\b',  # 01-08-2025
        r'\b(\d{2}[- /.]\d{2}[- /.]\d{2})\b',  # 01-08-25
    ]

    for pattern in date_patterns:
        matches = re.findall(pattern, text)
        for raw in matches:
            cleaned = raw.replace('/', '-').replace('.', '-').replace(' ', '')
            for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%m-%d-%Y", "%d-%m-%y", "%m-%d-%y"):
                try:
                    parsed = datetime.strptime(cleaned, fmt)
                    if 1900 < parsed.year < 2100:
                        return parsed.strftime("%Y-%m-%d")
                except ValueError:
                    continue

    # Fallback to GPT if no date found
    return extract_with_gpt(
        text,
        "Extract the purchase date in YYYY-MM-DD format from this invoice. Only return the date."
    )


def extract_amount(text: str) -> str:
    """
    Reverted to a robust version of your original logic.
    Focuses on finding numbers near keywords and handles various currency formats.
    """
    labels = ["total", "amount due", "amount paid", "balance due", "grand total", "sum"]
    lines = text.lower().splitlines()
    candidates = []

    for line in lines:
        if any(label in line for label in labels):
            # Find numbers that look like currency (e.g., 1,234.56 or 1234.56 or 1234,56)
            nums = re.findall(r"\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})|\d+(?:[.,]\d{2})?", line)
            for num in nums:
                number = num.replace("$", "").replace("€", "").replace("£", "").replace(" ", "")
                # Handle European decimal comma if present (e.g., 123,45 -> 123.45)
                if ',' in num and '.' not in num:
                    number = num.replace(',', '.')
                else:
                    # Remove thousand separators if any (commas or dots before decimal)
                    parts = re.split(r'[.,]', number)
                    if len(parts) > 2:
                        # Reconstruct number without thousand separators
                        number = ''.join(parts[:-1]) + '.' + parts[-1]
                    else:
                        pass  # No change

                try:
                    candidates.append(float(number))
                except ValueError:
                    continue

    if candidates:
        return str(max(candidates))

    # Fallback to GPT if no candidate is found
    return extract_with_gpt(
        text,
        "Extract the total amount paid in this invoice. Only return the number, without currency symbols or extra text."
    )


def extract_vendor_name(text: str) -> str:
    """
    Reverted to the original GPT-based vendor extraction.
    This was working and is a more robust approach than a custom heuristic.
    """
    instruction = (
        "You are an intelligent invoice parser. "
        "From the following OCR text of a receipt or invoice, extract only the name of the vendor, store, or restaurant "
        "that issued the document. Return the name in proper spacing and capitalization, exactly as a human would expect to see it. "
        "Return only the vendor name, no extra text."
    )

    try:
        vendor = extract_with_gpt(text, instruction, max_tokens=20)
        # Add a check to prevent returning common OCR errors
        if len(vendor) < 3 or re.search(r'\d', vendor):
            # If the result looks like an error, re-run with a slightly different prompt
            logger.warning(f"GPT returned a suspicious vendor name: {vendor}. Retrying...")
            vendor = extract_with_gpt(text,
                                      "Extract the main vendor or company name from this invoice. Return only the name.",
                                      max_tokens=20)

        return vendor.title().strip()
    except Exception as e:
        logger.warning(f"Vendor extraction with GPT failed: {e}")
        return "Unknown"


def extract_with_gpt(text: str, instruction: str, max_tokens: int = 50) -> str:
    """Generic function to extract information using GPT."""
    try:
        response = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": instruction},
                {"role": "user", "content": text[:2000]}
            ],
            max_tokens=max_tokens,
            temperature=0.0,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.warning(f"GPT extraction failed: {e}")
        return "Unknown"


def classify_category(text: str) -> str:
    """Classifies the invoice category using OpenAI's GPT-3.5-turbo."""
    categories = [
        'Groceries', 'Restaurants/Cafes', 'Utilities', 'Transportation',
        'Clothing', 'Health', 'Education', 'Entertainment',
        'Communication', 'Housing', 'Insurance', 'Repairs',
        'Gifts', 'Electronics', 'Sports', 'Books', 'Travel',
        'Financial Services', 'Personal Care', 'Childcare', 'Pet Supplies',
        'Home Improvement', 'Subscriptions', 'Donations', 'Taxes', 'Other'
    ]
    prompt = (
        f"Categorize this invoice text into one of these categories: {', '.join(categories)}.\n"
        f"Respond only with the category.\n\nInvoice text: {text[:1500]}"
    )
    try:
        response = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a classification model."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=15,
            temperature=0.0,
        )
        result = response.choices[0].message.content.strip()
        return result if result in categories else "Other"
    except Exception as e:
        logger.warning(f"Category classification failed: {e}")
        return "Other"


# Data Extraction
def extract_all_data(text: str) -> dict:
    """Extracts all relevant data (amount, vendor, date) using a combination of regex and GPT."""
    amount = extract_amount(text)
    vendor = extract_vendor_name(text)
    date = extract_date(text)

    logger.info(f"Extracted vendor name: {vendor}")
    logger.info(f"Amount: {amount}")
    logger.info(f"Date: {date}")

    return {
        "amount": amount or "Unknown",
        "vendor_name": vendor or "Unknown",
        "purchase_date": date or "Unknown"
    }


# --- Main Processing Function ---
def process_invoice(image_bytes: bytes, invoice_id: int, user_id: int, original_s3_key_placeholder: str):
    """
    Processes an invoice image: performs OCR, extracts data, classifies,
    uploads the image to S3, and updates the database.
    """
    try:
        logger.info(
            f"Processing invoice {invoice_id} for user {user_id} with placeholder S3 key: {original_s3_key_placeholder}")

        # Perform OCR
        text = perform_ocr(image_bytes, invoice_id)
        if len(text.strip()) < 20:
            raise ValueError(f"OCR output too short or empty for invoice {invoice_id}: {repr(text)}")
        logger.info(f"OCR extracted text: {text}")

        # Classify category and extract data
        category = classify_category(text)
        extracted = extract_all_data(text)

        logger.info(f"Vendor Name Detected: {extracted['vendor_name']}")
        logger.info(f"Amount: {extracted['amount']}")
        logger.info(f"Date: {extracted['purchase_date']}")
        logger.info(f"Category: {category}")

        # --- Upload image to S3 ---
        file_extension = os.path.splitext(original_s3_key_placeholder)[
            1] if original_s3_key_placeholder else ".jpg"
        actual_s3_key = f"invoices/{user_id}/{uuid.uuid4()}{file_extension}"

        try:
            s3_client.put_object(Bucket=S3_BUCKET, Key=actual_s3_key, Body=image_bytes, ContentType='image/jpeg')
            logger.info(f"Invoice {invoice_id}: Uploaded image to S3 as {actual_s3_key}")
        except Exception as e:
            logger.error(f"Invoice {invoice_id}: Failed to upload image to S3: {e}", exc_info=True)
            raise

        # Prepare extracted data
        extracted_data = {
            "raw_text": text,
            "category_prediction": category,
            **extracted
        }

        # Update the database with processed data and the actual S3 key
        with engine.begin() as conn:
            result = conn.execute(
                update(invoices)
                .where(invoices.c.id == invoice_id)
                .values(
                    extracted_data=extracted_data,
                    category=category,
                    status="processed",
                    s3_key=actual_s3_key
                )
            )
            if result.rowcount == 0:
                logger.warning(f"Invoice ID {invoice_id} not found for update after processing.")
            else:
                logger.info(f"Invoice {invoice_id} updated successfully with actual S3 key {actual_s3_key}.")

    except Exception as e:
        logger.error(f"Processing failed for invoice {invoice_id}: {e}", exc_info=True)
        # Update invoice status to 'failed' if processing fails
        with engine.begin() as conn:
            conn.execute(
                update(invoices)
                .where(invoices.c.id == invoice_id)
                .values(
                    status="failed",
                    extracted_data={"error": str(e), "message": "Processing failed."}
                )
            )
            logger.info(f"Invoice {invoice_id} status updated to 'failed'.")


# --- Telegram Interaction Functionality (Moved from API Server) ---
async def send_telegram_message(chat_id: str, text: str = None, photo_buffer: io.BytesIO = None,
                                document_buffer: io.BytesIO = None, filename: str = None, caption: str = None):
    """
    Sends a message, photo, or document to a Telegram chat.
    """
    if not telegram_bot_instance:
        logger.error("Telegram bot instance not initialized in worker. Cannot send message.")
        return

    try:
        if photo_buffer:
            await telegram_bot_instance.send_photo(chat_id=chat_id,
                                                   photo=InputFile(photo_buffer, filename=filename or "image.png"),
                                                   caption=caption)
            logger.info(f"Sent photo to Telegram chat_id: {chat_id}")
        elif document_buffer:
            await telegram_bot_instance.send_document(chat_id=chat_id, document=InputFile(document_buffer,
                                                                                          filename=filename or "document.pdf"),
                                                      caption=caption)
            logger.info(f"Sent document to Telegram chat_id: {chat_id}")
        elif text:
            await telegram_bot_instance.send_message(chat_id=chat_id, text=text)
            logger.info(f"Sent text message to Telegram chat_id: {chat_id}")
        else:
            logger.warning(f"No content provided to send to Telegram chat_id: {chat_id}")
    except Exception as e:
        logger.error(f"Error sending message to Telegram chat_id {chat_id}: {e}", exc_info=True)


# --- Report Generation Functions (Moved from API Server) ---

async def generate_and_send_excel_report(user_id: int, telegram_chat_id: str):
    logger.info(f"Generating Excel report for user {user_id} (chat_id: {telegram_chat_id})")
    invoices_list = []
    with engine.connect() as conn:
        query = select(invoices).where(invoices.c.user_id == user_id).order_by(invoices.c.created_at.asc())
        result = conn.execute(query).fetchall()
        for row in result:
            invoice_dict = row._asdict()
            if 'extracted_data' in invoice_dict and isinstance(invoice_dict['extracted_data'], str):
                try:
                    invoice_dict['extracted_data'] = json.loads(invoice_dict['extracted_data'])
                except json.JSONDecodeError:
                    invoice_dict['extracted_data'] = {}
            invoice_dict['category'] = invoice_dict.get('category') or "Uncategorized"
            invoices_list.append(invoice_dict)

    if not invoices_list:
        await send_telegram_message(telegram_chat_id, text="No invoices found to generate an Excel report.")
        logger.info(f"No invoices for Excel report for user {user_id}.")
        return

    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output, {'in_memory': True})
    worksheet = workbook.add_worksheet("Invoices")

    headers = [
        "ID", "Status", "Category", "Created At", "Vendor", "Amount",
        "Purchase Date", "Original Download URL"
    ]

    for col_num, header in enumerate(headers):
        worksheet.write(0, col_num, header)

    for row_num, invoice in enumerate(invoices_list, start=1):
        extracted = invoice.get('extracted_data', {}) or {}
        s3_key = invoice.get('s3_key', '')

        # Generate presigned URL for download
        presigned_url = "#"  # Default in case of error or if not yet uploaded to S3
        if S3_BUCKET and s3_key and not s3_key.startswith("pending_upload_"):  # Only if it's a real S3 key
            try:
                presigned_url = s3_client.generate_presigned_url(
                    'get_object',
                    Params={
                        'Bucket': S3_BUCKET,
                        'Key': s3_key,
                        'ResponseContentDisposition': 'attachment'
                    },
                    ExpiresIn=3600  # URL valid for 1 hour
                )
            except Exception as e:
                logger.error(f"Error generating presigned URL for {s3_key}: {e}", exc_info=True)

        worksheet.write(row_num, 0, invoice.get('id'))
        worksheet.write(row_num, 1, invoice.get('status', 'Unknown'))
        worksheet.write(row_num, 2, invoice.get('category', 'Uncategorized'))
        worksheet.write(row_num, 3, invoice.get('created_at').isoformat() if invoice.get('created_at') else '')
        worksheet.write(row_num, 4, extracted.get('vendor_name', 'Unknown'))
        worksheet.write(row_num, 5, extracted.get('amount', 'Unknown'))
        worksheet.write(row_num, 6, extracted.get('purchase_date', 'Unknown'))
        worksheet.write_url(row_num, 7, presigned_url, string="Download")  # Write URL as clickable link

    workbook.close()
    output.seek(0)

    await send_telegram_message(
        chat_id=telegram_chat_id,
        document_buffer=output,
        filename="invoices.xlsx",
        caption="Here is your invoice data as an Excel file."
    )
    logger.info(f"Excel report sent to Telegram for user {user_id}.")


async def generate_and_send_chart_report(user_id: int, telegram_chat_id: str, categories_summary: list[dict]):
    logger.info(f"Generating chart report for user {user_id} (chat_id: {telegram_chat_id})")

    if not categories_summary:
        await send_telegram_message(telegram_chat_id, text="No data provided to generate a chart report.")
        logger.info(f"No chart data for user {user_id}.")
        return

    labels = [item['category'] for item in categories_summary]
    sizes = [item['total_amount'] for item in categories_summary]

    if not labels or not sizes:
        await send_telegram_message(telegram_chat_id, text="No valid data to generate a chart report.")
        logger.info(f"Invalid chart data for user {user_id}.")
        return

    fig, ax = plt.subplots(figsize=(8, 8))

    colors = ['#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', '#9966FF', '#FF9F40', '#6A5ACD', '#20B2AA', '#7B68EE',
              '#FFD700', '#A9A9A9', '#ADD8E6', '#8A2BE2', '#7FFF00', '#DC143C', '#00FFFF', '#00008B', '#B8860B',
              '#006400', '#8B008B']
    pie_colors = [colors[i % len(colors)] for i in range(len(labels))]

    ax.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=90, colors=pie_colors,
           wedgeprops={'edgecolor': 'black'}, textprops={'fontsize': 10})
    ax.axis('equal')
    ax.set_title('Invoice Category Distribution', fontsize=16, pad=20)

    buffer = io.BytesIO()
    plt.savefig(buffer, format='png', bbox_inches='tight', dpi=100)
    buffer.seek(0)
    plt.close(fig)

    await send_telegram_message(
        chat_id=telegram_chat_id,
        photo_buffer=buffer,
        filename="invoice_categories_chart.png",
        caption="Here is your invoice category distribution chart."
    )
    logger.info(f"Chart report sent to Telegram for user {user_id}.")


# --- Function to handle OTP sending (Moved from Telegram Bot's consumer logic) ---
async def send_otp_to_telegram(user_id: int, otp_secret: str, telegram_chat_id: str):
    logger.info(f"Sending OTP to user {user_id} (chat_id: {telegram_chat_id})")
    await send_telegram_message(
        chat_id=telegram_chat_id,
        text=f"Your OTP for Invoice Manager is: {otp_secret}. It is valid for 5 minutes."
    )
    logger.info(f"OTP sent to Telegram for user {user_id}.")
