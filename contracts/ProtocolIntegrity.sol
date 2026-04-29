// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

contract ProtocolIntegrity {
    // Протоколын бүтэц
    struct record {
        string ipfsHash;
        uint256 timestamp;
        address owner;
    }

    // ID-аар нь хадгалах сан
    mapping(uint256 => record) public meetingRecords;

    // Үйл явдлыг бүртгэх (Frontend-д мэдэгдэхэд хэрэгтэй)
    event RecordStored(uint256 indexed meetingId, string ipfsHash);

    // Хадгалах функц
    function storeHash(uint256 _meetingId, string memory _ipfsHash) public {
        meetingRecords[_meetingId] = record(_ipfsHash, block.timestamp, msg.sender);
        emit RecordStored(_meetingId, _ipfsHash);
    }

    function getHash(uint256 _meetingId) public view returns (string memory) {
        return meetingRecords[_meetingId].ipfsHash;
    }
}