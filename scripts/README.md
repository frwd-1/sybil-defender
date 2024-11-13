# GraphQL Label Query Script

This script queries the Sybil Defender GraphQL API to retrieve onchain addresses labeled for specific activities (e.g., "Wash Trading") and writes the results to a CSV file. It pulls data at set intervals, filters results based on configurable typologies, and avoids duplicate entries by tracking previously seen addresses across fetches.

## Getting Started

### Prerequisites

- Node.js and npm installed on your machine.
- An `.env` file in the project directory containing your `GRAPHQL_KEY` API token to access the GraphQL API.

### Setup

1. Clone this repository and navigate to the project directory.
2. Run `npm install` to install dependencies.
3. Create a `.env` file in the project root directory with the following content:
   ```plaintext
   GRAPHQL_KEY=your_api_key_here
   ```
4. Adjust the GraphQL query in `interactionQuery.graphql` as needed.

## Usage

To start the script, run:

```bash
node your_script_name.js
```

### Features

- **Automated Fetching**: By default, the script runs an initial data fetch immediately and then repeats every 60 seconds.
- **Duplicate Prevention**: The script tracks previously fetched wallets, preventing duplicates in subsequent runs.
- **Configurable Filters**: The script allows you to filter wallets based on specific typologies (e.g., "Wash Trading") for targeted data collection.

## Configuration Options

### 1. Adjusting the Data Ranges

To change the date range of data pulled, modify the `afterCreatedAtDate` and `beforeCreatedAtDate` parameters in the `variables` object within the `fetchAndWriteEntitiesToCSV` function. These parameters filter data based on the creation date of labels.

**Example:**

```javascript
let variables = {
  input: {
    sourceIds: [
      "0x349f4fc9abbd76fdcdb9b0a73b0ef1c3d53935d7ad41a3cf8b8bd32fcf514113",
    ],
    afterCreatedAtDate: "2024-10-01", // Start date
    beforeCreatedAtDate: "2024-10-31", // End date
    chainIds: [137], // Chain IDs (e.g., Polygon)
  },
};
```

### 2. Adjusting the Frequency of Data Fetching

To adjust the frequency with which data is fetched, change the interval duration in the `setInterval` function at the end of the script. The interval is currently set to 60 seconds (60000 milliseconds).

**Example:**

To set the fetch interval to 5 minutes:

```javascript
setInterval(() => {
  console.log("Starting a new data fetch cycle...");
  fetchAndWriteEntitiesToCSV(outputFile);
}, 300000); // 300,000 milliseconds = 5 minutes
```

### 3. Configuring Typologies to Search For

The script is currently configured to pull wallets with the single typology `"Wash Trading"`. To adjust this filter or include multiple typologies (e.g., "Asset Farming" and "ML: Flow Through"), update the filtering logic in the `fetchAndWriteEntitiesToCSV` function.

#### **To Include Multiple Typologies**

Modify the `if` condition that checks the typology in the following section of the code:

**Single Typology Example:**

```javascript
if (typologies.length === 1 && typologies[0] === 'Wash Trading') {
```

**Multiple Typologies Example:**

```javascript
const allowedTypologies = ['Wash Trading', 'Asset Farming', 'ML: Flow Through'];
if (typologies.every(t => allowedTypologies.includes(t))) {
```

The `allowedTypologies` array defines the typologies you want to fetch. The condition above checks that all the typologies associated with a wallet are in the `allowedTypologies` list.

### Additional Configuration Options

- **Adjusting the Output File Name**: Change the `outputFile` variable to specify a different CSV file name or path.

  ```javascript
  const outputFile = path.join(__dirname, "YourOutputFileName.csv");
  ```

- **Logging Level**: The script logs high-level activity to the console. To reduce verbosity, you can remove or comment out certain `console.log` statements.

## Example Usage

```plaintext
node script.js
```

Upon starting, the script will immediately begin fetching data, writing new entries to `TrialRun.csv` and repeating every 60 seconds. It will only log unique, filtered addresses based on the specified typology criteria.

## Typology Descriptions

The script filters addresses based on various typologies, which are labels assigned to addresses exhibiting specific patterns of on-chain behavior. Below are descriptions of the currently available typologies:

Wash Trading:
Wash Trading labels are assigned to addresses that engage in transactions designed to create the illusion of high trading activity, typically with the aim of artificially inflating the price or perceived demand of an asset. This practice can mislead other participants in the market by simulating liquidity or interest in the asset without genuine market-driven exchange activity.

Asset Farming:
Asset Farming labels are applied to addresses that demonstrate high-frequency interactions with a project or protocol, where the primary motivation is to accumulate eligibility for potential airdrops or token rewards. These interactions are often repetitive and transactional, lacking substantive engagement with the project aside from the intent to maximize personal gains through farming tactics.

ML: Flow Through:
ML: Flow Through labels are used for clusters of addresses that appear to intentionally obscure the origin or destination of funds. Such activity is often structured to make on-chain financial flows difficult to trace, possibly with the objective of hiding connections to specific accounts or transactions. This label is frequently applied to Sybil clusters that use complex transfer patterns to mask their activities.
