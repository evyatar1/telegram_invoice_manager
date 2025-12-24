import asyncio
import logging
from .kafka_consumer import consume_loop

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main_worker_loop():
    logger.info("Starting Kafka consumer...")
    await consume_loop()

if __name__ == "__main__":
    try:
        asyncio.run(main_worker_loop())
    except KeyboardInterrupt:
        logger.info("Worker shutdown requested by user.")
