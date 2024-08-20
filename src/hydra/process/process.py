from src.hydra.database_controllers.models import Transfer, ContractTransaction
from src.hydra.graph_controllers.graph_controller import (
    add_transactions_to_graph,
    adjust_edge_weights_and_variances,
    convert_decimal_to_float,
    process_partitions,
)

from src.hydra.dynamic.dynamic_suspicious import (
    merge_final_graphs,
)
from src.hydra.graph_controllers.final_graph_controller import load_graph, save_graph

from src.hydra.analysis.transaction_analysis.algorithm import run_algorithm
from src.hydra.database_controllers.clustering import generate_alerts
from src.hydra.database_controllers.db_controller import get_async_session
from sqlalchemy.future import select
from src.hydra.analysis.community_analysis.base_analyzer import (
    analyze_communities,
)

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
        key_mapping[key_id] = attr_name
    return key_mapping


async def extract_node_data(node, key_mapping):
    data = {}
    for child in node:
        attr_name = key_mapping.get(child.get("key"))
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


async def process_transactions(network_name: str):
    findings = []
    print("network name is:", network_name)

    async with get_async_session(network_name) as session:
        print("pulling all transfers...")

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

    print("analyzing clusters for suspicious activity")
    analyzed_subgraph = (
        await analyze_communities(updated_subgraph, contract_transactions) or []
    )

    try:
        persisted_graph = load_graph(
            f"src/g/graphs_two/final_{network_name}_graph.graphml"
        )

    except Exception as e:
        persisted_graph = nx.Graph()

    final_graph, previous_community_ids = merge_final_graphs(
        analyzed_subgraph, persisted_graph
    )

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

    graphml_filename = f"final_{network_name}_graph.graphml"

    print("loaded graph into neo4j")

    print("COMPLETE")
    return findings
