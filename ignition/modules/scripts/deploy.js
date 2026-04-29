import hre from "hardhat";

async function main() {
  console.log("-----------------------------------------");
  console.log("Deploying ProtocolIntegrity contract...");

  // 1. Contract-ийг ачаалах 
  const Protocol = await hre.ethers.getContractFactory("ProtocolIntegrity");
  
  // 2. Блокчэйн рүү илгээх
  const protocol = await Protocol.deploy();
  
  // 3. Байршиж дуустал хүлээх
  await protocol.waitForDeployment();

  // 4. Хаягийг хэвлэх
  const address = await protocol.getAddress();
  
  console.log("-----------------------------------------");
  console.log("АМЖИЛТТАЙ: Smart Contract байршлаа!");
  console.log("Contract Address:", address);
  console.log("-----------------------------------------");
}

main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error("Алдаа гарлаа:", error);
    process.exit(1);
  });