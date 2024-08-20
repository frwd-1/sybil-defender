import networkx as nx
import logging


def merge_final_graphs_neo4j(driver, G_analyzed, network_name):
    with driver.session() as session:

        session.run(
            """
        MATCH (n {network_name: $network_name, status: 'suspicious'})
        DETACH DELETE n
        """,
            network_name=network_name,
        )

        for node, data in G_analyzed.nodes(data=True):

            session.run(
                """
            MERGE (n:Node {id: $id, network_name: $network_name})
            ON CREATE SET n += $properties
            """,
                id=node,
                network_name=network_name,
                properties=data,
            )

        for u, v, data in G_analyzed.edges(data=True):
            session.run(
                """
            MATCH (n1:Node {id: $u, network_name: $network_name}), (n2:Node {id: $v, network_name: $network_name})
            MERGE (n1)-[r:TRANSFER]->(n2)
            ON CREATE SET r += $properties
            """,
                u=u,
                v=v,
                network_name=network_name,
                properties=data,
            )


def merge_final_graphs(G_analyzed, persistent_graph):
    print("Starting merge of final graphs...")

    if not isinstance(G_analyzed, nx.Graph) or not isinstance(
        persistent_graph, nx.Graph
    ):
        logging.error(
            "Invalid input types. Both parameters should be NetworkX graph objects."
        )
        return persistent_graph

    try:
        nodes_to_remove = [
            node
            for node, data in G_analyzed.nodes(data=True)
            if data.get("status") != "suspicious"
        ]
        previous_community_ids = {
            node_data.get("community")
            for _, node_data in persistent_graph.nodes(data=True)
        }

        G_analyzed.remove_nodes_from(nodes_to_remove)

        previous_communities = nx.get_node_attributes(persistent_graph, "community")
        print(
            f"Number of communities in persistent_graph: {len(set(previous_communities.values()))}"
        )

        overlapping_nodes = set(persistent_graph.nodes()).intersection(
            G_analyzed.nodes()
        )
        print("overlapping nodes:", overlapping_nodes)
        print(f"Number of overlapping nodes: {len(overlapping_nodes)}")

        overlap_detail = {}
        merge_map = {}

        original_G_analyzed_communities = nx.get_node_attributes(
            G_analyzed, "community"
        ).copy()
        print(
            f"Number of communities in G_analyzed: {len(set(original_G_analyzed_communities.values()))}"
        )

        for node in overlapping_nodes:
            print("processing node:", node)
            target_community = previous_communities.get(node)
            print("target community is:", target_community)

            if target_community is not None:
                G_analyzed_community = original_G_analyzed_communities[node]
                print("G_analyzed community is:", G_analyzed_community)

                merge_map[G_analyzed_community] = target_community

                overlap_detail.setdefault(G_analyzed_community, {}).setdefault(
                    target_community, []
                ).append(node)

                if G_analyzed_community != target_community:
                    for n, d in G_analyzed.nodes(data=True):
                        if d["community"] == G_analyzed_community:
                            d["community"] = target_community
                            print(
                                f"Updating node {n} from community {G_analyzed_community} to {target_community}."
                            )

        for G_analyzed_comm, overlaps in overlap_detail.items():
            for persistent_comm, nodes in overlaps.items():
                print(
                    f"Nodes {nodes} in G_analyzed community {G_analyzed_comm} overlap with community {persistent_comm} in persistent_graph."
                )

        max_existing_community_id = max(previous_communities.values(), default=0)
        print("max existing community id is:", max_existing_community_id)

        new_community_id = max_existing_community_id + 1
        print(f"Starting new community IDs from: {new_community_id}")

        for community in set(original_G_analyzed_communities.values()):
            if community not in merge_map:
                nodes_in_community = [
                    node
                    for node, comm in original_G_analyzed_communities.items()
                    if comm == community
                ]
                print(f"Community {community} has {len(nodes_in_community)} nodes.")

                for node in nodes_in_community:
                    if node in G_analyzed.nodes():
                        G_analyzed.nodes[node]["community"] = new_community_id
                        print(
                            f"Assigning new community ID {new_community_id} to node {node}."
                        )

                new_community_id += 1

        persistent_graph.add_nodes_from(G_analyzed.nodes(data=True))
        persistent_graph.add_edges_from(G_analyzed.edges(data=True))

        print("Completed merge of final graphs.")

    except AttributeError as e:
        logging.error(f"An AttributeError occurred: {e}")
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")

    return persistent_graph, previous_community_ids


logging.basicConfig(level=logging.ERROR)  # or appropriate level


# def merge_graphs(G_analyzed, persistent_graph):
#     for node, attr in G_analyzed.nodes(data=True):
#         if attr.get("status") == "suspicious":
#             # Check if the node has a "community" attribute in G_analyzed
#             G_analyzed_community_id = attr.get("community", None)
#             if G_analyzed_community_id is None:
#                 continue  # Skip this node, as it doesn't have a community ID in G_analyzed

#             # If the node is not in the persistent graph, add it and its associated edges
#             if node not in persistent_graph:
#                 persistent_graph.add_node(node, **attr)
#                 for neighbor in G_analyzed.neighbors(node):
#                     if G_analyzed.nodes[neighbor].get("status") == "suspicious":
#                         persistent_graph.add_edge(
#                             node, neighbor, **G_analyzed[node][neighbor]
#                         )

#             else:
#                 # If node is already in the persistent graph, check if it has a "community" attribute
#                 if "community" in persistent_graph.nodes[node]:
#                     persistent_community_id = persistent_graph.nodes[node]["community"]

#                     # Update nodes in G_analyzed with the community ID from the persistent graph
#                     for n, a in G_analyzed.nodes(data=True):
#                         if a.get("community") == G_analyzed_community_id:
#                             a["community"] = persistent_community_id

#                     # Add nodes and edges from G_analyzed's community to persistent graph
#                     nodes_in_G_analyzed_community = [
#                         n
#                         for n, a in G_analyzed.nodes(data=True)
#                         if a.get("community") == persistent_community_id
#                     ]
#                     persistent_graph = nx.compose(
#                         persistent_graph,
#                         G_analyzed.subgraph(nodes_in_G_analyzed_community),
#                     )

#     return persistent_graph


# def merge_new_communities(updated_subgraph):
#     print("Starting merge of new communities...")

#     G2 = globals.G2
#     previous_communities = nx.get_node_attributes(G2, "community")
#     print(f"Number of communities in G2: {len(set(previous_communities.values()))}")

#     overlapping_nodes = set(G2.nodes()).intersection(updated_subgraph.nodes())

#     merged_communities = set()
#     original_subgraph_communities = nx.get_node_attributes(
#         updated_subgraph, "community"
#     ).copy()

#     for node in overlapping_nodes:
#         target_community = previous_communities.get(node)
#         if target_community is not None:
#             subgraph_community = updated_subgraph.nodes[node]["community"]
#             merged_communities.add(subgraph_community)

#             for n, d in updated_subgraph.nodes(data=True):
#                 if d["community"] == subgraph_community:
#                     d["community"] = target_community
#                     print(
#                         f"Updating node {n} from community {subgraph_community} to {target_community}."
#                     )

#     max_existing_community_id = max(previous_communities.values(), default=0)
#     new_community_id = max_existing_community_id + 1
#     print(f"Starting new community IDs from: {new_community_id}")

#     for community in set(original_subgraph_communities.values()):
#         if community not in merged_communities:
#             nodes_in_community = [
#                 node
#                 for node, comm in original_subgraph_communities.items()
#                 if comm == community
#             ]

#             for node in nodes_in_community:
#                 if node in updated_subgraph.nodes():
#                     updated_subgraph.nodes[node]["community"] = new_community_id
#                     print(
#                         f"Assigning new community ID {new_community_id} to node {node}."
#                     )

#             new_community_id += 1

#     G2.add_nodes_from(updated_subgraph.nodes(data=True))
#     G2.add_edges_from(updated_subgraph.edges(data=True))

#     print("Completed merge of new communities.")
