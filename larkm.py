from typing import Optional
from typing_extensions import Annotated
from fastapi import FastAPI, Response, Request, Header, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from uuid import uuid4
import copy
import re
import sqlite3
import json
import logging
from datetime import datetime
import time
import os
from whoosh import index
from whoosh.qparser import QueryParser

with open("larkm.json", "r") as config_file:
    config = json.load(config_file)
    config["allowed_shoulders"].insert(0, config["default_shoulder"])

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


@app.get("/ark:{naan}/{identifier}")
@app.get("/ark:/{naan}/{identifier}")
def resolve_ark(request: Request, naan: str, identifier: str, info: Optional[str] = None, authorization: Annotated[str | None, Header()] = None):
    """
    The ARK resolver. Redirects the client to the target URL associated with the ARK.
    Sample request:

    curl -L "http://127.0.0.1:8000/ark:12345/x9062cdde7-f9d6-48bb-be17-bd3b9f441ec4"

    - **naan**: the NAAN portion of the ARK.
    - **identifier**: the identifier portion of the ARK. A v4 UUID prepended
      with a 2-character shoulder (in this example, "x9").
    - **info**: As described in the ARK specification, '?info' appended
      to the ARK string should return a committment statement and resource metadata.
    """
    ark_string = f'ark:{naan}/{identifier}'

    ark_string = normalize_ark_string(ark_string)
    if not ark_string:
        raise HTTPException(status_code=422, detail="Invalid ARK string.")

    if len(config["private_shoulders"]) > 0:
        shoulder = identifier[:2]
        private_shoulders = list(config["private_shoulders"].keys())
        if shoulder in private_shoulders:
            if request.client.host not in config["private_shoulders"][shoulder]:
                message = f"Resolution of ARK with a private shoulder ({ark_string}) from an unregistered IP address ({request.client.host}): resolve_ark()"
                log_request('WARNING', request.client.host, '', request.headers, message)
                raise HTTPException(status_code=403)

        if len(config["api_keys"]) > 0 and authorization not in config["api_keys"]:
            message = f"API key {authorization} not configured."
            log_request('WARNING', request.client.host, '', request.headers, message)
            raise HTTPException(status_code=403)

    try:
        con = sqlite3.connect(config["sqlite_db_path"])
        con.row_factory = sqlite3.Row
        cur = con.cursor()
        cur.execute("select * from arks where ark_string = :a_s", {"a_s": ark_string})
        record = cur.fetchone()
        if record is None:
            con.close()
            if config["log_file_path"]:
                log_request('INFO', request.client.host, ark_string, request.headers, "ARK not found")
            raise HTTPException(status_code=404, detail="ARK not found")
        con.close()
    except sqlite3.DatabaseError as e:
        # @todo: log (do not add to response!) str(e).
        raise HTTPException(status_code=500)

    if info is None:
        if config["log_file_path"]:
            log_request('INFO', request.client.host, ark_string, request.headers, 'Resolution')
        return RedirectResponse(record['target'])
    else:
        erc = f"erc:\nwho: {record['erc_who']}\nwhat: {record['erc_what']}\nwhen: {record['erc_when']}\nwhere: {record['erc_where']}\n"
        if len(record['policy']) > 0:
            policy = "policy: " + record['policy']
        else:
            for sh in config["allowed_shoulders"]:
                if ark_string.startswith(sh):
                    policy = "policy: " + config["committment_statements"][sh]
                else:
                    policy = "policy: " + config["committment_statements"]["default"]
        if config["log_file_path"]:
            log_request('INFO', request.client.host, ark_string, request.headers, '?info')
        return Response(content=erc + policy + "\n\n", media_type="text/plain")


@app.get("/larkm/search")
def search_arks(request: Request, q: Optional[str] = '', page=1, page_size=20, authorization: Annotated[str | None, Header()] = None):
    """
    Endpoint for searching the Whoosh index of ARK metadata. Sample request:

    curl "http://127.0.0.1:8000/larkm/search?q=erc_what:example"

    - **q**: the Whoosh query, using Whoosh's default query language. Must be URL escaped.
      See the README for more information.
    - **page**: the page number to retrieve from the results.
    - **page_size**: the number of results to include in the page.
    """
    if len(config["trusted_ips"]) > 0 and request.client.host not in config["trusted_ips"]:
        message = f"Request from untrusted IP address: search_arks()"
        log_request('WARNING', request.client.host, '', request.headers, message)
        raise HTTPException(status_code=403)

    if len(config["api_keys"]) > 0 and authorization not in config["api_keys"]:
        message = f"API key {authorization} not configured."
        log_request('WARNING', request.client.host, '', request.headers, message)
        raise HTTPException(status_code=403)

    if not os.path.exists(config['whoosh_index_dir_path']):
        raise HTTPException(status_code=204)

    # Validate values provided in date_created and date_modified fields.
    request_args = dict(request.query_params)
    fields_to_validate = ['date_created', 'date_modified']
    if 'q' in request_args:
        field_queries = request_args['q'].split('&')
        for field_query in field_queries:
            field_name = field_query.split(':')[0]
            if field_name in fields_to_validate:
                field_value = field_query.split(':')[1]
                if 'to'.lower() in field_value.lower():
                    # We have a range query.
                    range_dates = field_value.lower().split('to')
                    for range_date in range_dates:
                        if validate_date(range_date.strip(' []')) is False:
                            raise HTTPException(status_code=422, detail=range_date.strip(' []') + " in " + field_name + " is not not a valid date.")
                else:
                    # Not a range query.
                    if validate_date(field_value) is False:
                        raise HTTPException(status_code=422, detail=field_value.strip(' ') + " in " + field_name + " is not not a valid date.")

    idx = index.open_dir(config['whoosh_index_dir_path'])

    query_parser = QueryParser("identifier", schema=idx.schema)
    query = query_parser.parse(q)
    with idx.searcher() as searcher:
        results = searcher.search_page(query, int(page), pagelen=int(page_size))
        number_of_results = len(results)
        identifier_list = list()
        for doc in results:
            identifier_list.append(doc['identifier'])

        if len(identifier_list) == 0:
            return {"num_results": number_of_results, "page": page, "page_size": page_size, "arks": []}

        try:
            con = sqlite3.connect(config["sqlite_db_path"])
            con.row_factory = sqlite3.Row
            cur = con.cursor()
            identifier_list_string = ','.join(f'"{i}"' for i in identifier_list)
            # identifier_list_string is safe to use here since it is not user input, it is
            # comprised of UUIDs that are validated using regex at the time of creation
            # in create_ark().
            cur.execute("select * from arks where identifier IN (" + identifier_list_string + ")")
            arks = cur.fetchmany(len(identifier_list))
            con.close()
        except sqlite3.DatabaseError as e:
            log_request('ERROR', request.client.host, ark_string, request.headers, str(e))
            raise HTTPException(status_code=500)

    if len(arks) == 0:
        return {"num_results": number_of_results, "page": page, "page_size": page_size, "arks": []}
    else:
        return_list = list()
        for ark in arks:
            return_list.append(ark)
    return {"num_results": number_of_results, "page": page, "page_size": page_size, "arks": return_list}


@app.post("/larkm", status_code=201)
def create_ark(request: Request, ark: Ark, authorization: Annotated[str | None, Header()] = None):
    """
    Create/mint a new ARK. Clients can provide an identifier string and/or
    a shoulder. If either of these is not provided, larkm will provide one.
    If a UUID v4 identifier is provided, it should not contain a shoulder,
    since larkm will always add a shoulder to new ARKs. Clients cannot
    provide a NAAN. Clients must always provide a "target" value.

    "where" always gets the value of ark_string.

    If the UUID that is provided is already in use, larkm will responde to the POST
    request with an HTTP `409` with the body `{"detail":"UUID already in use."}`.

    Sample request with an provided ID/name and shoulder:

    curl -v -X POST "http://127.0.0.1:8000/larkm" \
        -H 'Content-Type: application/json' \
        -d '{"shoulder": "x1", "identifier": "fde97fb3-634b-4232-b63e-e5128647efe7", "target": "https://digital.lib.sfu.ca"}'

    Sample request with only a 'where', an identifier and a name, which asks larkm to
    generate an ARK string based on the NAAN specified in configuration settings, the
    default shoulder, and the provided ID/name:

    curl -v -X POST "http://127.0.0.1:8000/larkm" \
        -H 'Content-Type: application/json' \
        -d '{"identifier": "fde97fb3-634b-4232-b63e-e5128647efe7", "target": "https://digital.lib.sfu.ca"}'

    Sample request with only a 'where' and a shoulder, which asks larkm to generate
    an ARK string based on the NAAN specified in configuration settings and the supplied
    shoulder. If the ID/name is not provided, larkm will provide one in the form of a
    v4 UUID:

    curl -v -X POST "http://127.0.0.1:8000/larkm" \
        -H 'Content-Type: application/json' \
        -d '{"shoulder": "x1", "target": "https://digital.lib.sfu.ca"}'

    Sample request with no 'where' or shoulder. larkm will generate an ARK using
    the configured NAAN, the default shoulder, and a v4 UUID.

    curl -v -X POST "http://127.0.0.1:8000/larkm" \
        -H 'Content-Type: application/json' \
        -d '{"target": "https://digital.lib.sfu.ca"}'

    Sample request with ERC metadata values. ERC elements ("who", "what", "when")
    not included in the request body are given defaults from config. The ARK's 'target'
    is given the value of the ARK's required 'where' value.

    curl -v -X POST "http://127.0.0.1:8000/larkm" \
        -H 'Content-Type: application/json' \
        -d '{"who": "Jordan, Mark", "what": "GitBags", "when": "2014", "target": "https://github.com/mjordan/GitBags"}'

    - **ark**: the ARK to create.
    """
    if len(config["trusted_ips"]) > 0 and request.client.host not in config["trusted_ips"]:
        message = f"Request from untrusted IP address: create_ark()"
        log_request('WARNING', request.client.host, '', request.headers, message)
        raise HTTPException(status_code=403)

    if len(config["api_keys"]) > 0 and authorization not in config["api_keys"]:
        message = f"API key {authorization} not configured: create_ark()"
        log_request('WARNING', request.client.host, '', request.headers, message)
        raise HTTPException(status_code=403)

    if ark.target is None:
        raise HTTPException(status_code=422, detail="A 'target' value is required.")

    # Validate shoulder if provided.
    if ark.shoulder is not None:
        for sh in config["allowed_shoulders"]:
            if ark.shoulder not in config["allowed_shoulders"]:
                raise HTTPException(status_code=422, detail="Provided shoulder is invalid.")

    # Validate UUID if provided.
    if ark.identifier is not None:
        if not re.match('^[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89aAbB][a-f0-9]{3}-[a-f0-9]{12}$', ark.identifier):
            raise HTTPException(status_code=422, detail=f"Provided UUID {ark.identifier} is invalid.")

        # See if provided UUID is already being used.
        try:
            con = sqlite3.connect(config["sqlite_db_path"])
            con.row_factory = sqlite3.Row
            cur = con.cursor()
            cur.execute("select * from arks where identifier = :a_s", {"a_s": ark.identifier})
            record = cur.fetchone()
            if record is not None:
                con.close()
                raise HTTPException(status_code=409, detail=f"UUID {ark.identifier} already in use.")
            con.close()
        except sqlite3.DatabaseError as e:
            log_request('ERROR', request.client.host, ark_string, request.headers, str(e))
            raise HTTPException(status_code=500)

    # See if provided 'target' value is already being used.
    try:
        con = sqlite3.connect(config["sqlite_db_path"])
        con.row_factory = sqlite3.Row
        cur = con.cursor()
        cur.execute("select * from arks where target = :a_s", {"a_s": ark.target})
        record = cur.fetchone()
        if record is not None:
            con.close()
            raise HTTPException(status_code=409, detail=f"'target' value {ark.target} already in use.")
        con.close()
    except sqlite3.DatabaseError as e:
        log_request('ERROR', request.client.host, ark_string, request.headers, str(e))
        raise HTTPException(status_code=500)

    # Assemble the ARK. Generate parts the client didn't provide.
    if ark.shoulder is None:
        ark.shoulder = config["default_shoulder"]
    if ark.identifier is None:
        ark.identifier = str(uuid4())

    ark.ark_string = f'ark:{config["NAAN"]}/{ark.shoulder}{ark.identifier}'

    if ark.who is None:
        ark.who = config["erc_metadata_defaults"]["who"]
    if ark.what is None:
        ark.what = config["erc_metadata_defaults"]["what"]
    if ark.when is None:
        ark.when = config["erc_metadata_defaults"]["when"]
    if ark.policy is None:
        if ark.shoulder in config["committment_statements"].keys():
            ark.policy = config["committment_statements"][ark.shoulder]
        else:
            ark.policy = config["committment_statements"]['default']

    ark.where = ark.ark_string

    try:
        ark_data = (ark.shoulder, ark.identifier, ark.ark_string, ark.target, ark.who, ark.what, ark.when, ark.where, ark.policy)
        con = sqlite3.connect(config["sqlite_db_path"])
        cur = con.cursor()
        cur.execute("insert into arks values (datetime(), datetime(), ?,?,?,?,?,?,?,?,?)", ark_data)
        con.commit()
        con.close()
    except sqlite3.DatabaseError as e:
        log_request('ERROR', request.client.host, ark_string, request.headers, str(e))
        raise HTTPException(status_code=500)

    urls = dict()
    if len(config["resolver_hosts"]["local"]) > 0:
        urls['local'] = f'{config["resolver_hosts"]["local"].rstrip("/")}/{ark.ark_string}'
    if len(config["resolver_hosts"]["global"]) > 0:
        urls['global'] = f'{config["resolver_hosts"]["global"].rstrip("/")}/{ark.ark_string}'

    return {"ark": ark, "urls": urls}


@app.put("/larkm/ark:{naan}/{identifier}")
def update_ark(request: Request, naan: str, identifier: str, ark: Ark, authorization: Annotated[str | None, Header()] = None):
    """
    Update an ARK with new metadata, or policy statement. Shoulders,
    identifiers, and ark_strings cannot be updated. ark_string is a required
    body field. 'where' always gets the value of ark_string. Sample query:

    curl -v -X PUT "http://127.0.0.1:8000/larkm/ark:12345/x931fd9bec-0bb6-4b6a-a08b-19554e6d711d" \
        -H 'Content-Type: application/json' \
        -d '{"ark_string": "ark:12345/x931fd9bec-0bb6-4b6a-a08b-19554e6d711d", "target": "https://example.com/foo"}'

    - **naan**: the NAAN portion of the ARK.
    - **identifier**: the identifier portion of the ARK, which will include a shoulder.
    """
    if len(config["trusted_ips"]) > 0 and request.client.host not in config["trusted_ips"]:
        message = f"Request from untrusted IP address: update_ark()"
        log_request('WARNING', request.client.host, ark_string, request.headers, message)
        raise HTTPException(status_code=403)

    if len(config["api_keys"]) > 0 and authorization not in config["api_keys"]:
        message = f"API key {authorization} not configured: update_ark()"
        log_request('WARNING', request.client.host, '', request.headers, message)
        raise HTTPException(status_code=403)

    if ark.ark_string is None:
        raise HTTPException(status_code=422, detail="When updatating ARKs, the ark_string must be provided in the request body.")

    ark_string = f'ark:{naan}/{identifier}'.strip()
    if ark_string != ark.ark_string:
        raise HTTPException(status_code=409, detail="NAAN/identifier combination and ark_string do not match.")

    # 'where' cannot be updated.
    if ark.where is not None:
        raise HTTPException(status_code=409, detail="\'where\' is automatically assigned the value of the ark string and cannot be updated.")

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
        log_request('ERROR', request.client.host, ark_string, request.headers, str(e))
        raise HTTPException(status_code=500)

    old_ark = dict(zip(record.keys(), record))

    # shoulder, identifier, and ark_string cannot be updated.
    ark.shoulder = old_ark['shoulder']
    ark.identifier = old_ark['identifier']
    ark.ark_string = old_ark['ark_string']

    # Only update ark properties that are in the request body, except for target, which
    # always gets the value of 'erc_where'.
    if ark.target is None:
        ark.target = old_ark['target']
    if ark.who is None:
        ark.who = old_ark['erc_who']
    if ark.what is None:
        ark.what = old_ark['erc_what']
    if ark.when is None:
        ark.when = old_ark['erc_when']
    if ark.policy is None:
        ark.policy = old_ark['policy']

    ark.where = ark.ark_string

    try:
        ark_data = (ark.shoulder, ark.identifier, ark.ark_string, ark.target, ark.who, ark.what, ark.when, ark.where, ark.policy, ark.ark_string)
        con = sqlite3.connect(config["sqlite_db_path"])
        cur = con.cursor()
        cur.execute("update arks set date_modified = datetime(), shoulder = ?, identifier = ?, ark_string = ?, target = ?, erc_who = ?, erc_what = ?, erc_when = ?, erc_where = ?, policy = ? where ark_string = ?", ark_data)
        con.commit()
        con.close()
    except sqlite3.DatabaseError as e:
        log_request('ERROR', request.client.host, ark_string, request.headers, str(e))
        raise HTTPException(status_code=500)

    urls = dict()
    if len(config["resolver_hosts"]["local"]) > 0:
        urls['local'] = f'{config["resolver_hosts"]["local"].rstrip("/")}/{ark.ark_string}'
    if len(config["resolver_hosts"]["global"]) > 0:
        urls['global'] = f'{config["resolver_hosts"]["global"].rstrip("/")}/{ark.ark_string}'

    return {"ark": ark, "urls": urls}


@app.delete("/larkm/ark:{naan}/{identifier}", status_code=204)
def delete_ark(request: Request, naan: str, identifier: str, authorization: Annotated[str | None, Header()] = None):
    """
    Given an ARK string, delete the ARK. Sample query:

    curl -v -X DELETE "http://127.0.0.1:8000/larkm/ark:12345/x931fd9bec-0bb6-4b6a-a08b-19554e6d711d"

    - **naan**: the NAAN portion of the ARK.
    - **identifier**: the identifier portion of the ARK.
    """
    if len(config["trusted_ips"]) > 0 and request.client.host not in config["trusted_ips"]:
        message = f"Request from untrusted IP address: delete_ark()"
        log_request('WARNING', request.client.host, ark_string, request.headers, message)
        raise HTTPException(status_code=403)

    if len(config["api_keys"]) > 0 and authorization not in config["api_keys"]:
        message = f"API key {authorization} not configured: delete_ark()"
        log_request('WARNING', request.client.host, '', request.headers, message)
        raise HTTPException(status_code=403)

    ark_string = f'ark:{naan}/{identifier}'

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
        log_request('ERROR', request.client.host, ark_string, request.headers, str(e))
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
            log_request('ERROR', request.client.host, ark_string, request.headers, str(e))
            raise HTTPException(status_code=500)


@app.get("/larkm/config")
def return_config(request: Request, authorization: Annotated[str | None, Header()] = None):
    """
    Returns a subset of larkm's configuration data to the client.
    """
    if len(config["trusted_ips"]) > 0 and request.client.host not in config["trusted_ips"]:
        message = f"Request from untrusted IP address: return_config()"
        log_request('WARNING', request.client.host, '', request.headers, message)
        raise HTTPException(status_code=403)

    if len(config["api_keys"]) > 0 and authorization not in config["api_keys"]:
        message = f"API key {authorization} not configured: return_config()"
        log_request('WARNING', request.client.host, '', request.headers, message)
        raise HTTPException(status_code=403)

    # Remove configuration data the client doesn't need to know.
    subset = copy.deepcopy(config)
    del subset['trusted_ips']
    del subset['api_keys']
    del subset['private_shoulders']
    del subset['sqlite_db_path']
    del subset['log_file_path']
    del subset['whoosh_index_dir_path']
    return subset


def log_request(level, client_ip, ark_string, request_headers, event_type):
    """
    Assembles a tab-delmited log entry and writes it to the log file.

    - **level**: INFO, WARNING, or ERROR from the standard Python logging levels.
    - **client_ip**: the IP address of the client triggering the event.
    - **ark_string**: the ARK string from the event being logged.
    - **request_headers**: the HTTP headers from the FastAPI Request object.
    - **event_type**: a brief description of the event.
    """
    if 'referer' in request_headers:
        referer = request_headers['referer']
    else:
        referer = 'null'

    now = datetime.now()
    date_format = "%Y-%m-%d %H:%M:%S"

    entry = f"{now.strftime(date_format)}\t{client_ip}\t{referer}\t{ark_string}\t{event_type}"
    logging.basicConfig(level=logging.INFO, filename=config['log_file_path'], filemode='a', format='%(message)s')
    if level == 'ERROR':
        logging.error(entry)
    elif level == 'WARNING':
        logging.warning(entry)
    else:
        logging.info(entry)


def normalize_ark_string(ark_string):
    """
    Reconsitutues the hypens in the UUID portion of the ARK string. The ARK
    spec requires hyphens to be insignificant.

    Assumes that the ARK string does not contain the / after 'ark:', that
    the NAAN is 5 characters long, and that the shoulder is present and is two
    characters long.

    - **ark_string**: an ARK string in the form ark:/12345/y2ee65209e67fe-45fc-a9721da0b602c742
      where the UUID part of the string contains a 2-character shoulder and 0 or more hyphens (-).

    Returns the reconstituted ARK string or False if the UUID is not a valid UUID v4.
    """
    # Everthing up to and including the shoulder.
    prefix = ark_string[:12]
    # Everything after the shoulder; assumed to be a UUID with or without hyphens.
    suffix = ark_string[12:]

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


def validate_date(date_string):
    """
    Validates a yyyy-mm-dd date string.
    - **date**: the date string to validate.
    """
    try:
        time.strptime(date_string, '%Y-%m-%d')
    except ValueError:
        return False

    # If there's no ValueError, date validates.
    return True
