import json
import logging
from kafka import KafkaConsumer

from base import Consumer
from db.init_db import init_db
from db.schema import SWAP_EVENTS_COLUMNS
from db.db import get_connection
from datetime import datetime


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BATCH_SIZE = 5

class UniswapSwapConsumer(Consumer):
    def __init__(self, end_point, topics, consumer_group="uniswap-swap-consumer"):
        super().__init__(end_point, topics, consumer_group=consumer_group)

        self.consumer = KafkaConsumer(
            *self.topics,
            bootstrap_servers=[self.end_point],
            group_id=self.consumer_group,
            value_deserializer=lambda m: json.loads(m.decode("utf-8")),
            auto_offset_reset="earliest",
            enable_auto_commit=True,
        )

        self.conn = get_connection()
        self.cursor = self.conn.cursor()
        self.batch = []

    def consume(self) -> None:
        logger.info(f"Consuming from topics: {self.topics}")
        try:
            for message in self.consumer:
                try:
                    self.process(message.value, message.topic)
                except Exception as e:
                    logger.exception(f"Failed to process message: {e}")
        finally:
            if self.batch:
                self.flush_batch()
            self.cursor.close()
            self.conn.close()

    def process(self, msg: dict, topic_name: str = None) -> None:
        logger.info(f"[Topic: {topic_name}] Message UUID: {msg.get('uuid')}")
        
        row = []
        for col in SWAP_EVENTS_COLUMNS:
            val = msg.get(col)
            if col == "timestamp" and isinstance(val, int):
                val = datetime.utcfromtimestamp(val)
            row.append(val)

        self.batch.append(row)

        if len(self.batch) >= BATCH_SIZE:
            self.flush_batch()


    def flush_batch(self):
        placeholders = ', '.join(['%s'] * len(SWAP_EVENTS_COLUMNS))
        sql = f"""
        INSERT INTO swap_events ({', '.join(SWAP_EVENTS_COLUMNS)})
        VALUES ({placeholders})
        ON CONFLICT (uuid) DO NOTHING;
        """
        try:
            self.cursor.executemany(sql, self.batch)
            self.conn.commit()
            logger.info(f"Inserted batch of {len(self.batch)} rows.")
            self.batch = []
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Batch insert failed: {e}")
            self.batch = []


if __name__ == "__main__":
    init_db()
    consumer = UniswapSwapConsumer(
        end_point="kafka:29092",
        topics=["uniswap.Swap.USDC-ETH-0.05",  
                 "uniswap.Swap.WETH-USDT-0.01"]
    )
    consumer.consume()