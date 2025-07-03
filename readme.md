# Pipeline for Consuming Onchain Events (Uniswap v3)

A modular, event-driven pipeline that listens for **Uniswap v3 Swap events**, transforms and publishes them to **Kafka**, and persists them to **Postgres**.

The pipeline is currently listening to Uniswap v3 events for the USDC-ETH & WETH-USDT pairs, but can be easily extended to support additional pairs by adding new configuration files.

> Built with Python3, Web3.py, Kafka, and Docker.

Tracked example pool:  
[0x88e6A0c2dDD26FEEb64F039a2c41296FcB3f5640](https://etherscan.io/address/0x88e6a0c2ddd26feeb64f039a2c41296fcb3f5640#events)

---

## Event Flow

- **Listener** → Pulls raw data from Uniswap v3 pool events
- **Web3.py** → Parses and transforms the raw logs
- **Kafka** → Brokers transformed messages between producer and consumer
- **Consumer** → Writes normalized events to Postgres
- **Postgres** → Stores structured and queryable event data

---

## Multi-Pool Support with Threads

Each Uniswap pool config file (in `configs/*.toml`) spins up **its own listener thread** via Python’s `multiprocessing.Process`. This allows multiple pools (e.g., `USDC-ETH-0.05`, `WETH-USDT-0.01`, etc.) to be ingested concurrently.

**How it works**:
- The main app scans the `configs/` directory
- For each `.toml` config, a new process is launched
- Each process:
  - Connects to the specified pool
  - Listens for `Swap` events
  - Publishes parsed output to Kafka

---


## Data Dictionary

| Column           | Description                                      |
|------------------|--------------------------------------------------|
| `uuid`           | Unique hash of the raw event                     |
| `event_type`     | Type of the event (e.g., Swap)                   |
| `pair`           | Token pair and fee tier (e.g., USDC-ETH-0.05)    |
| `block_number`   | Ethereum block number                            |
| `timestamp`      | ISO-formatted timestamp                          |
| `tx_hash`        | Transaction hash                                 |
| `sender`         | Address initiating the swap                      |
| `recipient`      | Swap recipient                                   |
| `amount0`        | Token0 amount (human-readable)                   |
| `amount1`        | Token1 amount (human-readable)                   |
| `token0_symbol`  | Symbol of token0                                 |
| `token1_symbol`  | Symbol of token1                                 |
| `gas_used`       | Gas used for transaction                         |
| `gas_price`      | Gas price in wei                                 |
| `gas_paid`       | Total gas paid in wei                            |
| `gas_paid_eth`   | Total gas paid in ETH                            |
| `raw_hash`       | Hash of raw event JSON for data integrity        |

---

## Contribution Details

- Each Uniswap v3 pool is defined in a config file (`configs/*.toml`)
- To add a new pair:
  1. Copy an existing `.toml` config
  2. Update `pair.name` and `pool.address`
- SwapListener supports multiple pairs using Python’s `multiprocessing`
- Includes a Dead Letter Queue (DLQ) for recoverable or malformed events


## Docker Setup Instructions

### 1. Create a `.env` file in the root directory with your secrets:

```env
RPC_ENDPOINT=https://eth-mainnet.g.alchemy.com/v2/YOUR_KEY
```


### 2. Launch the entire pipeline:

```bash
docker-compose up --build -d
```

This will start:

 1. Kafka (event broker)
 2. PostgreSQL (event store)
 3. Producer(s) for Uniswap V3 pools
 4. Consumer that saves transformed data to Postgres

## Scaling Strategy
This pipeline supports both **vertical** and **horizontal** scaling, allowing flexible expansion for high-throughput and multi-event-type workloads.

---

### Vertical Scaling

You can increase container capacity for heavier workloads:

- Adjust CPU/memory limits in Docker Compose or Kubernetes
- Tune Kafka producer configs (`batch_size`, `linger_ms`) and web3 rate limits
- Use Postgres connection pooling (e.g., with `pgbouncer`)

### Horizontal Scaling

Per-Pool Parallelization

Each .toml config spawns a new listener using multiprocessing.Process() — scaling naturally with the number of configured pools.

High-Volume Pools
You can run high-volume pools in dedicated containers to isolate traffic:

Multiple Event Types (Swap, Mint, Burn)
With minor tweaks, this pipeline supports other Uniswap V3 event types like Mint, Burn, etc. Each event type can run in a separate container, using custom Kafka topics and consumer logic:

| Component     | Scaling Strategy                                                                 |
|----------------|----------------------------------------------------------------------------------|
| **Listener**   | Add new `.toml` config for each pool — each runs in its own Python `Process()`  |
| **High-Volume Pools** | Optionally run these listeners in **dedicated containers** for isolation     |
| **Kafka**      | Scales naturally via topic partitioning                                          |
| **Consumer**   | Add more replicas to consume from multiple partitions concurrently               |
| **Postgres**   | Scale writes with batching or use managed services with write replicas           |
| **Orchestration** | Use Kubernetes or ECS for service distribution                |
| **Monitoring** | Add Prometheus + Grafana for performance tracking (future enhancement)          |

### Pool Isolation Strategy

To better manage traffic:

- Light traffic pools can be grouped and run in a shared listener container
- **High-volume pools** (like `USDC-ETH-0.05`) can be deployed in a **separate container** using a minimal Docker Compose override or custom service definition
- This prevents noisy pools from starving less active ones
