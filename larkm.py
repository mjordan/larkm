import os
import time
import copy
import re
import sqlite3
import json
from uuid import uuid4
import logging
from datetime import datetime
from typing import Optional

from typing_extensions import Annotated
from fastapi import FastAPI, Response, Request, Header, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from whoosh import index
from whoosh.qparser import QueryParser

config_file_path = os.getenv("LARKM_CONFIG_FILE_PATH") or "larkm.json"
with open(config_file_path, "r") as config_file:
    config = json.load(config_file)

app = FastAPI()


class Ark(BaseModel):
    naan: Optional[str] = None
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
def resolve_ark(
    request: Request,
    naan: str,
    identifier: str,
    info: Optional[str] = None,
):
    """
    The ARK resolver. Redirects the client to the target URL associated with the ARK.
    Sample request:

    curl -L "http://127.0.0.1:8000/ark:12345/x9062cdde7f9d6"

    - **naan**: the NAAN portion of the ARK.
    - **identifier**: the identifier portion of the ARK. The first 12 characters of a
      v4 UUID (with dashes removed) prepended with a 2-character shoulder (in this example, "x9").
    - **info**: As described in the ARK specification, '?info' appended
      to the ARK string should return a commitment statement and resource metadata.
    """
    ark_string = f"ark:{naan}/{identifier}"

    if naan not in config.keys():
        log_request(
            "ERROR",
            request.client.host,
            ark_string,
            request.headers,
            None,
            "Resolution attempt - invalid NAAN.",
        )
        raise HTTPException(status_code=422, detail="Invalid NAAN.")

    if config[naan]["default_shoulder"] not in config[naan]["allowed_shoulders"]:
        config[naan]["allowed_shoulders"].insert(0, config[naan]["default_shoulder"])

    try:
        con = sqlite3.connect(config[naan]["sqlite_db_path"])
        con.row_factory = sqlite3.Row
        cur = con.cursor()
        cur.execute(
            "select target from arks where ark_string = :a_s", {"a_s": ark_string}
        )
        record = cur.fetchone()
        if record is None:
            con.close()
            if config[naan]["log_file_path"]:
                log_request(
                    "INFO",
                    request.client.host,
                    ark_string,
                    request.headers,
                    None,
                    "ARK not found",
                )
            raise HTTPException(status_code=404, detail="ARK not found")
        con.close()
    except sqlite3.DatabaseError as e:
        log_request(
            "ERROR", request.client.host, ark_string, request.headers, None, str(e)
        )
        raise HTTPException(status_code=500)

    # No target.
    if len(record[0]) == 0:
        info_content = get_info_content(ark_string)

        if info_content is None:
            raise HTTPException(status_code=404, detail="ARK not found")

        # get_info_content() can also return an exception.
        if isinstance(info_content, Exception):
            log_request(
                "ERROR", request.client.host, ark_string, request.headers, None, str(e)
            )
            raise HTTPException(status_code=500)

        if config[naan]["log_file_path"]:
            log_request(
                "INFO",
                request.client.host,
                ark_string,
                request.headers,
                None,
                "ARK has no target",
            )
        return Response(info_content, media_type="text/plain")

    if info is None:
        if config[naan]["log_file_path"]:
            log_request(
                "INFO",
                request.client.host,
                ark_string,
                request.headers,
                None,
                f'Resolution to {record["target"]}',
            )
        return RedirectResponse(record["target"])
    else:
        info_content = get_info_content(ark_string)

        if info_content is None:
            raise HTTPException(status_code=404, detail="ARK not found")

        # get_info_content() can also return an exception.
        if isinstance(info_content, Exception):
            log_request(
                "ERROR", request.client.host, ark_string, request.headers, None, str(e)
            )
            raise HTTPException(status_code=500)

        if config[naan]["log_file_path"]:
            log_request(
                "INFO", request.client.host, ark_string, request.headers, None, "?info"
            )
        return Response(info_content, media_type="text/plain")


@app.get("/larkm/ark:{naan}/{identifier}")
@app.get("/larkm/ark:/{naan}/{identifier}")
def get_ark(
    request: Request,
    naan: str,
    identifier: str,
    authorization: Annotated[str | None, Header()] = None,
):
    """
    Retrieve all the ARK's data, for example to populate a form on an external CRUD tool.
    Sample request:

    curl "http://127.0.0.1:8000/larkm/ark:12345/x931fd9bec0bb6"

    - **naan**: the NAAN portion of the ARK.
    - **identifier**: the identifier portion of the ARK, which will include a shoulder.
    """
    check_access(request, naan, authorization)

    ark_string = f"ark:{naan}/{identifier}"

    try:
        con = sqlite3.connect(config[naan]["sqlite_db_path"])
        con.row_factory = sqlite3.Row
        cur = con.cursor()
        cur.execute("select * from arks where ark_string = :a_s", {"a_s": ark_string})
        record = cur.fetchone()
        if record is None:
            con.close()
            if config[naan]["log_file_path"]:
                log_request(
                    "INFO",
                    request.client.host,
                    ark_string,
                    request.headers,
                    authorization,
                    "ARK not found",
                )
            raise HTTPException(status_code=404, detail="ARK not found")
        con.close()
        ark = record
    except sqlite3.DatabaseError as e:
        log_request(
            "ERROR",
            request.client.host,
            ark_string,
            request.headers,
            authorization,
            str(e),
        )
        raise HTTPException(status_code=500)

    if config[naan]["log_file_path"]:
        log_request(
            "INFO",
            request.client.host,
            ark_string,
            request.headers,
            authorization,
            "ARK data retrieved.",
        )

    # Row objects aren't subscriptable so we need to convert it into a dict.
    record_to_return = dict()
    columns = [
        "date_created",
        "date_modified",
        "shoulder",
        "identifier",
        "ark_string",
        "target",
        "erc_who",
        "erc_what",
        "erc_when",
        "erc_where",
        "policy",
    ]
    for col, val in zip(columns, record):
        if col == "erc_where":
            record_to_return["erc_where"] = get_erc_where_value(naan, ark_string)
        else:
            record_to_return[col] = val

    return record_to_return


@app.post("/larkm", status_code=201)
def create_ark(
    request: Request, ark: Ark, authorization: Annotated[str | None, Header()] = None
):
    """
    Create/mint a new ARK. Clients must provide a NAAN, and may provide an identifier
    string and/or a shoulder. If either of these is not provided, larkm will provide one.
    If an identifier (either a full UUIDv4s or the first 12 characters of a UUIDv4 with
    dashes removed) is provided, it should not contain a shoulder, since larkm will always
    add a shoulder to new ARKs either based on the configured default shoulder or using
    the one provided in the "shoulder" key in the request body.

    If the identifier that is provided is already in use, larkm will respond to the POST
    request with an HTTP `409` with the body `{"detail":"Identifier <identifier> already in use."}`.

    Sample request with an provided identifier and shoulder:

    curl -v -X POST "http://127.0.0.1:8000/larkm" \
        -H 'Content-Type: application/json' \
        -d '{"shoulder": "x1", "naan": "99999", "identifier": "fde97fb3634b", "target": "https://digital.lib.sfu.ca"}'

    Sample request with only a target and a identifier, which asks larkm to
    generate an ARK string based on the default shoulder:

    curl -v -X POST "http://127.0.0.1:8000/larkm" \
        -H 'Content-Type: application/json' \
        -d '{"naan": "99999", "identifier": "fde97fb3-634b4232", "target": "https://digital.lib.sfu.ca"}'

    Sample request with only a target and a shoulder, which asks larkm to generate an ARK
    string based on the supplied NAAN and the supplied shoulder. If the identifier is not provided,
    larkm will provide one in the form of the first 12 characters of a UUIDv4 with dashes removed:

    curl -v -X POST "http://127.0.0.1:8000/larkm" \
        -H 'Content-Type: application/json' \
        -d '{"shoulder": "x1", "naan": "99999", "target": "https://digital.lib.sfu.ca"}'

    Sample request with no shoulder. larkm will generate an ARK using the provided NAAN,
    the default shoulder, and a identifier (first 12 characters of a UUIDv4 with dashes removed).

    curl -v -X POST "http://127.0.0.1:8000/larkm" \
        -H 'Content-Type: application/json' \
        -d '{"naan": "99999", "target": "https://digital.lib.sfu.ca"}'

    Sample request with ERC metadata values. ERC elements ("who", "what", "when")
    not included in the request body are given defaults from config.

    curl -v -X POST "http://127.0.0.1:8000/larkm" \
        -H 'Content-Type: application/json' \
        -d '{"naan": "99999", "who": "Jordan, Mark", "what": "GitBags", "when": "2014", "target": "https://github.com/mjordan/GitBags"}'

    As per the ARK specification, the ERC property "where" always gets the
    value of ark_string, regardless of whether it is provided in the request body.

    - **ark**: the ARK to create.
    """
    check_access(request, ark.naan, authorization)

    if (
        config[ark.naan]["default_shoulder"]
        not in config[ark.naan]["allowed_shoulders"]
    ):
        config[ark.naan]["allowed_shoulders"].insert(
            0, config[ark.naan]["default_shoulder"]
        )

    # Validate shoulder if provided.
    if ark.shoulder is not None:
        if ark.shoulder not in config[ark.naan]["allowed_shoulders"]:
            raise HTTPException(status_code=422, detail="Provided shoulder is invalid.")

    # Validate NAAN.
    if ark.naan is not None:
        if ark.naan != config[ark.naan]["naan"]:
            raise HTTPException(status_code=422, detail="Provided NAAN is invalid.")

    if (
        ark.policy is not None
        and config[ark.naan]["constrain_commitment_statements"] == "yes"
    ):
        raise HTTPException(
            status_code=422, detail="Providing a policy is not allowed."
        )

    # Validate identifer if provided.
    if ark.identifier is not None and len(ark.identifier) == 36:
        if validate_uuid(ark.identifier) is True:
            ark.identifier = generate_identifier(uuid=ark.identifier)
        else:
            raise HTTPException(
                status_code=422,
                detail=f"Provided UUID {ark.identifier} is invalid.",
            )
    elif ark.identifier is not None and len(ark.identifier) == 12:
        if validate_identifier(ark.identifier) is False:
            raise HTTPException(
                status_code=422,
                detail=f"Provided UUID {ark.identifier} is invalid.",
            )
    elif ark.identifier is not None and validate_identifier(ark.identifier) is False:
        raise HTTPException(
            status_code=422,
            detail=f"Provided identifier {ark.identifier} is invalid.",
        )
    else:
        ark.identifier = generate_identifier()

    # See if provided identifier is already being used.
    try:
        con = sqlite3.connect(config[ark.naan]["sqlite_db_path"])
        con.row_factory = sqlite3.Row
        cur = con.cursor()
        cur.execute(
            "select * from arks where identifier = :a_s", {"a_s": ark.identifier}
        )
        record = cur.fetchone()
        if record is not None:
            con.close()
            raise HTTPException(
                status_code=409,
                detail=f"Identifier {ark.identifier} already in use.",
            )
        con.close()
    except sqlite3.DatabaseError as e:
        log_request(
            "ERROR",
            request.client.host,
            ark.ark_string,
            request.headers,
            authorization,
            str(e),
        )
        raise HTTPException(status_code=500)

    # See if provided 'target' value is already being used.
    if ark.target is None:
        ark.target = ""
    else:
        check_target_already_registered(ark, request, authorization)

    # Assemble the ARK. Generate parts the client didn't provide.
    if ark.naan is None:
        ark.naan = config[ark.naan]["naan"]
    if ark.shoulder is None:
        ark.shoulder = config[ark.naan]["default_shoulder"]
    if ark.identifier is None:
        ark.identifier = generate_identifier()

    ark.ark_string = f"ark:{ark.naan}/{ark.shoulder}{ark.identifier}"

    if ark.who is None:
        ark.who = config[ark.naan]["erc_metadata_defaults"]["who"]
    if ark.what is None:
        ark.what = config[ark.naan]["erc_metadata_defaults"]["what"]
    if ark.when is None:
        ark.when = config[ark.naan]["erc_metadata_defaults"]["when"]
    if ark.policy is None:
        if ark.shoulder in config[ark.naan]["commitment_statements"].keys():
            ark.policy = config[ark.naan]["commitment_statements"][ark.shoulder]
        else:
            ark.policy = config[ark.naan]["commitment_statements"]["default"]

    ark.where = ark.ark_string

    try:
        ark_data = (
            ark.shoulder,
            ark.identifier,
            ark.ark_string,
            ark.target,
            ark.who,
            ark.what,
            ark.when,
            ark.where,
            ark.policy,
        )
        con = sqlite3.connect(config[ark.naan]["sqlite_db_path"])
        cur = con.cursor()
        cur.execute(
            "insert into arks values (datetime(), datetime(), ?,?,?,?,?,?,?,?,?)",
            ark_data,
        )
        con.commit()
        con.close()
    except sqlite3.DatabaseError as e:
        log_request(
            "ERROR",
            request.client.host,
            ark.ark_string,
            request.headers,
            authorization,
            str(e),
        )
        raise HTTPException(status_code=500)

    urls = dict()
    if len(config[ark.naan]["resolver_hosts"]["local"]) > 0:
        urls["local"] = (
            f'{config[ark.naan]["resolver_hosts"]["local"].rstrip("/")}/{ark.ark_string}'
        )
    if len(config[ark.naan]["resolver_hosts"]["global"]) > 0:
        urls["global"] = (
            f'{config[ark.naan]["resolver_hosts"]["global"].rstrip("/")}/{ark.ark_string}'
        )

    log_request(
        "INFO",
        request.client.host,
        ark.ark_string,
        request.headers,
        authorization,
        "ARK created.",
    )

    ark.where = get_erc_where_value(ark.naan, ark.ark_string)
    # Delete the NAAN because we do not return it to the requesting client.
    del ark.naan
    return {"ark": ark, "urls": urls}


@app.patch("/larkm/ark:{naan}/{identifier}")
def update_ark(
    request: Request,
    naan: str,
    identifier: str,
    ark: Ark,
    authorization: Annotated[str | None, Header()] = None,
):
    """
    Update an ARK with new ERC metadata, or policy statement. Shoulders, NAANs,
    identifiers, and ark_strings cannot be updated. ark_string is a required
    body field. 'where' always gets the value of ark_string. Sample request:

    curl -v -X PATCH "http://127.0.0.1:8000/larkm/ark:12345/x931fd9bec0bb6" \
        -H 'Content-Type: application/json' \
        -d '{"ark_string": "ark:12345/x931fd9bec0bb6", "target": "https://example.com/foo"}'

    - **naan**: the NAAN portion of the ARK.
    - **identifier**: the identifier portion of the ARK, which will include a shoulder.
    """
    check_access(request, naan, authorization)

    if ark.ark_string is None:
        raise HTTPException(
            status_code=422,
            detail="When updatating ARKs, the ark_string must be provided in the request body.",
        )

    ark_string = f"ark:{naan}/{identifier}".strip()
    if ark_string != ark.ark_string:
        raise HTTPException(
            status_code=409,
            detail="NAAN/identifier combination and ark_string do not match.",
        )

    if (
        ark.policy is not None
        and config[naan]["constrain_commitment_statements"] == "yes"
    ):
        raise HTTPException(status_code=409, detail="Policy cannot be updated.")

    # 'where' cannot be updated.
    if ark.where is not None:
        raise HTTPException(
            status_code=409,
            detail="'where' is automatically assigned the value of the ark string and cannot be updated.",
        )

    try:
        con = sqlite3.connect(config[naan]["sqlite_db_path"])
        con.row_factory = sqlite3.Row
        cur = con.cursor()
        cur.execute("select * from arks where ark_string = :a_s", {"a_s": ark_string})
        record = cur.fetchone()
        if record is None:
            con.close()
            raise HTTPException(status_code=404, detail="ARK not found")
        con.close()
    except sqlite3.DatabaseError as e:
        log_request(
            "ERROR",
            request.client.host,
            ark_string,
            request.headers,
            authorization,
            str(e),
            naan=naan,
        )
        raise HTTPException(status_code=500)

    old_ark = dict(zip(record.keys(), record))

    # naan, shoulder, identifier, and ark_string cannot be updated.
    ark.naan = naan
    ark.shoulder = old_ark["shoulder"]
    ark.identifier = old_ark["identifier"]
    ark.ark_string = old_ark["ark_string"]

    # Only update ark properties that are in the request body, except for ark.where, which
    # always gets the value of the ark_string. We also create two dictionaries for logging
    # one containing the old property values and the other containing the updated properties.
    original_properties = dict()
    updated_properties = dict()
    if ark.target is None:
        ark.target = old_ark["target"]
    else:
        original_properties["target"] = old_ark["target"]
        updated_properties["target"] = ark.target
    check_target_already_registered(ark, request, authorization)
    if ark.who is None:
        ark.who = old_ark["erc_who"]
    else:
        original_properties["erc_who"] = old_ark["erc_who"]
        updated_properties["erc_who"] = ark.who
    if ark.what is None:
        ark.what = old_ark["erc_what"]
    else:
        original_properties["erc_what"] = old_ark["erc_what"]
        updated_properties["erc_what"] = ark.what
    if ark.when is None:
        ark.when = old_ark["erc_when"]
    else:
        original_properties["erc_when"] = old_ark["erc_when"]
        updated_properties["erc_when"] = ark.when
    if ark.policy is None:
        ark.policy = old_ark["policy"]
    else:
        original_properties["policy"] = old_ark["policy"]
        updated_properties["policy"] = ark.policy

    ark.where = ark.ark_string

    try:
        ark_data = (
            ark.shoulder,
            ark.identifier,
            ark.ark_string,
            ark.target,
            ark.who,
            ark.what,
            ark.when,
            ark.where,
            ark.policy,
            ark.ark_string,
        )

        con = sqlite3.connect(config[naan]["sqlite_db_path"])
        cur = con.cursor()
        cur.execute(
            "update arks set date_modified = datetime(), shoulder = ?, identifier = ?, ark_string = ?, target = ?, erc_who = ?, erc_what = ?, erc_when = ?, erc_where = ?, policy = ? where ark_string = ?",
            ark_data,
        )
        con.commit()
        con.close()
        log_request(
            "INFO",
            request.client.host,
            ark_string,
            request.headers,
            authorization,
            f"ARK updated: {original_properties} updated to {updated_properties}",
            naan=naan,
        )
    except sqlite3.DatabaseError as e:
        log_request(
            "ERROR",
            request.client.host,
            ark_string,
            request.headers,
            authorization,
            str(e),
            naan=naan,
        )
        raise HTTPException(status_code=500)

    urls = dict()
    if len(config[naan]["resolver_hosts"]["local"]) > 0:
        urls["local"] = (
            f'{config[naan]["resolver_hosts"]["local"].rstrip("/")}/{ark.ark_string}'
        )
    if len(config[naan]["resolver_hosts"]["global"]) > 0:
        urls["global"] = (
            f'{config[naan]["resolver_hosts"]["global"].rstrip("/")}/{ark.ark_string}'
        )

    ark.where = get_erc_where_value(ark.naan, ark.ark_string)
    # Delete the NAAN because we do not return it to the requesting client.
    del ark.naan
    return {"ark": ark, "urls": urls}


@app.delete("/larkm/ark:{naan}/{identifier}", status_code=204)
def delete_ark(
    request: Request,
    naan: str,
    identifier: str,
    authorization: Annotated[str | None, Header()] = None,
):
    """
    Given an ARK string, delete the ARK. Sample query:

    curl -v -X DELETE "http://127.0.0.1:8000/larkm/ark:12345/x931fd9bec0bb6"

    - **naan**: the NAAN portion of the ARK.
    - **identifier**: the identifier portion of the ARK.
    """
    check_access(request, naan, authorization)

    ark_string = f"ark:{naan}/{identifier}"

    try:
        con = sqlite3.connect(config[naan]["sqlite_db_path"])
        cur = con.cursor()
        cur.execute(
            "select ark_string from arks where ark_string = :a_s", {"a_s": ark_string}
        )
        record = cur.fetchone()
        if record is None:
            con.close()
            raise HTTPException(status_code=404, detail="ARK not found")
        con.close()
    except sqlite3.DatabaseError as e:
        log_request(
            "ERROR",
            request.client.host,
            ark_string,
            request.headers,
            authorization,
            str(e),
        )
        raise HTTPException(status_code=500)

    # If ARK found, delete it.
    else:
        try:
            con = sqlite3.connect(config[naan]["sqlite_db_path"])
            cur = con.cursor()
            cur.execute("delete from arks where ark_string=:a_s", {"a_s": ark_string})
            con.commit()
            con.close()
            log_request(
                "INFO",
                request.client.host,
                ark_string,
                request.headers,
                authorization,
                "ARK deleted.",
            )
        except sqlite3.DatabaseError as e:
            log_request(
                "ERROR",
                request.client.host,
                ark_string,
                request.headers,
                authorization,
                str(e),
            )
            raise HTTPException(status_code=500)

    log_request(
        "INFO",
        request.client.host,
        ark_string,
        request.headers,
        authorization,
        "ARK deleted.",
    )


@app.get("/larkm/search")
def search_arks(
    request: Request,
    naan: Optional[str] = "",
    q: Optional[str] = "",
    page=1,
    page_size=20,
    authorization: Annotated[str | None, Header()] = None,
):
    """
    Endpoint for searching the Whoosh index of ARK metadata. Sample request:

    curl "http://127.0.0.1:8000/larkm/search?naan=99999&q=erc_what:example"

    - **naan**: the NAAN.
    - **q**: the Whoosh query, using Whoosh's default query language. Must be URL escaped.
      See the README for more information.
    - **page**: the page number to retrieve from the results.
    - **page_size**: the number of results to include in the page.
    """
    request_args = dict(request.query_params)

    check_access(request, naan, authorization)

    if config[naan]["whoosh_index_dir_path"] == "":
        log_request(
            "ERROR",
            request.client.host,
            q,
            request.headers,
            authorization,
            f"whoosh_index_dir_path config setting for NAAN {naan} is empty",
            naan=naan,
        )
        raise HTTPException(status_code=422)

    if not os.path.exists(config[naan]["whoosh_index_dir_path"]):
        message = f'Directory defined in whoosh_index_dir_path config setting {config[naan]["whoosh_index_dir_path"]} for NAAN {naan} not found'
        log_request(
            "ERROR",
            request.client.host,
            q,
            request.headers,
            authorization,
            message,
            naan=naan,
        )
        raise HTTPException(status_code=422)

    # Validate values provided in date_created and date_modified fields.
    fields_to_validate = ["date_created", "date_modified"]
    if "naan" in request_args and "q" in request_args:
        field_queries = request_args["q"].split("&")
        for field_query in field_queries:
            field_name = field_query.split(":")[0]
            if field_name in fields_to_validate:
                field_value = field_query.split(":")[1]
                if "to".lower() in field_value.lower():
                    # We have a range query.
                    range_dates = field_value.lower().split("to")
                    for range_date in range_dates:
                        if validate_date(range_date.strip(" []")) is False:
                            raise HTTPException(
                                status_code=422,
                                detail=range_date.strip(" []")
                                + " in "
                                + field_name
                                + " is not a valid date.",
                            )
                else:
                    # Not a range query.
                    if validate_date(field_value) is False:
                        raise HTTPException(
                            status_code=422,
                            detail=field_value.strip(" ")
                            + " in "
                            + field_name
                            + " is not a valid date.",
                        )
    else:
        log_request(
            "ERROR",
            request.client.host,
            q,
            request.headers,
            authorization,
            'Bad request: both "naan" and "q" are required arguments.',
            naan=naan,
        )
        raise HTTPException(status_code=400)

    idx = index.open_dir(config[naan]["whoosh_index_dir_path"])

    query_parser = QueryParser("identifier", schema=idx.schema)
    query = query_parser.parse(f"naan:{naan} AND ({q})")
    with idx.searcher() as searcher:
        results = searcher.search_page(query, int(page), pagelen=int(page_size))
        number_of_results = len(results)
        identifier_list = list()
        for doc in results:
            identifier_list.append(doc["identifier"])

        if len(identifier_list) == 0:
            return {
                "num_results": number_of_results,
                "page": page,
                "page_size": page_size,
                "arks": [],
            }

        # We have retrieved identifiers from the Woosh index, now we get the full ARK records from the
        # database to return to the user.
        try:
            con = sqlite3.connect(config[naan]["sqlite_db_path"])
            con.row_factory = sqlite3.Row
            cur = con.cursor()
            identifier_list_string = ",".join(f'"{i}"' for i in identifier_list)
            # identifier_list_string is safe to use here since it is not user input, it is
            # validated using a regex at the time of creation in create_ark().
            cur.execute(
                "select * from arks where identifier IN ("
                + identifier_list_string
                + ")"
            )
            arks = cur.fetchmany(len(identifier_list))
            con.close()
        except sqlite3.DatabaseError as e:
            log_request(
                "ERROR",
                request.client.host,
                q,
                request.headers,
                authorization,
                str(e),
                naan=naan,
            )
            raise HTTPException(status_code=500)

    log_request(
        "INFO",
        request.client.host,
        q,
        request.headers,
        authorization,
        f"ARK data for NAAN {naan} searched ({number_of_results} results).",
        naan=naan,
    )

    if len(arks) == 0:
        return {
            "num_results": number_of_results,
            "page": page,
            "page_size": page_size,
            "arks": [],
        }
    else:
        return_list = list()
        for ark in arks:
            return_list.append(ark)
    return {
        "num_results": number_of_results,
        "page": page,
        "page_size": page_size,
        "arks": return_list,
    }


@app.get("/larkm/config/{naan}")
def return_config(
    request: Request, naan: str, authorization: Annotated[str | None, Header()] = None
):
    """
    Returns a subset of larkm's configuration data to the client.

    curl "http://127.0.0.1:8000/larkm/config/99999"

    - **naan**: the NAAN.
    """
    check_access(request, naan, authorization)

    if config[naan]["default_shoulder"] in config[naan]["allowed_shoulders"]:
        config[naan]["allowed_shoulders"].remove(config[naan]["default_shoulder"])

    # Remove configuration data the client doesn't need to know.
    subset = copy.deepcopy(config[naan])
    del subset["naan"]
    del subset["trusted_ips"]
    del subset["api_keys"]
    del subset["sqlite_db_path"]
    del subset["log_file_path"]
    del subset["whoosh_index_dir_path"]

    log_request(
        "INFO",
        request.client.host,
        f"/larkm/config/{naan}",
        request.headers,
        authorization,
        f"Config requested for NAAN {naan}.",
        naan=naan,
    )

    return subset


def check_target_already_registered(ark, request, authorization):
    # We allow empty targets.
    if ark.target is None or len(ark.target) == 0:
        return
    try:
        con = sqlite3.connect(config[ark.naan]["sqlite_db_path"])
        con.row_factory = sqlite3.Row
        cur = con.cursor()
        cur.execute("select * from arks where target = :a_s", {"a_s": ark.target})
        records = cur.fetchall()
        con.close()
        # We allow the current ARK to use that target, but only the current ARK.
        # So we need to see if there are any others before thowing the exception.
        if len(records) > 0:
            ark_strings = []
            for record in records:
                ark_strings.append(record["ark_string"])
            if len(ark_strings) == 1 and ark.ark_string in ark_strings:
                pass
            else:
                raise HTTPException(
                    status_code=409,
                    detail=f"'target' value {ark.target} already in use.",
                )
    except sqlite3.DatabaseError as e:
        # We don't have the ark_string at this point so we use the ark.identifier in our log entry.
        log_request(
            "ERROR",
            request.client.host,
            ark.identifier,
            request.headers,
            authorization,
            str(e),
        )
        raise HTTPException(status_code=500)


def get_info_content(ark_string):
    """
    Assembles the content to return in response to a ?info request.

    - **ark_string**: the ARK as a string, i.e., ark:{naan}/{identifier}
    """
    naan = get_naan_from_ark_string(ark_string)

    try:
        con = sqlite3.connect(config[naan]["sqlite_db_path"])
        con.row_factory = sqlite3.Row
        cur = con.cursor()
        cur.execute(
            "select erc_who, erc_what, erc_when, erc_where, policy from arks where ark_string = :a_s",
            {"a_s": ark_string},
        )
        record = cur.fetchone()
        if record is None:
            return None
        con.close()
    except sqlite3.DatabaseError as e:
        return e

    erc = f"erc:\nwho: {record[0]}\nwhat: {record[1]}\nwhen: {record[2]}\nwhere: {get_erc_where_value(naan, record[3])}\n"
    if len(record[4]) > 0:
        policy = f"policy: {record[4]}"
    else:
        for sh in config[naan]["allowed_shoulders"]:
            if ark_string.startswith(sh):
                policy = "policy: " + config[naan]["commitment_statements"][sh]
            else:
                policy = "policy: " + config[naan]["commitment_statements"]["default"]

    return erc + policy + "\n\n"


def log_request(
    level, client_ip, ark_string, request_headers, auth_key, event_details, naan=None
):
    """
    Assembles a tab-delmited log entry and writes it to the log file.

    - **level**: INFO, WARNING, or ERROR from the standard Python logging levels.
    - **client_ip**: the IP address of the client triggering the event.
    - **ark_string**: the ARK string from the event being logged. When called from search_arks(),
      this is the request "q" query parameter.
    - **request_headers**: the HTTP headers from the FastAPI Request object.
    - **auth_key**: The "Authorization" header, Annotated[str | None, Header()]
    - **event_details**: a brief description of the event.
    - **naan**: the NAAN.
    """
    if "referer" in request_headers:
        referer = request_headers["referer"]
    else:
        referer = "null"

    if auth_key is None:
        api_key_suffix = "null"
    else:
        api_key_suffix = auth_key[-4:]

    if naan is None:
        naan = get_naan_from_ark_string(ark_string)

    now = datetime.now()
    date_format = "%Y-%m-%d %H:%M:%S"

    entry = f"{now.strftime(date_format)}\t{client_ip}\t{api_key_suffix}\t{referer}\t{ark_string}\t{event_details}"
    logging.basicConfig(
        level=logging.INFO,
        filename=config[naan]["log_file_path"],
        filemode="a",
        format="%(message)s",
    )
    if level == "ERROR":
        logging.error(entry)
    elif level == "WARNING":
        logging.warning(entry)
    else:
        logging.info(entry)


def generate_identifier(uuid=None):
    """
    Derives an identifier from a UUIDv4. If UUID is not provided,
    generates one and uses it.
    """
    if uuid is None:
        uuid_without_hypens = str(uuid4()).replace("-", "")
        return uuid_without_hypens[:12]
    else:
        uuid_without_hypens = uuid.replace("-", "")
        return uuid_without_hypens[:12]


def validate_identifier(identifier):
    if re.match(
        "^[a-f0-9]{12}$",
        identifier,
    ):
        return True
    else:
        return False


def validate_uuid(identifier):
    if re.match(
        "^[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89aAbB][a-f0-9]{3}-[a-f0-9]{12}$",
        identifier,
    ):
        return True
    else:
        return False


def validate_date(date_string):
    """
    Validates a yyyy-mm-dd date string.

    - **date**: the date string to validate.
    """
    try:
        time.strptime(date_string, "%Y-%m-%d")
    except ValueError:
        return False

    # If there's no ValueError, date validates.
    return True


def get_naan_from_ark_string(ark_string):
    """
    Extracts the NAAN from an ARK.

    - **ark_string**: the ARK as a string, i.e., ark:{naan}/{identifier}
    """

    pattern = r"ark:/{0,1}(.+)/"
    match = re.search(pattern, ark_string)
    if match:
        return match.group(1)
    else:
        # If there's no NAAN, return None.
        return None


def get_erc_where_value(naan, ark_string):
    """An ARK's "where" property is stored in the db as the ARK string, but clients
    expect it to be a fully resolvable durable URL. This function assembles the
    value to return to clients.
    """
    return f'{config[naan]["resolver_hosts"]["erc_where"].rstrip("/")}/{ark_string}'


def check_access(request, naan, authorization):
    """Checks whether client has access to a route. Doesn't return anything
    to caller, but raises an exception that is returned to the client.

    - **request**: The Request object.
    - **naan*: The NAAN.
    - **authorization**: The "authorization" header, Annotated[str | None, Header()]
    """
    registered_naans = config.keys()
    if naan not in registered_naans:
        message = f"Request using an unregistered NAAN."
        log_request(
            "WARNING",
            request.client.host,
            str(request.url),
            request.headers,
            authorization,
            message,
            naan,
        )
        raise HTTPException(status_code=403)

    # "trusted_ips" can be empty.
    if (
        len(config[naan]["trusted_ips"]) > 0
        and request.client.host not in config[naan]["trusted_ips"]
    ):
        message = f"Request from an untrusted IP address."
        log_request(
            "WARNING",
            request.client.host,
            str(request.url),
            request.headers,
            authorization,
            message,
            naan,
        )
        raise HTTPException(status_code=403)

    # API keys are not required.
    if authorization not in config[naan]["api_keys"]:
        message = f"API key {authorization} not configured."
        log_request(
            "WARNING",
            request.client.host,
            str(request.url),
            request.headers,
            authorization,
            message,
            naan,
        )
        raise HTTPException(status_code=403)
