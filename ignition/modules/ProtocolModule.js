import { buildModule } from "@nomicfoundation/hardhat-ignition/modules";
export default buildModule("ProtocolModule", (m) => {
  const protocol = m.contract("ProtocolIntegrity");
  return { protocol };
});