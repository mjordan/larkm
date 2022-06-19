# larkm: A Lightweight ARK Manager

# Overview

larkm is a simple [ARK](https://arks.org/) manager that can:

* persist new ARKs to an sqlite database
* mint ARKs using UUID (v4) strings
* validate ARK shoulders
* resolve ARKs to their target URLs
* update the target URLs, ERC/Kernel metadata, and committment statements of existing ARKs
* provide the target URLs of ARKs it manages, and provide the ARK associated with a URL
* provide basic [committment statements](https://arks.org/about/best-practices/) that are specific to shoulders
* delete ARKs
* log requests for ARK resolution

ARK resolution is provided via requests to larkm's host followed by an ARK (e.g. `https://myhost.net/ark:/12345/876543`) and the other operations are provided through standard REST requests to larkm's management endpoint (`/larkm`). This REST interface allows creating, persisting, updating, and deleting ARKs, and can expose a subset of larkm's configuration data to clients. Access to the REST endpoints can be controlled by registering the IP addresses of trused clients, as explained in the "Configuration" section below.

larkm is currently a proof of concept as we learn about locally mananging ARKs. It is considered "lightweight" because it supports only a subset of ARK functionality, focusing on providing ways to manage ARKs locally and on using ARKs as persistent, resolvable identifiers. ARK features such as suffix passthrough and ARK qualifiers are currently out of scope.

## Requirements

* Python 3.7+
* [FastAPI](https://fastapi.tiangolo.com/)
* [Uvicorn](https://www.uvicorn.org/) for demo/testing, or some other ASGI web server for production uses.
* sqlite3 (installed by default with Python)
* To have your ARKs resolve from [N2T](http://n2t.net/), you will to register a NAAN (Name Assigning Authority Number) using [this form](https://goo.gl/forms/bmckLSPpbzpZ5dix1).

## Usage

### Creating the database

larkm provides an empty sqlite database that you can use, `larkm_template.db` in the extras directory.

If you want to create your own, run the following commands:

1. `sqlite3 path/to/mydb.db`
1. within sqlite, run `CREATE TABLE arks(date_created TEXT NOT NULL, date_modified TEXT NOT NULL, shoulder TEXT NOT NULL, identifier TEXT NOT NULL, ark_string TEXT NOT NULL, target TEXT NOT NULL, erc_who TEXT NOT NULL, erc_what TEXT NOT NULL, erc_when TEXT NOT NULL, erc_where TEXT NOT NULL, policy TEXT NOT NULL);`
1. `.quit`

### Configuration

larkm uses a JSON configuration file in the same directory as `larkm.py` named `larkm.json`. Copy the sample configuration file, `larkm.json.sample`, to `larkm.json`, make any changes you need, and you are good to go.

Currently, there are four config settings:

* "NAAN", which is your insitution's Name Assigning Authority Number.
* "default_shoulder", the ARK shoulder applied to new ARKs if one is not provided).
* "allowed_shoulders", a list of shoulders that are allowed in new ARKs provided by clients). If your default shoulder is the only one currently used by your NAAN, provide an empty list for "allowed_shoulders" (e.g. `[]`).
* "committment_statement", a mapping from shoulders to text expressing your institution's committment to maintaining the ARKs.
* "sqlite_db_path": absolute or relative (to larkm.py) path to larkm's sqlite3 database file.
* "log_file_path": absolute or relative (to larkm.py) path to the log file. Directory must exist and be writable by the process running larkm.
* "resolver_hosts": definition of the resolvers to include in the `urls` list returned to clients.
* "trusted_ips": list of client IP addresses that can create, update, and delete ARKs; leave empty to no restrict access to these functions (e.g. during testing).

```json
{
  "NAAN": "12345",
  "default_shoulder": "s1",
  "allowed_shoulders": ["s8", "s9", "x9"],
  "committment_statement": {
       "s1": "ACME University commits to maintain ARKs that have 's1' as a shoulder for a long time.",
       "s8": "ACME University commits to maintain ARKs that have 's8' as a shoulder until the end of 2025.",
       "default": "Default committment statement."
  },
  "erc_metadata_defaults": {
       "who": ":at",
       "what": ":at",
       "when": ":at",
       "where": ""
  },
  "sqlite_db_path": "testdb/larkmtest.db",
  "log_file_path": "/tmp/larkm.log",
  "resolver_hosts": {
     "global": "https://n2t.net/",
     "local": "https://resolver.myorg.net"
  },
  "trusted_ips": []
}
```

### Starting larkm

To start the larkm app within local Uvicorn we server, in a terminal run `python3 -m uvicorn larkm:app`

### Resolving an ARK

Visit `http://127.0.0.1:8000/ark:/12345/x9062cdde7-f9d6-48bb-be17-bd3b9f441ec4` using `curl -Lv`. You will see a redirect to `https://example.com/foo`.

To see the configured metadata and committment statement for the ARK instead of resolving to its target, append `?info` to the end of the ARK, e.g., `http://127.0.0.1:8000/ark:/12345/x9062cdde7-f9d6-48bb-be17-bd3b9f441ec4?info`.

> To comply with the ARK specification, the hyphens in the identifier are optional. Therefore, `http://127.0.0.1:8000/ark:/12345/x9062cdde7-f9d648bbbe17bd3--b9f441ec4` is equivalent to `http://127.0.0.1:8000/ark:/12345/x9062cdde7-f9d6-48bb-be17-bd3b9f441ec4`.  Since hyphens are integral parts of UUIDs, larkm restores the hyphens to their expected location within the UUID to perform its lookups during resolution. Hyphens in UUIDs are optional/ignored only when resolving an ARK. They are required for all other operations described below. 

### Creating a new ARK

REST clients can provide a `shoulder` and/or an `identifer` value in the requst body.

* Clients cannot provide a NAAN.
* Clients must always provide a `target`.
* If a should is not provided, larkm will use its default shoulder.
* If an identifier is not provided, larkm will generate a v4 UUID as the identifier.
* If an identifier is provided, it must not contain a shoulder.
* If the identifier that is provided is already in use, larkm will respond to the `POST` request with an `409` status code acommpanied by the body `{"detail":"UUID already in use."}`.

To add a new ARK (for example, to resolve to https://digital.lib.sfu.ca), issue the following request using curl:

`curl -v -X POST "http://127.0.0.1:8000/larkm" -H 'Content-Type: application/json' -d '{"shoulder": "s1", "identifier": "fde97fb3-634b-4232-b63e-e5128647efe7", "target": "https://digital.lib.sfu.ca"}'`

If you now visit `http://127.0.0.1:8000/ark:/12345/s1fde97fb3-634b-4232-b63e-e5128647efe7`, you will be redirected to https://digital.lib.sfu.ca.

If you omit the `shoulder`, the configured default shoulder will be used. If you omit the `identifier`, larkm will mint one using a v4 UUID.

All responses to a POST will include in their body `shoulder`, `identifier`, `target`, metadata and `policy` values provided in the POST request. The `where` value will be identical to the provided`target` value. Metadata values not provided will get the ERC ":at" ("the real value is at the given URL or identifier") value:

`{"ark":{"shoulder": "s1", "identifier": "fde97fb3-634b-4232-b63e-e5128647efe7", "ark_string":"ark:/12345/s1fde97fb3-634b-4232-b63e-e5128647efe7","target":"https://digital.lib.sfu.ca", "who":":at", "when":":at", "where":"https://digital.lib.sfu.ca", "what":":at"}, "urls":{"local":"https://resolver.myorg.net/ark:/12345/s1fde97fb3-634b-4232-b63e-e5128647efe7","global":"https://n2t.net/ark:/99999/s1fde97fb3-634b-4232-b63e-e5128647efe7"}}`

Also included in the response are values for global and local `urls`.

Values provided in the request body for `what`, `who`, `when`, and `policy` will be returned in the response:

`curl -v -X POST "http://127.0.0.1:8000/larkm" -H 'Content-Type: application/json' -d '{"shoulder": "s1", "target": "https://digital.lib.sfu.ca", "who": "Jordan, Mark", "when": "2020", "policy": "We commit to maintaining this ARK for a long time."}'`

will return

`{"ark":{"shoulder": "s1", "identifier": "fde97fb3-634b-4232-b63e-e5128647efe7", "ark_string":"ark:/12345/s1fde97fb3-634b-4232-b63e-e5128647efe7","target":"https://digital.lib.sfu.ca", "who":"Jordan, Mark", "when":"2020", "where":"https://digital.lib.sfu.ca", "policy":"We commit to maintaining this ARK for a long time."}, "urls":{"local":"https://resolver.myorg.net/ark:/12345/s1fde97fb3-634b-4232-b63e-e5128647efe7","global":"https://n2t.net/ark:/12345/s1fde97fb3-634b-4232-b63e-e5128647efe7"}}`

### Updating an ARK's target URL and metadata

You can update an existing ARK's target, metadata, or policy statement. However, an ARK's `shoulder`, `identifier`, and `ark_string` cannot be updated. `ark_string` is a required body field, and the ARK NAAN, shoulder, and identifier provided in the PUT request URL must match those in the "ark_string" body field.

Some sample queries:

`curl -v -X PUT "http://127.0.0.1:8000/larkm/ark:/12345/s1fde97fb3-634b-4232-b63e-e5128647efe7" -H 'Content-Type: application/json' -d '{"ark_string": "ark:/12345/s1fde97fb3-634b-4232-b63e-e5128647efe7", "target": "https://summit.sfu.ca"}'`

`curl -v -X PUT "http://127.0.0.1:8000/larkm/ark:/12345/s1fde97fb3-634b-4232-b63e-e5128647efe7" -H 'Content-Type: application/json' -d '{"ark_string": "ark:/12345/s1fde97fb3-634b-4232-b63e-e5128647efe7", "who": "Jordan, Mark", "when": "2020", "policy": "We will maintain this ARK for a long time."}'`

### Getting the target URL for an ARK, or an ARK of a URL

If you want to know the target URL associated with an ARK without resolving to that URL, do this:

`curl "http://127.0.0.1:8000/larkm?ark_string=ark:/12345/s1fde97fb3-634b-4232-b63e-e5128647efe7"`

If you want the ARK for a URL, do this:

`curl "http://127.0.0.1:8000/larkm?target=https://summit.sfu.ca"`

In both cases, larkm will return a JSON response body that looks like this:

`{"ark_string": "ark:/12345/s1fde97fb3-634b-4232-b63e-e5128647efe7", "target": "https://summit.sfu.ca", "urls":{"local":"https://resolver.myorg.net/ark:/12345/s1fde97fb3-634b-4232-b63e-e5128647efe7","global":"https://n2t.net/ark:/12345/s1fde97fb3-634b-4232-b63e-e5128647efe7"}}`

or a 404 if the ARK or URL you used in your request wasn't found.

### Deleting an ARK

Delete an ARK using a request like:

`curl -v -X DELETE "http://127.0.0.1:8000/larkm/ark:/12345/s1fde97fb3-634b-4232-b63e-e5128647efe7"`

If the ARK was deleted, larkm returns a `204 No Content` response with no body. If the ARK was not found, larkm returns a `404` response with the body `{"detail":"ARK not found"}`.

### Getting larkm's configuration data

`curl -v "http://127.0.0.1:8000/larkm/config"`

Note that larkm returns only the subset of configuration data that clients need to create new ARKs, specifically the "default_shoulder", "allowed_shoulders", "committment_statement", and "erc_metadata_defaults" configuration data. Only clients whose IP addresses are listed in the `trusted_ips` configuration option may request configuration data.

## Metadata support

larkm supports the [Electronic Resource Citation](https://www.dublincore.org/groups/kernel/spec/) (ERC) metadata format expressed in ANVL syntax. Note that larkm accepts the raw values provided by the client and does not validate or format the values in any way.

If the default "where" ERC metadata is an empty string (as illustrated in the configuration data above), larkm assigns the ARK's target value to it.

## Shoulders

Following ARK best practice, larkm requires the use of [shoulders](https://wiki.lyrasis.org/display/ARKs/ARK+Identifiers+FAQ#ARKIdentifiersFAQ-shouldersWhatisashoulder?) in newly added ARKs. Shoulders allowed within your NAAN are defined in the "default_shoulder" and "allowed_shoulders" configuration settings. When a new ARK is added, larkm will validate that the ARK string starts with either the default shoulder or one of the allowed shoulders. Note however that larkm does not validate the [format of shoulders](https://wiki.lyrasis.org/display/ARKs/ARK+Shoulders+FAQ#ARKShouldersFAQ-HowdoIformatashoulder?).

## Using the Names to Things global resolver

If you have a registered NAAN that points to the server running larkm, you can use the Names to Things global ARK resolver's domain redirection feature by replacing the hostname of the server larkm is running on with `https://n2t.net/`. For example, if the local server larkm is running on is `https://ids.myorg.ca`, and your insitution's NAAN is registered to use that hostname, you can use a local instance of larkm to manage ARKs like `https://n2t.net/ark:/12345/s1fde97fb3-634b-4232-b63e-e5128647efe7` (using your NAAN instead of `12345`) and they will resolve through your local larkm running on `https://ids.myorg.ca` to their target URLs.

An advantage of doing this is that if your local resolver needs to be changed from `https://ids.myorg.ca/` to another host, assuming you update your NAAN record to use the new host, requests to `https://n2t.net/ark:/12345/s1fde97fb3-634b-4232-b63e-e5128647efe7` will continue to resolve to their targets.

## API docs

Thanks to [OpenAPI](https://github.com/OAI/OpenAPI-Specification), you can see larkm's API docs by visiting `http://127.0.0.1:8000/docs#`.

## Logging

larkm provides basic logging of requests to its resolver endpoint (i.e., `/ark:/foo/bar`). The path to the log is set in the "log_file_path" configuration option. To disable logging, use `false` as the value of this option. The log is a tab-delimited file containing a datestamp, the client's IP address, the requested ARK string, the corresponding target URL (or "ARK not found" if the requested ARK was not found, or "info" if the request was for the ARK's metadata), and the HTTP referer. If the referer is not available, the last value in the TSV is "null".

## Scripts

The "extras" directory contains two sample scripts:

1. a script to test larkm's performance
1. a script to mint ARKs from a CSV file
1. a script to mint ARKs from the output of the [larkm Integration Drupal module](https://github.com/mjordan/larkm_integration)

Instructions are at the top of each file.

## Development

* Run `larkm.py` and `test_larkm.py` through pycodestyle: `pycodestyle --show-source --show-pep8 --ignore=E402,E501,W504 *.py`
* To run tests:
   * you don't need to start the web server or create a database
   * within the larkm directory, copy `larkm.json.sample` to `larkm.json` (back up `larkm.json` first if you have custom values in it)
   * execute `pytest`

## License

MIT
