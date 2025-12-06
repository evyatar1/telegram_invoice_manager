from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Request
from pydantic import BaseModel, EmailStr
from sqlalchemy import create_engine, Table, Column, Integer, String, MetaData, DateTime, JSON, select, delete, ForeignKey, update as sql_update
from passlib.context import CryptContext
from jose import jwt, JWTError
from datetime import datetime, timedelta, timezone
import uuid, random, boto3, os
import logging
import base64

# Import shared configuration from the shared.config module.
# This module is expected to be accessible via PYTHONPATH in the Docker environment.
from shared.config import (
    DB_URL, S3_BUCKET, S3_REGION, JWT_SECRET, JWT_ALGO, JWT_EXP_DELTA_SECONDS,
    KAFKA_TOPIC, KAFKA_TELEGRAM_OTP_TOPIC, KAFKA_REPORT_REQUEST_TOPIC
)
from aiokafka import AIOKafkaProducer # This import is not strictly needed here as producer is accessed via request.app.state
from fastapi.security import OAuth2PasswordBearer
import io
import json

# Configure logging for this module.
# This ensures that logs from routes.py are handled by the configured logging system.
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Database setup using SQLAlchemy.
# This defines the connection to the PostgreSQL database.
engine = create_engine(DB_URL)
metadata = MetaData()

# Define the 'users' table schema.
# This mirrors the structure of the 'users' table in your PostgreSQL database.
users = Table("users", metadata,
              Column("id", Integer, primary_key=True, autoincrement=True),
              Column("email", String, unique=True, nullable=False),
              Column("hashed_pw", String, nullable=False),
              Column("phone", String, unique=True, nullable=True),
              Column("is_verified", Integer, default=0), # 0 for not verified, 1 for verified
              Column("otp_secret", String, nullable=True),
              Column("otp_expires", DateTime, nullable=True),
              Column("telegram_chat_id", String, unique=True, nullable=True)
              )

# Define the 'invoices' table schema.
# This mirrors the structure of the 'invoices' table in your PostgreSQL database.
invoices = Table(
    "invoices",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("user_id", Integer, ForeignKey("users.id"), nullable=False),
    Column("s3_key", String, unique=True, nullable=False), # s3_key will now be a placeholder initially
    Column("created_at", DateTime, default=datetime.now(timezone.utc)),
    Column("status", String, default="pending"),
    Column("extracted_data", JSON),
    Column("category", String),
)

# Create all defined tables in the database if they do not already exist.
metadata.create_all(engine)

# Password hashing context using Passlib.
# Configured to use bcrypt for secure password hashing.
# pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

pwd_context = CryptContext(
    schemes=["pbkdf2_sha256"],
    deprecated="auto"
)


# OAuth2PasswordBearer for extracting JWT tokens from Authorization headers.
# The tokenUrl points to the login endpoint where clients can obtain a token.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

# AWS S3 client for interacting with Amazon S3.
# Used for deleting objects and generating pre-signed URLs.
s3_client = boto3.client("s3", region_name=S3_REGION)

# FastAPI router to group related API endpoints.
router = APIRouter()


# Helper function to create JWT access tokens.
def create_access_token(data: dict, expires_delta: timedelta | None = None):
    """
    Creates a JWT access token with an expiration time.
    :param data: Dictionary containing claims to be encoded in the token (e.g., {"sub": user_email}).
    :param expires_delta: Optional timedelta for token expiration. Defaults to 15 minutes if not provided.
    :return: Encoded JWT string.
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire}) # Add expiration timestamp to the payload
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGO)
    return encoded_jwt


# Dependency function to get the current authenticated user.
async def get_current_user(token: str = Depends(oauth2_scheme)):
    """
    Decodes and validates the JWT token from the request header to authenticate the user.
    Raises HTTPException if credentials are invalid or token is expired.
    :param token: The JWT token extracted by oauth2_scheme.
    :return: A dictionary representing the authenticated user's data from the database.
    """
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        # Decode the JWT token using the secret key and algorithm.
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
        user_email: str = payload.get("sub") # Get the subject (user email) from the token payload
        if user_email is None:
            raise credentials_exception # Raise exception if email is not found in token

        # Query the database to retrieve user details based on the email.
        with engine.connect() as conn:
            stmt = select(users).where(users.c.email == user_email)
            result = conn.execute(stmt).first()
            if result is None:
                raise credentials_exception # Raise exception if user not found in DB
            return result._asdict() # Return user data as a dictionary
    except JWTError:
        raise credentials_exception # Raise exception if JWT decoding/validation fails


# Pydantic models for validating request and response bodies.

class UserCreate(BaseModel):
    """Pydantic model for user registration request."""
    email: EmailStr # EmailStr ensures valid email format
    password: str
    phone: str

class UserLogin(BaseModel):
    """Pydantic model for user login request."""
    email: EmailStr
    password: str

class Token(BaseModel):
    """Pydantic model for JWT token response."""
    access_token: str
    token_type: str = "bearer"

class VerifyOtp(BaseModel):
    """Pydantic model for OTP verification request."""
    email: EmailStr
    otp: str

class InvoiceResponse(BaseModel):
    """Pydantic model for invoice response data."""
    id: int
    user_id: int
    s3_key: str # S3 key will be the real S3 key after worker upload, or a placeholder
    created_at: datetime
    status: str
    extracted_data: dict | None = None
    category: str | None = None
    preview_url: str # Will be a presigned URL or '#' if not yet in S3

class TelegramLinkRequest(BaseModel):
    """Pydantic model for linking Telegram account request."""
    phone: str
    telegram_chat_id: str

class ChartRequest(BaseModel):
    """Pydantic model for chart generation request."""
    chart_data: list[dict] = []


# API Endpoints

@router.delete("/invoices/{invoice_id}")
async def delete_invoice(invoice_id: int, current_user: dict = Depends(get_current_user)):
    """
    Deletes an invoice record from the database and its corresponding file from S3.
    Requires authentication.
    :param invoice_id: The ID of the invoice to delete.
    :param current_user: Authenticated user's data.
    :return: Success message.
    """
    with engine.begin() as conn: # Use a transaction for database operations
        # Query to find the invoice belonging to the current user
        query = select(invoices).where(invoices.c.id == invoice_id, invoices.c.user_id == current_user['id'])
        result = conn.execute(query).fetchone()

        if not result:
            raise HTTPException(status_code=404, detail="Invoice not found or you don't have permission to delete it.")

        s3_key = result.s3_key # Get S3 key if it exists

        # Only try to delete from S3 if an S3 key exists and it's not a placeholder
        if s3_key and not s3_key.startswith("pending_upload_"):
            try:
                s3_client.delete_object(Bucket=S3_BUCKET, Key=s3_key)
                logger.info(f"S3 object deleted: {s3_key}") # Log S3 deletion
            except Exception as e:
                logger.error(f"Error deleting from S3: {e}", exc_info=True) # Log S3 deletion error

        # Delete the invoice record from the database
        conn.execute(delete(invoices).where(invoices.c.id == invoice_id))

    return {"message": "Invoice deleted successfully"}



@router.post("/register")
async def register_user(user: UserCreate):
    with engine.connect() as conn:
        existing_user_query = select(users).where(users.c.email == user.email)
        existing_user = conn.execute(existing_user_query).fetchone()
        if existing_user:
            raise HTTPException(status_code=400, detail="Email already registered")

        # Convert password to bytes and truncate to 72 bytes
        password_bytes = user.password.encode('utf-8')[:72]  # <-- truncate to max 72 bytes
        password_truncated = password_bytes.decode('utf-8', 'ignore')  # convert back to str safely
        hashed_password = pwd_context.hash(password_truncated)  # Passlib wants str

        # Insert new user
        insert_stmt = users.insert().values(
            email=user.email,
            hashed_pw=hashed_password,
            phone=user.phone,
            is_verified=0,
            otp_secret=None,
            otp_expires=None,
            telegram_chat_id=None
        )
        conn.execute(insert_stmt)
        conn.commit()

    logger.info(f"User {user.email} registered successfully.")
    return {"message": "User registered successfully. Please link your Telegram account to verify."}



@router.post("/link-telegram-account")
async def link_telegram_account(telegram_link_data: TelegramLinkRequest, request: Request):
    """
    Endpoint for Telegram bot to link a user's Telegram chat ID
    and send OTP via Telegram. The API server sends a Kafka message
    for the worker to handle the actual OTP sending.
    :param telegram_link_data: TelegramLinkRequest Pydantic model with phone and telegram_chat_id.
    :param request: The FastAPI request object, used to access app.state.
    :return: Status message.
    """
    with engine.connect() as conn:
        # Find the user by phone number
        user_query = select(users).where(users.c.phone == telegram_link_data.phone)
        user = conn.execute(user_query).fetchone()

        if not user:
            raise HTTPException(status_code=404, detail="User with this phone number not found.")

        # Check if the phone number is already linked to a different Telegram account
        if user.telegram_chat_id and user.telegram_chat_id != telegram_link_data.telegram_chat_id:
             raise HTTPException(status_code=400, detail="This phone number is already linked to a different Telegram account.")

        # Generate a random OTP and set its expiration time
        otp_secret = str(random.randint(100000, 999999))
        otp_expires = datetime.now(timezone.utc) + timedelta(minutes=5)

        # Update user record with Telegram chat ID, OTP, and expiration
        update_stmt = sql_update(users).where(users.c.id == user.id).values(
            telegram_chat_id=telegram_link_data.telegram_chat_id,
            otp_secret=otp_secret,
            otp_expires=otp_expires
        )
        conn.execute(update_stmt)
        conn.commit() # Commit the transaction

        logger.info(f"User {user.email} updated with chat_id {telegram_link_data.telegram_chat_id} and OTP.") # Log update (not the OTP itself)

        # Ensure Kafka producer is initialized before sending message
        if not hasattr(request.app.state, 'kafka_producer') or not request.app.state.kafka_producer:
            raise HTTPException(status_code=500, detail="Kafka producer is not initialized.")

        # Prepare message payload for Kafka to send OTP
        message_payload = {
            "user_id": user.id,
            "otp_secret": otp_secret, # OTP is sensitive, but sent over internal Kafka topic to trusted worker
            "chat_id": telegram_link_data.telegram_chat_id,
            "action": "send_otp" # Action for worker to identify task
        }
        logger.info(
            f"Preparing to send OTP Kafka message for user {user.id} with chat_id {telegram_link_data.telegram_chat_id}")
        # Send the message to the Kafka OTP topic
        await request.app.state.kafka_producer.send_and_wait(
            KAFKA_TELEGRAM_OTP_TOPIC,
            json.dumps(message_payload).encode("utf-8")
        )
        logger.info(f"Sent OTP Kafka message for user {user.id} to topic {KAFKA_TELEGRAM_OTP_TOPIC}.") # Log Kafka message sent

    return {"message": "Telegram account linked. OTP sent to your Telegram."}


@router.post("/verify-otp", response_model=Token)
async def verify_otp(otp_data: VerifyOtp):
    """
    Verifies the provided OTP for a user and marks the account as verified if successful.
    Returns a JWT token upon successful verification.
    :param otp_data: VerifyOtp Pydantic model with email and OTP.
    :return: JWT access token.
    """
    with engine.connect() as conn:
        # Query user by email
        query = select(users).where(users.c.email == otp_data.email)
        user = conn.execute(query).fetchone()

        # Validate OTP and expiration
        if not user or user.otp_secret != otp_data.otp or (user.otp_expires and user.otp_expires < datetime.now(timezone.utc)):
            logger.warning(f"Failed OTP verification attempt for {otp_data.email}.") # Log failed attempt
            raise HTTPException(status_code=400, detail="Invalid or expired OTP")

        # Clear OTP data and mark user as verified
        update_stmt = sql_update(users).where(users.c.email == otp_data.email).values(
            otp_secret=None,
            otp_expires=None,
            is_verified=1
        )
        conn.execute(update_stmt)
        conn.commit() # Commit the transaction
        logger.info(f"User {user.email} successfully verified.") # Log successful verification

        # Create and return a new access token for the verified user
        access_token = create_access_token(
            data={"sub": user.email},
            expires_delta=timedelta(seconds=JWT_EXP_DELTA_SECONDS)
        )
        return {"access_token": access_token, "token_type": "bearer"}


@router.post("/login", response_model=Token)
async def login_for_access_token(user_login: UserLogin):
    """
    Authenticates a user and returns a JWT access token.
    :param user_login: UserLogin Pydantic model with email and password.
    :return: JWT access token.
    """
    with engine.connect() as conn:
        # Find user by email
        stmt = select(users).where(users.c.email == user_login.email)
        user = conn.execute(stmt).fetchone()

        # Verify user existence and password
        if not user or not pwd_context.verify(user_login.password, user.hashed_pw):
            logger.warning(f"Failed login attempt for {user_login.email}.") # Log failed login attempt
            raise HTTPException(status_code=400, detail="Incorrect email or password")

        # Create and return access token
        access_token = create_access_token(
            data={"sub": user.email},
            expires_delta=timedelta(seconds=JWT_EXP_DELTA_SECONDS)
        )
        logger.info(f"User {user_login.email} logged in successfully.") # Log successful login
        return {"access_token": access_token, "token_type": "bearer"}


@router.post("/upload-invoice")
async def upload_invoice(
        request: Request,
        file: UploadFile = File(...),
        current_user: dict = Depends(get_current_user)
):
    """
    Handles invoice file uploads. Stores a placeholder in DB and sends image bytes
    to Kafka for asynchronous processing by the worker.
    :param request: The FastAPI request object.
    :param file: The uploaded invoice file.
    :param current_user: Authenticated user's data.
    :return: Status message and invoice ID.
    """
    user_id = current_user['id']
    file_extension = os.path.splitext(file.filename)[1]
    # Generate a temporary/placeholder S3 key for the DB record.
    # The actual S3 key will be set by the worker after upload to S3.
    temp_s3_key = f"pending_upload_{user_id}_{uuid.uuid4()}{file_extension}"

    try:
        file_content = await file.read()
        # Encode image bytes to base64 for JSON serialization over Kafka.
        # This allows sending binary data through Kafka messages.
        encoded_image_bytes = base64.b64encode(file_content).decode('utf-8')

        with engine.begin() as conn:
            # Record a pending invoice in the database with a temporary S3 key.
            insert_stmt = invoices.insert().values(
                user_id=user_id,
                s3_key=temp_s3_key, # Store the temporary S3 key
                status="pending",
                created_at=datetime.now(timezone.utc)
            ).returning(invoices.c.id) # Return the ID of the newly inserted invoice
            result = conn.execute(insert_stmt)
            invoice_id = result.scalar_one() # Get the invoice ID
            logger.info(f"Recorded invoice {file.filename} in DB for user {user_id} with temp_s3_key {temp_s3_key} (invoice_id={invoice_id})")

        # Ensure Kafka producer is initialized
        if not hasattr(request.app.state, 'kafka_producer') or not request.app.state.kafka_producer:
            raise HTTPException(status_code=500, detail="Kafka producer is not initialized.")

        # Prepare message payload for Kafka to trigger invoice processing
        message_payload = {
            "invoice_id": invoice_id,
            "image_bytes_base64": encoded_image_bytes, # Send image bytes over Kafka
            "user_id": user_id,
            "original_s3_key_placeholder": temp_s3_key # Pass the placeholder for worker to update
        }

        # Send the message to the Kafka topic for invoice processing
        await request.app.state.kafka_producer.send_and_wait(
            KAFKA_TOPIC, # This is the topic for invoice processing requests
            json.dumps(message_payload).encode("utf-8")
        )
        logger.info(f"Sent Kafka message with image bytes for invoice {invoice_id} to topic {KAFKA_TOPIC}")

        return {
            "message": "Invoice uploaded and submitted for processing",
            "invoice_id": invoice_id,
            "s3_key": temp_s3_key # Return the temporary key if frontend expects it
        }

    except Exception as e:
        logger.error(f"Error during upload or Kafka message: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to upload invoice or send for processing: {e}")


async def get_invoices(current_user: dict):
    """
    Retrieves all invoices for the current user from the database and generates pre-signed URLs for S3 files.
    :param current_user: Authenticated user's data.
    :return: A list of invoice dictionaries.
    """
    user_id = current_user['id']
    invoices_list = []

    with engine.connect() as conn:
        # Query invoices for the current user, ordered by creation date.
        query = select(invoices).where(invoices.c.user_id == user_id).order_by(invoices.c.created_at.asc())
        result = conn.execute(query).fetchall()

        for row in result:
            invoice_dict = row._asdict()

            # Handle extracted_data which might be stored as a string JSON
            if 'extracted_data' in invoice_dict and isinstance(invoice_dict['extracted_data'], str):
                try:
                    invoice_dict['extracted_data'] = json.loads(invoice_dict['extracted_data'])
                except json.JSONDecodeError:
                    invoice_dict['extracted_data'] = {}

            # Set default category if not present
            invoice_dict['category'] = invoice_dict.get('category') or "Uncategorized"

            # Check if s3_key is a real S3 key (not a placeholder) to generate presigned URL
            if row.s3_key and not row.s3_key.startswith("pending_upload_"):
                try:
                    # Generate a pre-signed URL for direct access to the S3 object
                    presigned_url = s3_client.generate_presigned_url(
                        'get_object',
                        Params={
                            'Bucket': S3_BUCKET,
                            'Key': row.s3_key,
                            'ResponseContentDisposition': 'attachment' # Suggests download
                        },
                        ExpiresIn=3600 # URL valid for 1 hour
                    )
                    invoice_dict['preview_url'] = presigned_url
                except Exception as e:
                    logger.error(f"ERROR generating presigned URL for {row.s3_key}: {e}", exc_info=True)
                    invoice_dict['preview_url'] = "#" # Fallback if URL generation fails
            else:
                # If it's a placeholder, no preview URL is available yet
                invoice_dict['preview_url'] = "#"

            invoices_list.append(invoice_dict)

        logger.info(f"Retrieved {len(invoices_list)} invoices for user {user_id}")

    return invoices_list


@router.get("/invoices", response_model=list[InvoiceResponse])
async def list_invoices(current_user: dict = Depends(get_current_user)):
    """
    API endpoint to list all invoices for the authenticated user.
    :param current_user: Authenticated user's data.
    :return: A list of InvoiceResponse models.
    """
    invoices_list = await get_invoices(current_user)
    return invoices_list


@router.post("/send-csv-to-telegram")
async def send_excel_to_telegram(request: Request, current_user: dict = Depends(get_current_user)):
    """
    Sends a request to Kafka to generate and send an Excel report to the user's Telegram.
    The actual report generation is handled by the worker.
    :param request: The FastAPI request object.
    :param current_user: Authenticated user's data.
    :return: Status message.
    """
    user_id = current_user['id']
    user_telegram_chat_id = current_user['telegram_chat_id']

    if not user_telegram_chat_id:
        raise HTTPException(status_code=400, detail="Telegram chat ID not registered for this user. Please link your Telegram account.")

    # Ensure Kafka producer is initialized
    if not hasattr(request.app.state, 'kafka_producer') or not request.app.state.kafka_producer:
        raise HTTPException(status_code=500, detail="Kafka producer is not initialized.")

    # Prepare message payload for Kafka to request Excel report
    message_payload = {
        "user_id": user_id,
        "telegram_chat_id": user_telegram_chat_id,
        "report_type": "excel", # Indicate that an Excel report is requested
        "request_timestamp": datetime.now(timezone.utc).isoformat()
    }

    # Send the message to the Kafka topic for report requests
    await request.app.state.kafka_producer.send_and_wait(
        KAFKA_REPORT_REQUEST_TOPIC,
        json.dumps(message_payload).encode("utf-8")
    )
    logger.info(f"Sent Kafka message for Excel report request for user {user_id} to topic {KAFKA_REPORT_REQUEST_TOPIC}.")

    return {"message": "Excel report generation requested. It will be sent to your Telegram shortly."}


@router.post("/send-chart-to-telegram")
async def send_chart_to_telegram(chart_request: ChartRequest, request: Request, current_user: dict = Depends(get_current_user)):
    """
    Sends a request to Kafka to generate and send a chart report to the user's Telegram.
    The actual chart generation is handled by the worker.
    :param chart_request: ChartRequest Pydantic model with chart data.
    :param request: The FastAPI request object.
    :param current_user: Authenticated user's data.
    :return: Status message.
    """
    user_id = current_user['id']
    user_telegram_chat_id = current_user['telegram_chat_id']

    if not user_telegram_chat_id:
        raise HTTPException(status_code=400, detail="Telegram chat ID not registered for this user. Please link your Telegram account.")

    if not chart_request.chart_data:
        raise HTTPException(status_code=404, detail="No chart data provided to generate chart.")

    # Ensure Kafka producer is initialized
    if not hasattr(request.app.state, 'kafka_producer') or not request.app.state.kafka_producer:
        raise HTTPException(status_code=500, detail="Kafka producer is not initialized.")

    # Prepare message payload for Kafka to request chart report
    message_payload = {
        "user_id": user_id,
        "telegram_chat_id": user_telegram_chat_id,
        "report_type": "chart", # Indicate that a chart report is requested
        "chart_data": chart_request.chart_data, # Pass the chart data directly
        "request_timestamp": datetime.now(timezone.utc).isoformat()
    }

    # Send the message to the Kafka topic for report requests
    await request.app.state.kafka_producer.send_and_wait(
        KAFKA_REPORT_REQUEST_TOPIC,
        json.dumps(message_payload).encode("utf-8")
    )
    logger.info(f"Sent Kafka message for Chart report request for user {user_id} to topic {KAFKA_REPORT_REQUEST_TOPIC}.")

    return {"message": "Chart report generation requested. It will be sent to your Telegram shortly."}

@router.get("/users/me")
async def get_user_profile(current_user: dict = Depends(get_current_user)):
    """
    Returns the current user's profile, including verification status and telegram_chat_id.
    This endpoint allows the frontend to retrieve authenticated user details.
    :param current_user: Authenticated user's data.
    :return: A dictionary containing relevant user profile information.
    """
    # current_user already contains all user fields from the DB due to get_current_user dependency.
    # We return a subset of fields relevant for the frontend, converting is_verified to boolean.
    return {
        "id": current_user['id'],
        "email": current_user['email'],
        "phone": current_user['phone'],
        "is_verified": bool(current_user['is_verified']), # Convert 0/1 integer to boolean for clarity
        "telegram_chat_id": current_user['telegram_chat_id']
    }
