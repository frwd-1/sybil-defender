from src.hydra.utils import globals
import networkx as nx
import community as community_louvain


# def merge_new_communities(updated_subgraph):
#     print("Starting merge of new communities...")

#     G2 = globals.G2  # Retrieve G2 from global scope

#     # Identify overlapping nodes between the existing graph and the updated subgraph.
#     overlapping_nodes = set(G2.nodes()).intersection(updated_subgraph.nodes())
#     print(f"Number of overlapping nodes: {len(overlapping_nodes)}")

#     # Fetch the previous partition.
#     prev_partition = community_louvain.best_partition(G2)
#     print("Previous partition retrieved.")

#     # Merge the previous graph and the updated subgraph.
#     combined_graph = nx.compose(G2, updated_subgraph)

#     # If the graph is directed, we convert it to undirected for the Louvain method.
#     if combined_graph.is_directed():
#         combined_graph = combined_graph.to_undirected()
#         print("Converted the graph to undirected for community detection.")

#     # Include new nodes from the updated subgraph into the previous partition with a unique community.
#     # We need to ensure that they don't clash with existing community IDs, so we find the maximum existing community ID and increment from there.
#     max_community_id = max(prev_partition.values(), default=-1) + 1
#     for node in updated_subgraph.nodes():
#         if node not in prev_partition:
#             prev_partition[node] = max_community_id
#             max_community_id += 1

#     # Apply the Louvain method using the previous partition as a starting point.
#     best_partition = community_louvain.best_partition(
#         combined_graph, partition=prev_partition
#     )
#     print(
#         "Best partition obtained using dynamic Louvain method with guidance from the previous partition."
#     )

#     # Ensure all nodes have a community
#     for node in combined_graph.nodes():
#         if node not in best_partition:
#             best_partition[node] = max_community_id  # assign a new community ID
#             max_community_id += 1

#     # Now correct any inconsistencies in the 'best_partition' by ensuring that connected communities have the same ID.
#     # First, create a new graph that represents the communities as nodes.
#     community_graph = nx.Graph()
#     for node, community_id in best_partition.items():
#         community_graph.add_node(community_id)
#         for neighbor in combined_graph.neighbors(node):
#             neighbor_community_id = best_partition[neighbor]
#             if community_id != neighbor_community_id:
#                 community_graph.add_edge(community_id, neighbor_community_id)

#     # Identify and correct connected communities that have been assigned different community IDs.
#     new_community_id = max(best_partition.values(), default=-1) + 1
#     corrected_partition = best_partition.copy()
#     for community_set in nx.connected_components(community_graph):
#         if (
#             len(community_set) > 1
#         ):  # If connected communities have different IDs, unify them.
#             unified_community_id = new_community_id
#             new_community_id += 1
#             for community_id in community_set:
#                 for node, original_community_id in best_partition.items():
#                     if original_community_id == community_id:
#                         corrected_partition[node] = unified_community_id

#     # Apply the corrected partition back to the original graph G2, ensuring all nodes have a community ID.
#     nx.set_node_attributes(G2, corrected_partition, "community")
#     print(
#         "Communities have been updated in the original graph based on the corrected partition."
#     )

#     # Integrate new interactions into the original graph.
#     new_edges = updated_subgraph.edges(data=True)
#     G2.add_edges_from(new_edges)
#     print("New interactions have been integrated into the original graph.")

#     print("Merge of new communities completed.")
#     return G2


def merge_new_communities(updated_subgraph):
    print("Starting merge of new communities...")

    G2 = globals.G2

    # Merge the previous graph and the updated subgraph.
    combined_graph = nx.compose(G2, updated_subgraph)

    # If the graph is directed, we convert it to undirected for the Louvain method.
    if combined_graph.is_directed():
        combined_graph = combined_graph.to_undirected()
        print("Converted the graph to undirected for community detection.")

    # Apply dynamic community detection to update G2 based on new interactions in the updated_subgraph.
    new_additions = (
        updated_subgraph.edges()
    )  # Assuming only edges are added and no nodes without edges
    dynamic_community_detection(combined_graph, new_additions)

    print("Merge of new communities completed.")
    return G2


def AffectedByAddition(edge):
    G2 = globals.G2

    node1, node2 = edge

    # Fetch the current partition of G2.
    current_partition = community_louvain.best_partition(G2)

    affected_communities = set()

    # If node1 exists in G2, add its community to affected_communities.
    if node1 in G2:
        affected_communities.add(current_partition.get(node1))

    # If node2 exists in G2, add its community to affected_communities.
    if node2 in G2:
        affected_communities.add(current_partition.get(node2))

    # Convert the set of affected communities to a list and return.
    return list(affected_communities)


# def AffectedByRemoval(edge, G):
#     # Placeholder: Implement the logic to return affected nodes and their communities by the removal of an edge.
#     return []


# def DisbandCommunities(affected_nodes, G):
#     # Placeholder: Implement the logic to disband affected communities.
#     pass


def UpdateCulWithCllChanges(affected_nodes, C_ll, C_ul):
    # Procedure P3: Update the Cul with changes of Cll.
    for node in affected_nodes:
        C_ul[node] = C_ll[node]


def LouvainAlgorithmStep1(G, C_ul):
    # Procedure P4: Perform the Louvain Algorithm Step 1.
    return community_louvain.best_partition(G, partition=C_ul)


def LouvainAlgorithmStep2(G, C_ul):
    # Procedure P6: Perform the Louvain Algorithm Step 2.
    return community_louvain.induced_graph(C_ul, G)


def dynamic_community_detection(G, A):
    E = set(G.edges())  # Using set for faster membership checking
    C_ul = community_louvain.best_partition(G)
    mod = community_louvain.modularity(C_ul, G)
    old_mod = 0

    for edge in A:
        if mod <= old_mod:
            break
        if edge not in E:
            G.add_edge(*edge)
            E.add(edge)
            C_temp = community_louvain.best_partition(G, partition=C_ul)
            temp_mod = community_louvain.modularity(C_temp, G)
            if temp_mod > mod:
                C_ul = C_temp
                mod = temp_mod
            else:
                # If modularity didn't improve, remove the added edge
                G.remove_edge(*edge)
                E.remove(edge)
        old_mod = mod

    nx.set_node_attributes(G, C_ul, "community")
    return G


def starred_merge_new_communities(updated_subgraph):
    print("Starting merge of new communities...")

    G2 = globals.G2

    previous_communities = nx.get_node_attributes(G2, "community")
    print(f"Number of communities in G2: {len(set(previous_communities.values()))}")

    overlapping_nodes = set(G2.nodes()).intersection(updated_subgraph.nodes())
    print("overlapping nodes:", overlapping_nodes)
    print(f"Number of overlapping nodes: {len(overlapping_nodes)}")

    merged_communities = set()
    original_subgraph_communities = nx.get_node_attributes(
        updated_subgraph, "community"
    ).copy()
    print(
        f"Number of communities in the updated subgraph: {len(set(original_subgraph_communities.values()))}"
    )

    overlap_detail = {}
    merge_map = {}

    for node in overlapping_nodes:
        print("processing node:", node)
        target_community = previous_communities.get(node)
        print("target community is:", target_community)

        if target_community is not None:
            subgraph_community = original_subgraph_communities[node]
            print("subgraph community is:", subgraph_community)

            merge_map[subgraph_community] = target_community

            overlap_detail.setdefault(subgraph_community, {}).setdefault(
                target_community, []
            ).append(node)

            print("second check subgraph community is:", subgraph_community)
            print("second check target community is:", target_community)
            if subgraph_community != target_community:
                for n, d in updated_subgraph.nodes(data=True):
                    if d["community"] == subgraph_community:
                        d["community"] = target_community
                        print(
                            f"Updating node {n} from community {subgraph_community} to {target_community}."
                        )

    for subgraph_comm, overlaps in overlap_detail.items():
        for G2_comm, nodes in overlaps.items():
            print(
                f"Nodes {nodes} in the updated subgraph community {subgraph_comm} overlap with community {G2_comm} in G2."
            )

    max_existing_community_id = max(previous_communities.values(), default=0)
    print("max existing community id is:", max_existing_community_id)
    new_community_id = max_existing_community_id + 1
    print(f"Starting new community IDs from: {new_community_id}")

    for community in set(original_subgraph_communities.values()):
        if community not in merge_map:
            nodes_in_community = [
                node
                for node, comm in original_subgraph_communities.items()
                if comm == community
            ]
            print(f"Community {community} has {len(nodes_in_community)} nodes.")

            for node in nodes_in_community:
                if node in updated_subgraph.nodes():
                    updated_subgraph.nodes[node]["community"] = new_community_id
                    print(
                        f"Assigning new community ID {new_community_id} to node {node}."
                    )

            new_community_id += 1

    G2.add_nodes_from(updated_subgraph.nodes(data=True))
    G2.add_edges_from(updated_subgraph.edges(data=True))

    print("Completed merge of new communities.")


def merge_new_communities(updated_subgraph):
    print("Starting merge of new communities...")

    G2 = globals.G2
    previous_communities = nx.get_node_attributes(G2, "community")
    print(f"Number of communities in G2: {len(set(previous_communities.values()))}")

    original_subgraph_communities = nx.get_node_attributes(
        updated_subgraph, "community"
    ).copy()

    overlapping_nodes = set(G2.nodes()).intersection(updated_subgraph.nodes())
    print("Overlapping nodes:", overlapping_nodes)

    overlap_graph = nx.Graph()
    for node in overlapping_nodes:
        g2_community = G2.nodes[node]["community"]
        subgraph_community = updated_subgraph.nodes[node]["community"]
        overlap_graph.add_edge(g2_community, subgraph_community)

    max_existing_community_id = max(previous_communities.values(), default=0)
    new_community_id = max_existing_community_id + 1

    for community_set in nx.connected_components(overlap_graph):
        target_community = min(community_set)
        print(
            f"Target community for merging: {target_community} from connected communities {community_set}"
        )

        for node, data in G2.nodes(data=True):
            if data["community"] in community_set:
                data["community"] = target_community

        for node, data in updated_subgraph.nodes(data=True):
            if data["community"] in community_set:
                data["community"] = target_community

    non_overlapping_communities = set(original_subgraph_communities.values()) - set(
        overlap_graph.nodes
    )
    for community in non_overlapping_communities:
        for node, data in updated_subgraph.nodes(data=True):
            if data["community"] == community:
                data["community"] = new_community_id
                print(
                    f"Assigning new community ID {new_community_id} to node {node} in updated subgraph."
                )
        new_community_id += 1

    G2.add_nodes_from(updated_subgraph.nodes(data=True))
    G2.add_edges_from(updated_subgraph.edges(data=True))

    print("Completed merge of new communities.")
