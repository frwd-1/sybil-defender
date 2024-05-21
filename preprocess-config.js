const fs = require('fs');

const configPath = './forta.config.json';
const rawConfig = fs.readFileSync(configPath, 'utf8');
const processedConfig = rawConfig
  .replace('${JSON_RPC_URL}', process.env.JSON_RPC_URL)
  .replace('${NETWORK_NAME}', process.env.NETWORK_NAME);

fs.writeFileSync(configPath, processedConfig);
