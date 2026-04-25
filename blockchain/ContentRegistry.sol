// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

contract ContentRegistry {
    struct ContentRecord {
        bytes32 dnaHash;     // keccak256(clip_vec || phash || owner_id)
        address owner;
        uint256 registeredAt;
        string  ipfsCid;
        bytes32 merkleRoot;
        bool    dmcaProtected;
    }

    mapping(bytes32 => ContentRecord) public records;

    event ContentRegistered(bytes32 indexed dnaHash, address indexed owner, string ipfsCid);
    event ViolationReported(bytes32 indexed dnaHash, string sourceUrl);

    function register(bytes32 dnaHash, string calldata ipfsCid, bytes32 merkleRoot) external {
        require(records[dnaHash].registeredAt == 0, "Record already exists");

        records[dnaHash] = ContentRecord({
            dnaHash: dnaHash,
            owner: msg.sender,
            registeredAt: block.timestamp,
            ipfsCid: ipfsCid,
            merkleRoot: merkleRoot,
            dmcaProtected: true
        });

        emit ContentRegistered(dnaHash, msg.sender, ipfsCid);
    }
}
