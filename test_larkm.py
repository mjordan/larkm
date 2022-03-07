from fastapi.testclient import TestClient
import os

from larkm import app

client = TestClient(app)


def setup_teardown(module):
    os.remove('larkm_test.db')


def test_resolve_ark():
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
    assert response.json() == {"ark": {"shoulder": "s1", "identifier": "9876", "ark_string": "ark:/99999/s19876",
                                       "target": "https://example.com", "who": ":at", "what": ":at", "when": ":at",
                                       "where": "https://example.com", "policy": "ACME University commits to maintain ARKs that have 's1' as a shoulder for a long time."}}

    response = client.post(
        "/larkm",
        json={
            "shoulder": "x9",
            "identifier": "9876",
            "target": "https://example.com"
        },
    )
    assert response.status_code == 201
    assert response.json() == {"ark": {"shoulder": "x9", "identifier": "9876", "ark_string": "ark:/99999/x99876",
                                       "target": "https://example.com", "who": ":at", "what": ":at", "when": ":at",
                                       "where": "https://example.com", "policy": "Default committment statement."}}


def test_delete_ark():
    create_response = client.post(
        "/larkm",
        json={
            "shoulder": "x9",
            "identifier": "0000",
            "target": "https://example.com"
        },
    )
    assert create_response.status_code == 201

    delete_response = client.delete(
        "/larkm/ark:/99999/x90000"
    )
    assert delete_response.status_code == 204
