from src.hydra.database_controllers.models import Transfer, ContractTransaction
from sqlalchemy.future import select

from src.hydra.database_controllers.db_controller import get_async_session

from src.hydra.database_controllers.models import (
    Transfer,
    ContractTransaction,
    SybilClusters,
)

# from src.neo4j.driver import get_neo4j_driver

# from kafka import KafkaProducer
# import json

# producer = KafkaProducer(
#     # bootstrap_servers="localhost:9092",
#     # value_serializer=lambda v: json.dumps(v).encode("utf-8"),
# )


# async def publish_transactions_to_kafka(transaction_event, topic="transaction_topic"):
#     message = {
#         "sender": transaction_event.from_,
#         "receiver": transaction_event.to,
#         "tx_hash": transaction_event.hash,
#         "amount": transaction_event.transaction.value / 10**18,
#         "gas_price": transaction_event.gas_price,
#         "timestamp": transaction_event.timestamp,
#         "data": transaction_event.transaction.data,
#         "chainId": str(transaction_event.network.name),
#     }
#     producer.send(topic, message)
#     print(f"Published transaction {transaction_event.hash} to Kafka topic {topic}")

#     producer.flush()


# async def add_transactions_to_neo4j(transaction_events):
#     driver = get_neo4j_driver()
#     if driver is None:
#         print("Failed to get Neo4j driver")
#         return

#     with driver.session() as session:
#         for transaction_event in transaction_events:
#             sender = transaction_event.from_
#             receiver = transaction_event.to
#             tx_hash = transaction_event.hash
#             amount = transaction_event.transaction.value / 10**18
#             gas_price = transaction_event.gas_price
#             timestamp = transaction_event.timestamp
#             data = transaction_event.transaction.data
#             chainId = str(transaction_event.network.name)

#             if data != "0x":
#                 # Transaction involves a Contract
#                 query = """
#                 MERGE (sender:Wallet {address: $sender})
#                 MERGE (receiver:Contract {address: $receiver})
#                 CREATE (sender)-[:CALLED {hash: $tx_hash, amount: $amount, gas_price: $gas_price,
#                                         timestamp: $timestamp, data: $data, chainId: $chainId}]->(receiver)
#                 """
#             else:
#                 # Transaction involves only Wallets
#                 query = """
#                 MERGE (sender:Wallet {address: $sender})
#                 MERGE (receiver:Wallet {address: $receiver})
#                 CREATE (sender)-[:SENT {hash: $tx_hash, amount: $amount, gas_price: $gas_price,
#                                         timestamp: $timestamp, data: $data, chainId: $chainId}]->(receiver)

#                 """

#             try:
#                 # Execute the Cypher query
#                 session.run(
#                     query,
#                     sender=sender,
#                     receiver=receiver,
#                     tx_hash=tx_hash,
#                     amount=amount,
#                     gas_price=gas_price,
#                     timestamp=timestamp,
#                     data=data,
#                     chainId=chainId,
#                 )
#                 print(f"Added transaction {tx_hash} to Neo4j")
#             except Exception as e:
#                 print(
#                     f"Error occurred while adding transaction {tx_hash} to Neo4j: {e}"
#                 )


async def add_transactions_b_to_db(session, transaction_events):
    for transaction_event in transaction_events:
        sender = transaction_event.from_
        receiver = transaction_event.to
        tx_hash = transaction_event.hash
        amount = transaction_event.transaction.value
        gas_price = transaction_event.gas_price
        timestamp = transaction_event.timestamp
        data = transaction_event.transaction.data
        chainId = str(transaction_event.network.name)

        # Check if the transaction already exists in the database
        existing_transfer = await session.execute(
            select(Transfer).where(Transfer.tx_hash == tx_hash)
        )
        existing_contract_tx = await session.execute(
            select(ContractTransaction).where(ContractTransaction.tx_hash == tx_hash)
        )

        # If a record with the same tx_hash exists, skip insertion
        if (
            existing_transfer.scalar_one_or_none()
            or existing_contract_tx.scalar_one_or_none()
        ):
            print(
                f"Transaction with hash {tx_hash} already exists in the database. Skipping..."
            )
            continue

        try:
            if data != "0x":
                session.add(
                    ContractTransaction(
                        tx_hash=tx_hash,
                        sender=sender,
                        contract_address=receiver,
                        amount=amount,
                        timestamp=timestamp,
                        data=data,
                        chainId=chainId,
                    )
                )
                print(f"Added ContractTransaction {tx_hash} to the database")
            else:
                session.add(
                    Transfer(
                        tx_hash=tx_hash,
                        sender=sender,
                        receiver=receiver,
                        amount=amount,
                        gas_price=gas_price,
                        timestamp=timestamp,
                        chainId=chainId,
                        processed=False,
                    )
                )
                print(f"Added Transfer {tx_hash} to the database")

        except Exception as e:
            print(
                f"Error occurred while adding transaction {tx_hash}: {e}. Skipping this transaction."
            )


async def remove_processed_transfers(network_name):
    async with get_async_session(network_name) as session:
        # Select all transfers where processed is True
        processed_txs = await session.execute(
            select(Transfer).where(Transfer.processed == True)
        )
        processed_txs = processed_txs.scalars().all()

        for tx in processed_txs:
            await session.delete(tx)

        await session.commit()


async def remove_processed_contract_transactions(network_name):
    async with get_async_session(network_name) as session:
        # Select all contract transactions where processed is True
        processed_ctxs = await session.execute(
            select(ContractTransaction).where(ContractTransaction.processed == True)
        )
        processed_ctxs = processed_ctxs.scalars().all()

        for ctx in processed_ctxs:
            await session.delete(ctx)

        await session.commit()


def extract_method_id(data):
    """Extract the method ID from the transaction data."""
    return data[:10]


async def load_all_nodes_from_database(session):
    result = await session.execute(select(SybilClusters))
    existing_clusters = result.scalars().all()
    return {cluster.address: cluster for cluster in existing_clusters}


# async def add_transaction_to_db(session, transaction_event):
#     sender = transaction_event.from_
#     receiver = transaction_event.to
#     tx_hash = transaction_event.hash
#     amount = transaction_event.transaction.value
#     gas_price = transaction_event.gas_price
#     timestamp = transaction_event.timestamp
#     data = transaction_event.transaction.data
#     chainId = transaction_event.network

#     try:
#         # Attempt to add ContractTransaction or Transfer
#         if data != "0x":
#             session.add(
#                 ContractTransaction(
#                     tx_hash=tx_hash,
#                     sender=sender,
#                     contract_address=receiver,
#                     amount=amount,
#                     timestamp=timestamp,
#                     data=data,
#                     chainId=chainId,
#                 )
#             )
#             print("added ContractTransaction to ContractTransaction table")
#         else:
#             session.add(
#                 Transfer(
#                     tx_hash=tx_hash,
#                     sender=sender,
#                     receiver=receiver,
#                     amount=amount,
#                     gas_price=gas_price,
#                     timestamp=timestamp,
#                     processed=False,
#                     chainId=chainId,
#                 )
#             )
#             print("added Transfer to Transfer table")

#     except Exception as e:
#         print(
#             f"Error occurred while processing transaction: {e}. Skipping this transaction."
#         )
