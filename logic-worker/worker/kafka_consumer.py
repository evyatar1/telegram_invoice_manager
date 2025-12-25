import asyncio
from aiokafka import AIOKafkaConsumer
import os
import json
import base64
import logging

# Import processing functions from task_processor
from .task_processor import process_invoice, send_otp_to_telegram, generate_and_send_excel_report, \
    generate_and_send_chart_report
# Import Kafka topics from shared.config
from shared.config import KAFKA_TOPIC, KAFKA_BOOTSTRAP_SERVERS, KAFKA_TELEGRAM_OTP_TOPIC, KAFKA_REPORT_REQUEST_TOPIC

# Setup logging for kafka_consumer
logger = logging.getLogger(__name__)
# Basic config is usually done once at the application's entry point (main.py)
# but we can add a handler here if needed for this specific module's logs.
# For consistency, we'll assume basicConfig is handled in main.py.


async def consume_loop():
    """
    Starts the Kafka consumer loop to listen for messages from various topics
    and dispatches them to appropriate processing functions.
    """
    logger.info("Starting Kafka consumer loop...")
    bootstrap_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "broker:9092")

    # Consumer will listen to multiple topics
    consumer = AIOKafkaConsumer(
        KAFKA_TOPIC,  # For invoice processing requests
        KAFKA_TELEGRAM_OTP_TOPIC,  # For OTP requests
        KAFKA_REPORT_REQUEST_TOPIC,  # For report generation requests
        bootstrap_servers=bootstrap_servers,
        group_id="invoice-workers", # A unique group ID for this consumer group
        auto_offset_reset="earliest", # Start consuming from the beginning if no committed offset is found
    )

    try:
        await consumer.start()
        logger.info(
            f"Kafka consumer started for topics: {KAFKA_TOPIC}, {KAFKA_TELEGRAM_OTP_TOPIC}, {KAFKA_REPORT_REQUEST_TOPIC} on {bootstrap_servers}")

        # Continuously consume messages
        async for msg in consumer:
            payload = msg.value.decode() # Decode message payload from bytes to string
            topic = msg.topic # Get the topic from which the message was consumed
            logger.info(f"Received Kafka message from topic '{topic}': {payload}")

            try:
                message_data = json.loads(payload) # Parse the JSON payload
                action = message_data.get("action") # Get the action type from the message (e.g., "send_otp")

                if topic == KAFKA_TELEGRAM_OTP_TOPIC and action == "send_otp":
                    # Handle OTP message
                    user_id = message_data.get("user_id")
                    otp_secret = message_data.get("otp_secret")
                    chat_id = message_data.get("chat_id")

                    if user_id is None or otp_secret is None or chat_id is None:
                        logger.error(
                            f"Malformed OTP Kafka message: missing user_id, otp_secret, or chat_id. Payload: {payload}. Skipping.")
                        continue

                    # Call the OTP sending function from task_processor
                    await send_otp_to_telegram(user_id, otp_secret, chat_id)
                    logger.info(f"Successfully processed OTP for user {user_id}.")

                elif topic == KAFKA_REPORT_REQUEST_TOPIC:
                    # Handle report generation message (Excel or Chart)
                    user_id = message_data.get("user_id")
                    telegram_chat_id = message_data.get("telegram_chat_id")
                    report_type = message_data.get("report_type")
                    chart_data = message_data.get("chart_data")  # Only present for chart reports

                    if user_id is None or telegram_chat_id is None or report_type is None:
                        logger.error(
                            f"Malformed Report Request Kafka message: missing user_id, telegram_chat_id, or report_type. Payload: {payload}. Skipping.")
                        continue

                    if report_type == "excel":
                        await generate_and_send_excel_report(user_id, telegram_chat_id)
                        logger.info(f"Successfully processed Excel report request for user {user_id}.")
                    elif report_type == "chart":
                        await generate_and_send_chart_report(user_id, telegram_chat_id, chart_data)
                        logger.info(f"Successfully processed Chart report request for user {user_id}.")
                    else:
                        logger.warning(
                            f"Unknown report_type '{report_type}' in Kafka message. Payload: {payload}. Skipping.")

                elif topic == KAFKA_TOPIC:
                    # Handle invoice processing message (original logic)
                    invoice_id = message_data.get("invoice_id")
                    user_id = message_data.get("user_id")
                    image_bytes_base64 = message_data.get("image_bytes_base64")
                    original_s3_key_placeholder = message_data.get("original_s3_key_placeholder")

                    if invoice_id is None or image_bytes_base64 is None:
                        logger.error(
                            f"Malformed Invoice Kafka message: missing invoice_id or image_bytes_base64. Payload: {payload}. Skipping.")
                        continue

                    try:
                        img_bytes = base64.b64decode(image_bytes_base64) # Decode base64 image bytes
                    except Exception as e:
                        logger.error(
                            f"Failed to decode base64 image for invoice {invoice_id}: {e}. Skipping processing.")
                        continue

                    # Process the invoice (now handles S3 upload and DB update)
                    process_invoice(img_bytes, invoice_id, user_id, original_s3_key_placeholder)
                    logger.info(f"Successfully processed invoice {invoice_id}.")

                else:
                    logger.warning(f"Received message from unhandled topic {topic}. Payload: {payload}. Skipping.")

            except json.JSONDecodeError:
                logger.warning(f"Malformed Kafka message: not valid JSON. Payload: {payload}. Skipping.")
            except Exception as e:
                logger.error(f"Error processing Kafka message: {payload}. Error: {e}", exc_info=True)
    except Exception as e:
        logger.critical(f"Critical error in Kafka consumer loop: {e}", exc_info=True)
    finally:
        logger.info("Kafka consumer stopping...")
        await consumer.stop() # Ensure the consumer is properly stopped on exit
