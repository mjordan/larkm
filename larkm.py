from typing import Optional
from fastapi import FastAPI, Response, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from uuid import uuid4
from copy import deepcopy
import json

with open("larkm.json", "r") as config_file:
    config = json.load(config_file)

app = FastAPI()

"""CREATE TABLE arks(shoulder TEXT, identifier TEXT, target TEXT, erc_who TEXT, erc_what TEXT, erc_when TEXT, erc_where TEXT, policy TEXT);
"""


class Ark(BaseModel):
    shoulder: Optional[str] = None
    identifier: Optional[str] = None
    ark_string: Optional[str] = None
    target: Optional[str] = None
    who: Optional[str] = None
    what: Optional[str] = None
    when: Optional[str] = None
    where: Optional[str] = None
    policy: Optional[str] = None


# During development and for demo purposes only, we use an in-memory
# dictionary of ARKS that persists as long as the app is running in
# the dev web server. In production, ARKS would be stored in a db.
test_arks = dict({'ark:/12345/x977777': {'shoulder': 'x9', 'identifier': '77777',
                                         'target': 'https://www.lib.sfu.ca',
                                         'who': ':at', 'what': ':at', 'when': ':at',
                                         'where': 'https://www.lib.sfu.ca', 'policy': ''}})


@app.get("/ark:/{naan}/{identifier}")
def resolve_ark(naan: str, identifier: str, info: Optional[str] = None):
    """
    The ARK resolver. Redirects the client to the target URL
    associated with the ARK. Sample query:

    curl -L "http://127.0.0.1:8000/ark:/12345/12"

    - **naan**: the NAAN portion of the ARK.
    - **identifier**: the identifier portion of the ARK.
    - **info**: As described in the ARK specification, '?info' appended
      to the ARK string should return a committment statement and resource
      metadata. For now, return the configured committment statement only.
    """
    ark = f'ark:/{naan}/{identifier}'
    if info is None:
        if ark.strip() in test_arks.keys() and test_arks.get(ark) is not None:
            return RedirectResponse(test_arks[ark]['target'])
        else:
            raise HTTPException(status_code=404, detail="ARK not found")
    else:
        config["allowed_shoulders"].insert(0, config["default_shoulder"])
        for sh in config["allowed_shoulders"]:
            if ark.startswith(sh):
                return Response(content=config["committment_statement"][sh], media_type="text/plain")
            else:
                return Response(content=config["committment_statement"]["default"], media_type="text/plain")


@app.get("/larkm")
def read_ark(ark_string: Optional[str] = '', target: Optional[str] = ''):
    """
    Get the target URL associated with an ARK, or the ARK assoicated
    with a target URL. Sample query:

    curl "http://127.0.0.1:8000/larkm?ark_string=ark:/12345/12" or
    curl "http://127.0.0.1:8000/larkm?target=https://www.lib.sfu.ca"

    - **ark_string**: the ARK the client wants to get the target for, in the
      form 'ark:/naan/id_string'.
    - **target**: the target the client wants to get the ark for, in
      the form of a fully qualified URL.

      Include either the "ark_string" or the "target" in requests, not both
      at the same time.
    """
    if ark_string.strip() in test_arks.keys():
        return {"ark_string": ark_string, "target": test_arks[ark_string]['target']}
    else:
        raise HTTPException(status_code=404, detail="ARK not found")
    if len(target) > 0:
        for ark_string, target_url in test_arks.items():
            if target_url.strip() == target.strip():
                return {"ark_string": ark_string, "target": test_arks[ark_string]['target']}
    # If no ARK found, raise a 404.
        raise HTTPException(status_code=404, detail="Target not found")


@app.post("/larkm", status_code=201)
def create_ark(ark: Ark):
    """
    Create a new ARK, optionally minting a new ARK. Clients can provide
    an identifier string and/or a shoulder. If either of these is not provided,
    larkm will provide one. If an identifier is provided, it should not contain
    a shoulder, since larkm will always add a shoulder. Clients cannot provide
    a NAAN. Clients must always provide a target.

    Sample request with an provided ID/name and shoulder:

    curl -v -X POST "http://127.0.0.1:8000/larkm" \
        -H 'Content-Type: application/json' \
        -d '{"shoulder": "x1", "identifier": "12345", "target": "https://digital.lib.sfu.ca"}'

    Sample request with only a target and an ID/name, which asks larkm to generate
    an ARK string based on the NAAN specified in configuration settings, the default
    soulder, and the provided ID/name:

    curl -v -X POST "http://127.0.0.1:8000/larkm" \
        -H 'Content-Type: application/json' \
        -d '{"identifier": "45679", "target": "https://digital.lib.sfu.ca"}'

    Sample request with only a target and a shoulder, which asks larkm to generate
    an ARK string based on the NAAN specified in configuration settings and the supplied
    shoulder. If the ID/name is not provided, larkm will provide one in the form of a
    v4 UUID:

    curl -v -X POST "http://127.0.0.1:8000/larkm" \
        -H 'Content-Type: application/json' \
        -d '{"shoulder": "x1", "target": "https://digital.lib.sfu.ca"}'

    Sample request with no target or shoulder. larkm will generate an ARK using
    the configured NAAN, the default shoulder, and a v4 UUID.

    curl -v -X POST "http://127.0.0.1:8000/larkm" \
        -H 'Content-Type: application/json' \
        -d '{"target": "https://digital.lib.sfu.ca"}'

    Sample request with ERC metadata values. ERC elements ("who", "what", "when",
    "where") not included in the request body, they are given defaults from config,
    except for "where", which is given the value of the ARK's target URL.

    curl -v -X POST "http://127.0.0.1:8000/larkm" \
        -H 'Content-Type: application/json' \
        -d '{"who": "Jordan, Mark", "what": "GitBags", "when": "2014", \
        "target": "https://github.com/mjordan/GitBags"}'

    - **ark**: the ARK to create, consisting of an ARK and a target URL.
    """
    if ark.target is None:
        raise HTTPException(status_code=422, detail="Missing target.")

    # Validate shoulder if provided.
    config["allowed_shoulders"].insert(0, config["default_shoulder"])
    if ark.shoulder is not None:
        for sh in config["allowed_shoulders"]:
            if ark.shoulder not in config["allowed_shoulders"]:
                raise HTTPException(status_code=422, detail="Provided shoulder is invalid.")

    # Assemble the ARK. Generate parts the client didn't provide.
    if ark.shoulder is None:
        shoulder = config["default_shoulder"]
    else:
        shoulder = ark.shoulder
    if ark.identifier is None:
        identifier = str(uuid4())
    else:
        identifier = ark.identifier

    ark.ark_string = f'ark:/{config["NAAN"]}/{shoulder}{identifier}'

    if ark.who is None:
        ark.who = config["erc_metadata_defaults"]["who"]
    if ark.what is None:
        ark.what = config["erc_metadata_defaults"]["what"]
    if ark.when is None:
        ark.when = config["erc_metadata_defaults"]["when"]
    if ark.where is None:
        ark.where = ark.target
    if ark.policy is None:
        if ark.shoulder in config["committment_statement"].keys():
            ark.policy = config["committment_statement"][ark.shoulder]
        else:
            ark.policy = config["committment_statement"]['default']

    # Add it to test_arks so it can be requested by a client.
    test_arks[ark.ark_string] = ark.dict()
    return {"ark": ark}


@app.put("/larkm/ark:/{naan}/{identifier}")
def update_ark(naan: str, identifier: str, ark: Ark):
    """
    Update an ARK with a new target, metadata, or policy statement. Shoulders,
    identifiers, and ark_strings cannot be updated. ark_string is a required
    body field. Sample query:

    curl -v -X PUT "http://127.0.0.1:8000/larkm/ark:/12345/s912" \
        -H 'Content-Type: application/json' \
        -d '{"ark_string": "ark:/12345/s912", "target": "https://summit.sfu.ca"}'

    - **naan**: the NAAN portion of the ARK.
    - **identifier**: the identifier portion of the ARK, which will include a shouder.
    """
    request_ark_string = f'ark:/{naan}/{identifier}'.strip()
    old_ark = deepcopy(test_arks[request_ark_string])

    if request_ark_string != ark.ark_string:
        raise HTTPException(status_code=409, detail="NAAN/identifier combination and ark_string do not match.")

    # shoulder, identifier, and ark_string cannot be updated.
    ark.shoulder = old_ark['shoulder']
    ark.identifier = old_ark['identifier']
    ark.ark_string = old_ark['ark_string']
    # Only update ark properties that are in the request body.
    if ark.who is None:
        ark.who = old_ark['who']
    if ark.what is None:
        ark.what = old_ark['what']
    if ark.when is None:
        ark.when = old_ark['when']
    if ark.policy is None:
        ark.policy = old_ark['policy']
    if ark.where is None:
        ark.where = old_ark['where']
    if ark.target is None:
        ark.target = old_ark['target']

    return {"ark": ark}


@app.delete("/larkm/ark:/{naan}/{identifier}", status_code=204)
def delete_ark(naan: str, identifier: str):
    """
    Given an ARK string, delete the ARK. Sample query:

    curl -v -X DELETE "http://127.0.0.1:8000/larkm/ark:/12345/12"

    - **naan**: the NAAN portion of the ARK.
    - **identifier**: the identifier portion of the ARK.
    """
    ark_string = f'ark:/{naan}/{identifier}'
    # If no ARK found, raise a 404.
    if ark_string.strip() not in test_arks.keys():
        raise HTTPException(status_code=404, detail="ARK not found")
    # If ARK found, delete it.
    else:
        del test_arks[ark_string.strip()]
