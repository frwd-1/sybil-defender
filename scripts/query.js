const path = require('path');
require('dotenv').config({ path: path.resolve(__dirname, '../.env') });
const { ApolloClient, InMemoryCache, HttpLink, gql } = require('@apollo/client/core');
const { setContext } = require('@apollo/client/link/context');
const fs = require('fs');
const fetch = require('cross-fetch');

console.log('Starting the script... Initializing Apollo Client and GraphQL setup.');

const queryPath = path.join(__dirname, 'interactionQuery.graphql');
const INTERACTION_QUERY_STRING = fs.readFileSync(queryPath, 'utf8');
const INTERACTION_QUERY = gql`${INTERACTION_QUERY_STRING}`;

console.log('GraphQL query loaded from file.');

const httpLink = new HttpLink({
  uri: 'https://api.forta.network/graphql',
  fetch,
});
console.log('HTTP link created for GraphQL API endpoint.');

const authLink = setContext((_, { headers }) => {
  const token = process.env.GRAPHQL_KEY;
  console.log('Attaching API token to request headers.');
  return {
    headers: {
      ...headers,
      authorization: `Bearer ${token}`,
    }
  };
});

const client = new ApolloClient({
  link: authLink.concat(httpLink),
  cache: new InMemoryCache(),
});
console.log('Apollo Client initialized.');

const globalWallets = new Set(); // Track unique wallets across intervals
const fetchAndWriteEntitiesToCSV = async (outputFile) => {
  console.log('Fetching new data and writing entities to CSV...');

  let endCursor = null;
  let hasNextPage = true;
  let pageCount = 0;
  let newWalletsCount = 0; // Count new wallets added in this run

  // Append to the CSV file without overwriting previous data
  const writeStream = fs.createWriteStream(outputFile, { flags: 'a' });

  try {
    while (hasNextPage) {
      console.log(`Sending GraphQL query (Page ${pageCount + 1})...`);

      let variables = {
        input: {
          sourceIds: ["0x349f4fc9abbd76fdcdb9b0a73b0ef1c3d53935d7ad41a3cf8b8bd32fcf514113"],
          afterCreatedAtDate: "2024-11-14",
          // beforeCreatedAtDate: "2024-11-01",
          chainIds: [137],
        },
      };

      if (endCursor) {
        variables.input.after = { pageToken: endCursor };
      }

      const { data } = await client.query({
        query: INTERACTION_QUERY,
        variables: variables,
      });

      console.log(`Page ${pageCount + 1} query successful. Received ${data.labels.labels.length} labels.`);
      pageCount++;

      data.labels.labels.forEach(label => {
        const metadata = label.label.metadata;
        const interactedContracts = metadata.find(str => str.startsWith('interacted contracts='));
        const typologies = label.label.label ? label.label.label.split(',') : [];

        // Typologies:
        // Wash Trading
        // ML: Flow Through
        // Asset Farming
        if (typologies.length === 1 && typologies[0] === 'Wash Trading') {
          const wallet = label.label.entity.trim().toLowerCase();

          if (!globalWallets.has(wallet)) {
            globalWallets.add(wallet);
            newWalletsCount++; // Increment count for this run
            console.log(`New wallet detected: ${wallet}`);

            const entityData = {
              wallet: wallet,
              chainId: metadata.find(str => str.startsWith('chainId='))?.split('=')[1] || '',
              clusterId: metadata.find(str => str.startsWith('cluster_id='))?.split('=')[1] || '',
              typology: typologies.join(', '),
              interactedContracts: interactedContracts ? interactedContracts.split('=')[1] : '',
            };

            const csvRow = [
              entityData.wallet,
              entityData.chainId,
              entityData.clusterId,
              entityData.typology,
              entityData.interactedContracts
            ].join(',') + '\n';

            writeStream.write(csvRow);
          } else {
            console.log(`Duplicate wallet ignored: ${wallet}`);
          }
        }
      });

      console.log(`Page ${pageCount} processed. Current count of new wallets in this run: ${newWalletsCount}`);

      // Clear Apollo Client cache
      client.cache.reset();

      // Force garbage collection
      if (global.gc) {
        global.gc();
      }

      hasNextPage = data.labels.pageInfo.hasNextPage;
      endCursor = hasNextPage ? data.labels.pageInfo.endCursor.pageToken : null;
    }

    console.log(`Total pages processed in this run: ${pageCount}`);
    console.log(`Total new wallets added in this run: ${newWalletsCount}`);
  } catch (error) {
    console.error('Error fetching or writing data:', error);
    if (error.networkError && error.networkError.result && error.networkError.result.errors) {
      console.error('GraphQL Errors:', error.networkError.result.errors);
    }
  } finally {
    writeStream.end();
    console.log('CSV write stream closed.');
  }
};

// Set the output file path
const outputFile = path.join(__dirname, 'TrialRun.csv');

// Run fetchAndWriteEntitiesToCSV every 60 seconds
console.log('Script initialized. Starting data fetch every 60 seconds.');
setInterval(() => {
  console.log('Starting a new data fetch cycle...');
  fetchAndWriteEntitiesToCSV(outputFile);
}, 60000);
