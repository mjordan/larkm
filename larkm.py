from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

app = FastAPI()


class Ark(BaseModel):
    ark_string: Optional[str] = None
    target: Optional[str] = None


# During development and for demo purposes only, we use an in-memory
# dictionary of ARKS that persists as long as the app is running in
# the dev web server. In production, ARKS would be stored in a db.
test_arks = dict({'ark:/19837/10': 'https://www.lib.sfu.ca'})


@app.get("/ark:/{naan}/{identifier}")
async def resolve_ark(naan: str, identifier: str):
    """
    The ARK resolver. Redirects the client to the target URL
    associated with the ARK. Sample query:

    curl -L "http://127.0.0.1:8000/ark:/19837/12"

    - **naan**: the nann portion of the ARK.
    - **identifier**: the identifier portion of the ARK.
    """
    ark = f'ark:/{naan}/{identifier}'
    if ark.strip() in test_arks.keys() and test_arks.get(ark) is not None:
        return RedirectResponse(test_arks[ark])
    else:
        raise HTTPException(status_code=404, detail="ARK not found")


@app.get("/larkm")
async def read_ark(ark: Optional[str] = '', target: Optional[str] = ''):
    """
    Get the target URL associated with an ARK, or the ARK assoicated
    with a target URL. Sample query:

    curl "http://127.0.0.1:8000/larkm?ark=ark:/19837/12" or
    curl "http://127.0.0.1:8000/larkm?target=https://www.lib.sfu.ca"

    - **ark**: the ARK the client wants to get the target for, in the
      form 'ark:/naan/id_string'.
    - **target**: the target the client wants to get the ark for, in
      the form of a fully qualified URL.
    """
    if ark.strip() in test_arks.keys():
        return {"ark": ark, "target": test_arks[ark]}
    else:
        raise HTTPException(status_code=404, detail="ARK not found")
    if len(target) > 0:
        for ark, target_url in test_arks.items():
            if target_url.strip() == target.strip():
                return {"ark": ark, "target": test_arks[ark]}
    # If no ARK found, raise a 404.
        raise HTTPException(status_code=404, detail="Target not found")


@app.post("/larkm", status_code=201)
async def create_ark(ark: Ark):
    """
    Create a new ARK. Sample query:

    curl -v -X POST  "http://127.0.0.1:8000/larkm" \
        -H 'Content-Type: application/json' \
        -d '{"ark_string": "ark:/19837/12", "target": "https://digital.lib.sfu.ca"}'

    - **ark**: the ARK to create, consisting of an ARK and a target URL.
    """
    # Add it to test_arks so it can be requested by a client.
    test_arks[ark.ark_string.strip()] = ark.target.strip()
    return {"ark": ark}


@app.put("/larkm/ark:/{naan}/{identifier}", response_model=Ark)
async def update_ark(naan: str, identifier: str, ark: Ark):
    """
    Update an ARK with a new target. Sample query:

    curl -v -X PUT  "http://127.0.0.1:8000/larkm/ark:/19837/12" \
        -H 'Content-Type: application/json' \
        -d '{"ark_string": "ark:/19837/12", "target": "https://summit.sfu.ca"}'

    - **naan**: the nann portion of the ARK.
    - **identifier**: the identifier portion of the ARK.
    """
    # Update the ARK in test_arks.
    ark_string = f'ark:/{naan}/{identifier}'
    if ark_string != ark.ark_string:
        raise HTTPException(status_code=409, detail="NAAN/identifier combination an ark_string do not match.")
    if ark.ark_string.strip() in test_arks.keys() and len(ark.target.strip()) > 0:
        test_arks[ark_string.strip()] = ark.target.strip()
        return {"ark_string": ark.ark_string, "target": ark.target}
