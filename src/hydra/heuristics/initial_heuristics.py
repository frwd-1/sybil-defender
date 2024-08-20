# from src.contracts.skip import STABLECOIN_ADDRESSES, EXCHANGES


# currently ruling out stablecoin addresses. can be reevaluated as needed
async def apply_initial_heuristics(transaction_event):
    print("checking if sender or receiver")
    if not transaction_event.from_ or not transaction_event.to:
        print("false - missing a sender or receiver")
        return False

    # if transaction_event.to in STABLECOIN_ADDRESSES:
    #     print("false - transaction to a stablecoin address")
    #     return False

    # if transaction_event.to in EXCHANGES:
    #     print("false - transaction to an exchange address")
    #     return False

    # if transaction_event.from_ in EXCHANGES:
    #     print("false - transaction from an exchange address")
    #     return False

    print("true")
    return True
