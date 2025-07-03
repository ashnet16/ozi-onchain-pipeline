SWAP_EVENTS_COLUMNS = [
    "uuid",
    "event_type",
    "pair",
    "block_number",
    "timestamp",
    "tx_hash",
    "sender",
    "recipient",
    "amount0",
    "amount1",
    "token0_symbol",
    "token1_symbol",
    "gas_used",
    "gas_price",
    "gas_paid",
    "gas_paid_eth",
    "raw_hash",
]

SWAP_EVENTS_TABLE_SQL = f"""
CREATE TABLE IF NOT EXISTS swap_events (
    {SWAP_EVENTS_COLUMNS[0]} TEXT PRIMARY KEY,
    {SWAP_EVENTS_COLUMNS[1]} TEXT,
    {SWAP_EVENTS_COLUMNS[2]} TEXT,
    {SWAP_EVENTS_COLUMNS[3]} BIGINT,
    {SWAP_EVENTS_COLUMNS[4]} TIMESTAMP,
    {SWAP_EVENTS_COLUMNS[5]} TEXT,
    {SWAP_EVENTS_COLUMNS[6]} TEXT,
    {SWAP_EVENTS_COLUMNS[7]} TEXT,
    {SWAP_EVENTS_COLUMNS[8]} DOUBLE PRECISION,
    {SWAP_EVENTS_COLUMNS[9]} DOUBLE PRECISION,
    {SWAP_EVENTS_COLUMNS[10]} TEXT,
    {SWAP_EVENTS_COLUMNS[11]} TEXT,
    {SWAP_EVENTS_COLUMNS[12]} BIGINT,
    {SWAP_EVENTS_COLUMNS[13]} BIGINT,
    {SWAP_EVENTS_COLUMNS[14]} BIGINT,
    {SWAP_EVENTS_COLUMNS[15]} DOUBLE PRECISION,
    {SWAP_EVENTS_COLUMNS[16]} TEXT
);

CREATE INDEX IF NOT EXISTS idx_swap_timestamp ON swap_events (timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_swap_pair_timestamp ON swap_events (pair, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_swap_sender ON swap_events (sender);
CREATE INDEX IF NOT EXISTS idx_swap_recipient ON swap_events (recipient);
"""
