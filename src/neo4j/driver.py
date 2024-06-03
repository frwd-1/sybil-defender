from neo4j import GraphDatabase

URI = "bolt://localhost:7687"
AUTH = ("neo4j", "HydraDBMS")
driver = GraphDatabase.driver(URI, auth=AUTH)


def get_neo4j_driver():
    try:
        driver.verify_connectivity()
        print("Connection to Neo4j verified successfully.")
        return driver
    except Exception as e:
        print(f"Failed to verify connection: {e}")
        return None
