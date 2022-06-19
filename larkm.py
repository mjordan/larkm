from typing import Optional
from fastapi import FastAPI, Response, Request, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from uuid import uuid4
import copy
import re
import sqlite3
import json
import logging
from datetime import datetime

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
def resolve_ark(request: Request, naan: str, identifier: str, info: Optional[str] = None):
    """
    The ARK resolver. Redirects the client to the target URL
    associated with the ARK. Sample query:

    curl -L "http://127.0.0.1:8000/ark:/12345/x9062cdde7-f9d6-48bb-be17-bd3b9f441ec4"
"

    - **naan**: the NAAN portion of the ARK.
    - **identifier**: the identifier portion of the ARK. A v4 UUID prepended
      with a 2-character shoulder (in this example, "x9").
    - **info**: As described in the ARK specification, '?info' appended
      to the ARK string should return a committment statement and resource
      metadata. For now, return the configured committment statement only.
    """
    ark_string = f'ark:/{naan}/{identifier}'

    ark_string = normalize_ark_string(ark_string)
    if not ark_string:
        raise HTTPException(status_code=422, detail="Invalid ARK string.")

    try:
        con = sqlite3.connect(config["sqlite_db_path"])
        con.row_factory = sqlite3.Row
        cur = con.cursor()
        cur.execute("select * from arks where ark_string = :a_s", {"a_s": ark_string})
        record = cur.fetchone()
        if record is None:
            con.close()
            if config["log_file_path"]:
                log_request(ark_string, request.client.host, request.headers, "ARK not found")
            raise HTTPException(status_code=404, detail="ARK not found")
        con.close()
    except sqlite3.DatabaseError as e:
        # @todo: log (do not add to response!) str(e).
        raise HTTPException(status_code=500)

    if info is None:
        if config["log_file_path"]:
            log_request(ark_string, request.client.host, request.headers, record['target'])
        return RedirectResponse(record['target'])
    else:
        erc = f"erc:\nwho: {record['erc_who']}\nwhat: {record['erc_what']}\nwhen: {record['erc_when']}\nwhere: {record['erc_where']}\n"
        config["allowed_shoulders"].insert(0, config["default_shoulder"])
        if len(record['policy']) > 0:
            policy = "policy: " + record['policy']
        else:
            for sh in config["allowed_shoulders"]:
                if ark_string.startswith(sh):
                    policy = "policy: " + config["committment_statements"][sh]
                else:
                    policy = "policy: " + config["committment_statements"]["default"]
        if config["log_file_path"]:
            log_request(ark_string, request.client.host, request.headers, 'info')
        return Response(content=erc + policy + "\n\n", media_type="text/plain")


@app.get("/larkm")
def read_ark(request: Request, ark_string: Optional[str] = '', target: Optional[str] = ''):
    """
    Get the target URL associated with an ARK, or the ARK assoicated
    with a target URL. Sample query:

    curl "http://127.0.0.1:8000/larkm?ark_string=ark:/12345/x931fd9bec-0bb6-4b6a-a08b-19554e6d711d" or
    curl "http://127.0.0.1:8000/larkm?target=https://example.com/foo"

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

        urls = dict()
        if len(config["resolver_hosts"]["local"]) > 0:
            urls['local'] = f'{config["resolver_hosts"]["local"].rstrip("/")}/{record["ark_string"]}'
        if len(config["resolver_hosts"]["global"]) > 0:
            urls['global'] = f'{config["resolver_hosts"]["global"].rstrip("/")}/{record["ark_string"]}'

        if record is not None:
            return {"ark_string": record['ark_string'], "target": record['target'], "urls": urls}
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
    larkm will provide one. If a UUID v4 identifier is provided, it should not
    contain a shoulder, since larkm will always add a shoulder to new ARKs. Clients
    cannot provide a NAAN. Clients must always provide a target.

    If the UUID that is provided is already in use, larkm will responde to the POST
    request with an HTTP `409` with the body `{"detail":"UUID already in use."}`.

    Sample request with an provided ID/name and shoulder:

    curl -v -X POST "http://127.0.0.1:8000/larkm" \
        -H 'Content-Type: application/json' \
        -d '{"shoulder": "x1", "identifier": "fde97fb3-634b-4232-b63e-e5128647efe7", "target": "https://digital.lib.sfu.ca"}'

    Sample request with only a target and an identifier and a name, which asks larkm to
    generate an ARK string based on the NAAN specified in configuration settings, the
    default shoulder, and the provided ID/name:

    curl -v -X POST "http://127.0.0.1:8000/larkm" \
        -H 'Content-Type: application/json' \
        -d '{"identifier": "fde97fb3-634b-4232-b63e-e5128647efe7", "target": "https://digital.lib.sfu.ca"}'

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

    # Validate UUID if provided.
    if ark.identifier is not None:
        if not re.match('^[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89aAbB][a-f0-9]{3}-[a-f0-9]{12}$', ark.identifier):
            raise HTTPException(status_code=422, detail="Provided UUID is invalid.")

        # See if provided UUID is already being used.
        try:
            con = sqlite3.connect(config["sqlite_db_path"])
            con.row_factory = sqlite3.Row
            cur = con.cursor()
            cur.execute("select * from arks where identifier = :a_s", {"a_s": ark.identifier})
            record = cur.fetchone()
            if record is not None:
                con.close()
                raise HTTPException(status_code=409, detail="UUID already in use.")
            con.close()
        except sqlite3.DatabaseError as e:
            # @todo: log (do not add to response!) str(e).
            raise HTTPException(status_code=500)

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
    if ark.where is None or len(ark.where) == 0:
        ark.where = ark.target
    if ark.policy is None:
        if ark.shoulder in config["committment_statements"].keys():
            ark.policy = config["committment_statements"][ark.shoulder]
        else:
            ark.policy = config["committment_statements"]['default']

    try:
        ark_data = (ark.shoulder, ark.identifier, ark.ark_string, ark.target, ark.who, ark.what, ark.when, ark.where, ark.policy)
        con = sqlite3.connect(config["sqlite_db_path"])
        cur = con.cursor()
        cur.execute("insert into arks values (datetime(), datetime(), ?,?,?,?,?,?,?,?,?)", ark_data)
        con.commit()
        con.close()
    except sqlite3.DatabaseError as e:
        # @todo: log (do not add to response!) str(e).
        print(str(e))
        raise HTTPException(status_code=500)

    urls = dict()
    if len(config["resolver_hosts"]["local"]) > 0:
        urls['local'] = f'{config["resolver_hosts"]["local"].rstrip("/")}/{ark.ark_string}'
    if len(config["resolver_hosts"]["global"]) > 0:
        urls['global'] = f'{config["resolver_hosts"]["global"].rstrip("/")}/{ark.ark_string}'

    return {"ark": ark, "urls": urls}


@app.put("/larkm/ark:/{naan}/{identifier}")
def update_ark(request: Request, naan: str, identifier: str, ark: Ark):
    """
    Update an ARK with a new target, metadata, or policy statement. Shoulders,
    identifiers, and ark_strings cannot be updated. ark_string is a required
    body field. Sample query:

    curl -v -X PUT "http://127.0.0.1:8000/larkm/ark:/12345/x931fd9bec-0bb6-4b6a-a08b-19554e6d711d" \
        -H 'Content-Type: application/json' \
        -d '{"ark_string": "ark:/12345/x931fd9bec-0bb6-4b6a-a08b-19554e6d711d", "target": "https://example.com/foo"}'

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
        cur.execute("update arks set date_modified = datetime(), shoulder = ?, identifier = ?, ark_string = ?, target = ?, erc_who = ?, erc_what = ?, erc_when = ?, erc_where = ?, policy = ? where ark_string = ?", ark_data)
        con.commit()
        con.close()
    except sqlite3.DatabaseError as e:
        # @todo: log (do not add to response!) str(e).
        print(str(e))
        raise HTTPException(status_code=500)

    urls = dict()
    if len(config["resolver_hosts"]["local"]) > 0:
        urls['local'] = f'{config["resolver_hosts"]["local"].rstrip("/")}/{ark.ark_string}'
    if len(config["resolver_hosts"]["global"]) > 0:
        urls['global'] = f'{config["resolver_hosts"]["global"].rstrip("/")}/{ark.ark_string}'

    return {"ark": ark, "urls": urls}


@app.delete("/larkm/ark:/{naan}/{identifier}", status_code=204)
def delete_ark(request: Request, naan: str, identifier: str):
    """
    Given an ARK string, delete the ARK. Sample query:

    curl -v -X DELETE "http://127.0.0.1:8000/larkm/ark:/12345/x931fd9bec-0bb6-4b6a-a08b-19554e6d711d"

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


@app.get("/larkm/config")
def return_config():
    """
    Returns a subset of larkm's configuration data to the client.
    """
    if len(config["trusted_ips"]) > 0 and request.client.host not in config["trusted_ips"]:
        raise HTTPException(status_code=403)

    # Remove configuration data the client doesn't need to know.
    subset = copy.deepcopy(config)
    del subset['trusted_ips']
    del subset['sqlite_db_path']
    del subset['log_file_path']
    return subset


def log_request(ark_string, client_ip, request_headers, request_type):
    if 'referer' in request_headers:
        referer = request_headers['referer']
    else:
        referer = 'null'

    now = datetime.now()
    date_format = "%Y-%m-%d %H:%M:%S"

    entry = f"{now.strftime(date_format)}\t{client_ip}\t{ark_string}\t{request_type}\t{referer}"
    logging.basicConfig(level=logging.INFO, filename=config['log_file_path'], filemode='a', format='%(message)s')
    logging.info(entry)


def normalize_ark_string(ark_string):
    """
    Reconsitutues the hypens in the UUID portion of the ARK string. The ARK
    spec requires hyphens to be insignificant.

    Assumes that the ARK string contains the optional / after 'ark:', that
    the NAAN is 5 characters long, and that the shoulder is present and is two
    characters long.

    - **ark_string**: an ARK string in the form ark:/12345/y2ee65209e67fe-45fc-a9721da0b602c742
      where the UUID part of the string contains a 2-character shoulder and 0 or more hyphens (-).
    - **identifier**: the identifier portion of the ARK.

    Returns the reconstituted ARK string or False if the UUID is not a valid UUID v4.
    """

    # Everthing up to and including the shoulder.
    prefix = ark_string[:13]
    # Everything after the shoulder; assumed to be a UUID with or without hyphens.
    suffix = ark_string[13:]

    uuid_sans_hyphens = suffix.replace('-', '')
    group5 = uuid_sans_hyphens[20:]
    group4 = uuid_sans_hyphens[16:20]
    group3 = uuid_sans_hyphens[12:16]
    group2 = uuid_sans_hyphens[8:12]
    group1 = uuid_sans_hyphens[:8]

    reconstituted_uuid = f'{group1}-{group2}-{group3}-{group4}-{group5}'
    if not re.match('^[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89aAbB][a-f0-9]{3}-[a-f0-9]{12}$', reconstituted_uuid):
        return False

    reconstituted_ark_string = prefix + reconstituted_uuid

    return reconstituted_ark_string
