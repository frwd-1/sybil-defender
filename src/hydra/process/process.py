from src.hydra.database_controllers.models import Transfer, ContractTransaction
from src.hydra.graph_controllers.graph_controller import (
    add_transactions_to_graph,
    adjust_edge_weights_and_variances,
    convert_decimal_to_float,
    process_partitions,
)

from src.hydra.dynamic.dynamic_suspicious import (
    merge_final_graphs,
    # merge_final_graphs_neo4j,
)
from src.hydra.graph_controllers.final_graph_controller import load_graph, save_graph

from src.hydra.analysis.transaction_analysis.algorithm import run_algorithm
from src.hydra.database_controllers.clustering import generate_alerts
from src.hydra.database_controllers.db_controller import get_async_session
from sqlalchemy.future import select
from src.hydra.analysis.community_analysis.base_analyzer import (
    analyze_communities,
)

# from src.neo4j.driver import get_neo4j_driver
from src.hydra.utils import globals
import networkx as nx
import json
import os
import asyncio
import xml.etree.ElementTree as ET
from neo4j import GraphDatabase


import xml.etree.ElementTree as ET
from neo4j import GraphDatabase
import asyncio


import xml.etree.ElementTree as ET


def create_key_mapping(root, ns):
    key_mapping = {}
    for key in root.findall(".//graphml:key", ns):
        attr_name = key.attrib["attr.name"]
        key_id = key.attrib["id"]
        key_mapping[key_id] = attr_name  # Map key_id to attr_name
    return key_mapping


async def extract_node_data(node, key_mapping):
    data = {}
    for child in node:
        attr_name = key_mapping.get(
            child.get("key")
        )  # Use the key to get the attr.name
        data[attr_name] = child.text

    labels = data.get("typology", "").split(";")
    valid_labels = {
        "ML: Flow Through": "ML_Flow_Through",
        "Asset Farming": "Asset_Farming",
        "Wash Trading": "Wash_Trading",
    }
    neo4j_labels = [
        valid_labels.get(label, label) for label in labels if label in valid_labels
    ]

    # Use the correct attribute names for properties
    return {
        "labels": neo4j_labels,
        "props": {
            "address": data.get("address"),
            "chainId": data.get("chainId"),
            "community": int(data.get("community", 0)),
            "interacting_contracts": json.loads(
                data.get("interacting_contracts", "[]")
            ),
            "label": data.get("label"),
            "status": data.get("status"),
            "typology": ";".join(neo4j_labels),
        },
    }


async def extract_edge_data(edge, key_mapping):
    data = {}
    for child in edge:
        attr_name = key_mapping.get(
            child.get("key")
        )  # Use the key to get the attr.name
        data[attr_name] = child.text

    # Use the correct attribute names for properties
    return {
        "source": edge.get("source"),
        "target": edge.get("target"),
        "type": "Transferred",
        "props": {
            "hash": data.get("hash"),
            "amount": float(data.get("amount", 0)),
            "timestamp": int(data.get("timestamp", 0)),
            "gas_price": float(data.get("gas_price", 0)),
            "chainId": data.get("chainId"),
        },
    }


async def parse_and_load_graphml_into_neo4j(driver, network_name):
    with driver.session() as session:
        graphml_path = f"src/g/graphs_two/final_{network_name}_graph.graphml"
        tree = ET.parse(graphml_path)
        root = tree.getroot()

        ns = {"graphml": "http://graphml.graphdrawing.org/xmlns"}
        key_mapping = create_key_mapping(root, ns)

        for node in root.findall(".//graphml:graph/graphml:node", ns):
            node_data = await extract_node_data(node, key_mapping)
            if node_data["labels"]:
                session.execute_write(
                    lambda tx: tx.run(
                        """
                        CALL apoc.merge.node($labels, {address: $props.address}, $props, {})
                        """,
                        labels=node_data["labels"],
                        props=node_data["props"],
                    )
                )

        for edge in root.findall(".//graphml:graph/graphml:edge", ns):
            edge_data = await extract_edge_data(edge, key_mapping)
            session.execute_write(
                lambda tx: tx.run(
                    """
                    MATCH (a {address: $source}), (b {address: $target})
                    CALL apoc.merge.relationship(a, $type, $identProps, $onCreateProps, b, $onMatchProps)
                    YIELD rel
                    RETURN id(a), id(b)
                    """,
                    source=edge_data["source"],
                    target=edge_data["target"],
                    type=edge_data["type"],
                    identProps={"hash": edge_data["props"]["hash"]},  # Corrected here
                    onCreateProps=edge_data["props"],
                    onMatchProps=edge_data["props"],
                )
            )
    print("GraphML data loaded into Neo4j.")


async def load_graphml_into_neo4j(driver, network_name):
    try:
        with driver.session() as session:
            import_result = session.run(
                "CALL apoc.import.graphml($file_path, {defaultRelationshipType: 'Transferred'})",
                {"file_path": f"/final_{network_name}_graph.graphml"},
            )
            import_summary = import_result.consume()
            print(f"GraphML import completed: {import_summary.counters}")

            label_result = session.run(
                """
                MATCH (n)
                WHERE n.typology IS NOT NULL
                WITH n, n.typology AS typology
                CALL apoc.create.addLabels(id(n), [typology]) YIELD node
                RETURN count(node)
                """
            )
            label_summary = label_result.consume()
            print(f"Labeling completed: {label_summary.counters}")

    except Exception as e:
        print(f"Failed to load GraphML into Neo4j and label nodes: {e}")


# async def detect_and_assign_communities_WCC():
#     driver = get_neo4j_driver()
#     if driver is None:
#         print("Failed to get Neo4j driver")
#         return

#     with driver.session() as session:
#         # Propagate existing component IDs to adjacent nodes
#         propagated_count = session.run(
#             """
#             MATCH (w1:Wallet)-[:SENT]->(w2:Wallet)
#             WHERE w1.componentId IS NOT NULL AND w2.componentId IS NULL
#             SET w2.componentId = w1.componentId
#             RETURN count(w2) AS propagatedCount
#             """
#         ).single()["propagatedCount"]
#         print(f"Component IDs propagated to {propagated_count} adjacent nodes.")

#         # Determine the highest current component ID
#         max_component_id_result = session.run(
#             """
#             MATCH (w:Wallet)
#             WHERE w.componentId IS NOT NULL
#             RETURN coalesce(max(w.componentId), 0) AS maxComponentId
#             """
#         ).single()
#         max_component_id = max_component_id_result["maxComponentId"]
#         print(f"Maximum component ID found: {max_component_id}")

#         hydraGraph = "hydraGraph"

#         result = session.run(
#             """
#             CALL gds.graph.project.cypher(
#                 'hydraGraph',
#                 'MATCH (n:Wallet) WHERE n.communityId IS NULL RETURN id(n) AS id',
#                 'MATCH (n:Wallet)-[r]->(m:Wallet) WHERE n.communityId IS NULL AND m.communityId IS NULL RETURN id(n) AS source, id(m) AS target'
#             )
#             YIELD graphName, nodeCount, relationshipCount
#             """
#         )

#         for record in result:
#             print(
#                 f"Graph name: {record['graphName']}, Node count: {record['nodeCount']}, Relationship count: {record['relationshipCount']}"
#             )

#         # Run WCC on the filtered graph
#         print("Running WCC on the filtered graph...")
#         wcc_result = session.run(
#             """
#             CALL gds.wcc.write($graphName, {
#                 writeProperty: 'componentId'
#             })
#             YIELD componentCount
#             """,
#             parameters={"graphName": hydraGraph},
#         )
#         component_count = wcc_result.single()["componentCount"]
#         print(f"Component Count for new communities: {component_count}")

#         print("Updating component IDs...")
#         result = session.run(
#             """
#             MATCH (n)
#             WHERE n.componentId IS NOT NULL
#             SET n.componentId = n.componentId + $max_component_id
#             """,
#             {"max_component_id": max_component_id},
#         )
#         print(f"Component IDs updated.")

#         # Handle small components
#         small_components = session.run(
#             """
#             MATCH (n)
#             WHERE n:Wallet OR n:Contract AND n.componentId IS NOT NULL
#             WITH n.componentId AS componentId, count(n) AS size
#             WHERE size <= 5
#             RETURN componentId
#         """
#         )
#         small_component_ids = [record["componentId"] for record in small_components]

#         for component_id in small_component_ids:
#             session.run(
#                 f"""
#                 MATCH (n)
#                 WHERE n.componentId = {component_id}
#                 DETACH DELETE n
#             """
#             )
#         print(f"Deleted nodes and edges from small components.")

#         # Update contracts with component interactions
#         session.run(
#             """
#             MATCH (w:Wallet)-[:CALLED]->(c:Contract)
#             WHERE w.componentId IS NOT NULL
#             WITH c, collect(DISTINCT w.componentId) AS components
#             SET c.interactions = components
#         """
#         )
#         print("Contracts updated with component interactions.")

#         # Delete contracts that have no interactions with any components
#         session.run(
#             """
#             MATCH (c:Contract)
#             WHERE c.interactions IS NULL OR size(c.interactions) = 0
#             DETACH DELETE c
#         """
#         )
#         print("Lonely contracts deleted.")

#         # Drop the graph projection
#         # session.run(f"CALL gds.graph.drop('{hydraGraphFiltered}')")
#         # print(f"Projection {hydraGraphFiltered} deleted.")
#         session.run(f"CALL gds.graph.drop('{hydraGraph}')")
#         print(f"Projection {hydraGraph} deleted.")


# async def detect_and_assign_communities_louvain():
#     driver = get_neo4j_driver()
#     if driver is None:
#         print("Failed to get Neo4j driver")
#         return

#     hydraGraph = "hydraGraph"

#     with driver.session() as session:
#         check_graph_query = f"""
#         CALL gds.graph.exists('{hydraGraph}')
#         YIELD exists
#         """
#         graph_exists_result = session.run(check_graph_query).single()["exists"]

#         if not graph_exists_result:
#             print(
#                 f"Graph {hydraGraph} does not exist in the GDS catalog. Creating the graph..."
#             )
#             create_graph_query = f"""
#             CALL gds.graph.project(
#                 '{hydraGraph}',
#                 ['Wallet', 'Contract'],
#                 {{
#                     SENT: {{
#                         type: 'SENT',
#                         properties: ['amount']
#                     }}
#                 }}
#             )
#             """
#             session.run(create_graph_query)
#             print(f"Graph {hydraGraph} created.")

#         community_detection_query = f"""
#         CALL gds.louvain.write('{hydraGraph}', {{
#             relationshipTypes: ['SENT'],
#             writeProperty: 'communityId'
#         }})
#         YIELD communityCount, modularity
#         """
#         result = session.run(community_detection_query)
#         for record in result:
#             print(
#                 f"Community Count: {record['communityCount']}, Modularity: {record['modularity']}"
#             )

#         print("Communities detected and assigned.")


async def process_transactions(network_name: str):
    findings = []
    print("network name is:", network_name)

    async with get_async_session(network_name) as session:
        print("pulling all transfers...")
        # Assume the Transfer model and select function are defined elsewhere
        transfer_result = await session.execute(
            select(Transfer).where(
                (Transfer.processed == False) & (Transfer.chainId == network_name)
            )
        )
        transfers = transfer_result.scalars().all()
        print("transfers pulled")
        globals.all_transfers += len(transfers)
        print("Number of transfers:", globals.all_transfers)

        contract_transaction_result = await session.execute(
            select(ContractTransaction).where(
                (ContractTransaction.processed == False)
                & (ContractTransaction.chainId == network_name)
            )
        )
        contract_transactions = contract_transaction_result.scalars().all()
        print("contract transactions pulled")
        globals.all_contract_transactions += len(contract_transactions)
        print("Number of contract transactions:", globals.all_contract_transactions)

        for transfer in transfers:
            transfer.processed = True
        for transaction in contract_transactions:
            transaction.processed = True
        await session.commit()

    subgraph = nx.DiGraph()
    subgraph, added_edges = add_transactions_to_graph(transfers, subgraph)
    print("added total edges:", len(added_edges))

    # globals.global_added_edges.extend(added_edges)
    # Create a new directed subgraph using only the edges added in the current iteration

    subgraph = adjust_edge_weights_and_variances(transfers, subgraph)

    subgraph = convert_decimal_to_float(subgraph)
    # nx.write_graphml(globals.G1, "src/graph/graphs/initial_global_graph.graphml")

    print(f"Number of nodes in subgraph: {subgraph.number_of_nodes()}")
    print(f"Number of edges in subgraph: {subgraph.number_of_edges()}")

    subgraph_partitions = run_algorithm(subgraph)

    updated_subgraph = process_partitions(subgraph_partitions, subgraph)
    nx.write_graphml(
        updated_subgraph,
        f"src/g/graphs/updated_{network_name}_subgraph.graphml",
    )

    # print("is initial batch?", globals.is_initial_batch)
    # if not globals.is_initial_batch:
    #     merge_new_communities(
    #         updated_subgraph,
    #     )
    # else:
    #     globals.G2 = updated_subgraph.copy()

    print("analyzing clusters for suspicious activity")
    analyzed_subgraph = (
        await analyze_communities(updated_subgraph, contract_transactions) or []
    )

    try:
        persisted_graph = load_graph(
            f"src/g/graphs_two/final_{network_name}_graph.graphml"
            # f"src/graph/graphs_two/final_graph17.graphml"
        )

    except Exception as e:
        persisted_graph = nx.Graph()

    # driver = get_neo4j_driver()
    # if driver is None:
    #     print("Failed to get Neo4j driver")
    #     return

    final_graph, previous_community_ids = merge_final_graphs(
        analyzed_subgraph, persisted_graph
    )

    # final_graph, previous_community_ids = merge_final_graphs_neo4j(
    #     driver, analyzed_subgraph, network_name
    # )

    for node, data in final_graph.nodes(data=True):
        for key, value in list(data.items()):
            if isinstance(value, type):
                data[key] = str(value)
            elif isinstance(value, list):
                data[key] = json.dumps(value)

    for u, v, data in final_graph.edges(data=True):
        for key, value in list(data.items()):
            if isinstance(value, type):
                data[key] = str(value)
            elif isinstance(value, list):
                data[key] = json.dumps(value)

    findings = await generate_alerts(
        analyzed_subgraph, persisted_graph, network_name, previous_community_ids
    )

    save_graph(
        final_graph,
        # f"src/graph/graphs_two/final_graph17.graphml"
        f"src/g/graphs_two/final_{network_name}_graph.graphml",
    )
    # save_graph(
    #     final_graph,
    #     f"/Users/andrewworth/Library/Application Support/Neo4j Desktop/Application/relate-data/dbmss/dbms-3022a2a9-de9d-4f32-858b-29e182c70fc0/import/final_{network_name}_graph.graphml",
    # )

    # neo4j_import_path = "/Users/andrewworth/Library/Application Support/Neo4j Desktop/Application/relate-data/dbmss/dbms-3022a2a9-de9d-4f32-858b-29e182c70fc0/import"
    graphml_filename = f"final_{network_name}_graph.graphml"
    # graphml_path = os.path.join(neo4j_import_path, graphml_filename)

    # await load_graphml_into_neo4j(driver, network_name)
    # await parse_and_load_graphml_into_neo4j(driver, network_name)
    print("loaded graph into neo4j")

    print("COMPLETE")
    return findings

    # create_graph_query = f"""
    #     CALL gds.graph.project(
    #         '{hydraGraph}',
    #         ['Wallet'],
    #         {{
    #             SENT: {{
    #                 type: 'SENT',
    #                 properties: ['amount']
    #             }}
    #         }}
    #     )
    #     """
    # session.run(create_graph_query)
    # print(f"Graph {hydraGraph} created.")

    # # Create a filtered graph projection for Wallet nodes without a component ID
    # hydraGraphFiltered = "WCCGraphFiltered"
    # session.run(
    #     f"""
    #     CALL gds.graph.filter(
    #         '{hydraGraphFiltered}',
    #         'hydraGraph',
    #         'n.componentId IS NULL',
    #         '*'
    #     )
    #     """
    # )
    # print(
    #     f"Filtered graph {hydraGraphFiltered} created for Wallet nodes without a component ID."
    # )
