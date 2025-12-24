import uvicorn
from fastapi import FastAPI
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import logging

from .kafka_producer import start_kafka_producer_instance, stop_kafka_producer_instance, get_kafka_producer
from .routes import router
from .telegram_bot import run_telegram_bot_background, stop_telegram_bot_background

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("API server lifespan startup")

    # wait for Kafka readiness
    logger.info("Waiting 15 seconds for Kafka services to become available...")
    await asyncio.sleep(15)

    # start Kafka producer
    await start_kafka_producer_instance()
    app.state.kafka_producer = get_kafka_producer()
    logger.info("Kafka producer started and attached to app.state.kafka_producer")

    # start Telegram bot in background
    app.state.telegram_bot_app = await run_telegram_bot_background()
    logger.info("Telegram bot started in background and attached to app.state.telegram_bot_app")

    try:
        yield
    finally:
        logger.info("API server lifespan shutdown starting")

        # stop Telegram bot
        try:
            if getattr(app.state, "telegram_bot_app", None):
                await stop_telegram_bot_background(app.state.telegram_bot_app)
                logger.info("Telegram bot stopped cleanly")
        except Exception as e:
            logger.exception("Error while stopping Telegram bot: %s", e)

        # stop Kafka producer
        try:
            await stop_kafka_producer_instance()
            logger.info("Kafka producer stopped")
        except Exception as e:
            logger.exception("Error while stopping Kafka producer: %s", e)

        logger.info("API server lifespan shutdown complete")


app = FastAPI(lifespan=lifespan)

# CORS config
origins = [
    "http://localhost",
    "http://localhost:3000",
    "http://host.docker.internal:3000",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# include routes
app.include_router(router)

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
        access_log=True,
        use_colors=True,
    )
