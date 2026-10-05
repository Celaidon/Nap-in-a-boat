# A frontend on another host (Vercel) can read the REST API only if its origin is allowed.
from fastapi.testclient import TestClient

from src.server.main import create_app
from src.server.settings import Settings

VERCEL = "https://nap-in-a-boat.vercel.app"


def get(origin, **settings):
    with TestClient(create_app(Settings(_env_file=None, fake_generator=True, **settings))) as client:
        return client.get("/api/registry", headers={"Origin": origin})


def test_listed_origin_is_allowed():
    r = get(VERCEL, cors_origins=f"{VERCEL}, http://localhost:5173")
    assert r.headers["access-control-allow-origin"] == VERCEL


def test_other_origin_is_not_allowed():
    assert "access-control-allow-origin" not in get("https://evil.example", cors_origins=VERCEL).headers


def test_off_by_default():
    assert "access-control-allow-origin" not in get(VERCEL).headers
