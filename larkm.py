from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from uuid import uuid4
import json

with open("larkm.json", "r") as config_file:
    config = json.load(config_file)

app = FastAPI()


class Ark(BaseModel):
    shoulder: Optional[str] = None
    ark_string: Optional[str] = None
    target: Optional[str] = None


# During development and for demo purposes only, we use an in-memory
# dictionary of ARKS that persists as long as the app is running in
# the dev web server. In production, ARKS would be stored in a db.
test_arks = dict({'ark:/99999/10': 'https://www.lib.sfu.ca'})


@app.get("/ark:/{naan}/{identifier}")
def resolve_ark(naan: str, identifier: str):
    """
    The ARK resolver. Redirects the client to the target URL
    associated with the ARK. Sample query:

    curl -L "http://127.0.0.1:8000/ark:/99999/12"

    - **naan**: the NAAN portion of the ARK.
    - **identifier**: the identifier portion of the ARK.
    """
    ark = f'ark:/{naan}/{identifier}'
    if ark.strip() in test_arks.keys() and test_arks.get(ark) is not None:
        return RedirectResponse(test_arks[ark])
    else:
        raise HTTPException(status_code=404, detail="ARK not found")


@app.get("/larkm")
def read_ark(ark_string: Optional[str] = '', target: Optional[str] = ''):
    """
    Get the target URL associated with an ARK, or the ARK assoicated
    with a target URL. Sample query:

    curl "http://127.0.0.1:8000/larkm?ark=ark:/99999/12" or
    curl "http://127.0.0.1:8000/larkm?target=https://www.lib.sfu.ca"

    - **ark**: the ARK the client wants to get the target for, in the
      form 'ark:/naan/id_string'.
    - **target**: the target the client wants to get the ark for, in
      the form of a fully qualified URL.
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
    Create a new ARK, optionally minting a new ARK. Sample request with an
    existing ARK string (i.e. provided by client):

    curl -v -X POST "http://127.0.0.1:8000/larkm" \
        -H 'Content-Type: application/json' \
        -d '{"shoulder": "x1", "ark_string": "ark:/99999/12", "target": "https://digital.lib.sfu.ca"}'

    Sample request with only a target and a shoulder, which asks larkm to generate
    an ARK string based on the NAAN specified in configuration settings, the supplied
    shoulder, and a v4 UUID:

    curl -v -X POST "http://127.0.0.1:8000/larkm" \
        -H 'Content-Type: application/json' \
        -d '{"shoulder": "x1", "target": "https://digital.lib.sfu.ca"}'

    If "shoulder" is absent from the request body, larkm will use the default
    shoulder specified in its config.

    - **ark**: the ARK to create, consisting of an ARK and a target URL.
    """
    config["allowed_shoulders"].insert(0, config["default_shoulder"])

    # Validate provided shoulder if provided.
    if ark.shoulder is not None:
        for sh in config["allowed_shoulders"]:
            if ark.shoulder not in config["allowed_shoulders"]:
                raise HTTPException(status_code=422, detail="Provided shoulder is invalid.")

    # Validate shoulder of provided ARK string.
    if ark.ark_string is not None:
        for sh in config["allowed_shoulders"]:
            if ark.ark_string.startswith(sh) is False:
                raise HTTPException(status_code=422, detail="ARK contains an invalid shoulder.")

    if ark.shoulder is None:
        ark.shoulder = config["default_shoulder"]
    if ark.ark_string is None:
        identifier = uuid4()
        ark.ark_string = f'ark:/{config["NAAN"]}/{ark.shoulder}{identifier}'

    # Add it to test_arks so it can be requested by a client.
    test_arks[ark.ark_string.strip()] = ark.target.strip()
    return {"ark": ark}


@app.put("/larkm/ark:/{naan}/{identifier}", response_model=Ark)
def update_ark(naan: str, identifier: str, ark: Ark):
    """
    Update an ARK with a new target. Sample query:

    curl -v -X PUT "http://127.0.0.1:8000/larkm/ark:/99999/12" \
        -H 'Content-Type: application/json' \
        -d '{"ark_string": "ark:/99999/12", "target": "https://summit.sfu.ca"}'

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

    curl -v -X DELETE "http://127.0.0.1:8000/larkm/ark:/99999/12"

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
