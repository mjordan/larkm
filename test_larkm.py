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
    assert response.text == "erc:\nwho: :at\nwhat: :at\nwhen: :at\nwhere: https://example.com/foo\npolicy: Default committment statement.\n\n"

    # Resolve same ARK but with random hypens in UUID.
    response = client.get("/ark:/12345/x9062-cdde7f9d64-8bbbe17-bd3b9f441ec4?info")
    assert response.status_code == 200
    assert response.text == "erc:\nwho: :at\nwhat: :at\nwhen: :at\nwhere: https://example.com/foo\npolicy: Default committment statement.\n\n"

    # Resolve same ARK but with different random hypens in UUID.
    response = client.get("/ark:/12345/x9--062cdde7f9d648bbbe17bd3b9f441ec4-?info")
    assert response.status_code == 200
    assert response.text == "erc:\nwho: :at\nwhat: :at\nwhen: :at\nwhere: https://example.com/foo\npolicy: Default committment statement.\n\n"

    # Resolve same ARK but with no hypens in UUID.
    response = client.get("/ark:/12345/x9062cdde7f9d648bbbe17bd3b9f441ec4?info")
    assert response.status_code == 200
    assert response.text == "erc:\nwho: :at\nwhat: :at\nwhen: :at\nwhere: https://example.com/foo\npolicy: Default committment statement.\n\n"


def test_create_ark():
    # Check the HTTP response code.
    response = client.post(
        "/larkm",
        json={
            "target": "https://example.com/ppppp"
        },
    )
    assert response.status_code == 201

    # Test if the generated identifier is a UUID v4.
    response = client.post(
        "/larkm",
        json={
            "target": "https://example.com/sssss"
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
            "target": "https://example.com/wwwww"
        },
    )
    assert response.status_code == 201
    assert response.json() == {"ark": {"shoulder": "s1", "identifier": "14b7f127-b358-4994-8888-5b7392f588d7",
                                       "ark_string": "ark:/99999/s114b7f127-b358-4994-8888-5b7392f588d7",
                                       "target": "https://example.com/wwwww", "who": ":at", "what": ":at", "when": ":at",
                                       "where": "https://example.com/wwwww",
                                       "policy": "ACME University commits to maintain ARKs that have 's1' as a shoulder for a long time."},
                                       "urls": {"local": "https://resolver.myorg.net/ark:/99999/s114b7f127-b358-4994-8888-5b7392f588d7",
                                       "global": "https://n2t.net/ark:/99999/s114b7f127-b358-4994-8888-5b7392f588d7"}}

    # Provide a shoulder that is mapped to the default policy statement.
    response = client.post(
        "/larkm",
        json={
            "shoulder": "x9",
            "identifier": "20578b9e-ba6e-494b-b35d-1419e06f9ced",
            "target": "https://example.com/kkkkk",
            "what": "A new ARK"
        },
    )
    assert response.status_code == 201
    assert response.json() == {"ark": {"shoulder": "x9", "identifier": "20578b9e-ba6e-494b-b35d-1419e06f9ced",
                                       "ark_string": "ark:/99999/x920578b9e-ba6e-494b-b35d-1419e06f9ced",
                                       "target": "https://example.com/kkkkk", "who": ":at", "what": "A new ARK", "when": ":at",
                                       "where": "https://example.com/kkkkk", "policy": "Default committment statement."},
                                       "urls": {"local": "https://resolver.myorg.net/ark:/99999/x920578b9e-ba6e-494b-b35d-1419e06f9ced",
                                       "global": "https://n2t.net/ark:/99999/x920578b9e-ba6e-494b-b35d-1419e06f9ced"}}

    # Get the 'info' for this ARK.
    response = client.get("/ark:/99999/x920578b9e-ba6e-494b-b35d-1419e06f9ced?info")
    assert response.status_code == 200
    response_text = "erc:\nwho: :at\nwhat: A new ARK\nwhen: :at\n"
    response_text = response_text + "where: https://example.com/kkkkk\npolicy: Default committment statement.\n\n"
    assert response.text == response_text

    # ARK with some special characters in its metadata.
    response = client.post(
        "/larkm",
        json={
            "shoulder": "x9",
            "identifier": "47321e02-7df6-4dfc-aad2-bdb75ab6b92b",
            "target": "https://example.com/fffff",
            "what": "A test ARK with some 'special' characters (`%&) in its metadata"
        },
    )
    assert response.status_code == 201
    assert response.json() == {"ark": {"shoulder": "x9", "identifier": "47321e02-7df6-4dfc-aad2-bdb75ab6b92b",
                                       "ark_string": "ark:/99999/x947321e02-7df6-4dfc-aad2-bdb75ab6b92b",
                                       "target": "https://example.com/fffff", "who": ":at", "when": ":at",
                                       "what": "A test ARK with some 'special' characters (`%&) in its metadata",
                                       "where": "https://example.com/fffff", "policy": "Default committment statement."},
                                       "urls": {"local": "https://resolver.myorg.net/ark:/99999/x947321e02-7df6-4dfc-aad2-bdb75ab6b92b",
                                       "global": "https://n2t.net/ark:/99999/x947321e02-7df6-4dfc-aad2-bdb75ab6b92b"}}

    # Create an ARK with a bad UUID.
    response = client.post(
        "/larkm",
        json={
            "shoulder": "s2",
            "identifier": "cda60df9-b468-4520-8e97-fc12deb5e324x",
            "target": "https://example.com/ddddd"

        },
    )
    assert response.status_code == 422
    assert response.text == '{"detail":"Provided UUID is invalid."}'

    # Create an ARK that uses a UUID already in the database.
    response = client.post(
        "/larkm",
        json={
            "shoulder": "s1",
            "identifier": "2d24d07f-ed23-4613-a7a3-0c46155c191f",
            "target": "https://example.com/ggggg"
        },
    )
    assert response.status_code == 201

    response = client.post(
        "/larkm",
        json={
            "shoulder": "s1",
            "identifier": "2d24d07f-ed23-4613-a7a3-0c46155c191f",
            "target": "https://example.com/hhhhh"
        },
    )
    assert response.status_code == 409

    # Create an ARK that uses a target already in the database.
    response = client.post(
        "/larkm",
        json={
            "shoulder": "s1",
            "identifier": "3dd364bd-ea7a-43d3-a6be-e7b52242c2c6",
            "target": "https://example.com/ggggg"
        },
    )
    assert response.status_code == 409


def test_search_arks():
    # Do a search that returns no ARKs.
    response = client.get("/larkm/search?q=policy%3Axxxxxxxx")
    assert response.status_code == 200
    assert response.json() == {"num_results":0,"page":1,"page_size":20,"arks":[]}

    # Do a search using page size and page number parameters.
    response = client.get("/larkm/search?q=policy%3Apolicy&page_size=2&page=2")
    assert response.status_code == 200
    assert response.json() == {"num_results":7,"page":"2","page_size":"2",
                               "arks":[{"date_created":"2022-06-23 03:00:45","date_modified":"2022-06-23 03:00:45",
                               "shoulder":"s1","identifier":"a0925880-1268-4059-980b-155f9d2ff02a",
                               "ark_string":"ark:/99999/s1a0925880-1268-4059-980b-155f9d2ff02a",
                               "target":"http://example.com/17","erc_who":"Avery Meyer",
                               "erc_what":"5 Things That Happen When You Are in SPACE",
                               "erc_when":":at","erc_where":"http://example.com/17",
                               "policy":"I am fundamentally against your policy."},
                               {"date_created":"2022-06-23 03:00:45","date_modified":"2022-06-23 03:00:45",
                               "shoulder":"s1","identifier":"a09d74a2-3e06-4d5a-9282-fc82c43a984a",
                               "ark_string":"ark:/99999/s1a09d74a2-3e06-4d5a-9282-fc82c43a984a",
                               "target":"http://example.com/20","erc_who":"Arden Mclean",
                               "erc_what":"What Everyone Ought to Know about GUM","erc_when":":at",
                               "erc_where":"http://example.com/20","policy":"No policy on this."}]}

    # Do a search with an invalid date in a range.
    response = client.get("/larkm/search?q=date_created%3A%5B2022-02-20%20TO%202022-02-29%5D")
    assert response.status_code == 422
    assert response.json() == {"detail":"2022-02-29 in date_created is not not a valid date."}


def test_update_ark():
    # Only provide the required body fields, see if larkm provides the correct default values for other fields.
    response = client.post(
        "/larkm",
        json={
            "shoulder": "s2",
            "identifier": "cda60df9-b468-4520-8e97-fc12deb5e324",
            "target": "https://example.com/nnnnn"

        },
    )
    assert response.status_code == 201
    assert response.json() == {"ark": {"shoulder": "s2", "identifier": "cda60df9-b468-4520-8e97-fc12deb5e324",
                                       "ark_string": "ark:/99999/s2cda60df9-b468-4520-8e97-fc12deb5e324",
                                       "target": "https://example.com/nnnnn", "who": ":at", "what": ":at", "when": ":at",
                                       "where": "https://example.com/nnnnn", "policy": "Default committment statement."},
                                       "urls": {"local": "https://resolver.myorg.net/ark:/99999/s2cda60df9-b468-4520-8e97-fc12deb5e324",
                                       "global": "https://n2t.net/ark:/99999/s2cda60df9-b468-4520-8e97-fc12deb5e324"}}

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
                                       "target": "https://example.com/nnnnn", "who": ":at", "what": "A test", "when": "2020",
                                       "where": "https://example.com/nnnnn", "policy": "Default committment statement."},
                                       "urls": {"local": "https://resolver.myorg.net/ark:/99999/s2cda60df9-b468-4520-8e97-fc12deb5e324",
                                       "global": "https://n2t.net/ark:/99999/s2cda60df9-b468-4520-8e97-fc12deb5e324"}}

    # Update the policy body field.
    response = client.post(
        "/larkm",
        json={
            "shoulder": "s2",
            "identifier": "aaed59b0-6ad6-4b69-8511-bcf781e386a0",
            "what": "New ARK with its own policy",
            "target": "https://example.com/jjjjj"
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
                                       "target": "https://example.com/jjjjj", "who": ":at", "what": "New ARK with its own policy",
                                       "when": ":at", "where": "https://example.com/jjjjj", "policy": "A test policy."},
                                        "urls": {
                                           "local": "https://resolver.myorg.net/ark:/99999/s2aaed59b0-6ad6-4b69-8511-bcf781e386a0",
                                           "global": "https://n2t.net/ark:/99999/s2aaed59b0-6ad6-4b69-8511-bcf781e386a0"}
                               }

    # Intentionally trigger a 409 by mismatching the URL parameters and the ark_string body field.
    response = client.post(
        "/larkm",
        json={
            "shoulder": "s2",
            "identifier": "3a8a9396-baa8-46be-ba22-b08b0de2db5b",
            "target": "https://foo.example.com/ttttt"
        },
    )
    assert response.status_code == 201

    response = client.put(
        "/larkm/ark:/99999/s23a8a9396-baa8-46be-ba22-b08b0de2db5b",
        json={
            "ark_string": "ark:/99999/s23a8a9396-baa8-46be-ba22-b08b0de2db5bxxx"
        },
    )
    assert response.status_code == 409
    assert response.json() == {'detail': 'NAAN/identifier combination and ark_string do not match.'}

    # Intentionally trigger a 409 by trying to update the target with a target that already exists.
    response = client.post(
        "/larkm",
        json={
            "shoulder": "s2",
            "identifier": "292c0745-7b79-4f05-b0bf-3329267a8655",
            "target": "https://foo.example.com/targettest"
        },
    )
    assert response.status_code == 201

    response = client.put(
        "/larkm/ark:/99999/s2292c0745-7b79-4f05-b0bf-3329267a8655",
        json={
            "ark_string": "ark:/99999/s2292c0745-7b79-4f05-b0bf-3329267a8655",
            "target": "http://example.com/15"
        },
    )
    assert response.status_code == 409
    assert response.json() == {'detail': 'Target already in use.'}

    # Intentionally trigger a 422 by not providing an ark_string in the body.
    response = client.put(
        "/larkm/ark:/99999/s2292c0745-7b79-4f05-b0bf-3329267a8655",
        json={
            "erc_when": "2022"
        },
    )
    assert response.status_code == 422
    assert response.json() == {'detail': 'When updatating ARKs, the ark_string must be provided in the request body.'}


def test_delete_ark():
    create_response = client.post(
        "/larkm",
        json={
            "shoulder": "x9",
            "identifier": "15a1a0a1-20a3-4ef9-a0b5-91a6115bb538",
            "target": "https://example.com"
        },
    )
    assert create_response.status_code == 201

    delete_response = client.delete(
        "/larkm/ark:/99999/x915a1a0a1-20a3-4ef9-a0b5-91a6115bb538"
    )
    assert delete_response.status_code == 204
