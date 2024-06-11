from fastapi.testclient import TestClient
from larkm import app
import shutil
import os
import re

client = TestClient(app)
client.headers = {"Authorization": "myapikey"}


def setup_module(module):
    shutil.copyfile('larkm.json', 'larkm.json.pretests')
    shutil.copyfile('fixtures/larkmtest.db.bak', 'fixtures/larkmtest.db')
    shutil.copyfile('fixtures/larkm.json.tests.privateshoulder', 'larkm.json')


def teardown_module(module):
    shutil.copyfile('fixtures/larkmtest.db.bak', 'fixtures/larkmtest.db')
    shutil.copyfile('larkm.json.pretests', 'larkm.json')


def test_resolve_private_shoulder():
    response = client.post(
        "/larkm",
        json={
            "shoulder": "p1",
            "identifier": "eb7b1687-6704-4986-87de-2e992b176ab5",
            "what": "A new ARK with a private shoulder",
            "target": "https://www.another.example.com/foo"
        },
    )
    assert response.status_code == 201

    # Expect a 403, since the IP address associated with the 'p1' shoulder is not 127.0.0.1.
    response = client.get("/ark:99999/p1eb7b1687-6704-4986-87de-2e992b176ab5")
    assert response.status_code == 403


def test_resolve_non_http_target_from_unregistered_address():
    response = client.post(
        "/larkm",
        json={
            "shoulder": "p1",
            "identifier": "8d3fd3f6-6ed0-4173-aea9-1784eaa5a656",
            "what": "A new ARK with a non-HTTP target",
            "target": "some_windows_share_UNC_address."
        },
    )
    assert response.status_code == 201

    # If the value of "target" does not start with "http", larkm returns a 403 the eqivalent of an "?info"
    # request with the target included.
    response = client.get("/ark:99999/p18d3fd3f6-6ed0-4173-aea9-1784eaa5a656")
    assert response.status_code == 403


