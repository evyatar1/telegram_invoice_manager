# worker/main.py
import asyncio
from .kafka_consumer import consume_loop

if __name__ == "__main__":
    asyncio.run(consume_loop())
