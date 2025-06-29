from PIL import Image, ImageFilter, ImageOps, ImageEnhance
import io
import pytesseract
import openai
import re
import logging
from datetime import datetime
from sqlalchemy import create_engine, MetaData, Table, update, Column, Integer, String, DateTime, JSON, ForeignKey
from paddleocr import PaddleOCR
import cv2
import numpy as np

from shared.config import DB_URL
from .config import OPENAI_API_KEY

# Logging setup
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# OpenAI API key
openai.api_key = OPENAI_API_KEY

# Database setup
engine = create_engine(DB_URL)
metadata = MetaData()

# DB Table
invoices = Table(
    "invoices", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("user_id", Integer, ForeignKey("users.id"), nullable=False),
    Column("s3_key", String, nullable=False, unique=True),
    Column("status", String, default="pending"),
    Column("created_at", DateTime, default=datetime.utcnow),
    Column("extracted_data", JSON),
    Column("category", String),
)
metadata.create_all(engine)

ocr = PaddleOCR(use_angle_cls=True, lang='en')

# OCR and Preprocessing
def preprocess_image(img_bytes: bytes) -> Image:
    img = Image.open(io.BytesIO(img_bytes)).convert("L")
    img = img.resize((img.width * 3, img.height * 3), Image.LANCZOS)
    img = ImageOps.autocontrast(img)
    img = img.filter(ImageFilter.MedianFilter(size=3))
    img = img.point(lambda x: 0 if x < 160 else 255)
    enhancer = ImageEnhance.Sharpness(img)
    img = enhancer.enhance(3.5)
    return img


def perform_ocr(img_bytes: bytes, invoice_id: int) -> str:
    img = preprocess_image(img_bytes)

    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    buffered.seek(0)
    file_bytes = np.asarray(bytearray(buffered.read()), dtype=np.uint8)
    img_cv = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)

    result = ocr.ocr(img_cv)

    text = ""
    if result and isinstance(result, list):
        for line in result[0]:
            text += line[1][0] + "\n"

    if len(text.strip()) < 20:
        logger.warning(f"OCR result too short for invoice {invoice_id}, fallback to Tesseract")
        text = pytesseract.image_to_string(img, lang="eng")

    with open(f"/tmp/ocr_debug_{invoice_id}.txt", "w", encoding="utf-8") as f:
        f.write(text)

    return text.strip()


# Extraction Utilities
def extract_date(text: str) -> str:
    patterns = [
        r'(\d{4}[- /.]\d{2}[- /.]\d{2})',
        r'(\d{2}[- /.]\d{2}[- /.]\d{4})',
        r'(\d{2}[- /.]\d{2}[- /.]\d{2})'
    ]
    for pattern in patterns:
        matches = re.findall(pattern, text)
        for raw_date in matches:
            cleaned = raw_date.replace('/', '-').replace('.', '-').replace(' ', '')
            for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%m-%d-%Y", "%d-%m-%y", "%m-%d-%y"):
                try:
                    parsed = datetime.strptime(cleaned, fmt)
                    if 1900 < parsed.year < 2100:
                        return parsed.strftime("%Y-%m-%d")
                except:
                    continue
    return extract_with_gpt(
        text,
        "Extract the purchase date in YYYY-MM-DD format from this invoice. Only return the date without extra text."
    )


def extract_amount(text: str) -> str:
    labels = ["total", "amount due", "amount paid", "balance due", "grand total"]
    lines = text.lower().splitlines()

    candidates = []

    for line in lines:
        if any(label in line for label in labels):
            nums = re.findall(r"\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})", line)
            for num in nums:
                number = num.replace(",", "").replace("$", "").replace(" ", "")
                try:
                    candidates.append(float(number))
                except:
                    continue

    if candidates:
        return str(max(candidates))

    return extract_with_gpt(
        text,
        "Extract the total amount paid in this invoice. Only return the number, without currency symbols or extra text."
    )


def extract_vendor_name(text: str) -> str:
    lines = text.strip().split("\n")
    candidates = []

    for line in lines:
        line_clean = line.strip()

        if not line_clean:
            continue

        if any(char.isdigit() for char in line_clean):
            continue

        letter_count = sum(c.isalpha() for c in line_clean)
        char_count = len(line_clean)

        if char_count == 0:
            continue

        letter_ratio = letter_count / char_count

        if letter_ratio < 0.6:
            continue

        if 3 <= len(line_clean) <= 40:
            score = (letter_ratio * 100) - abs(20 - len(line_clean))
            candidates.append((score, line_clean))

    if candidates:
        candidates.sort(key=lambda x: x[0], reverse=True)
        top_candidate = candidates[0][1]
        # Validate top candidate with GPT
        if is_valid_vendor_with_gpt(text, top_candidate):
            return top_candidate.title().strip()

    # Fallback to GPT directly
    return fallback_vendor_with_gpt(text)


def is_valid_vendor_with_gpt(full_text: str, candidate: str) -> bool:
    try:
        prompt = f"Is '{candidate}' the name of the store, restaurant, or vendor in this invoice text?\n\nAnswer Yes or No only.\n\n{full_text[:2000]}"
        response = openai.chat.completions.create(
            model="gpt-4-turbo",
            messages=[
                {"role": "system", "content": "You are an assistant that verifies whether a candidate string is the vendor name in an invoice."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=3,
            temperature=0.0,
        )
        result = response.choices[0].message.content.strip().lower()
        return result == "yes"
    except:
        return False


def fallback_vendor_with_gpt(text: str) -> str:
    try:
        result = extract_with_gpt(
            text,
            "Extract the main vendor, restaurant, or store name from this invoice. Only return the name without any extra text, no labels, no words like invoice or total."
        )
        return result.title().strip()
    except:
        return "Unknown"


def extract_with_gpt(text: str, instruction: str, max_tokens: int = 20) -> str:
    try:
        response = openai.chat.completions.create(
            model="gpt-4-turbo",
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
        f"Respond only with the category.\n\n{text[:1500]}"
    )
    try:
        response = openai.chat.completions.create(
            model="gpt-4-turbo",
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


# Main Processing Function
def process_invoice(s3_key: str, img_bytes: bytes, invoice_id: int):
    logger.info(f"Processing invoice {s3_key} (ID: {invoice_id})")
    try:
        text = perform_ocr(img_bytes, invoice_id)
        if len(text.strip()) < 20:
            raise ValueError(f"OCR output too short: {repr(text)}")

        logger.debug(f"OCR text: {text}")

        category = classify_category(text)
        extracted = extract_all_data(text)

        logger.info(f"Vendor Name Detected: {extracted['vendor_name']}")
        logger.info(f"Amount: {extracted['amount']}")
        logger.info(f"Date: {extracted['purchase_date']}")
        logger.info(f"Category: {category}")

        extracted_data = {
            "raw_text": text,
            "category_prediction": category,
            **extracted
        }

        with engine.begin() as conn:
            result = conn.execute(
                update(invoices)
                .where(invoices.c.id == invoice_id)
                .values(
                    extracted_data=extracted_data,
                    category=category,
                    status="processed"
                )
            )
            if result.rowcount == 0:
                logger.warning(f"Invoice ID {invoice_id} not found.")
            else:
                logger.info(f"Invoice {invoice_id} updated successfully.")

    except Exception as e:
        logger.error(f"Processing failed for invoice {invoice_id}: {e}", exc_info=True)
        with engine.begin() as conn:
            conn.execute(
                update(invoices)
                .where(invoices.c.id == invoice_id)
                .values(
                    status="failed",
                    extracted_data={"error": str(e), "message": "Processing failed."}
                )
            )
