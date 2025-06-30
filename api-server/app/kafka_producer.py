from aiokafka import AIOKafkaProducer
import os

# Global producer instance. This is what main.py and routes.py will import.
producer: AIOKafkaProducer | None = None

async def start_kafka():
    """Initializes and starts the global Kafka producer."""
    global producer
    if producer is None: # Only initialize if not already done
        try:
            producer = AIOKafkaProducer(bootstrap_servers=os.getenv("KAFKA_BOOTSTRAP_SERVERS"))
            await producer.start()
            print("Kafka producer initialized and started.")
        except Exception as e:
            print(f"ERROR: Failed to initialize and start Kafka producer: {e}")
            raise # Re-raise to indicate a critical startup failure

async def stop_kafka():
    """Stops the global Kafka producer."""
    global producer
    if producer:
        await producer.stop()
        print("Kafka producer stopped.")
        producer = None # Clear the producer instance
