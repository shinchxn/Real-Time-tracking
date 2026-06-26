"""
Content Registry Contract — Content DNA Apex v7.1
FIX 23: Full implementation using web3.py + Fernet-encrypted private key from vault.
Matches call signature in background_tasks.py anchor_to_blockchain:
    registry = ContentRegistryContract()
    tx_hash = registry.register_asset(
        private_key=private_key,
        dna_hash_hex=asset["dna_hash"],
        ipfs_cid=asset.get("ipfs_cid", ""),
        merkle_root_hex=asset.get("merkle_root", "")
    )
"""
import json
import logging
import os

logger = logging.getLogger(__name__)

# ── ABI path ──────────────────────────────────────────────────────────────────
_ABI_PATH = os.path.join(os.path.dirname(__file__), "abi", "ContentRegistry.json")
_FALLBACK_ABI = [
    {
        "inputs": [
            {"internalType": "bytes", "name": "dnaHash", "type": "bytes"},
            {"internalType": "string", "name": "ipfsCid", "type": "string"},
            {"internalType": "bytes", "name": "merkleRoot", "type": "bytes"}
        ],
        "name": "registerAsset",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    }
]


def _load_abi() -> list:
    if os.path.exists(_ABI_PATH):
        with open(_ABI_PATH) as f:
            return json.load(f)
    logger.warning("[registry] ABI file not found at %s — using fallback ABI", _ABI_PATH)
    return _FALLBACK_ABI


class ContentRegistryContract:
    """
    Wraps the on-chain ContentRegistry smart contract.
    Connects via Web3 HTTP provider (configured in settings).
    Falls back gracefully when not connected (returns mock hash).
    """

    def __init__(self):
        from config import settings
        try:
            from web3 import Web3
            self.w3 = Web3(Web3.HTTPProvider(settings.WEB3_RPC_URL))
            abi = _load_abi()
            if settings.CONTRACT_ADDRESS and settings.CONTRACT_ADDRESS != "":
                self.contract = self.w3.eth.contract(
                    address=Web3.to_checksum_address(settings.CONTRACT_ADDRESS),
                    abi=abi
                )
            else:
                logger.warning("[registry] CONTRACT_ADDRESS not set — blockchain txns will be skipped")
                self.contract = None
            self._web3_ok = self.w3.is_connected()
        except Exception as e:
            logger.warning("[registry] Web3 init failed: %s", e)
            self.w3 = None
            self.contract = None
            self._web3_ok = False

    def register_asset(
        self,
        private_key: str,
        dna_hash_hex: str,
        ipfs_cid: str,
        merkle_root_hex: str
    ) -> str:
        """
        Submit registerAsset transaction to the blockchain.

        Args:
            private_key: Decrypted hex private key (0x-prefixed or plain hex)
            dna_hash_hex: Asset DNA hash as hex string
            ipfs_cid: IPFS content identifier string
            merkle_root_hex: Merkle root as hex string

        Returns:
            Transaction hash as hex string
        """
        if not self._web3_ok or not self.contract:
            mock_hash = f"0x_mock_{dna_hash_hex[:8] if dna_hash_hex else 'nohash'}"
            logger.warning("[registry] Web3 not connected — returning mock tx hash: %s", mock_hash)
            return mock_hash

        from config import settings
        try:
            from web3 import Web3
            account = self.w3.eth.account.from_key(private_key)
            nonce = self.w3.eth.get_transaction_count(account.address)

            # Encode hash fields — pad/trim to valid bytes
            def _to_bytes(hex_str: str) -> bytes:
                hex_str = hex_str.strip()
                if hex_str.startswith("0x"):
                    hex_str = hex_str[2:]
                # Ensure even-length hex
                if len(hex_str) % 2 != 0:
                    hex_str = "0" + hex_str
                return bytes.fromhex(hex_str) if hex_str else b""

            dna_bytes = _to_bytes(dna_hash_hex)
            merkle_bytes = _to_bytes(merkle_root_hex)

            tx = self.contract.functions.registerAsset(
                dna_bytes,
                ipfs_cid or "",
                merkle_bytes
            ).build_transaction({
                "chainId": settings.CHAIN_ID,
                "gas": 200000,
                "gasPrice": self.w3.eth.gas_price,
                "nonce": nonce,
                "from": account.address
            })

            signed = self.w3.eth.account.sign_transaction(tx, private_key)
            tx_hash = self.w3.eth.send_raw_transaction(signed.raw_transaction)
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
            return receipt.transactionHash.hex()

        except Exception as e:
            logger.error("[registry] Transaction failed: %s", e)
            raise
