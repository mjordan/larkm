from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

app = FastAPI()


class Ark(BaseModel):
    ark_string: str
    target: str


# An in-memory list of ARKS that persists as long as the app is
# running in the dev web server.Ideally, ARKS would be storedin a db.
test_arks = dict({'ark:/19837/10': 'https://www.lib.sfu.ca'})


@app.get("/ark:/{naan}/{identifier}")
async def read_ark(naan: str, identifier: str):
    """
    ARK resolver. Redirects the client to the target URL
    associated with this ARK. Sample query:

    curl "http://127.0.0.1:8000/ark:/19837/12"

    - **naan**: the nann portion of the ARK.
    - **identifier**: the identifier portion of the ARK.
    """
    ark = f'ark:/{naan}/{identifier}'
    if ark in test_arks.keys():
        return RedirectResponse(test_arks[ark])
    else:
        raise HTTPException(status_code=404, detail="ARK not found")


@app.get("/larkm")
async def read_ark(ark: str = ''):
    """
    Get the target URL associated with an ARK. Sample query:

    curl "http://127.0.0.1:8000/larkm?ark=ark:/19837/12"

    - **ark**: the ARK the client wants to know everything about.
    """
    return {"ark": ark, "target": test_arks[ark]}


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
    test_arks[ark.ark_string] = ark.target
    return {"ark": ark}
