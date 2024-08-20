# from collections import defaultdict
# from src.hydra.analysis.transaction_analysis.helpers import (
#     build_contract_activity_dict,
# )
# from src.contracts.targets import TARGET_ADDRESSES


# async def group_addresses_by_community(updated_subgraph):
#     grouped_addresses = defaultdict(set)
#     community_edges_count = {}

#     # Group nodes by community and create subgraphs for each community
#     for node, data in updated_subgraph.nodes(data=True):
#         if "community" in data:
#             community_id = data["community"]
#             grouped_addresses[community_id].add(node)

#     # Create a subgraph for each community and count the edges
#     for community_id, nodes in grouped_addresses.items():
#         community_subgraph = updated_subgraph.subgraph(nodes)
#         community_edges_count[community_id] = community_subgraph.number_of_edges()

#     return grouped_addresses, community_edges_count


# async def target_interaction_analysis(updated_subgraph, contract_transactions):
#     grouped_addresses, _ = await group_addresses_by_community(updated_subgraph)

#     for community_id, addresses in grouped_addresses.items():
#         print("Processing community:", community_id)

#         # Check for transactions with target contracts
#         target_interactions = [
#             tx
#             for tx in contract_transactions
#             if tx.contract_address in TARGET_ADDRESSES and tx.sender in addresses
#         ]

#         # If the community has interactions with target contracts
#         if target_interactions:
#             print(f"Community {community_id} interacted with target contracts.")
#             interacting_contracts = {tx.contract_address for tx in target_interactions}
#             for address in addresses:
#                 updated_subgraph.nodes[address]["status"] = "suspicious"
#                 updated_subgraph.nodes[address]["label"] = "sybil attacker"
#                 updated_subgraph.nodes[address]["typology"] = "target"
#                 updated_subgraph.nodes[address]["interacting_contracts"] = list(
#                     interacting_contracts
#                 )

#     return updated_subgraph
