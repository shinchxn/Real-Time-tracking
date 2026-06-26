"""
Blockchain Routes — Content DNA Apex
Asset registration on Polygon + ZK proof generation
"""
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

router = APIRouter()


@router.post("/blockchain/register/{asset_id}")
async def blockchain_register(asset_id: str, request: Request):
    """Anchor an asset's DNA hash to the Polygon blockchain."""
    try:
        faiss_index = request.app.state.faiss_index
        # Find asset dna hash from metadata
        dna_hash = ""
        for idx, meta in faiss_index.metadata.items():
            if meta.get("asset_id") == asset_id:
                dna_hash = meta.get("dna_hash", "")
                break
        if not dna_hash:
            return JSONResponse({"status": "not_found", "asset_id": asset_id}, status_code=404)

        from blockchain.registry import ContentRegistryContract
        registry = ContentRegistryContract()
        tx = registry.register_asset(
            private_key=__import__("os").getenv("BLOCKCHAIN_PRIVATE_KEY", ""),
            dna_hash_hex=dna_hash,
            ipfs_cid="",
            merkle_root_hex=""
        )
        return JSONResponse({"status": "anchored", "asset_id": asset_id,
                              "tx_hash": tx, "chain": "Polygon"})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/blockchain/verify/{asset_id}")
async def blockchain_verify(asset_id: str):
    """Verify asset existence on blockchain (mock for prototype)."""
    return JSONResponse({
        "asset_id": asset_id,
        "verified": True,
        "chain": "Polygon",
        "note": "Connect CONTRACT_ADDRESS env var for live verification"
    })


@router.post("/proof/generate/{asset_id}")
async def proof_generate(asset_id: str):
    """Generate a ZK proof for asset ownership."""
    try:
        from blockchain.zk_proofs import generate_ownership_proof
        proof = generate_ownership_proof(asset_id)
        return JSONResponse({"asset_id": asset_id, "proof": proof})
    except Exception as e:
        return JSONResponse({"asset_id": asset_id,
                             "proof": f"zk_proof_mock_{asset_id[:8]}",
                             "note": str(e)})
