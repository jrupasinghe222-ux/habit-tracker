import asyncio

import httpx

from backend.main import app


def get(path: str) -> httpx.Response:
    async def request() -> httpx.Response:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            return await client.get(path)

    return asyncio.run(request())


def test_health_is_public_and_does_not_claim_database_readiness():
    response = get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["content-type"] == "application/json"


def test_unknown_api_route_is_not_reported_as_healthy():
    assert get("/api/not-a-route").status_code == 404
