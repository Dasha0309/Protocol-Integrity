// Deploys ProtocolIntegrity to the running local Hardhat node.
// Usage: npx hardhat run scripts/deploy.js --network localhost
const hre = require("hardhat");

async function main() {
  const [deployer] = await hre.ethers.getSigners();
  console.log("Deploying with account:", deployer.address);

  const Factory = await hre.ethers.getContractFactory("ProtocolIntegrity");
  const contract = await Factory.deploy();
  await contract.waitForDeployment();

  const addr = await contract.getAddress();
  console.log("");
  console.log("ProtocolIntegrity deployed to:", addr);
  console.log("");
  console.log("Update ~/.protocol_integrity/env.json:");
  console.log(`  "contract_address": "${addr}"`);
  console.log(`  "account_address":  "${deployer.address}"`);
}

main().catch((err) => {
  console.error(err);
  process.exitCode = 1;
});
