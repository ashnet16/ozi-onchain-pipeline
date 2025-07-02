# Pipeline for Consuming Events onchain.



Listner(Includes Timestamps) --> Listens for events onchain

Pulls Raw data from Uniswap V3 pool events and writes to Kafka: https://etherscan.io/address/0x88e6a0c2ddd26feeb64f039a2c41296fcb3f5640#events

Uses Web3.py Python library for interacting with Ethereum


Kafka --> Data broker for producers and consumers


Consume and write data (Includes timestamps) to postgres  --> 
    - consumer.py
        consume_event_types


Postgres container --> Includes data from protocol that we need.




## Data Dictionary 







## Contribution details





## Setup Instructions

1. To run outside of docker. In the root directory create a virtual environment: python3 -m venv ozi
2. Activate your virtualenv source venv/bin/activate
3. pip install -r requirements.txt
4. Ensure the following environment variables are set:
   - `KAFKA_BROKER_URL`: URL of the Kafka broker
   - `POSTGRES_URL`: URL of the Postgres database
   - `POSTGRES_USER`: Username for the Postgres database
   - `POSTGRES_PASSWORD`: Password for the Postgres database
   -  RPC_ENDPOINT: Ethereum RPC endpoint (e.g., Infura, Alchemy)
   -  UNISWAP_POOL: Uniswap pool address to listen to events from
   Example: export KAFKA_BROKER_URL="localhost:9092"


