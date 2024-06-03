from Crypto.Hash import keccak
from forta_agent import Finding, FindingSeverity, FindingType, EntityType
from src.hydra.utils import globals


from Crypto.Hash import keccak


def generate_alert_details(community_id, nodes, labels, contracts, chainId, action):
    contract_anomaly_score = (
        (globals.sybil_contract_transactions / globals.all_contract_transactions * 100)
        if globals.all_contract_transactions
        else 0
    )
    transfer_anomaly_score = (
        (globals.sybil_transfers / globals.all_transfers * 100)
        if globals.all_transfers
        else 0
    )

    metadata = {
        "cluster_id": community_id,
        "chainId": chainId,
        "contract transaction anomaly score": contract_anomaly_score,
        "transfer anomaly score": transfer_anomaly_score,
        "interacted contracts": contracts,
    }

    labels_with_metadata = [
        {
            "entity_type": EntityType.Address,
            "entity": node,
            "confidence": 90,
            "label": label,
            "metadata": metadata,
        }
        for node in nodes
        for label in labels
    ]

    if action == "created":
        alert_name = "New sybil attack cluster identified"
        alert_description = f"Cluster {community_id} shows signs of sybil attack"
    else:
        alert_name = "Existing sybil attack cluster updated"
        alert_description = (
            f"Cluster {community_id} has been updated with new activities"
        )

    alert_details = {
        "name": alert_name,
        "description": alert_description,
        "alert_id": keccak.new(
            data=f"sybil_attacker_{community_id}".encode(), digest_bits=256
        ).hexdigest(),
        "severity": FindingSeverity.Medium,
        "type": FindingType.Suspicious,
        "addresses": list(nodes),
        "labels": labels_with_metadata,
    }

    return alert_details
