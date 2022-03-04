from typing import Optional
from fastapi import FastAPI, Response, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from uuid import uuid4
import json

with open("larkm.json", "r") as config_file:
    config = json.load(config_file)

app = FastAPI()


class Ark(BaseModel):
    shoulder: Optional[str] = None
    identifier: Optional[str] = None
    ark_string: Optional[str] = None
    target: Optional[str] = None


# During development and for demo purposes only, we use an in-memory
# dictionary of ARKS that persists as long as the app is running in
# the dev web server. In production, ARKS would be stored in a db.
test_arks = dict({'ark:/12345/x977777': 'https://www.lib.sfu.ca'})


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
            return RedirectResponse(test_arks[ark])
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
        return {"ark_string": ark_string, "target": test_arks[ark_string]}
    else:
        raise HTTPException(status_code=404, detail="ARK not found")
    if len(target) > 0:
        for ark_string, target_url in test_arks.items():
            if target_url.strip() == target.strip():
                return {"ark_string": ark_string, "target": test_arks[ark_string]}
    # If no ARK found, raise a 404.
        raise HTTPException(status_code=404, detail="Target not found")


@app.post("/larkm", status_code=201)
def create_ark(ark: Ark):
    """
    Create a new ARK, optionally minting a new ARK. Clients can provide
    an ID/name string and/or a shoulder. If either of these is not provided,
    larkm will provide one. If an ID/name is provided, it should not contain
    a shoulder. Clients cannot provide a NAAN. Clients must always provide
    a target.

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
        ark.shoulder = config["default_shoulder"]
    if ark.identifier is None:
        identifier = uuid4()
    else:
        identifier = ark.identifier

    ark.ark_string = f'ark:/{config["NAAN"]}/{ark.shoulder}{identifier}'

    # Add it to test_arks so it can be requested by a client.
    test_arks[ark.ark_string.strip()] = ark.target.strip()
    return {"ark": ark}


@app.put("/larkm/ark:/{naan}/{identifier}", response_model=Ark)
def update_ark(naan: str, identifier: str, ark: Ark):
    """
    Update an ARK with a new target. Sample query:

    curl -v -X PUT "http://127.0.0.1:8000/larkm/ark:/12345/12" \
        -H 'Content-Type: application/json' \
        -d '{"ark_string": "ark:/12345/12", "target": "https://summit.sfu.ca"}'

    - **naan**: the NAAN portion of the ARK.
    - **identifier**: the identifier portion of the ARK.
    """
    # Update the ARK in test_arks.
    ark_string = f'ark:/{naan}/{identifier}'
    if ark_string != ark.ark_string:
        raise HTTPException(status_code=409, detail="NAAN/identifier combination and ark_string do not match.")
    if ark.ark_string.strip() in test_arks.keys() and len(ark.target.strip()) > 0:
        test_arks[ark_string.strip()] = ark.target.strip()
        return {"ark_string": ark.ark_string, "target": ark.target}


@app.delete("/larkm/ark:/{naan}/{identifier}", status_code=204)
def delete_ark(naan: str, identifier: str):
    """
    Delete an ARK using its ARK string. Sample query:

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
