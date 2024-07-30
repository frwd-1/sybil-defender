const path = require('path');
require('dotenv').config({ path: path.resolve(__dirname, '../.env') });
const { ApolloClient, InMemoryCache, HttpLink, gql } = require('@apollo/client/core');
const { setContext } = require('@apollo/client/link/context');
const fs = require('fs');
const fetch = require('cross-fetch');

console.log('Starting the script...');

const queryPath = path.join(__dirname, 'interactionQuery.graphql');
const INTERACTION_QUERY_STRING = fs.readFileSync(queryPath, 'utf8');
const INTERACTION_QUERY = gql`${INTERACTION_QUERY_STRING}`;

console.log('GraphQL query defined.');

const httpLink = new HttpLink({
  uri: 'https://api.forta.network/graphql',
  fetch,
});

console.log('HTTP link created.');

const authLink = setContext((_, { headers }) => {
  const token = process.env.GRAPHQL_KEY;
  console.log('Attaching the API token to the request headers.');
  return {
    headers: {
      ...headers,
      authorization: `Bearer ${token}`,
    }
  };
});

console.log('Auth link set up.');

const client = new ApolloClient({
  link: authLink.concat(httpLink),
  cache: new InMemoryCache(),
});

console.log('Apollo Client initialized.');

const readWalletsFromFile = (filePath) => {
  console.log(`Reading wallets from file: ${filePath}`);
  try {
    const data = fs.readFileSync(filePath, 'utf8');
    const wallets = data.split('\n').slice(1); // Skip the header line
    console.log(`Wallets read from file: ${wallets}`);
    return wallets.map(wallet => wallet.trim().toLowerCase()).filter(wallet => wallet !== '');
  } catch (err) {
    console.error('Error reading wallets file:', err);
    return [];
  }
};

const removeDuplicates = (data) => {
  const seen = new Set();
  return data.filter(item => {
    const duplicate = seen.has(item.wallet);
    seen.add(item.wallet);
    return !duplicate;
  });
};

const fetchAndWriteEntitiesToCSV = async (walletAddresses, outputFile, processedWalletsFile) => {
  console.log('Running fetchAndWriteEntitiesToCSV...');

  const normalizedWalletAddresses = walletAddresses.map(addr => addr.trim().toLowerCase());
  console.log(`Normalized wallet addresses: ${normalizedWalletAddresses}`);

  let allEntities = []; // Store all entities to process duplicates after writing to CSV
  let pageCount = 0;
  let csvHeadersSet = false;
  let csvHeaders = [];

  // Define the batch size
  const batchSize = 1000; // Max 1000 wallets per batch
  const batches = [];

  // Split the wallet addresses into batches
  for (let i = 0; i < normalizedWalletAddresses.length; i += batchSize) {
    batches.push(normalizedWalletAddresses.slice(i, i + batchSize));
  }

  try {
    for (const batch of batches) {
      let endCursor = null;
      let hasNextPage = true;

      while (hasNextPage) {
        console.log('Sending query to GraphQL API...');
        let variables = {
          input: {
            entities: batch,
            sourceIds: ["0x349f4fc9abbd76fdcdb9b0a73b0ef1c3d53935d7ad41a3cf8b8bd32fcf514113"],
            afterCreatedAtDate: "2024-3-1",
            chainIds: [
              42161, // Arbitrum 
              56, // Binance Smart Chain 
              137, // Polygon 
              250, // Fantom 
              1, // Ethereum 
              43114, // Avalanche chain
              10, // Optimism 
            ],
          },
        };

        if (endCursor) {
          variables.input.after = { pageToken: endCursor };
        }

        console.log('Variables:', variables);

        const { data } = await client.query({
          query: INTERACTION_QUERY,
          variables: variables,
        });

        console.log(`Query successful, received ${data.labels.labels.length} labels`);
        pageCount++;

        data.labels.labels.forEach(label => {
          const matchedAddresses = batch.filter(addr => label.label.entity.trim().toLowerCase() === addr);
          if (matchedAddresses.length > 0) {
            const entityData = {
              wallet: label.label.entity.trim().toLowerCase(),
              chainId: label.source.chainId,
              label: label.label.label, 
              entityType: label.label.entityType,
              confidence: label.label.confidence,
            };

            label.label.metadata.forEach(item => {
              const [key, value] = item.split('=');
              if (key !== 'interacted contracts' && key !== 'chainId' && key !== 'cluster_id') {
                entityData[key] = value;
              }
            });

            allEntities.push(entityData); 
          }
        });

        hasNextPage = data.labels.pageInfo.hasNextPage;
        endCursor = hasNextPage ? data.labels.pageInfo.endCursor.pageToken : null;

        if (!hasNextPage) {
          console.log('No more pages to fetch.');
          break;
        }
      }
    }

    console.log(`Total number of pages retrieved: ${pageCount}`);

    const uniqueEntities = removeDuplicates(allEntities);

    const writeStream = fs.createWriteStream(outputFile, { flags: 'a' });
    uniqueEntities.forEach(entity => {
      if (!csvHeadersSet) {
        csvHeaders = Object.keys(entity);
        csvHeadersSet = true;
        writeStream.write(`${csvHeaders.join(',')}\n`);
      }
      const csvRow = csvHeaders.map(header => entity[header] || '').join(',');
      writeStream.write(`${csvRow}\n`);
    });
    writeStream.end();

    const processedWalletsStream = fs.createWriteStream(processedWalletsFile, { flags: 'a' });
    uniqueEntities.forEach(entity => {
      processedWalletsStream.write(`${entity.wallet}\n`);
    });
    processedWalletsStream.end();

  } catch (error) {
    console.error('Error fetching or writing data:', error);
    if (error.networkError && error.networkError.result && error.networkError.result.errors) {
      console.error('GraphQL Errors:', error.networkError.result.errors);
    }
  } finally {
    console.log(`Data has been written to ${outputFile}`);
  }
};

const getNewWallets = (allWallets, processedWallets) => {
  const processedSet = new Set(processedWallets);
  return allWallets.filter(wallet => !processedSet.has(wallet));
};

const walletsFilePath = path.join(__dirname, 'wallets.txt');
const processedWalletsFilePath = path.join(__dirname, 'processed_wallets.txt');
const walletAddresses = readWalletsFromFile(walletsFilePath);
const processedWallets = readWalletsFromFile(processedWalletsFilePath);
const newWalletAddresses = getNewWallets(walletAddresses, processedWallets);
const outputFile = path.join(__dirname, 'Wallets_Labels_Match.csv');

fetchAndWriteEntitiesToCSV(newWalletAddresses, outputFile, processedWalletsFilePath);

// Function to monitor continuously
const monitorWalletsContinuously = async (walletsFilePath, processedWalletsFilePath, outputFile) => {
  setInterval(async () => {
    console.log('Checking for updates...');
    const walletAddresses = readWalletsFromFile(walletsFilePath);
    const processedWallets = readWalletsFromFile(processedWalletsFilePath);
    const newWalletAddresses = getNewWallets(walletAddresses, processedWallets);
    await fetchAndWriteEntitiesToCSV(newWalletAddresses, outputFile, processedWalletsFilePath);
  }, 60000); // Checking every 60 seconds, adjust as needed
};

// Start continuous monitoring
monitorWalletsContinuously(walletsFilePath, processedWalletsFilePath, outputFile);
