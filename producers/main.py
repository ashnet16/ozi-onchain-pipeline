import os
import time
import json
import uuid
import logging
import toml
import glob
import multiprocessing
import hashlib
import json
from abc import ABC, abstractmethod
from web3 import Web3
from web3.types import LogReceipt
from hexbytes import HexBytes
from kafka import KafkaProducer
from dotenv import load_dotenv

DLQ_TOPIC = "uniswap.dlq"

class DLQKafkaProducer:
    def __init__(self, bootstrap_servers):
        self.producer = KafkaProducer(
            bootstrap_servers=[bootstrap_servers],
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            linger_ms=100,
            batch_size=16384,
        )

    def send(self, event, reason=None):
        if reason:
            event["dlq_reason"] = reason
        try:
            self.producer.send(DLQ_TOPIC, value=event)
            self.producer.flush()
            logging.warning(f"Sent failed event to DLQ: {DLQ_TOPIC}")
        except Exception as e:
            logging.error(f"Failed to send to DLQ: {e}")


class KafkaJSONTopic:
    def __init__(self, topic_name, bootstrap_servers):
        self.topic_name = topic_name
        self.producer = KafkaProducer(
            bootstrap_servers=[bootstrap_servers],
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            linger_ms=100,
            batch_size=16384,
        )

    def produce(self, event, topic_name=None):
        target_topic = topic_name or self.topic_name
        try:
            self.producer.send(target_topic, value=event)
            self.producer.flush()
            logging.info(f"Sent to Kafka topic: {target_topic}")
        except Exception as e:
            logging.error(f" Kafka send failed: {e}")

class UniswapSwapTransformer:
    def __init__(self, raw_log_dict: dict):
        self.raw = raw_log_dict

    def transform(self):
        token0_decimals = self.raw["token0"]["decimals"]
        token1_decimals = self.raw["token1"]["decimals"]

        amount0 = float(self.raw["amount0"]) / (10 ** token0_decimals)
        amount1 = float(self.raw["amount1"]) / (10 ** token1_decimals)

        raw_json_str = json.dumps(self.raw, sort_keys=True, separators=(",", ":"))
        raw_hash = hashlib.sha256(raw_json_str.encode("utf-8")).hexdigest()

    
        iso_timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(self.raw["timestamp"]))

        return {
            "schema_version": "v1",
            "event_type": "Swap",
            "uuid": self.raw["uuid"],
            "pair": self.raw["pair"],
            "block_number": self.raw["blockNumber"],
            "timestamp": iso_timestamp,
            "tx_hash": self.raw["txHash"],
            "sender": self.raw["sender"],
            "recipient": self.raw["recipient"],
            "amount0": amount0,
            "amount1": amount1,
            "token0_symbol": self.raw["token0"]["symbol"],
            "token1_symbol": self.raw["token1"]["symbol"],
            "gas_used": self.raw["gasUsed"],
            "gas_price": self.raw["gasPrice"],
            "gas_paid": self.raw["gasPaid"],
            "gas_paid_eth": self.raw["gasPaidETH"],
            "raw_hash": raw_hash,
            "raw": self.raw,
        }


class BaseUniswapListener(ABC):
    def __init__(self, config: dict):
        load_dotenv()
        self.config = config
        self.pair_name = config.get("pair", {}).get("name", "Unnamed-Pair")
        self.web3 = Web3(Web3.HTTPProvider(self._get_rpc_endpoint()))
        self.pool_address = Web3.to_checksum_address(self._get_pool_address())
        self.event_abi = self._get_event_abi()

        self.contract = self.contract = self.web3.eth.contract(address=self.pool_address, abi=self._load_shared_abi())
        self.event_topic_hash = self.web3.keccak(
            text=self.event_abi['name'] + "(" + ",".join(i['type'] for i in self.event_abi['inputs']) + ")"
        ).hex()

        self._setup_tokens()

    def _get_rpc_endpoint(self):
        return os.getenv("RPC_ENDPOINT") or self.config["eth"]["rpc_endpoint"]


    def _get_pool_address(self):
        return os.getenv("UNISWAP_POOL") or self.config["pool"]["address"]

    def _get_event_abi(self):
        return next(
            (item for item in self.config["abi"] if item["type"] == "event" and item["name"] == "Swap"), None
        )

    def _setup_tokens(self):
        pool_abi = [
            {"inputs": [], "name": "token0", "outputs": [{"internalType": "address", "name": "", "type": "address"}], "stateMutability": "view", "type": "function"},
            {"inputs": [], "name": "token1", "outputs": [{"internalType": "address", "name": "", "type": "address"}], "stateMutability": "view", "type": "function"},
        ]
        erc20_abi = [
            {"constant": True, "inputs": [], "name": "symbol", "outputs": [{"name": "", "type": "string"}], "type": "function"},
            {"constant": True, "inputs": [], "name": "decimals", "outputs": [{"name": "", "type": "uint8"}], "type": "function"},
        ]

        pool_contract = self.web3.eth.contract(address=self.pool_address, abi=pool_abi)
        self.token0_address = pool_contract.functions.token0().call()
        self.token1_address = pool_contract.functions.token1().call()

        token0 = self.web3.eth.contract(address=self.token0_address, abi=erc20_abi)
        token1 = self.web3.eth.contract(address=self.token1_address, abi=erc20_abi)

        self.token0_symbol = token0.functions.symbol().call()
        self.token1_symbol = token1.functions.symbol().call()
        self.token0_decimals = token0.functions.decimals().call()
        self.token1_decimals = token1.functions.decimals().call()

    def _load_shared_abi(self):
        path = os.path.join("configs", "uniswap_swap_abi.json")
        with open(path) as f:
            return json.load(f)

    def _get_event_abi(self):
        return next(
            (item for item in self._load_shared_abi() if item["type"] == "event" and item["name"] == "Swap"),
            None
        )
    
    def _hexbytes_to_str(self, obj):
        if isinstance(obj, HexBytes):
            return obj.hex()
        elif isinstance(obj, bytes):
            return obj.hex()
        elif isinstance(obj, dict):
            return {k: self._hexbytes_to_str(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._hexbytes_to_str(v) for v in obj]
        else:
            return obj

    def fetch_logs(self, from_block: int, to_block: int):
        try:
            logs: list[LogReceipt] = self.web3.eth.get_logs({
                "fromBlock": from_block,
                "toBlock": to_block,
                "address": self.pool_address,
                "topics": [self.event_topic_hash]
            })
            logging.info(f"[{self.pair_name}] {len(logs)} logs from blocks {from_block}–{to_block}")
            return logs
        except Exception as e:
            logging.warning(f"[{self.pair_name}] Error fetching logs: {e}")
            return []

    @abstractmethod
    def process_log(self, log):
        pass

    def listen(self):
        logging.info(f"[{self.pair_name}] Listening to pool {self.pool_address}...")
        latest_block = self.web3.eth.block_number

        while True:
            current_block = self.web3.eth.block_number

            if current_block >= latest_block:
                logs = self.fetch_logs(latest_block, latest_block)
                for log in logs:
                    try:
                        self.process_log(log)
                    except Exception as e:
                        logging.warning(f"[{self.pair_name}] Failed to process log: {e}")
                latest_block += 1
            else:
                time.sleep(1)


class SwapListener(BaseUniswapListener):
    def __init__(self, config: dict):
        super().__init__(config)
        topic = f"uniswap.Swap.{self.pair_name}"
        self.kafka_topic = KafkaJSONTopic(
            topic_name=topic,
            bootstrap_servers=self.config.get("kafka", {}).get("bootstrap_servers", "localhost:9092")
        )
        self.dlq_producer = DLQKafkaProducer(
        bootstrap_servers=self.config.get("kafka", {}).get("bootstrap_servers", "localhost:9092")
    )


    def process_log(self, log):
        tx_hash = log["transactionHash"]
        decoded = self.contract.events.Swap().process_log(log)
        receipt = self.web3.eth.get_transaction_receipt(tx_hash)
        tx = self.web3.eth.get_transaction(tx_hash)
        block = self.web3.eth.get_block(log["blockNumber"])

        gas_used = receipt["gasUsed"]
        gas_price = tx.get("maxFeePerGas") or tx.get("gasPrice") or 0
        gas_paid = gas_used * gas_price
        eth_gas_paid = Web3.from_wei(gas_paid, "ether")

        full_event = {
            "uuid": str(uuid.uuid5(uuid.NAMESPACE_URL, f"{tx_hash.hex()}-{log['logIndex']}")),
            "pair": self.pair_name,
            "txHash": tx_hash,
            "blockNumber": log["blockNumber"],
            "logIndex": log["logIndex"],
            "timestamp": block["timestamp"],
            "poolAddress": log["address"],
            "sender": decoded["args"]["sender"],
            "recipient": decoded["args"]["recipient"],
            "amount0": str(decoded["args"]["amount0"]),
            "amount1": str(decoded["args"]["amount1"]),
            "sqrtPriceX96": str(decoded["args"]["sqrtPriceX96"]),
            "liquidity": str(decoded["args"]["liquidity"]),
            "tick": decoded["args"]["tick"],
            "from": tx["from"],
            "to": tx.get("to"),
            "gasUsed": gas_used,
            "gasPrice": gas_price,
            "gasPaid": gas_paid,
            "gasPaidETH": str(eth_gas_paid),
            "nonce": tx["nonce"],
            "value": tx["value"],
            "input": tx["input"],
            "status": receipt["status"],
            "cumulativeGasUsed": receipt["cumulativeGasUsed"],
            "effectiveGasPrice": receipt.get("effectiveGasPrice", gas_price),
            "token0": {
                "address": self.token0_address,
                "symbol": self.token0_symbol,
                "decimals": self.token0_decimals,
            },
            "token1": {
                "address": self.token1_address,
                "symbol": self.token1_symbol,
                "decimals": self.token1_decimals,
            },
        }

        try:
            transformed_event = UniswapSwapTransformer(self._hexbytes_to_str(full_event)).transform()
            self.kafka_topic.produce(transformed_event)
        except Exception as e:
            logging.warning(f"[{self.pair_name}] Failed to transform event: {e}")
            fallback_event = self._hexbytes_to_str(full_event)
            self.dlq_producer.send(fallback_event, reason=str(e))


def run_listener(config_file):
    try:
        config = toml.load(config_file)
        listener = SwapListener(config)
        listener.listen()
    except Exception as e:
        logging.exception(f"Listener failed for {config_file}: {e}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    config_dir = "configs"
    config_files = glob.glob(os.path.join(config_dir, "*.toml"))

    if not config_files:
        logging.warning("No TOML files found. Sleeping instead of exiting to keep container alive.") # i was debugging
        while True:
            time.sleep(60)

    processes = []
    for cfg in config_files:
        p = multiprocessing.Process(target=run_listener, args=(cfg,))
        p.start()
        processes.append(p)

    for p in processes:
        p.join()