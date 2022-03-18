from typing import Optional
from fastapi import FastAPI, Response, Request, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from uuid import uuid4
import sqlite3
import json

with open("larkm.json", "r") as config_file:
    config = json.load(config_file)

app = FastAPI()


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
    ark_string = f'ark:/{naan}/{identifier}'
    try:
        con = sqlite3.connect(config["sqlite_db_path"])
        con.row_factory = sqlite3.Row
        cur = con.cursor()
        cur.execute("select * from arks where ark_string = :a_s", {"a_s": ark_string})
        record = cur.fetchone()
        if record is None:
            con.close()
            raise HTTPException(status_code=404, detail="ARK not found")
        con.close()
    except sqlite3.DatabaseError as e:
        # @todo: log (do not add to response!) str(e).
        raise HTTPException(status_code=500)

    if info is None:
        return RedirectResponse(record['target'])
    else:
        erc = f"erc:\nwho: {record['erc_who']}\nwhat: {record['erc_what']}\nwhen: {record['erc_when']}\nwhere: {record['erc_where']}\n"
        config["allowed_shoulders"].insert(0, config["default_shoulder"])
        if len(record['policy']) > 0:
            policy = "policy: " + record['policy']
        else:
            for sh in config["allowed_shoulders"]:
                if ark_string.startswith(sh):
                    policy = "policy: " + config["committment_statement"][sh]
                else:
                    policy = "policy: " + config["committment_statement"]["default"]

        return Response(content=erc + policy + "\n\n", media_type="text/plain")


@app.get("/larkm")
def read_ark(request: Request, ark_string: Optional[str] = '', target: Optional[str] = ''):
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
    if len(config["trusted_ips"]) > 0 and request.client.host not in config["trusted_ips"]:
        raise HTTPException(status_code=403)

    try:
        con = sqlite3.connect(config["sqlite_db_path"])
        con.row_factory = sqlite3.Row
        cur = con.cursor()
        if ark_string:
            cur.execute("select * from arks where ark_string=:a_s", {"a_s": ark_string})
        if target:
            cur.execute("select * from arks where target=:t", {"t": target})
        record = cur.fetchone()
        con.close()

        if record is not None:
            return {"ark_string": record['ark_string'], "target": record['target']}
        else:
            raise HTTPException(status_code=404, detail="ARK not found")
    except sqlite3.DatabaseError as e:
        # @todo: log (do not add to response!) str(e).
        raise HTTPException(status_code=500)


@app.post("/larkm", status_code=201)
def create_ark(request: Request, ark: Ark):
    """
    Create a new ARK, optionally minting a new ARK. Clients can provide
    an identifier string and/or a shoulder. If either of these is not provided,
    larkm will provide one. If an identifier is provided, it should not contain
    a shoulder, since larkm will always add a shoulder to new ARKs. Clients
    cannot provide a NAAN. Clients must always provide a target.

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
    if len(config["trusted_ips"]) > 0 and request.client.host not in config["trusted_ips"]:
        raise HTTPException(status_code=403)

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
        ark.identifier = str(uuid4())

    ark.ark_string = f'ark:/{config["NAAN"]}/{ark.shoulder}{ark.identifier}'

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

    try:
        ark_data = (ark.shoulder, ark.identifier, ark.ark_string, ark.target, ark.who, ark.what, ark.when, ark.where, ark.policy)
        con = sqlite3.connect(config["sqlite_db_path"])
        cur = con.cursor()
        cur.execute("insert into arks values (?,?,?,?,?,?,?,?,?)", ark_data)
        con.commit()
        con.close()
    except sqlite3.DatabaseError as e:
        # @todo: log (do not add to response!) str(e).
        print(str(e))
        raise HTTPException(status_code=500)
    return {"ark": ark}


@app.put("/larkm/ark:/{naan}/{identifier}")
def update_ark(request: Request, naan: str, identifier: str, ark: Ark):
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
    if len(config["trusted_ips"]) > 0 and request.client.host not in config["trusted_ips"]:
        raise HTTPException(status_code=403)

    ark_string = f'ark:/{naan}/{identifier}'.strip()
    if ark_string != ark.ark_string:
        raise HTTPException(status_code=409, detail="NAAN/identifier combination and ark_string do not match.")

    try:
        con = sqlite3.connect(config["sqlite_db_path"])
        con.row_factory = sqlite3.Row
        cur = con.cursor()
        cur.execute("select * from arks where ark_string = :a_s", {"a_s": ark_string})
        record = cur.fetchone()
        if record is None:
            con.close()
            raise HTTPException(status_code=404, detail="ARK not found")
        con.close()
    except sqlite3.DatabaseError as e:
        # @todo: log (do not add to response!) str(e).
        raise HTTPException(status_code=500)

    old_ark = dict(zip(record.keys(), record))

    # shoulder, identifier, and ark_string cannot be updated.
    ark.shoulder = old_ark['shoulder']
    ark.identifier = old_ark['identifier']
    ark.ark_string = old_ark['ark_string']
    # Only update ark properties that are in the request body.
    if ark.target is None:
        ark.target = old_ark['target']
    if ark.who is None:
        ark.who = old_ark['erc_who']
    if ark.what is None:
        ark.what = old_ark['erc_what']
    if ark.when is None:
        ark.when = old_ark['erc_when']
    if ark.where is None:
        ark.where = old_ark['erc_where']
    if ark.policy is None:
        ark.policy = old_ark['policy']

    try:
        ark_data = (ark.shoulder, ark.identifier, ark.ark_string, ark.target, ark.who, ark.what, ark.when, ark.where, ark.policy, ark.ark_string)
        con = sqlite3.connect(config["sqlite_db_path"])
        cur = con.cursor()
        cur.execute("update arks set shoulder = ?, identifier = ?, ark_string = ?, target = ?, erc_who = ?, erc_what = ?, erc_when = ?, erc_where = ?, policy = ? where ark_string = ?", ark_data)
        con.commit()
        con.close()
    except sqlite3.DatabaseError as e:
        # @todo: log (do not add to response!) str(e).
        print(str(e))
        raise HTTPException(status_code=500)

    return {"ark": ark}


@app.delete("/larkm/ark:/{naan}/{identifier}", status_code=204)
def delete_ark(request: Request, naan: str, identifier: str):
    """
    Given an ARK string, delete the ARK. Sample query:

    curl -v -X DELETE "http://127.0.0.1:8000/larkm/ark:/12345/12"

    - **naan**: the NAAN portion of the ARK.
    - **identifier**: the identifier portion of the ARK.
    """
    if len(config["trusted_ips"]) > 0 and request.client.host not in config["trusted_ips"]:
        raise HTTPException(status_code=403)

    ark_string = f'ark:/{naan}/{identifier}'

    try:
        con = sqlite3.connect(config["sqlite_db_path"])
        cur = con.cursor()
        cur.execute("select ark_string from arks where ark_string = :a_s", {"a_s": ark_string})
        record = cur.fetchone()
        if record is None:
            con.close()
            raise HTTPException(status_code=404, detail="ARK not found")
        con.close()
    except sqlite3.DatabaseError as e:
        # @todo: log (do not add to response!) str(e).
        raise HTTPException(status_code=500)

    # If ARK found, delete it.
    else:
        try:
            con = sqlite3.connect(config["sqlite_db_path"])
            cur = con.cursor()
            cur.execute("delete from arks where ark_string=:a_s", {"a_s": ark_string})
            con.commit()
            con.close()
        except sqlite3.DatabaseError as e:
            # @todo: log (do not add to response!) str(e).
            raise HTTPException(status_code=500)
