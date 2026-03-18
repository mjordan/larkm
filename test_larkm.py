from fastapi.testclient import TestClient
from larkm import app, get_naan_from_ark_string
import shutil
import re

client = TestClient(app)
client.headers = {"Authorization": "myapikey"}


# Replace Woosh index data with backups to ensure reliable test data.
def setup_module(module):
    shutil.copyfile(
        "fixtures/index_dir/_MAIN_1.toc.bak", "fixtures/index_dir/_MAIN_1.toc"
    )
    shutil.copyfile(
        "fixtures/index_dir/MAIN_6ydemc1f3h6z75lb.seg.bak",
        "fixtures/index_dir/MAIN_6ydemc1f3h6z75lb.seg",
    )


# Replace SQLite db with backup since testing will have altered the db.
def teardown_module(module):
    shutil.copyfile("fixtures/larkmtest.db.bak", "fixtures/larkmtest.db")


# Test the redirect functionality and other aspects of ARK resolution.
def test_resolve_ark():
    # Test basic resolution request by checking for a 307 response. To do this we create a fresh ARK.
    response = client.post(
        "/larkm",
        json={
            "naan": "99999",
            "shoulder": "s1",
            "identifier": "bd805e3b-6ba6-4517-a197-05d99981bcba",
            "target": "https://example.com/redirect_target",
        },
    )
    assert response.status_code == 201

    response = client.get("/ark:99999/s1bd805e3b6ba6", follow_redirects=False)
    assert response.status_code == 307

    # Same ARK but with optional /.
    response = client.get("/ark:/99999/s1bd805e3b6ba6", follow_redirects=False)
    assert response.status_code == 307

    # Test basic ?info request.
    response = client.get("/ark:12345/x9062cdde7f9d6?info")
    assert response.status_code == 200
    assert (
        response.text
        == "erc:\nwho: :at\nwhat: :at\nwhen: :at\nwhere: https://resolver.myorg.net/ark:12345/x9062cdde7f9d6\npolicy: Default committment statement.\n\n"
    )

    # Same ARK but with optional /.
    response = client.get("/ark:/12345/x9062cdde7f9d6?info")
    assert response.status_code == 200
    assert (
        response.text
        == "erc:\nwho: :at\nwhat: :at\nwhen: :at\nwhere: https://resolver.myorg.net/ark:12345/x9062cdde7f9d6\npolicy: Default committment statement.\n\n"
    )

    # Ark not found.
    response = client.get("/ark:/12345/x9062cdde7f111?info")
    assert response.status_code == 404
    assert response.text == '{"detail":"ARK not found"}'

    # Path not found.
    response = client.get("/foo/bar")
    assert response.status_code == 404
    assert response.text == '{"detail":"Not Found"}'

    # Resolve an ARK with no target.
    response = client.post(
        "/larkm",
        json={
            "naan": "99999",
            "shoulder": "s1",
            "identifier": "e6aca090-4cc6-4459-b87d-3c3e358f1f62",
        },
    )
    assert response.status_code == 201
    assert response.json() == {
        "ark": {
            "shoulder": "s1",
            "identifier": "e6aca0904cc6",
            "ark_string": "ark:99999/s1e6aca0904cc6",
            "target": "",
            "who": ":at",
            "what": ":at",
            "when": ":at",
            "where": "https://resolver.myorg.net/ark:99999/s1e6aca0904cc6",
            "policy": "ACME University commits to maintain ARKs that have 's1' as a shoulder for a long time.",
        },
        "urls": {
            "local": "https://resolver.myorg.net/ark:99999/s1e6aca0904cc6",
            "global": "https://n2t.net/ark:99999/s1e6aca0904cc6",
        },
    }
    response = client.get("/ark:99999/s1e6aca0904cc6")
    assert response.status_code == 200
    assert (
        response.text
        == "erc:\nwho: :at\nwhat: :at\nwhen: :at\nwhere: https://resolver.myorg.net/ark:99999/s1e6aca0904cc6\npolicy: ACME University commits to maintain ARKs that have 's1' as a shoulder for a long time.\n\n"
    )


# Test the "get ARK" functionality.
def test_get_ark():
    response = client.get("/larkm/ark:/99999/s1cea8e7f31c84")
    assert response.status_code == 200
    assert response.json() == {
        "date_created": "2022-06-23 03:00:45",
        "date_modified": "2022-06-23 03:00:45",
        "shoulder": "s1",
        "identifier": "cea8e7f31c84",
        "ark_string": "ark:99999/s1cea8e7f31c84",
        "target": "http://example.com/15",
        "erc_who": "Derex Godfry",
        "erc_what": "5 Ways to Immediately Start Selling WATER",
        "erc_when": ":at",
        "erc_where": "https://resolver.myorg.net/ark:99999/s1cea8e7f31c84",
        "policy": "Random policy generators generally suck.",
    }


def test_create_ark():
    # Create an ARK using all available defaults.
    response = client.post(
        "/larkm",
        json={"naan": "99999", "target": "https://example.com/ppppp"},
    )
    assert response.status_code == 201

    # Create an ARK with no target.
    response = client.post(
        "/larkm",
        json={"naan": "99999"},
    )
    assert response.status_code == 201

    # Test if the generated identifier is valid.
    response = client.post(
        "/larkm",
        json={"naan": "99999", "target": "https://example.com/sssss"},
    )
    body = response.json()
    assert re.match(
        "^[a-f0-9]{12}$",
        body["ark"]["identifier"],
    )

    # Provide a shoulder and UUID v4 as the identifier.
    response = client.post(
        "/larkm",
        json={
            "naan": "99999",
            "shoulder": "s1",
            "identifier": "586ef08c-b2a0-4b5b-a9e9-954e0259ed63",
            "target": "https://example.com/zxzxzx",
        },
    )
    assert response.status_code == 201
    assert response.json() == {
        "ark": {
            "shoulder": "s1",
            "identifier": "586ef08cb2a0",
            "ark_string": "ark:99999/s1586ef08cb2a0",
            "target": "https://example.com/zxzxzx",
            "who": ":at",
            "what": ":at",
            "when": ":at",
            "where": "https://resolver.myorg.net/ark:99999/s1586ef08cb2a0",
            "policy": "ACME University commits to maintain ARKs that have 's1' as a shoulder for a long time.",
        },
        "urls": {
            "local": "https://resolver.myorg.net/ark:99999/s1586ef08cb2a0",
            "global": "https://n2t.net/ark:99999/s1586ef08cb2a0",
        },
    }

    # Provide a malformed UUID v4 as the identifier.
    response = client.post(
        "/larkm",
        json={
            "naan": "99999",
            "shoulder": "s1",
            "identifier": "fdd17ff8892d7-4671-b25b-e9d8ead90239",
            "target": "https://example.com/zxzxzxc",
        },
    )
    assert response.status_code == 422

    # Provide a shoulder and identifier.
    response = client.post(
        "/larkm",
        json={
            "naan": "99999",
            "shoulder": "s1",
            "identifier": "14b7f127b358",
            "target": "https://example.com/wwwww",
        },
    )
    assert response.status_code == 201
    assert response.json() == {
        "ark": {
            "shoulder": "s1",
            "identifier": "14b7f127b358",
            "ark_string": "ark:99999/s114b7f127b358",
            "target": "https://example.com/wwwww",
            "who": ":at",
            "what": ":at",
            "when": ":at",
            "where": "https://resolver.myorg.net/ark:99999/s114b7f127b358",
            "policy": "ACME University commits to maintain ARKs that have 's1' as a shoulder for a long time.",
        },
        "urls": {
            "local": "https://resolver.myorg.net/ark:99999/s114b7f127b358",
            "global": "https://n2t.net/ark:99999/s114b7f127b358",
        },
    }

    # Provide a malformed identifier (contains hyphen).
    response = client.post(
        "/larkm",
        json={
            "naan": "99999",
            "shoulder": "s1",
            "identifier": "4eed199-4600",
            "target": "https://example.com/wwwwwx",
        },
    )
    assert response.status_code == 422

    # Provide a malformed identifier (invalid letter).
    response = client.post(
        "/larkm",
        json={
            "naan": "99999",
            "shoulder": "s1",
            "identifier": "80304d63ac0k",
            "target": "https://example.com/wwwwwa",
        },
    )
    assert response.status_code == 422

    # Provide an identifier that is not 12 characters long.
    response = client.post(
        "/larkm",
        json={
            "naan": "99999",
            "shoulder": "s1",
            "identifier": "d52d68a12d504",
            "target": "https://example.com/wwwwwz",
        },
    )
    assert response.status_code == 422

    # Provide a NAAN, shoulder and identifier.
    response = client.post(
        "/larkm",
        json={
            "naan": "12345",
            "shoulder": "s1",
            "identifier": "9e2e12759dfc",
            "target": "https://example.com/uuytr",
        },
    )
    assert response.status_code == 201
    assert response.json() == {
        "ark": {
            "shoulder": "s1",
            "identifier": "9e2e12759dfc",
            "ark_string": "ark:12345/s19e2e12759dfc",
            "target": "https://example.com/uuytr",
            "who": ":at",
            "what": ":at",
            "when": ":at",
            "where": "https://resolver.myorg.net/ark:12345/s19e2e12759dfc",
            "policy": "ACME University commits to maintain ARKs that have 's1' as a shoulder for a long time.",
        },
        "urls": {
            "local": "https://resolver.myorg.net/ark:12345/s19e2e12759dfc",
            "global": "https://n2t.net/ark:12345/s19e2e12759dfc",
        },
    }

    # Provide a shoulder that is mapped to the default policy statement.
    response = client.post(
        "/larkm",
        json={
            "naan": "99999",
            "shoulder": "x9",
            "identifier": "20578b9eba6e",
            "what": "A new ARK",
            "target": "https://example.com/kkkkk",
        },
    )
    assert response.status_code == 201
    assert response.json() == {
        "ark": {
            "shoulder": "x9",
            "identifier": "20578b9eba6e",
            "ark_string": "ark:99999/x920578b9eba6e",
            "target": "https://example.com/kkkkk",
            "who": ":at",
            "what": "A new ARK",
            "when": ":at",
            "where": "https://resolver.myorg.net/ark:99999/x920578b9eba6e",
            "policy": "Default committment statement.",
        },
        "urls": {
            "local": "https://resolver.myorg.net/ark:99999/x920578b9eba6e",
            "global": "https://n2t.net/ark:99999/x920578b9eba6e",
        },
    }

    # Get the 'info' for this ARK.
    response = client.get("/ark:99999/x920578b9eba6e?info")
    assert response.status_code == 200
    response_text = "erc:\nwho: :at\nwhat: A new ARK\nwhen: :at\n"
    response_text = (
        response_text
        + "where: https://resolver.myorg.net/ark:99999/x920578b9eba6e\npolicy: Default committment statement.\n\n"
    )
    assert response.text == response_text

    # ARK with some special characters in its metadata.
    response = client.post(
        "/larkm",
        json={
            "naan": "99999",
            "shoulder": "x9",
            "identifier": "47321e027df6",
            "target": "https://example.com/fffff",
            "what": "A test ARK with some 'special' characters (`%&) in its metadata",
        },
    )
    assert response.status_code == 201
    assert response.json() == {
        "ark": {
            "shoulder": "x9",
            "identifier": "47321e027df6",
            "ark_string": "ark:99999/x947321e027df6",
            "target": "https://example.com/fffff",
            "who": ":at",
            "when": ":at",
            "what": "A test ARK with some 'special' characters (`%&) in its metadata",
            "where": "https://resolver.myorg.net/ark:99999/x947321e027df6",
            "policy": "Default committment statement.",
        },
        "urls": {
            "local": "https://resolver.myorg.net/ark:99999/x947321e027df6",
            "global": "https://n2t.net/ark:99999/x947321e027df6",
        },
    }

    # Create an ARK with a bad identifier.
    response = client.post(
        "/larkm",
        json={
            "naan": "99999",
            "shoulder": "s2",
            "identifier": "cda60df9-b468-4520-8e9",
            "target": "https://example.com/ddddd",
        },
    )
    assert response.status_code == 422
    assert (
        response.text
        == '{"detail":"Provided identifier cda60df9-b468-4520-8e9 is invalid."}'
    )

    # Create an ARK that uses a identifier already in the database.
    # First, create an ARK to test against.
    response = client.post(
        "/larkm",
        json={
            "naan": "12345",
            "shoulder": "s1",
            "identifier": "2d24d07fed23",
            "target": "https://example.com/ggggg",
        },
    )
    assert response.status_code == 201

    # Then create another ARK with the same identifier.
    response = client.post(
        "/larkm",
        json={
            "naan": "12345",
            "shoulder": "s1",
            "identifier": "2d24d07fed23",
            "target": "https://example.com/hhhhh",
        },
    )
    assert response.status_code == 409
    assert response.json() == {"detail": "Identifier 2d24d07fed23 already in use."}

    # Create an ARK that has a target already in the database.
    # First, create an ARK to test against.
    response = client.post(
        "/larkm",
        json={
            "naan": "12345",
            "target": "https://example.com/testingforexistingtarget",
        },
    )
    assert response.status_code == 201

    # Then create another ARK with the same identifier.
    response = client.post(
        "/larkm",
        json={
            "naan": "12345",
            "target": "https://example.com/testingforexistingtarget",
        },
    )
    assert response.status_code == 409
    assert response.json() == {
        "detail": "'target' value https://example.com/testingforexistingtarget already in use."
    }

    # Create multiple ARKs that have an empty or missing target.
    # First, create an ARK to test against.
    response = client.post(
        "/larkm",
        json={"naan": "12345"},
    )
    assert response.status_code == 201

    # Then create another ARK with the same identifier.
    response = client.post(
        "/larkm",
        json={
            "naan": "12345",
            # "target": "",
        },
    )
    assert response.status_code == 201

    # Create an ARK that uses an erc_where value already in the database.
    response = client.post(
        "/larkm",
        json={
            "naan": "99999",
            "shoulder": "s1",
            "identifier": "3dd364bdea7a",
            "target": "https://example.com/ggggg",
        },
    )
    assert response.status_code == 409


def test_update_ark():
    # Create an ARK to update.
    response = client.post(
        "/larkm",
        json={
            "naan": "99999",
            "shoulder": "s2",
            "identifier": "cda60df9b468",
            "target": "https://example.com/x8ui8i",
        },
    )
    assert response.status_code == 201
    assert response.json() == {
        "ark": {
            "shoulder": "s2",
            "identifier": "cda60df9b468",
            "ark_string": "ark:99999/s2cda60df9b468",
            "target": "https://example.com/x8ui8i",
            "who": ":at",
            "what": ":at",
            "when": ":at",
            "where": "https://resolver.myorg.net/ark:99999/s2cda60df9b468",
            "policy": "Default committment statement.",
        },
        "urls": {
            "local": "https://resolver.myorg.net/ark:99999/s2cda60df9b468",
            "global": "https://n2t.net/ark:99999/s2cda60df9b468",
        },
    }

    # Then update the when and what body fields.
    response = client.patch(
        "/larkm/ark:99999/s2cda60df9b468",
        json={
            "when": "2020",
            "what": "A test",
            "ark_string": "ark:99999/s2cda60df9b468",
        },
    )
    assert response.status_code == 200
    assert response.json() == {
        "ark": {
            "shoulder": "s2",
            "identifier": "cda60df9b468",
            "ark_string": "ark:99999/s2cda60df9b468",
            "target": "https://example.com/x8ui8i",
            "who": ":at",
            "what": "A test",
            "when": "2020",
            "where": "https://resolver.myorg.net/ark:99999/s2cda60df9b468",
            "policy": "Default committment statement.",
        },
        "urls": {
            "local": "https://resolver.myorg.net/ark:99999/s2cda60df9b468",
            "global": "https://n2t.net/ark:99999/s2cda60df9b468",
        },
    }

    # Update the policy field.
    response = client.post(
        "/larkm",
        json={
            "naan": "12345",
            "shoulder": "s2",
            "identifier": "aaed59b06ad6",
            "what": "New ARK with its own policy",
            "target": "https://example.com/jjjjj",
        },
    )

    response = client.patch(
        "/larkm/ark:12345/s2aaed59b06ad6",
        json={
            "policy": "A test policy.",
            "ark_string": "ark:12345/s2aaed59b06ad6",
        },
    )
    assert response.status_code == 200
    assert response.json() == {
        "ark": {
            "shoulder": "s2",
            "identifier": "aaed59b06ad6",
            "ark_string": "ark:12345/s2aaed59b06ad6",
            "target": "https://example.com/jjjjj",
            "who": ":at",
            "what": "New ARK with its own policy",
            "when": ":at",
            "where": "https://resolver.myorg.net/ark:12345/s2aaed59b06ad6",
            "policy": "A test policy.",
        },
        "urls": {
            "local": "https://resolver.myorg.net/ark:12345/s2aaed59b06ad6",
            "global": "https://n2t.net/ark:12345/s2aaed59b06ad6",
        },
    }

    # Test updating the target to be empty.
    response = client.post(
        "/larkm",
        json={
            "naan": "12345",
            "shoulder": "s2",
            "identifier": "fd3d3febf720",
            "what": "New ARK with its own policy",
            "target": "https://example.com/jzjzjzjz",
        },
    )
    assert response.status_code == 201
    response = client.patch(
        "/larkm/ark:12345/s2fd3d3febf720",
        json={
            "policy": "A test policy.",
            "target": "",
            "ark_string": "ark:12345/s2fd3d3febf720",
        },
    )
    assert response.status_code == 200
    assert response.json() == {
        "ark": {
            "shoulder": "s2",
            "identifier": "fd3d3febf720",
            "ark_string": "ark:12345/s2fd3d3febf720",
            "target": "",
            "who": ":at",
            "what": "New ARK with its own policy",
            "when": ":at",
            "where": "https://resolver.myorg.net/ark:12345/s2fd3d3febf720",
            "policy": "A test policy.",
        },
        "urls": {
            "local": "https://resolver.myorg.net/ark:12345/s2fd3d3febf720",
            "global": "https://n2t.net/ark:12345/s2fd3d3febf720",
        },
    }

    # Test updating an ARK so that is uses a target that is already registered.
    response = client.post(
        "/larkm",
        json={
            "naan": "99999",
            "shoulder": "s2",
            "identifier": "62cf2b0488a8",
            "target": "https://example.com/62cf2b04xxx",
        },
    )
    assert response.status_code == 201

    # Then update the target (http://example.com/10 exists in the larkmtest.db).
    response = client.patch(
        "/larkm/ark:99999/s262cf2b0488a8",
        json={
            "target": "http://example.com/10",
            "ark_string": "ark:99999/s262cf2b0488a8",
        },
    )
    assert response.status_code == 409

    # Intentionally trigger a 409 by mismatching the URL parameters and the ark_string body field.
    response = client.post(
        "/larkm",
        json={
            "naan": "12345",
            "shoulder": "s2",
            "identifier": "3a8a9396baa8",
            "target": "https://foo.example.com/ttttt",
        },
    )
    assert response.status_code == 201

    response = client.patch(
        "/larkm/ark:12345/s23a8a9396-baa8",
        json={"ark_string": "ark:12345/s23a8a9396baa85bxxx"},
    )
    assert response.status_code == 409
    assert response.json() == {
        "detail": "NAAN/identifier combination and ark_string do not match."
    }

    # Intentionally trigger a 409 by trying to update the erc_where property.
    response = client.post(
        "/larkm",
        json={
            "naan": "99999",
            "shoulder": "s2",
            "identifier": "292c07457b79",
            "target": "https://foo.example.com/wheretest",
        },
    )
    assert response.status_code == 201

    response = client.patch(
        "/larkm/ark:99999/s2292c07457b79",
        json={
            "ark_string": "ark:99999/s2292c07457b79",
            "target": "http://example.com/15",
            "where": "asdkf",
        },
    )
    assert response.status_code == 409
    assert response.json() == {
        "detail": "'where' is automatically assigned the value of the ark string and cannot be updated."
    }

    # Intentionally trigger a 422 by not providing an ark_string in the body.
    response = client.patch(
        "/larkm/ark:99999/s2292c07457b79",
        json={"erc_when": "2022"},
    )
    assert response.status_code == 422
    assert response.json() == {
        "detail": "When updatating ARKs, the ark_string must be provided in the request body."
    }


def test_delete_ark():
    create_response = client.post(
        "/larkm",
        json={
            "naan": "12345",
            "shoulder": "x9",
            "identifier": "5c6b0d2314e4",
            "target": "https://example.com",
        },
    )
    assert create_response.status_code == 201

    delete_response = client.delete("/larkm/ark:12345/x95c6b0d2314e4")
    assert delete_response.status_code == 204


def test_search_arks():
    # Do a search that returns no ARKs.
    response = client.get("/larkm/search?naan=99999&q=policy%3Axxxxxxxx")
    assert response.status_code == 200
    assert response.json() == {"num_results": 0, "page": 1, "page_size": 20, "arks": []}

    # Do a search where searching is not enabled.
    response = client.get("/larkm/search?naan=00000&q=foo")
    assert response.status_code == 422

    # Do a search using page size and page number parameters.
    response = client.get(
        "/larkm/search?naan=99999&q=policy%3Apolicy&page_size=2&page=2"
    )
    assert response.status_code == 200
    assert response.json() == {
        "num_results": 7,
        "page": "2",
        "page_size": "2",
        "arks": [
            {
                "date_created": "2022-06-23 03:00:45",
                "date_modified": "2022-06-23 03:00:45",
                "shoulder": "s1",
                "identifier": "a09258801268",
                "ark_string": "ark:99999/s1a09258801268",
                "target": "http://example.com/17",
                "erc_who": "Avery Meyer",
                "erc_what": "5 Things That Happen When You Are in SPACE",
                "erc_when": ":at",
                "erc_where": "ark:99999/s1a09258801268",
                "policy": "I am fundamentally against your policy.",
            },
            {
                "date_created": "2022-06-23 03:00:45",
                "date_modified": "2022-06-23 03:00:45",
                "shoulder": "s1",
                "identifier": "a09d74a23e06",
                "ark_string": "ark:99999/s1a09d74a23e06",
                "target": "http://example.com/20",
                "erc_who": "Arden Mclean",
                "erc_what": "What Everyone Ought to Know about GUM",
                "erc_when": ":at",
                "erc_where": "ark:99999/s1a09d74a23e06",
                "policy": "No policy on this.",
            },
        ],
    }

    # Do a search with an invalid date in a range.
    response = client.get(
        "/larkm/search?naan=99999&q=date_created%3A%5B2022-02-20%20TO%202022-02-29%5D"
    )
    assert response.status_code == 422
    assert response.json() == {
        "detail": "2022-02-29 in date_created is not a valid date."
    }


def test_get_config():
    response = client.get("/larkm/config/99999")
    assert response.status_code == 200
    assert response.json() == {
        "default_shoulder": "s1",
        "allowed_shoulders": ["s2", "s3", "x9"],
        "committment_statements": {
            "s1": "ACME University commits to maintain ARKs that have 's1' as a shoulder for a long time.",
            "s3": "ACME University commits to maintain ARKs that have 's3' as a shoulder until the end of 2025.",
            "default": "Default committment statement.",
        },
        "erc_metadata_defaults": {"who": ":at", "what": ":at", "when": ":at"},
        "resolver_hosts": {
            "global": "https://n2t.net/",
            "local": "https://resolver.myorg.net",
            "erc_where": "https://resolver.myorg.net",
        },
    }

    response = client.get("/larkm/config/00000")
    assert response.status_code == 200
    assert response.json() == {
        "default_shoulder": "v1",
        "allowed_shoulders": ["v2", "v3"],
        "committment_statements": {
            "v1": "somerandomstring.",
            "v3": "anotherrandomstring",
            "default": "Default random committment statement.",
        },
        "erc_metadata_defaults": {"who": ":at", "what": ":at", "when": ":at"},
        "resolver_hosts": {
            "global": "https://persist.acme.net/",
            "local": "https://resolver.myorg.net",
            "erc_where": "https://resolver.myorg.net",
        },
    }


def test_bad_api_key():
    create_response = client.post(
        "/larkm",
        json={
            "naan": "99999",
            "shoulder": "x9",
            "identifier": "2d1237ef9f7f",
            "target": "https://example.com/deleteme",
        },
    )
    assert create_response.status_code == 201

    # Provide an API key that is not registered in the config file to trigger a 403.
    delete_response = client.delete(
        "/larkm/ark:99999/x915a1a0a120a3",
        headers={"Authorization": ""},
    )
    assert delete_response.status_code == 403

    delete_response = client.delete(
        "/larkm/ark:99999/x915a1a0a120a3",
        headers={"Authorization": "badkey"},
    )
    assert delete_response.status_code == 403


def test_bad_trusted_host():
    response = client.get("/larkm/config/11111")
    # The FastAPI test client's IP address is "testclient".
    assert response.status_code == 403


def test_get_naan_from_ark():
    naans_to_get_from_arks = {
        "12345": "ark:12345/x9062cdde7f9d6",
        "49875": "ark:49875/s19d7adca03a96",
        "10190": "ark:10190/s175b939ec2b46",
        "83765": "ark:/83765/s1114064a06c67",
        "28272": "ark:28272/s1a47f2e3afb9d",
        "95876": "https://foo.com/ark:95876/s1a39b99f934e6",
        "57209": "https://foobar.org/ark:/57209/s17ffc8979b4d6",
        "87256": "ark:/87256/s10903ff26d28a",
        "99999": "ark:99999/s1338c49c7a3d9",
    }

    for naan, ark in naans_to_get_from_arks.items():
        ret = get_naan_from_ark_string(ark)
        assert ret == naan
