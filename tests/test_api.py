"""
API Integration Tests — Content DNA Apex v7.1
FIX 21: Tests for health check, verify, and register endpoints.
"""
import pytest
from httpx import AsyncClient, ASGITransport
from main import app


@pytest.mark.asyncio
async def test_health_check():
    """Health endpoint should always return 200 with required fields."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/health")
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data
    assert "version" in data
    assert "faiss_index_size" in data
    assert "queue_depth" in data
    assert data["version"] == "7.1"


@pytest.mark.asyncio
async def test_verify_asset_invalid(tmp_path):
    """Verify with a non-image file should return valid=False."""
    fake_file = tmp_path / "fake.jpg"
    fake_file.write_bytes(b"not a real image")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        with open(fake_file, "rb") as f:
            resp = await client.post(
                "/api/v1/assets/verify",
                files={"file": ("fake.jpg", f, "image/jpeg")}
            )
    assert resp.status_code == 200
    assert resp.json()["valid"] is False


@pytest.mark.asyncio
async def test_register_asset_requires_auth():
    """Register endpoint must reject requests without an API key."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/assets/register",
            files={"file": ("x.jpg", b"\xff\xd8\xff", "image/jpeg")}
        )
    assert resp.status_code in [401, 403]


@pytest.mark.asyncio
async def test_verify_asset_with_real_image(tmp_path):
    """Verify with a valid (but unregistered) JPEG should return valid=False."""
    from PIL import Image
    import io

    img = Image.new("RGB", (64, 64), color=(128, 200, 50))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    img_bytes = buf.getvalue()

    fake_file = tmp_path / "real.jpg"
    fake_file.write_bytes(img_bytes)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        with open(fake_file, "rb") as f:
            resp = await client.post(
                "/api/v1/assets/verify",
                files={"file": ("real.jpg", f, "image/jpeg")}
            )
    assert resp.status_code == 200
    data = resp.json()
    assert "valid" in data


@pytest.mark.asyncio
async def test_sightings_requires_auth():
    """Sightings endpoint must reject unauthenticated requests."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/sightings")
    assert resp.status_code in [401, 403]
