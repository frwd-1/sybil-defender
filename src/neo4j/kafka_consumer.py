import json
import logging
from kafka import KafkaConsumer
from neo4j import GraphDatabase

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


class Neo4jConsumer:
    def __init__(self, uri, user, password, topic):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self.consumer = KafkaConsumer(
            topic,
            bootstrap_servers="localhost:9092",
            auto_offset_reset="earliest",
            value_deserializer=lambda m: json.loads(m.decode("utf-8")),
        )
        logging.info("Initialized Neo4jConsumer for topic: %s", topic)

    def consume_transactions(self):
        logging.info("Starting to consume transactions...")
        for message in self.consumer:
            transaction_data = message.value
            logging.info("Consumed transaction: %s", transaction_data)
            self.add_transaction_to_neo4j(transaction_data)

    def add_transaction_to_neo4j(self, transaction_data):
        with self.driver.session() as session:

            sender = transaction_data["sender"]
            receiver = transaction_data["receiver"]
            tx_hash = transaction_data["tx_hash"]
            amount = transaction_data["amount"]
            gas_price = transaction_data["gas_price"]
            timestamp = transaction_data["timestamp"]
            data = transaction_data.get("data", "0x")
            chainId = str(transaction_data["chainId"])

            if data != "0x":
                # Transaction involves a Contract
                query = """
                MERGE (sender:Wallet {address: $sender})
                MERGE (receiver:Contract {address: $receiver})
                CREATE (sender)-[:CALLED {hash: $tx_hash, amount: $amount, gas_price: $gas_price, 
                                        timestamp: $timestamp, data: $data, chainId: $chainId}]->(receiver)
                """
            else:
                # Transaction involves only Wallets
                query = """
                MERGE (sender:Wallet {address: $sender})
                MERGE (receiver:Wallet {address: $receiver})
                CREATE (sender)-[:SENT {hash: $tx_hash, amount: $amount, gas_price: $gas_price, 
                                        timestamp: $timestamp, data: $data, chainId: $chainId}]->(receiver)
                """

            try:
                session.run(
                    query,
                    sender=sender,
                    receiver=receiver,
                    tx_hash=tx_hash,
                    amount=amount,
                    gas_price=gas_price,
                    timestamp=timestamp,
                    data=data,
                    chainId=chainId,
                )
                print(f"Added transaction {tx_hash} to Neo4j")
            except Exception as e:
                print(
                    f"Error occurred while adding transaction {tx_hash} to Neo4j: {e}"
                )


if __name__ == "__main__":
    logging.info("Script started")
    neo4j_uri = "bolt://localhost:7687"
    user = "neo4j"
    password = "HydraDBMS"
    topic = "transaction_topic"
    consumer = Neo4jConsumer(neo4j_uri, user, password, topic)
    consumer.consume_transactions()
    logging.info("Script ended")
