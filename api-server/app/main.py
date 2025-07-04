import uvicorn
from fastapi import FastAPI
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import os
from aiokafka import AIOKafkaProducer  # Import AIOKafkaProducer

# Define producer as part of app.state, not a global variable here
# producer: AIOKafkaProducer | None = None # REMOVED

async def start_kafka_producer(app: FastAPI): # Pass app directly
    """Starts the Kafka producer and attaches it to app.state."""
    try:
        app.state.kafka_producer = AIOKafkaProducer(bootstrap_servers=os.getenv("KAFKA_BOOTSTRAP_SERVERS"))
        await app.state.kafka_producer.start()
        print("Kafka producer started successfully and attached to app.state.")
    except Exception as e:
        print(f"CRITICAL ERROR: Failed to start Kafka producer: {e}")
        raise


async def stop_kafka_producer(app: FastAPI): # Pass app directly
    """Stops the Kafka producer."""
    if hasattr(app.state, 'kafka_producer') and app.state.kafka_producer:
        await app.state.kafka_producer.stop()
        print("Kafka producer stopped.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manages the startup and shutdown events for the FastAPI application.
    """
    print("Starting API Server lifespan startup...")

    print("Waiting 15 seconds for Kafka services to become available...")
    await asyncio.sleep(15)  # Give Kafka broker some time to be fully ready

    # Start Kafka producer
    await start_kafka_producer(app) # Pass app to start_kafka_producer

    yield  # Application runs

    # Shutdown events
    print("API Server lifespan shutdown complete.")
    await stop_kafka_producer(app) # Pass app to stop_kafka_producer


app = FastAPI(lifespan=lifespan)

# Add CORS middleware
origins = [
    "http://localhost",
    "http://localhost:3000",
    "http://host.docker.internal:3000"  # ADD THIS!
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Import and include the API router after the app is created
from .routes import router
app.include_router(router)
