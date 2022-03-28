from fastapi.testclient import TestClient
from larkm import app
import shutil
import os
import re

client = TestClient(app)


def teardown_module(module):
    shutil.copyfile('testdb/larkmtest.db.bak', 'testdb/larkmtest.db')


def test_resolve_ark():
    response = client.get("/ark:/12345/x9062cdde7-f9d6-48bb-be17-bd3b9f441ec4?info")
    assert response.status_code == 200
    response_text = "erc:\nwho: :at\nwhat: :at\nwhen: :at\n"
    response_text = response_text + "where: https://example.com/foo\npolicy: Default committment statement.\n\n"
    assert response.text == response_text

    # Resolve same ARK but with random hypens in UUID.
    response = client.get("/ark:/12345/x9062-cdde7f9d64-8bbbe17-bd3b9f441ec4?info")
    assert response.status_code == 200
    response_text = "erc:\nwho: :at\nwhat: :at\nwhen: :at\n"
    response_text = response_text + "where: https://example.com/foo\npolicy: Default committment statement.\n\n"
    assert response.text == response_text

    # Resolve same ARK but with different random hypens in UUID.
    response = client.get("/ark:/12345/x9--062cdde7f9d648bbbe17bd3b9f441ec4-?info")
    assert response.status_code == 200
    response_text = "erc:\nwho: :at\nwhat: :at\nwhen: :at\n"
    response_text = response_text + "where: https://example.com/foo\npolicy: Default committment statement.\n\n"
    assert response.text == response_text

    # Resolve same ARK but with no hypens in UUID.
    response = client.get("/ark:/12345/x9062cdde7f9d648bbbe17bd3b9f441ec4?info")
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
            "identifier": "14b7f127-b358-4994-8888-5b7392f588d7",
            "target": "https://example.com"
        },
    )
    assert response.status_code == 201
    assert response.json() == {"ark": {"shoulder": "s1", "identifier": "14b7f127-b358-4994-8888-5b7392f588d7",
                                       "ark_string": "ark:/99999/s114b7f127-b358-4994-8888-5b7392f588d7",
                                       "target": "https://example.com", "who": ":at", "what": ":at", "when": ":at",
                                       "where": "https://example.com", "policy": "ACME University commits to maintain ARKs that have 's1' as a shoulder for a long time."}}

    # Provide a shoulder that is mapped to the default policy statement.
    response = client.post(
        "/larkm",
        json={
            "shoulder": "x9",
            "identifier": "20578b9e-ba6e-494b-b35d-1419e06f9ced",
            "target": "https://example.com/bar",
            "what": "A new ARK"
        },
    )
    assert response.status_code == 201
    assert response.json() == {"ark": {"shoulder": "x9", "identifier": "20578b9e-ba6e-494b-b35d-1419e06f9ced",
                                       "ark_string": "ark:/99999/x920578b9e-ba6e-494b-b35d-1419e06f9ced",
                                       "target": "https://example.com/bar", "who": ":at", "what": "A new ARK", "when": ":at",
                                       "where": "https://example.com/bar", "policy": "Default committment statement."}}

    # Get the 'info' for this ARK.
    response = client.get("/ark:/99999/x920578b9e-ba6e-494b-b35d-1419e06f9ced?info")
    assert response.status_code == 200
    response_text = "erc:\nwho: :at\nwhat: A new ARK\nwhen: :at\n"
    response_text = response_text + "where: https://example.com/bar\npolicy: Default committment statement.\n\n"
    assert response.text == response_text

    # ARK with some special characters in its metadata.
    response = client.post(
        "/larkm",
        json={
            "shoulder": "x9",
            "identifier": "47321e02-7df6-4dfc-aad2-bdb75ab6b92b",
            "target": "https://example.com/bar",
            "what": "A test ARK with some 'special' characters (`%&) in its metadata"
        },
    )
    assert response.status_code == 201
    assert response.json() == {"ark": {"shoulder": "x9", "identifier": "47321e02-7df6-4dfc-aad2-bdb75ab6b92b",
                                       "ark_string": "ark:/99999/x947321e02-7df6-4dfc-aad2-bdb75ab6b92b",
                                       "target": "https://example.com/bar", "who": ":at", "when": ":at",
                                       "what": "A test ARK with some 'special' characters (`%&) in its metadata",
                                       "where": "https://example.com/bar", "policy": "Default committment statement."}}

    # Create an ARK with a bad UUID.
    response = client.post(
        "/larkm",
        json={
            "shoulder": "s2",
            "identifier": "cda60df9-b468-4520-8e97-fc12deb5e324x",
            "target": "https://example.com"

        },
    )
    assert response.status_code == 422
    assert response.text == '{"detail":"Provided UUID is invalid."}'


def test_update_ark():
    # Only provide the required body fields, see if larkm provides the correct default values for other fields.
    response = client.post(
        "/larkm",
        json={
            "shoulder": "s2",
            "identifier": "cda60df9-b468-4520-8e97-fc12deb5e324",
            "target": "https://example.com"

        },
    )
    assert response.status_code == 201
    assert response.json() == {"ark": {"shoulder": "s2", "identifier": "cda60df9-b468-4520-8e97-fc12deb5e324",
                                       "ark_string": "ark:/99999/s2cda60df9-b468-4520-8e97-fc12deb5e324",
                                       "target": "https://example.com", "who": ":at", "what": ":at", "when": ":at",
                                       "where": "https://example.com", "policy": "Default committment statement."}}

    # Then update the when and what body fields.
    response = client.put(
        "/larkm/ark:/99999/s2cda60df9-b468-4520-8e97-fc12deb5e324",
        json={
            "when": "2020",
            "what": "A test",
            "ark_string": "ark:/99999/s2cda60df9-b468-4520-8e97-fc12deb5e324"
        },
    )
    assert response.status_code == 200
    assert response.json() == {"ark": {"shoulder": "s2", "identifier": "cda60df9-b468-4520-8e97-fc12deb5e324",
                                       "ark_string": "ark:/99999/s2cda60df9-b468-4520-8e97-fc12deb5e324",
                                       "target": "https://example.com", "who": ":at", "what": "A test", "when": "2020",
                                       "where": "https://example.com", "policy": "Default committment statement."}}

    # Update the policy body field.
    response = client.post(
        "/larkm",
        json={
            "shoulder": "s2",
            "identifier": "aaed59b0-6ad6-4b69-8511-bcf781e386a0",
            "what": "New ARK with its own policy",
            "target": "https://example.com"
        },
    )

    response = client.put(
        "/larkm/ark:/99999/s2aaed59b0-6ad6-4b69-8511-bcf781e386a0",
        json={
            "policy": "A test policy.",
            "ark_string": "ark:/99999/s2aaed59b0-6ad6-4b69-8511-bcf781e386a0"
        },
    )
    assert response.status_code == 200
    assert response.json() == {"ark": {"shoulder": "s2", "identifier": "aaed59b0-6ad6-4b69-8511-bcf781e386a0",
                                       "ark_string": "ark:/99999/s2aaed59b0-6ad6-4b69-8511-bcf781e386a0",
                                       "target": "https://example.com", "who": ":at", "what": "New ARK with its own policy",
                                       "when": ":at", "where": "https://example.com", "policy": "A test policy."}}

    # Intentionally trigger a 409 by mismatching the URL parameters and the ark_string body field.
    response = client.post(
        "/larkm",
        json={
            "shoulder": "s2",
            "identifier": "3a8a9396-baa8-46be-ba22-b08b0de2db5b",
            "target": "https://foo.example.com"
        },
    )

    response = client.put(
        "/larkm/ark:/99999/s23a8a9396-baa8-46be-ba22-b08b0de2db5b",
        json={
            "ark_string": "ark:/99999/s23a8a9396-baa8-46be-ba22-b08b0de2db5bxxx"
        },
    )
    assert response.status_code == 409


def test_delete_ark():
    create_response = client.post(
        "/larkm",
        json={
            "shoulder": "x9",
            "identifier": "20578b9e-ba6e-494b-b35d-1419e06f9ced",
            "target": "https://example.com"
        },
    )
    assert create_response.status_code == 201

    delete_response = client.delete(
        "/larkm/ark:/99999/x920578b9e-ba6e-494b-b35d-1419e06f9ced"
    )
    assert delete_response.status_code == 204
