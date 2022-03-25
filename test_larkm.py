from fastapi.testclient import TestClient
from larkm import app
import shutil
import os
import re

client = TestClient(app)


def teardown_module(module):
    shutil.copyfile('testdb/larkmtest.db.bak', 'testdb/larkmtest.db')


def test_resolve_ark():
    response = client.get("/ark:/12345/x977777?info")
    assert response.status_code == 200
    response_text = "erc:\nwho: :at\nwhat: :at\nwhen: :at\n"
    response_text = response_text + "where: https://example.com/foo\npolicy: Default committment statement.\n\n"
    assert response.text == response_text


def test_create_ark():
    # Check the HTTP response code.
    response = client.post(
        "/larkm",
        json={
            "target": "https://example.com"
        },
    )
    assert response.status_code == 201

    # Test if the generated identifier is a UUID v4.
    response = client.post(
        "/larkm",
        json={
            "target": "https://example.com/test"
        },
    )
    body = response.json()
    assert re.match('^[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89aAbB][a-f0-9]{3}-[a-f0-9]{12}$', body['ark']['identifier'])

    # Provide a shoulder and identifier.
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

    # Provide a shoulder that is mapped to the default policy statement.
    response = client.post(
        "/larkm",
        json={
            "shoulder": "x9",
            "identifier": "9876",
            "target": "https://example.com/bar",
            "what": "A new ARK"
        },
    )
    assert response.status_code == 201
    assert response.json() == {"ark": {"shoulder": "x9", "identifier": "9876", "ark_string": "ark:/99999/x99876",
                                       "target": "https://example.com/bar", "who": ":at", "what": "A new ARK", "when": ":at",
                                       "where": "https://example.com/bar", "policy": "Default committment statement."}}

    # Get the 'info' for this ARK.
    response = client.get("/ark:/99999/x99876?info")
    assert response.status_code == 200
    response_text = "erc:\nwho: :at\nwhat: A new ARK\nwhen: :at\n"
    response_text = response_text + "where: https://example.com/bar\npolicy: Default committment statement.\n\n"
    assert response.text == response_text

    # ARK with some special characters in its metadata.
    response = client.post(
        "/larkm",
        json={
            "shoulder": "x9",
            "identifier": "0000000000",
            "target": "https://example.com/bar",
            "what": "A test ARK with some 'special' characters (`%&) in its metadata"
        },
    )
    assert response.status_code == 201
    assert response.json() == {"ark": {"shoulder": "x9", "identifier": "0000000000", "ark_string": "ark:/99999/x90000000000",
                                       "target": "https://example.com/bar", "who": ":at", "when": ":at",
                                       "what": "A test ARK with some 'special' characters (`%&) in its metadata",
                                       "where": "https://example.com/bar", "policy": "Default committment statement."}}


def test_update_ark():
    # Only provide the required body fields, see if larkm provides the correct default values for other fields.
    response = client.post(
        "/larkm",
        json={
            "shoulder": "s2",
            "identifier": "55555",
            "target": "https://example.com"

        },
    )
    assert response.status_code == 201
    assert response.json() == {"ark": {"shoulder": "s2", "identifier": "55555", "ark_string": "ark:/99999/s255555",
                                       "target": "https://example.com", "who": ":at", "what": ":at", "when": ":at",
                                       "where": "https://example.com", "policy": "Default committment statement."}}

    # Then update the when and what body fields.
    response = client.put(
        "/larkm/ark:/99999/s255555",
        json={
            "when": "2020",
            "what": "A test",
            "ark_string": "ark:/99999/s255555"
        },
    )
    assert response.status_code == 200
    assert response.json() == {"ark": {"shoulder": "s2", "identifier": "55555", "ark_string": "ark:/99999/s255555",
                                       "target": "https://example.com", "who": ":at", "what": "A test", "when": "2020",
                                       "where": "https://example.com", "policy": "Default committment statement."}}

    # Update the policy body field.
    response = client.post(
        "/larkm",
        json={
            "shoulder": "s2",
            "identifier": "987654",
            "what": "New ARK with its own policy",
            "target": "https://example.com"
        },
    )

    response = client.put(
        "/larkm/ark:/99999/s2987654",
        json={
            "policy": "A test policy.",
            "ark_string": "ark:/99999/s2987654"
        },
    )
    assert response.status_code == 200
    assert response.json() == {"ark": {"shoulder": "s2", "identifier": "987654", "ark_string": "ark:/99999/s2987654",
                                       "target": "https://example.com", "who": ":at", "what": "New ARK with its own policy",
                                       "when": ":at", "where": "https://example.com", "policy": "A test policy."}}

    # Intentionally trigger a 409 by mismatching the URL parameters and the ark_string body field.
    response = client.post(
        "/larkm",
        json={
            "shoulder": "s2",
            "identifier": "111111",
            "target": "https://foo.example.com"
        },
    )

    response = client.put(
        "/larkm/ark:/99999/s2111111",
        json={
            "ark_string": "ark:/99999/s2111111xxx"
        },
    )
    assert response.status_code == 409


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
