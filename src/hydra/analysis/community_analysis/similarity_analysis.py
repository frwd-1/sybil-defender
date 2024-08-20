from collections import defaultdict
from src.hydra.database_controllers.db_controller import get_async_session
from src.hydra.database_controllers.models import SybilClusters
from src.hydra.utils import globals
from src.constants import I_RATIO, S_THRESHOLD
from src.hydra.analysis.community_analysis.typology_analysis import analyze_typology
from sqlalchemy.future import select

from src.hydra.analysis.transaction_analysis.helpers import (
    get_unique_senders,
    compute_similarity,
    build_contract_activity_dict,
)


async def group_addresses_by_community(updated_subgraph):
    grouped_addresses = defaultdict(set)
    community_edges_count = {}

    # Group nodes by community and create subgraphs for each community
    for node, data in updated_subgraph.nodes(data=True):
        if "community" in data:
            community_id = data["community"]
            grouped_addresses[community_id].add(node)

    # Create a subgraph for each community and count the edges
    for community_id, nodes in grouped_addresses.items():
        community_subgraph = updated_subgraph.subgraph(nodes)
        community_edges_count[community_id] = community_subgraph.number_of_edges()

    return grouped_addresses, community_edges_count


async def similarity_analysis(updated_subgraph, contract_transactions):
    grouped_addresses, community_edges_count = await group_addresses_by_community(
        updated_subgraph
    )

    for community_id, addresses in grouped_addresses.items():
        print("Processing community:", community_id)

        community_transactions = [
            tx for tx in contract_transactions if tx.sender in addresses
        ]
        number_of_community_transactions = len(community_transactions)
        print(
            f"The number of community transactions is: {number_of_community_transactions}"
        )

        unique_senders = await get_unique_senders(contract_transactions)

        if len(unique_senders) < len(addresses) * I_RATIO:
            continue

        contract_activity_dict = await build_contract_activity_dict(
            community_transactions
        )
        avg_similarity, analyzed_methods = await compute_similarity(
            addresses, contract_activity_dict
        )

        if avg_similarity >= S_THRESHOLD:
            print(f"Suspicious community detected: {community_id}")
            print(f"Avg similarity: {avg_similarity}")
            print(f"Addresses in community: {addresses}")
            print(f"Analyzed methods: {analyzed_methods}")
            globals.sybil_contract_transactions += number_of_community_transactions
            print(
                "all sybil contract transactions is:",
                globals.sybil_contract_transactions,
            )
            globals.sybil_transfers += community_edges_count[community_id]
            print("all sybil transfers is:", globals.sybil_transfers)

            typologies = await analyze_typology(analyzed_methods)
            print(f"Typologies for community {community_id}: {typologies}")

            for address in addresses:
                updated_subgraph.nodes[address]["status"] = "suspicious"
                updated_subgraph.nodes[address]["label"] = "sybil wallet"
                updated_subgraph.nodes[address]["typology"] = typologies

            interacting_contracts = {
                tx.contract_address for tx in community_transactions
            }

            interacting_contracts = {
                tx.contract_address for tx in community_transactions
            }
            contract_method_typologies = defaultdict(set)
            for address in addresses:
                for method, contract_address in contract_activity_dict[address]:
                    typology = await analyze_typology([method])
                    if typology != "pattern":  # If a specific typology is identified
                        contract_method_typologies[contract_address].add(typology)

            for contract_address, typologies in contract_method_typologies.items():
                typology_label = ", ".join(typologies)
                updated_subgraph.add_node(
                    contract_address, label="Wash traded asset", typology=typology_label
                )
                for typology in typologies:
                    updated_subgraph.nodes[contract_address][
                        f"typology_{typology}"
                    ] = True

            print(
                f"Interacting contracts for community {community_id}: {list(interacting_contracts)}"
            )

            interacting_contracts_list = list(interacting_contracts)
            # TODO: add the functionality that adds contracts as nodes
            for address in addresses:
                updated_subgraph.nodes[address][
                    "interacting_contracts"
                ] = interacting_contracts_list

            print(
                f"Interacting contracts for community {community_id}: {interacting_contracts_list}"
            )

    return updated_subgraph
