from web3 import Web3
from config import settings
import json
import logging

logger = logging.getLogger(__name__)

class ContentRegistryContract:
    def __init__(self):
        self.w3 = Web3(Web3.HTTPProvider(settings.POLYGON_RPC))
        self.contract_address = "0x0000000000000000000000000000000000000000" # Placeholders
        self.abi = [
            {
                "inputs": [
                    {"internalType": "bytes32", "name": "dnaHash", "type": "bytes32"},
                    {"internalType": "string", "name": "ipfsCid", "type": "string"},
                    {"internalType": "bytes32", "name": "merkleRoot", "type": "bytes32"}
                ],
                "name": "register",
                "outputs": [],
                "stateMutability": "nonpayable",
                "type": "function"
            }
        ]
        if self.w3.is_connected():
            self.contract = self.w3.eth.contract(address=self.contract_address, abi=self.abi)
        else:
            self.contract = None
            
    def register_asset(self, private_key: str, dna_hash_hex: str, ipfs_cid: str, merkle_root_hex: str) -> str:
        """Submits transaction to Polygon POS."""
        if not self.contract:
            logger.warning("Web3 not connected, skipping Polygon registration")
            return "0x_mock_tx_hash_" + dna_hash_hex[:8]
            
        account = self.w3.eth.account.from_key(private_key)
        
        # Build transaction
        tx = self.contract.functions.register(
            bytes.fromhex(dna_hash_hex),
            ipfs_cid,
            bytes.fromhex(merkle_root_hex)
        ).build_transaction({
            'from': account.address,
            'nonce': self.w3.eth.get_transaction_count(account.address),
            'gas': 2000000,
            'gasPrice': self.w3.to_wei('50', 'gwei')
        })
        
        signed_tx = self.w3.eth.account.sign_transaction(tx, private_key)
        tx_hash = self.w3.eth.send_raw_transaction(signed_tx.rawTransaction)
        
        return self.w3.to_hex(tx_hash)
