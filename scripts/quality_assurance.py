import sqlite3


def get_false_positives():
    conn = sqlite3.connect("sybil_defender_false_positives.db")
    cursor = conn.cursor()
    cursor.execute("SELECT wallet_address, reason FROM false_positives")
    results = cursor.fetchall()
    conn.close()
    return results


if __name__ == "__main__":
    false_positives = get_false_positives()
    if false_positives:
        print("False Positive Wallets:")
        for wallet, reason in false_positives:
            print(f"Wallet: {wallet}, Reason: {reason}")
    else:
        print("No false positives found.")
