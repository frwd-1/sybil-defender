import csv
import os
from forta_agent import TransactionEvent
from web3 import Web3
import datetime
import asyncio

# Constants
OUTPUT_FOLDER = "dataextract/etherscan_results"
CSV_FILE = os.path.join(OUTPUT_FOLDER, "OKXHotWallet_transaction_history.csv")
WALLET_ADDRESS = "0x0938c63109801ee4243a487ab84dffa2bba4589e"

# Ensure the output folder exists
if not os.path.exists(OUTPUT_FOLDER):
    os.makedirs(OUTPUT_FOLDER)

# Create the CSV file and write the header if it doesn't exist
if not os.path.isfile(CSV_FILE):
    with open(CSV_FILE, mode="w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["Hash", "From", "To", "Value", "Time"])


def handle_transaction(transaction_event: TransactionEvent):
    loop = asyncio.get_event_loop()
    if not loop.is_running():
        return loop.run_until_complete(handle_transaction_async(transaction_event))
    else:
        return asyncio.run(handle_transaction_async(transaction_event))


async def handle_transaction_async(transaction_event: TransactionEvent):
    findings = []
    tx = transaction_event
    if tx.from_ == WALLET_ADDRESS or tx.to == WALLET_ADDRESS:
        await save_transaction_to_csv(tx)
    return findings


async def save_transaction_to_csv(tx):
    with open(CSV_FILE, mode="a", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(
            [
                tx.hash,  # Assuming tx.hash is already a string
                tx.from_,
                tx.to,
                tx.transaction.value,
                # Web3.fromWei(tx.value, "ether"),
                datetime.datetime.utcfromtimestamp(tx.timestamp).strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
            ]
        )
    print(f"Transaction saved to {CSV_FILE}")


if __name__ == "__main__":
    # This script is intended to be run as part of the Forta agent
    pass
