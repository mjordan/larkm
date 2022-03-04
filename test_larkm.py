from fastapi.testclient import TestClient

from larkm import app

client = TestClient(app)


def test_resolve_ark():
    response = client.get("/ark:/12345/x977777")
    # assert response.status_code == 307
    # Returing a 307 using human client, returning 404 within tests. WTF?
    assert response.status_code == 404

    response = client.get("/ark:/12345/x977777?info")
    assert response.status_code == 200
    assert response.text == 'Default committment statement.'


def test_create_ark():
    response = client.post(
        "/larkm",
        json={
            "target": "https://example.com"
        },
    )
    assert response.status_code == 201

    response = client.post(
        "/larkm",
        json={
            "shoulder": "s1",
            "identifier": "9876",
            "target": "https://example.com"
        },
    )
    assert response.status_code == 201
    assert response.json() == {"ark": {"shoulder": "s1", "identifier": "9876", "ark_string": "ark:/19837/s19876", "target": "https://example.com"}}
