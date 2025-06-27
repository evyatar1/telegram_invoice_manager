from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Request
from pydantic import BaseModel, EmailStr
from sqlalchemy import create_engine, Table, Column, Integer, String, MetaData, DateTime, JSON, select, delete
from passlib.context import CryptContext
from jose import jwt, JWTError
from datetime import datetime, timedelta, timezone
import uuid, random, boto3, os
from shared.config import DB_URL, S3_BUCKET, S3_REGION, JWT_SECRET, JWT_ALGO, JWT_EXP_DELTA_SECONDS, KAFKA_TOPIC
from aiokafka import AIOKafkaProducer
from fastapi.security import OAuth2PasswordBearer
import io
import json
import csv
from telegram import Bot, InputFile
import matplotlib.pyplot as plt

from .kafka_producer import producer as kafka_producer_instance

# DB setup (single DB with multiple tables)
engine = create_engine(DB_URL)
metadata = MetaData()

TELEGRAM_TOKEN = os.getenv("TG_BOT_TOKEN")
if not TELEGRAM_TOKEN:
    print("Warning: TG_BOT_TOKEN not set. Telegram features will be disabled.")
    bot = None  # Set bot to None if token is not available
else:
    bot = Bot(token=TELEGRAM_TOKEN)

# Users table definition
users = Table("users", metadata,
              Column("id", Integer, primary_key=True, autoincrement=True),
              Column("email", String, unique=True, nullable=False),
              Column("hashed_pw", String, nullable=False),
              Column("phone", String, unique=True),
              Column("telegram_chat_id", String, unique=True),
              Column("otp_code", String),
              Column("otp_expires", DateTime)
              )

invoices = Table(
    "invoices",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("user_id", Integer, nullable=False),
    Column("s3_key", String, unique=True, nullable=False),
    Column("created_at", DateTime, default=datetime.now(timezone.utc)),
    Column("status", String, default="pending"),
    Column("extracted_data", JSON),  # To store OCR/NLP results
    Column("category", String),  # New column for category
)

metadata.create_all(engine)  # Create tables if they don't exist

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2PasswordBearer for token extraction
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")  # "token" is the endpoint that issues token

# S3 client
s3_client = boto3.client("s3", region_name=S3_REGION)

# Router for API endpoints
router = APIRouter()


# Helper for JWT token
def create_jwt_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGO)  # Corrected encoding
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
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    with engine.connect() as connection:
        query = select(users).where(users.c.email == email)
        user = connection.execute(query).fetchone()
        if user is None:
            raise credentials_exception
        return user


# Pydantic models for request/response bodies
class UserCreate(BaseModel):
    email: EmailStr
    password: str
    phone: str
    telegram_chat_id: str | None = None


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class OTPVerify(BaseModel):
    email: EmailStr
    otp: str
    telegram_chat_id: str | None = None


class InvoiceResponse(BaseModel):
    id: int
    user_id: int
    s3_key: str
    created_at: datetime
    status: str
    extracted_data: dict | None = None
    category: str | None = None
    preview_url: str  # Add this for the frontend


# API Endpoints
@router.delete("/invoices/{invoice_id}")
async def delete_invoice(invoice_id: int, current_user: dict = Depends(get_current_user)):
    with engine.begin() as conn:
        query = select(invoices).where(invoices.c.id == invoice_id, invoices.c.user_id == current_user.id)
        result = conn.execute(query).fetchone()

        if not result:
            raise HTTPException(status_code=404, detail="Invoice not found")

        s3_key = result.s3_key

        try:
            s3_client.delete_object(Bucket=S3_BUCKET, Key=s3_key)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to delete from S3: {e}")

        conn.execute(delete(invoices).where(invoices.c.id == invoice_id))

    return {"message": "Invoice deleted successfully"}


@router.post("/register")
async def register_user(user: UserCreate):
    with engine.connect() as conn:
        # Check if user already exists
        existing_user_query = select(users).where(users.c.email == user.email)
        existing_user = conn.execute(existing_user_query).fetchone()
        if existing_user:
            raise HTTPException(status_code=400, detail="Email already registered")

        hashed_password = pwd_context.hash(user.password)
        otp_code = str(random.randint(100000, 999999))
        otp_expires = datetime.now(timezone.utc) + timedelta(minutes=5)

        insert_stmt = users.insert().values(
            email=user.email,
            hashed_pw=hashed_password,
            phone=user.phone,
            telegram_chat_id=user.telegram_chat_id,
            otp_code=otp_code,
            otp_expires=otp_expires
        )
        conn.execute(insert_stmt)
        conn.commit()

        # Send OTP via Telegram if chat ID is provided
        if user.telegram_chat_id and bot:
            try:
                await bot.send_message(chat_id=user.telegram_chat_id, text=f"Your OTP is: {otp_code}")
                print(f"Sent OTP {otp_code} to Telegram chat ID {user.telegram_chat_id}")
            except Exception as e:
                print(f"Error sending Telegram OTP: {e}")
                raise HTTPException(status_code=500,
                                    detail="Registration successful, but failed to send OTP via Telegram. Check your Telegram chat ID or bot token.")

    return {"message": "User registered successfully! OTP sent if Telegram chat ID provided."}


@router.post("/verify-otp", response_model=Token)
async def verify_otp(otp_data: OTPVerify):
    with engine.connect() as conn:
        query = select(users).where(users.c.email == otp_data.email)
        user = conn.execute(query).fetchone()

        if not user or user.otp_code != otp_data.otp or user.otp_expires < datetime.now(timezone.utc):
            raise HTTPException(status_code=400, detail="Invalid or expired OTP")

        # Clear OTP after successful verification
        update_stmt = users.update().where(users.c.email == otp_data.email).values(otp_code=None, otp_expires=None)
        conn.execute(update_stmt)
        conn.commit()

        access_token = create_jwt_token(
            data={"sub": user.email},
            expires_delta=timedelta(seconds=JWT_EXP_DELTA_SECONDS)
        )
        return {"access_token": access_token, "token_type": "bearer"}


@router.post("/login", response_model=Token)
async def login_for_access_token(user_login: UserLogin):
    with engine.connect() as conn:
        query = select(users).where(users.c.email == user_login.email)
        user = conn.execute(query).fetchone()

        if not user or not pwd_context.verify(user_login.password, user.hashed_pw):
            raise HTTPException(status_code=400, detail="Incorrect email or password")

        access_token = create_jwt_token(
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

    user_id = current_user.id
    file_extension = os.path.splitext(file.filename)[1]
    s3_key = f"invoices/{user_id}/{uuid.uuid4()}{file_extension}"

    try:
        # Upload file to S3
        file_content = await file.read()
        s3_client.put_object(Bucket=S3_BUCKET, Key=s3_key, Body=file_content, ContentType=file.content_type)
        print(f"API Server: Uploaded {file.filename} to S3 as {s3_key}")

        # Record in database and get the inserted invoice_id
        with engine.begin() as conn:
            insert_stmt = invoices.insert().values(
                user_id=user_id,
                s3_key=s3_key,
                status="pending",
                created_at=datetime.now(timezone.utc)
            ).returning(invoices.c.id)  # Get the inserted invoice ID
            result = conn.execute(insert_stmt)
            invoice_id = result.scalar_one()
            print(f"API Server: Recorded invoice {s3_key} in DB for user {user_id} (invoice_id={invoice_id})")

        # Send message to Kafka (as valid JSON)
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
        print(f"API Server: Sent Kafka message: {message_payload}")

        return {
            "message": "Invoice uploaded and submitted for processing",
            "invoice_id": invoice_id,
            "s3_key": s3_key
        }

    except Exception as e:
        print(f"API Server: Error during upload or Kafka message: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to upload invoice or send for processing: {e}")


@router.get("/invoices", response_model=list[InvoiceResponse])
async def get_invoices(current_user: dict = Depends(get_current_user)):
    user_id = current_user.id
    invoices_list = []

    with engine.connect() as conn:
        query = select(invoices).where(invoices.c.user_id == user_id)
        result = conn.execute(query).fetchall()

        for row in result:
            invoice_dict = row._asdict()  # Convert Row to dict

            # Ensure extracted_data is a dict for frontend consistency
            if 'extracted_data' in invoice_dict and isinstance(invoice_dict['extracted_data'], str):
                try:
                    invoice_dict['extracted_data'] = json.loads(invoice_dict['extracted_data'])
                except json.JSONDecodeError:
                    invoice_dict['extracted_data'] = {}  # Fallback if not valid JSON string

            # Set category or fallback to "Uncategorized"
            invoice_dict['category'] = row.category if row.category else "Uncategorized"

            # Generate presigned S3 URL that forces file download
            try:
                presigned_url = s3_client.generate_presigned_url(
                    'get_object',
                    Params={
                        'Bucket': S3_BUCKET,
                        'Key': row.s3_key,
                        'ResponseContentDisposition': 'attachment'  # 👈 Force browser download
                    },
                    ExpiresIn=3600  # URL valid for 1 hour
                )
                invoice_dict['preview_url'] = presigned_url
            except Exception as e:
                print(f"API Server: ERROR generating presigned URL for {row.s3_key}: {e}")
                invoice_dict['preview_url'] = "#"  # Fallback if URL generation fails

            invoices_list.append(invoice_dict)

        print(f"API Server: Retrieved {len(invoices_list)} invoices for user {user_id}")

    return invoices_list


@router.post("/send-csv-to-telegram")
async def send_csv_to_telegram(current_user: dict = Depends(get_current_user)):
    if not bot:
        raise HTTPException(status_code=500, detail="Telegram bot not configured. TG_BOT_TOKEN is missing.")

    user_telegram_chat_id = current_user.telegram_chat_id
    if not user_telegram_chat_id:
        raise HTTPException(status_code=400, detail="Telegram chat ID not registered for this user.")

    invoices_list = await get_invoices(current_user)
    if not invoices_list:
        raise HTTPException(status_code=404, detail="No invoices found to generate CSV.")

    s3_client = boto3.client('s3', region_name=os.getenv('S3_REGION'))
    bucket_name = os.getenv('S3_BUCKET')

    def generate_presigned_url(s3_key: str) -> str:
        try:
            url = s3_client.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': bucket_name,
                    'Key': s3_key,
                    'ResponseContentDisposition': 'attachment'  # Force download
                },
                ExpiresIn=3600  # 1 hour
            )
            return url
        except ClientError as e:
            logger.error(f"Failed to generate presigned URL for {s3_key}: {e}")
            return s3_key  # fallback to raw key

    csv_buffer = io.StringIO()
    writer = csv.writer(csv_buffer)

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
    writer.writerow(headers)

    for invoice in invoices_list:
        extracted = invoice.get('extracted_data', {}) or {}
        s3_key = invoice.get('s3_key', '')
        presigned_url = generate_presigned_url(s3_key) if s3_key else ''

        writer.writerow([
            invoice.get('id'),
            invoice.get('status', 'Unknown'),
            invoice.get('category', 'Uncategorized'),
            invoice.get('created_at').isoformat() if invoice.get('created_at') else '',
            extracted.get('vendor_name', 'Unknown'),
            extracted.get('amount', 'Unknown'),
            extracted.get('purchase_date', 'Unknown'),
            presigned_url
        ])

    csv_buffer.seek(0)

    try:
        await bot.send_document(
            chat_id=user_telegram_chat_id,
            document=InputFile(csv_buffer.getvalue(), filename="invoices.csv"),
            caption="Here are your invoices as a CSV file."
        )
        return {"message": "CSV sent to Telegram successfully!"}
    except Exception as e:
        logger.error(f"Error sending CSV to Telegram: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to send CSV to Telegram: {e}")


@router.post("/send-chart-to-telegram")
async def send_chart_to_telegram(current_user: dict = Depends(get_current_user)):
    if not bot:
        raise HTTPException(status_code=500, detail="Telegram bot not configured. TG_BOT_TOKEN is missing.")

    user_id = current_user.id
    user_telegram_chat_id = current_user.telegram_chat_id

    if not user_telegram_chat_id:
        raise HTTPException(status_code=400, detail="Telegram chat ID not registered for this user.")

    # Fetch invoices for the current user
    invoices_list = await get_invoices(current_user)

    if not invoices_list:
        raise HTTPException(status_code=404, detail="No invoices found to generate chart.")

    # Aggregate categories for the chart
    categories = {}
    for invoice in invoices_list:
        category = invoice.get('category') or "Uncategorized"
        categories[category] = categories.get(category, 0) + 1

    if not categories:
        raise HTTPException(status_code=404, detail="No categorized data to generate chart.")

    # Generate the pie chart using matplotlib
    fig, ax = plt.subplots(figsize=(8, 8))
    labels = list(categories.keys())
    sizes = list(categories.values())

    # Add a fallback for colors, ensure enough colors for all categories
    # You might want to define a fixed set of colors or a color map
    colors = ['#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', '#9966FF', '#FF9F40', '#6A5ACD', '#20B2AA', '#7B68EE',
              '#FFD700', '#A9A9A9', '#ADD8E6']
    # If there are more categories than defined colors, cycle through them
    pie_colors = [colors[i % len(colors)] for i in range(len(labels))]

    ax.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=90, colors=pie_colors,
           wedgeprops={'edgecolor': 'black'}, textprops={'fontsize': 10})
    ax.axis('equal')  # Equal aspect ratio ensures that pie is drawn as a circle.
    ax.set_title('Invoice Category Distribution', fontsize=16, pad=20)

    # Save chart to an in-memory byte buffer
    buffer = io.BytesIO()
    plt.savefig(buffer, format='png', bbox_inches='tight', dpi=100)
    buffer.seek(0)  # Rewind to the beginning of the buffer
    plt.close(fig)  # Close the figure to free up memory

    try:
        # Send the chart image to Telegram
        await bot.send_photo(
            chat_id=user_telegram_chat_id,
            photo=InputFile(buffer, filename="invoice_categories_chart.png"),
            caption="Here is your invoice category distribution chart."
        )
        return {"message": "Chart sent to Telegram successfully!"}
    except Exception as e:
        print(f"Error sending chart to Telegram: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to send chart to Telegram: {e}")
