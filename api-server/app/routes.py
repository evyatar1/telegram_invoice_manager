# api-server/app/routes.py
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Request
from pydantic import BaseModel, EmailStr
from sqlalchemy import create_engine, Table, Column, Integer, String, MetaData, DateTime, JSON, select, delete, ForeignKey, update as sql_update
from passlib.context import CryptContext
from jose import jwt, JWTError
from datetime import datetime, timedelta, timezone
import uuid, random, boto3, os
# Ensure shared.config is correctly imported. If it's in a 'shared' directory at the project root,
# and '/app' is added to PYTHONPATH in Dockerfile, this import should work.
from shared.config import DB_URL, S3_BUCKET, S3_REGION, JWT_SECRET, JWT_ALGO, JWT_EXP_DELTA_SECONDS, KAFKA_TOPIC, KAFKA_TELEGRAM_OTP_TOPIC
from aiokafka import AIOKafkaProducer
from fastapi.security import OAuth2PasswordBearer
import io
import json
import csv
from telegram import Bot, InputFile
import matplotlib.pyplot as plt
import xlsxwriter
from sqlalchemy.engine.row import Row
from botocore.exceptions import ClientError
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# DB setup (single DB with multiple tables)
engine = create_engine(DB_URL)
metadata = MetaData()

TELEGRAM_TOKEN = os.getenv("TG_BOT_TOKEN")
if not TELEGRAM_TOKEN:
    logger.warning("TG_BOT_TOKEN not set. Telegram features will be disabled.")
    bot = None
else:
    bot = Bot(token=TELEGRAM_TOKEN)

# Users table definition - NOW MATCHES init.sql EXACTLY
users = Table("users", metadata,
              Column("id", Integer, primary_key=True, autoincrement=True),
              Column("email", String, unique=True, nullable=False),
              Column("hashed_pw", String, nullable=False),
              Column("phone", String, unique=True, nullable=True),
              Column("is_verified", Integer, default=0), # 0 for not verified, 1 for verified
              Column("otp_secret", String, nullable=True), # Changed from otp_code to otp_secret
              Column("otp_expires", DateTime, nullable=True),
              Column("telegram_chat_id", String, unique=True, nullable=True)
              )

invoices = Table(
    "invoices",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("user_id", Integer, ForeignKey("users.id"), nullable=False),
    Column("s3_key", String, unique=True, nullable=False),
    Column("created_at", DateTime, default=datetime.now(timezone.utc)),
    Column("status", String, default="pending"),
    Column("extracted_data", JSON),
    Column("category", String),
)

metadata.create_all(engine)

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2PasswordBearer for token extraction
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

# S3 client
s3_client = boto3.client("s3", region_name=S3_REGION)

# Router for API endpoints
router = APIRouter()


# Helper for JWT token
def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGO)
    return encoded_jwt


# Helper for getting current user
async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
        user_email: str = payload.get("sub")
        if user_email is None:
            raise credentials_exception
        with engine.connect() as conn:
            stmt = select(users).where(users.c.email == user_email)
            result = conn.execute(stmt).first()
            if result is None:
                raise credentials_exception
            return result._asdict()
    except JWTError:
        raise credentials_exception


# Pydantic models for request/response bodies

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    phone: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class VerifyOtp(BaseModel):
    email: EmailStr
    otp: str

class InvoiceResponse(BaseModel):
    id: int
    user_id: int
    s3_key: str
    created_at: datetime
    status: str
    extracted_data: dict | None = None
    category: str | None = None
    preview_url: str

class TelegramLinkRequest(BaseModel):
    phone: str
    telegram_chat_id: str

class ChartRequest(BaseModel):
    chart_data: list[dict] = []

# API Endpoints
@router.delete("/invoices/{invoice_id}")
async def delete_invoice(invoice_id: int, current_user: dict = Depends(get_current_user)):
    with engine.begin() as conn:
        query = select(invoices).where(invoices.c.id == invoice_id, invoices.c.user_id == current_user['id'])
        result = conn.execute(query).fetchone()

        if not result:
            raise HTTPException(status_code=404, detail="Invoice not found or you don't have permission to delete it.")

        s3_key = result.s3_key

        try:
            s3_client.delete_object(Bucket=S3_BUCKET, Key=s3_key)
            logger.info(f"S3 object deleted: {s3_key}")
        except Exception as e:
            logger.error(f"Error deleting from S3: {e}")

        conn.execute(delete(invoices).where(invoices.c.id == invoice_id))

    return {"message": "Invoice deleted successfully"}


@router.post("/register")
async def register_user(user: UserCreate):
    with engine.connect() as conn:
        existing_user_query = select(users).where(users.c.email == user.email)
        existing_user = conn.execute(existing_user_query).fetchone()
        if existing_user:
            raise HTTPException(status_code=400, detail="Email already registered")

        hashed_password = pwd_context.hash(user.password)

        insert_stmt = users.insert().values(
            email=user.email,
            hashed_pw=hashed_password,
            phone=user.phone,
            is_verified=0,
            otp_secret=None, # Changed from otp_code
            otp_expires=None,
            telegram_chat_id=None
        )
        conn.execute(insert_stmt)
        conn.commit()

    return {"message": "User registered successfully. Please link your Telegram account to verify."}

@router.post("/link-telegram-account")
async def link_telegram_account(telegram_link_data: TelegramLinkRequest, request: Request):
    """
    Endpoint for Telegram bot to link a user's Telegram chat ID
    and send OTP via Telegram.
    """
    with engine.connect() as conn:
        user_query = select(users).where(users.c.phone == telegram_link_data.phone)
        user = conn.execute(user_query).fetchone()

        if not user:
            raise HTTPException(status_code=404, detail="User with this phone number not found.")

        if user.telegram_chat_id and user.telegram_chat_id != telegram_link_data.telegram_chat_id:
             raise HTTPException(status_code=400, detail="This phone number is already linked to a different Telegram account.")

        otp_secret = str(random.randint(100000, 999999)) # Changed from otp_code
        otp_expires = datetime.now(timezone.utc) + timedelta(minutes=5)

        update_stmt = sql_update(users).where(users.c.id == user.id).values(
            telegram_chat_id=telegram_link_data.telegram_chat_id,
            otp_secret=otp_secret, # Changed from otp_code
            otp_expires=otp_expires
        )
        conn.execute(update_stmt)
        conn.commit()
        logger.info(f"User {user.email} updated with chat_id {telegram_link_data.telegram_chat_id} and OTP.")

        if not hasattr(request.app.state, 'kafka_producer') or not request.app.state.kafka_producer:
            raise HTTPException(status_code=500, detail="Kafka producer is not initialized.")

        message_payload = {
            "user_id": user.id,
            "otp_secret": otp_secret, # Changed from otp_code
            "chat_id": telegram_link_data.telegram_chat_id
        }
        await request.app.state.kafka_producer.send_and_wait(
            KAFKA_TELEGRAM_OTP_TOPIC,
            json.dumps(message_payload).encode("utf-8")
        )
        logger.info(f"Sent OTP Kafka message for user {user.id} to topic {KAFKA_TELEGRAM_OTP_TOPIC}.")

    return {"message": "Telegram account linked. OTP sent to your Telegram chat."}


@router.post("/verify-otp", response_model=Token)
async def verify_otp(otp_data: VerifyOtp):
    with engine.connect() as conn:
        query = select(users).where(users.c.email == otp_data.email)
        user = conn.execute(query).fetchone()

        if not user or user.otp_secret != otp_data.otp or (user.otp_expires and user.otp_expires < datetime.now(timezone.utc)): # Changed from otp_code
            raise HTTPException(status_code=400, detail="Invalid or expired OTP")

        update_stmt = sql_update(users).where(users.c.email == otp_data.email).values(
            otp_secret=None, # Changed from otp_code
            otp_expires=None,
            is_verified=1
        )
        conn.execute(update_stmt)
        conn.commit()
        logger.info(f"User {user.email} successfully verified.")

        access_token = create_access_token(
            data={"sub": user.email},
            expires_delta=timedelta(seconds=JWT_EXP_DELTA_SECONDS)
        )
        return {"access_token": access_token, "token_type": "bearer"}


@router.post("/login", response_model=Token)
async def login_for_access_token(user_login: UserLogin):
    with engine.connect() as conn:
        stmt = select(users).where(users.c.email == user_login.email)
        user = conn.execute(stmt).fetchone()

        if not user or not pwd_context.verify(user_login.password, user.hashed_pw):
            raise HTTPException(status_code=400, detail="Incorrect email or password")

        # --- START OF MODIFICATION ---
        # REMOVED/COMMENTED OUT THE VERIFICATION CHECK FOR LOGIN
        # if not user.is_verified:
        #     raise HTTPException(status_code=400, detail="Account not verified. Please complete Telegram linking and OTP verification.")
        # --- END OF MODIFICATION ---

        access_token = create_access_token(
            data={"sub": user.email},
            expires_delta=timedelta(seconds=JWT_EXP_DELTA_SECONDS)
        )
        return {"access_token": access_token, "token_type": "bearer"}


@router.post("/upload-invoice")
async def upload_invoice(
        request: Request,
        file: UploadFile = File(...),
        current_user: dict = Depends(get_current_user)
):
    if not S3_BUCKET:
        raise HTTPException(status_code=500, detail="S3_BUCKET environment variable not set.")

    user_id = current_user['id']
    file_extension = os.path.splitext(file.filename)[1]
    s3_key = f"invoices/{user_id}/{uuid.uuid4()}{file_extension}"

    try:
        file_content = await file.read()
        s3_client.put_object(Bucket=S3_BUCKET, Key=s3_key, Body=file_content, ContentType=file.content_type)
        logger.info(f"API Server: Uploaded {file.filename} to S3 as {s3_key}")

        with engine.begin() as conn:
            insert_stmt = invoices.insert().values(
                user_id=user_id,
                s3_key=s3_key,
                status="pending",
                created_at=datetime.now(timezone.utc)
            ).returning(invoices.c.id)
            result = conn.execute(insert_stmt)
            invoice_id = result.scalar_one()
            logger.info(f"API Server: Recorded invoice {s3_key} in DB for user {user_id} (invoice_id={invoice_id})")

        if not hasattr(request.app.state, 'kafka_producer') or not request.app.state.kafka_producer:
            raise HTTPException(status_code=500, detail="Kafka producer is not initialized.")

        message_payload = {
            "invoice_id": invoice_id,
            "s3_key": s3_key
        }

        await request.app.state.kafka_producer.send_and_wait(
            KAFKA_TOPIC,
            json.dumps(message_payload).encode("utf-8")
        )
        logger.info(f"API Server: Sent Kafka message: {message_payload}")

        return {
            "message": "Invoice uploaded and submitted for processing",
            "invoice_id": invoice_id,
            "s3_key": s3_key
        }

    except Exception as e:
        logger.error(f"API Server: Error during upload or Kafka message: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to upload invoice or send for processing: {e}")


async def get_invoices(current_user: dict):
    user_id = current_user['id']
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

            try:
                presigned_url = s3_client.generate_presigned_url(
                    'get_object',
                    Params={
                        'Bucket': S3_BUCKET,
                        'Key': row.s3_key,
                        'ResponseContentDisposition': 'attachment'
                    },
                    ExpiresIn=3600
                )
                invoice_dict['preview_url'] = presigned_url
            except Exception as e:
                logger.error(f"API Server: ERROR generating presigned URL for {row.s3_key}: {e}", exc_info=True)
                invoice_dict['preview_url'] = "#"

            invoices_list.append(invoice_dict)

        logger.info(f"API Server: Retrieved {len(invoices_list)} invoices for user {user_id}")

    return invoices_list


@router.get("/invoices", response_model=list[InvoiceResponse])
async def list_invoices(current_user: dict = Depends(get_current_user)):
    invoices_list = await get_invoices(current_user)
    return invoices_list


@router.post("/send-csv-to-telegram")
async def send_excel_to_telegram(current_user: dict = Depends(get_current_user)):
    TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
    if not TG_BOT_TOKEN:
        raise HTTPException(status_code=500, detail="Telegram bot not configured. TG_BOT_TOKEN is missing.")

    user_telegram_chat_id = current_user['telegram_chat_id']
    if not user_telegram_chat_id:
        raise HTTPException(status_code=400, detail="Telegram chat ID not registered for this user.")

    invoices_list = await get_invoices(current_user)
    if not invoices_list:
        raise HTTPException(status_code=404, detail="No invoices found to generate Excel.")

    bucket_name = S3_BUCKET

    def generate_presigned_url_for_excel(s3_key: str) -> str:
        try:
            return s3_client.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': bucket_name,
                    'Key': s3_key,
                    'ResponseContentDisposition': 'attachment'
                },
                ExpiresIn=3600
            )
        except ClientError as e:
            logger.error(f"Error generating URL for {s3_key}: {e}")
            return s3_key

    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output, {'in_memory': True})
    worksheet = workbook.add_worksheet("Invoices")

    headers = [
        "ID",
        "Status",
        "Category",
        "Created At",
        "Vendor",
        "Amount",
        "Purchase Date",
        "Download Original"
    ]

    for col_num, header in enumerate(headers):
        worksheet.write(0, col_num, header)

    for row_num, invoice in enumerate(invoices_list, start=1):
        extracted = invoice.get('extracted_data', {}) or {}
        s3_key = invoice.get('s3_key', '')
        presigned_url = generate_presigned_url_for_excel(s3_key) if s3_key else ''

        worksheet.write(row_num, 0, invoice.get('id'))
        worksheet.write(row_num, 1, invoice.get('status', 'Unknown'))
        worksheet.write(row_num, 2, invoice.get('category', 'Uncategorized'))
        worksheet.write(row_num, 3, invoice.get('created_at').isoformat() if invoice.get('created_at') else '')
        worksheet.write(row_num, 4, extracted.get('vendor_name', 'Unknown'))
        worksheet.write(row_num, 5, extracted.get('amount', 'Unknown'))
        worksheet.write(row_num, 6, extracted.get('purchase_date', 'Unknown'))
        worksheet.write_url(row_num, 7, presigned_url, string="Download")

    workbook.close()
    output.seek(0)

    try:
        telegram_bot_instance = bot if bot else Bot(token=TG_BOT_TOKEN)
        await telegram_bot_instance.send_document(
            chat_id=user_telegram_chat_id,
            document=InputFile(output, filename="invoices.xlsx"),
            caption="Here are your invoices as an Excel file."
        )
        return {"message": "Excel file sent to Telegram successfully!"}
    except Exception as e:
        logger.error(f"Error sending Excel to Telegram: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to send Excel to Telegram: {e}")


@router.post("/send-chart-to-telegram")
async def send_chart_to_telegram(chart_request: ChartRequest, current_user: dict = Depends(get_current_user)):
    if not bot:
        raise HTTPException(status_code=500, detail="Telegram bot not configured. TG_BOT_TOKEN is missing.")

    user_id = current_user['id']
    user_telegram_chat_id = current_user['telegram_chat_id']

    if not user_telegram_chat_id:
        raise HTTPException(status_code=400, detail="Telegram chat ID not registered for this user.")

    categories_summary = chart_request.chart_data

    if not categories_summary:
        raise HTTPException(status_code=404, detail="No chart data provided.")

    labels = [item['category'] for item in categories_summary]
    sizes = [item['total_amount'] for item in categories_summary]

    if not labels or not sizes:
        raise HTTPException(status_code=404, detail="No valid data to generate chart.")

    fig, ax = plt.subplots(figsize=(8, 8))

    colors = ['#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', '#9966FF', '#FF9F40', '#6A5ACD', '#20B2AA', '#7B68EE',
              '#FFD700', '#A9A9A9', '#ADD8E6', '#8A2BE2', '#7FFF00', '#DC143C', '#00FFFF', '#00008B', '#B8860B', '#006400', '#8B008B']
    pie_colors = [colors[i % len(colors)] for i in range(len(labels))]

    ax.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=90, colors=pie_colors,
           wedgeprops={'edgecolor': 'black'}, textprops={'fontsize': 10})
    ax.axis('equal')
    ax.set_title('Invoice Category Distribution', fontsize=16, pad=20)

    buffer = io.BytesIO()
    plt.savefig(buffer, format='png', bbox_inches='tight', dpi=100)
    buffer.seek(0)
    plt.close(fig)

    try:
        await bot.send_photo(
            chat_id=user_telegram_chat_id,
            photo=InputFile(buffer, filename="invoice_categories_chart.png"),
            caption="Here is your invoice category distribution chart."
        )
        return {"message": "Chart sent to Telegram successfully!"}
    except Exception as e:
        logger.error(f"Error sending chart to Telegram: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to send chart to Telegram: {e}")

@router.get("/users/me")
async def get_user_profile(current_user: dict = Depends(get_current_user)):
    """
    Returns the current user's profile, including verification status and telegram_chat_id.
    """
    # current_user already contains all user fields from the DB due to get_current_user
    # We can return a subset or all of it, depending on what frontend needs.
    # For now, let's return relevant fields.
    return {
        "id": current_user['id'],
        "email": current_user['email'],
        "phone": current_user['phone'],
        "is_verified": bool(current_user['is_verified']), # Convert 0/1 to boolean
        "telegram_chat_id": current_user['telegram_chat_id']
    }
