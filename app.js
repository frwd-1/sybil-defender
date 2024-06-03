const express = require('express');
const neo4j = require('neo4j-driver');

const app = express();
const port = 3000;

// Set up Neo4j connection
const uri = "bolt://localhost:7687";
const user = "neo4j";
const password = "HydraDBMS";
const driver = neo4j.driver(uri, neo4j.auth.basic(user, password));
const session = driver.session();

app.use(express.static('public'));

app.use(express.json());

app.get('/wallet/:address', async (req, res) => {
    console.log("Received request for wallet address:", req.params.address);
    try {
        console.log("Running Neo4j query...");
        const result = await session.run(
            'MATCH (n {address: $address}) RETURN n.label AS label, n.status AS status, n.typology AS typology',
            { address: req.params.address }
        );
        console.log("Neo4j query executed successfully.");
        console.log("Number of results:", result.records.length);

        const data = result.records.map(record => ({
            label: record.get('label'),
            status: record.get('status'),
            typology: record.get('typology')
        }));

        console.log("Data found:", data);
        res.send(data);
    } catch (error) {
        console.error('Error accessing Neo4j', error);
        res.status(500).send('Error accessing the database');
    }
});



app.listen(port, () => {
    console.log(`Server running on http://localhost:${port}`);
});
