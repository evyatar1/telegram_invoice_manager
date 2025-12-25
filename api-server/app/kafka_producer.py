from aiokafka import AIOKafkaProducer
import os
import logging

logger = logging.getLogger(__name__)

# Global producer instance. This will be managed by the functions below.
producer: AIOKafkaProducer | None = None


async def start_kafka_producer_instance():
    """Initializes and starts the global Kafka producer instance."""
    global producer
    if producer is None: # Only initialize if not already done
        try:
            producer = AIOKafkaProducer(bootstrap_servers=os.getenv("KAFKA_BOOTSTRAP_SERVERS"))
            await producer.start()
            logger.info("Kafka producer initialized and started.")
        except Exception as e:
            logger.critical(f"CRITICAL ERROR: Failed to initialize and start Kafka producer: {e}", exc_info=True)
            raise # Re-raise to indicate a critical startup failure


async def stop_kafka_producer_instance():
    """Stops the global Kafka producer instance."""
    global producer
    if producer:
        await producer.stop()
        logger.info("Kafka producer stopped.")
        producer = None # Clear the producer instance after stopping


def get_kafka_producer() -> AIOKafkaProducer:
    """Returns the globally managed Kafka producer instance."""
    if producer is None:
        # This case should ideally not happen if start_kafka_producer_instance was awaited correctly during app startup.
        # However, for robustness, we raise an error to indicate a programming error (producer not started).
        raise RuntimeError("Kafka producer has not been initialized or is not running.")
    return producer
