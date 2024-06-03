from src.hydra.analysis.community_analysis.similarity_analysis import (
    similarity_analysis,
)

# from src.hydra.analysis.community_analysis.target_analysis import (
#     target_interaction_analysis,
# )


async def analyze_communities(updated_subgraph, contract_transactions):
    similarity_analyzed_subgraph = await similarity_analysis(
        updated_subgraph, contract_transactions
    )

    # final_analyzed_subgraph = await target_interaction_analysis(
    #     similarity_analyzed_subgraph, contract_transactions
    # )

    return similarity_analyzed_subgraph
