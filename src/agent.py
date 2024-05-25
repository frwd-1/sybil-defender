import asyncio
from flask import Flask, request, jsonify
from forta_agent import TransactionEvent

from src.hydra.database_controllers.db_controller import initialize_database
from src.hydra.database_controllers.db_controller import get_async_session
from src.hydra.database_controllers.db_utils import (
    add_transactions_b_to_db,
    remove_processed_transfers,
    remove_processed_contract_transactions,
)

from src.hydra.process.process import process_transactions
from src.hydra.heuristics.initial_heuristics import apply_initial_heuristics
from src.hydra.utils import globals
from src.constants import N, B_SIZE
from src.hydra.utils.utils import update_transaction_counter

app = Flask(__name__)

DATABASE_TYPE = "local"
transaction_b = []


@app.route("/transaction", methods=["POST"])
def transaction():
    data = request.get_json()
    asyncio.run(handle_transaction(data))
    return jsonify({"status": "success"})


if __name__ == "__main__":
    app.run(port=5000)


# forta sdk doesn't recognize async handle_transaction so it needs to be wrapped
def handle_transaction(transaction_event: TransactionEvent):
    print("running handle transaction")
    loop = asyncio.get_event_loop()
    network_name = transaction_event.network.name

    # neo4j-kafka is expected to be initialized outside of the agent
    if DATABASE_TYPE != "neo4jkafka":
        if not loop.is_running():
            loop.run_until_complete(initialize_database(network_name))
        else:
            loop.create_task(initialize_database(network_name))

    return loop.run_until_complete(
        handle_transaction_async(transaction_event, network_name)
    )


async def handle_transaction_async(
    transaction_event: TransactionEvent, network_name: str
):
    findings = []

    print("applying initial heuristics")

    if not await apply_initial_heuristics(transaction_event):
        return []

    # neo4j-kafka database config option
    if DATABASE_TYPE == "neo4jkafka":
        try:
            # await publish_transactions_to_kafka(transaction_event)
            print(f"transaction committed to Kafka")
        except Exception as e:
            print(f"An error occurred in Kafka: {e}")
    else:
        transaction_b.append(transaction_event)
        print("batch size is:", len(transaction_b))
        if len(transaction_b) >= B_SIZE:
            if DATABASE_TYPE == "local":
                async with get_async_session(network_name) as session:
                    try:
                        await add_transactions_b_to_db(session, transaction_b)
                        print(f"{B_SIZE} transactions committed to the local database")
                    except Exception as e:
                        print(f"An error occurred in local DB: {e}")

            transaction_b.clear()

    update_transaction_counter()

    print("transaction counter is", globals.transaction_counter)
    print("current block is...", transaction_event.block_number)
    if globals.transaction_counter >= N:

        if DATABASE_TYPE == "local":
            print("processing transactions")
            findings.extend(await process_transactions(network_name))
            await remove_processed_transfers(network_name)
            await remove_processed_contract_transactions(network_name)

        globals.transaction_counter = 0
        print("ALL COMPLETE")
        return findings

    return []
