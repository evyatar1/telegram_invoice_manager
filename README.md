# **AI-Driven Invoice Processing and Classification System**
This microservices-based system automates the end-to-end process of extracting and
organizing data from invoice images. Users can upload invoices through a **Web Interface** or
send them via **Telegram**. The system then uses **OCR** and **OpenAI** to read the images, extract
key details like vendor names, dates, and amounts, and classify the information into a
structured format. To ensure smooth performance, the entire workflow is managed through
**Kafka**, which handles the image processing and data storage in a **PostgreSQL** database as an
asynchronous background task.


## **System Architecture**
The system is built using a containerized microservices architecture, orchestrated with **Docker
Compose**. It consists of the following components:

* **API Gateway (FastAPI):** Acts as the primary entry point for the **Web Interface**. It handles
image uploads and retrieves invoice status and data from the database.

* **Telegram Bot Service:** Manages incoming images from users via the Telegram Bot API
and forwards them to the processing pipeline.

* **Message Broker (Kafka):** Facilitates asynchronous communication. It decouples the
ingestion services (Web/Telegram) from the heavy processing workers, ensuring the
system remains responsive.

* **Invoice Processing Worker:** The core engine of the system. It consumes messages from
Kafka, performs **Image Pre-processing**, executes **OCR**, and uses **OpenAI** to parse and
classify the extracted text into structured data.

* **Database (PostgreSQL):** Provides persistent storage for user information and structured
invoice data. It is accessed via **SQLAlchemy Core** for optimized performance and data integrity.

<img width="1417" height="621" alt="architecture" src="https://github.com/user-attachments/assets/7dbdadbc-dd44-4e95-96fe-5e2fd6158301" />

# **Quick Start**
## **1. Clone the repository**
```
git clone https://github.com/evyatar1/telegram_invoice_manager.git
cd telegram_invoice_manager
```
## **2. Set Up Environment Variables**

The system uses two separate .env files for the microservices.

**Important:** Never commit your .env files to version control. Ensure they are added to your .gitignore to prevent exposing sensitive credentials.

**API Server** ``` api-server/.env ```
```
DATABASE_URL=postgresql://postgres:your_password@db:5432/appdb
JWT_SECRET=your_jwt_secret
KAFKA_BOOTSTRAP_SERVERS=broker:9092
KAFKA_TOPIC=invoices
TG_BOT_TOKEN=your_telegram_bot_token
AWS_ACCESS_KEY_ID=your_aws_key
AWS_SECRET_ACCESS_KEY=your_aws_secret
API_USER_EMAIL=admin@example.com
API_USER_PASSWORD=your_password
```

**Logic Worker** ``` /logic-worker/.env ```
```
DATABASE_URL=postgresql://postgres:your_password@db:5432/appdb
KAFKA_BOOTSTRAP_SERVERS=broker:9092
KAFKA_TOPIC=invoices
KAFKA_TELEGRAM_OTP_TOPIC=telegram-otp-messages
S3_BUCKET=your_s3_bucket_name
S3_REGION=your_s3_region
OPENAI_API_KEY=your_openai_api_key
AWS_ACCESS_KEY_ID=your_aws_key
AWS_SECRET_ACCESS_KEY=your_aws_secret
TG_BOT_TOKEN=your_telegram_bot_token
JWT_SECRET=your_jwt_secret
```

## **3. Build and Start the Services**

The system uses a **multi-stage build** with a shared base image to optimize build time and resource usage.
```bash
# 1. Build the base image
docker build -t base -f Dockerfile.base .

# 2. Launch all services (API, Worker, Kafka, Postgres)
docker-compose up --build -d
```

## **4. Prerequisites & Environment Setup**

Before running the system, you must configure the external services. The system **will not function** without these credentials.

**A. AWS Infrastructure (Storage)**

1. **S3 Bucket:** Create a private S3 bucket (e.g., ```my-invoice-storage```). This is where the Worker stores processed invoice images.

2. **IAM User:** Create an IAM user with ```AmazonS3FullAccess``` (or a scoped policy).

3. **Credentials:** Generate an ```AWS_ACCESS_KEY_ID``` and ```AWS_SECRET_ACCESS_KEY```.

**B. OpenAI API**

1. **Purpose:** OpenAI is used to process the raw text extracted by the OCR library and convert it into a structured JSON format (Total amount, Date, Vendor name, etc.).

2. **API Key:** Generate a new API Key in the [OpenAI Dashboard](https://platform.openai.com/api-keys).

3. **Config:** Add the key to ```OPENAI_API_KEY``` in your ```logic-worker/.env```.

**C. Telegram Bot (Interface)**

1. **BotFather:** Create a new bot via [@BotFather](https://t.me/botfather) on Telegram to get your ```TG_BOT_TOKEN```.

## **5. User Interaction & Workflow**

The system provides a seamless interface via Telegram for secure and automated invoice processing.

**Phase 1: Secure Onboarding & Identity Verification**

1. **Initiation:** Locate the bot on Telegram and send the ```/start``` command.

2. **Contact Sharing:** For security and identity verification, the bot will prompt you with a **"Share Phone Number"** button. Click this to securely provide your contact details to the system.

3. **One-Time Password (OTP):** Once your number is verified, the system will issue a **One-Time Password (OTP)** sent via the chat.

4. **Authorization:** Enter the received code to authorize your session and enable document uploads.

**Phase 2: Document Submission**
1. **Upload:** Simply send or forward an invoice image directly to the bot.

2. **Confirmation:** The system will acknowledge receipt and begin processing the data immediately in the background.

**Phase 3: Automated Extraction**

Once processing is complete, you will receive a structured summary directly in the chat containing:

* Vendor Name
* Transaction Date
* Total Amount
