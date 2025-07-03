import asyncio
from aiokafka import AIOKafkaConsumer
import os
import json
from .task_processor import process_invoice
from .aws_s3 import download_to_memory
from shared.config import KAFKA_TOPIC, KAFKA_BOOTSTRAP_SERVERS
import logging

# Setup logging for kafka_consumer
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def consume_loop():
    logger.info("Starting Kafka consumer loop...")
    bootstrap_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "broker:9092")

    consumer = AIOKafkaConsumer(
        KAFKA_TOPIC,
        bootstrap_servers=bootstrap_servers,
        group_id="invoice-workers",
        auto_offset_reset="earliest",
    )

    try:
        await consumer.start()
        logger.info(f"Kafka consumer started for topic: {KAFKA_TOPIC} on {bootstrap_servers}")
        async for msg in consumer:
            payload = msg.value.decode()
            logger.info(f"Received Kafka message: {payload}")

            try:
                message_data = json.loads(payload)
                s3_key = message_data.get("s3_key")
                invoice_id = message_data.get("invoice_id")
                user_id = message_data.get("user_id") # We receive user_id but don't strictly need it here for current logic

                if not s3_key or invoice_id is None:
                    logger.error(f"Malformed Kafka message: missing s3_key or invoice_id. Payload: {payload}. Skipping.")
                    continue

                # Download image from S3
                img_bytes = download_to_memory(s3_key)
                if img_bytes:
                    # Process the invoice, passing invoice_id for direct update
                    process_invoice(s3_key, img_bytes, invoice_id)
                else:
                    logger.error(f"Failed to download image from S3 for key: {s3_key}. Skipping processing.")
            except json.JSONDecodeError:
                logger.warning(f"Malformed Kafka message: not valid JSON. Payload: {payload}. Skipping.")
            except Exception as e:
                logger.error(f"Error processing Kafka message: {payload}. Error: {e}", exc_info=True)
    except Exception as e:
        logger.critical(f"Critical error in Kafka consumer loop: {e}", exc_info=True)
    finally:
        logger.info("Kafka consumer stopping...")
        await consumer.stop()
