# larkm: A Lightweight ARK Manager

# Overview

larkm is a simple [ARK](https://arks.org/) manager that can:

* resolve ARKs to their target URLs
* supports ARKs with the optional trailing `/` (e.g. `ark:` and `ark:/`)
* mint ARKs using UUID (v4) strings
* persist new ARKs to an sqlite database
* validate ARK shoulders
* update the ERC/Kernel metadata, committment statements, and target URLs of existing ARKs
* provide basic [committment statements](https://arks.org/about/best-practices/) that are specific to shoulders
* proivdes fulltext indexing of ERC metadata
* delete ARKs
* log requests for ARK resolution

ARK resolution is provided via requests to larkm's host followed by an ARK (e.g. `https://myhost.net/ark:12345/876543`) and the other operations are provided through standard REST requests to larkm's management endpoint (`/larkm`). This REST interface allows creating, persisting, updating, and deleting ARKs, and can expose a subset of larkm's configuration data to clients. Access to the REST endpoints can be controlled by registering the IP addresses of trused clients, as explained in the "Configuration" section below.

larkm is considered "lightweight" because it supports only a subset of ARK functionality, focusing on providing ways to manage ARKs locally and on using ARKs as persistent, resolvable identifiers. ARK features such as suffix passthrough and ARK qualifiers are currently out of scope.

## Requirements

* Python 3.7+
* sqlite3 (installed by default with Python)
* [FastAPI](https://fastapi.tiangolo.com/)
* [Uvicorn](https://www.uvicorn.org/) for demo/testing, or some other ASGI web server for production uses
* [Whoosh](https://pypi.org/project/Whoosh/) for fulltext indexing of metadata
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

The config settings are:

* "NAAN", which is your insitution's Name Assigning Authority Number.
* "default_shoulder", the ARK shoulder applied to new ARKs if one is not provided).
* "allowed_shoulders", a list of shoulders that are allowed in new ARKs provided by clients). If your default shoulder is the only one currently used by your NAAN, provide an empty list for "allowed_shoulders" (e.g. `[]`).
* "committment_statement", a mapping from shoulders to text expressing your institution's committment to maintaining the ARKs.
* "sqlite_db_path": absolute or relative (to larkm.py) path to larkm's sqlite3 database file.
* "log_file_path": absolute or relative (to larkm.py) path to the log file. Directory must exist and be writable by the process running larkm.
* "resolver_hosts": definition of the resolvers to include in the `urls` list returned to clients.
* "whoosh_index_dir_path": absolute or relative (to larkm.py) path to the Whoosh index data directory. Leave empty if you are not indexing ARK data.
* "trusted_ips": list of client IP addresses that can create, update, delete, and search ARKs; leave empty to no restrict access to these functions (e.g. during testing.
* "private_shoulders": list of shouder-to-IP list mappings that defines which client IP addresses resolution requests for ARKs with those shoulders may come from.

```json
{
  "NAAN": "12345",
  "default_shoulder": "s1",
  "allowed_shoulders": ["s8", "s9", "x9", "z1"],
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
  "sqlite_db_path": "fixtures/larkmtest.db",
  "log_file_path": "/tmp/larkm.log",
  "resolver_hosts": {
     "global": "https://n2t.net/",
     "local": "https://resolver.myorg.net"
  },
  "whoosh_index_dir_path": "index_dir",
  "trusted_ips": ["142.58.23.213", "142.59.78.175"],
  "private_shoulders":  {
     "x9": ["123.456.789.123"],
     "z1": ["142.158.36.213", "142.58.123.45"]
  }
}
```

### Starting larkm

To start the larkm app with the local Uvicorn web server, in a terminal run `python3 -m uvicorn larkm:app`

### Resolving an ARK

Visit `http://127.0.0.1:8000/ark:12345/x9062cdde7-f9d6-48bb-be17-bd3b9f441ec4` using `curl -Lv`. You will see a redirect to `https://example.com/foo`.

To see the configured metadata and committment statement for the ARK instead of resolving to its target, append `?info` to the end of the ARK, e.g., `http://127.0.0.1:8000/ark:12345/x9062cdde7-f9d6-48bb-be17-bd3b9f441ec4?info`.

> To comply with the ARK specification, the hyphens in the identifier are optional. Therefore, `http://127.0.0.1:8000/ark:12345/x9062cdde7-f9d648bbbe17bd3--b9f441ec4` is equivalent to `http://127.0.0.1:8000/ark:12345/x9062cdde7-f9d6-48bb-be17-bd3b9f441ec4`.  Since hyphens are integral parts of UUIDs, larkm restores the hyphens to their expected location within the UUID to perform its lookups during resolution. Hyphens in UUIDs are optional/ignored only when resolving an ARK. They are required for all other operations described below.

### Creating a new ARK

REST clients can provide a `shoulder` and/or an `identifer` value in the requst body.

* Clients cannot provide a NAAN.
* Clients must always provide a `target` value.
* If a shoulder is not provided, larkm will use its default shoulder.
* If an identifier is not provided, larkm will generate a v4 UUID as the identifier.
* If an identifier is provided, it must not contain a shoulder.
* If the identifier that is provided is already in use, larkm will respond to the `POST` request with an `409` status code acommpanied by the body `{"detail":"UUID <uuid> already in use."}`.

To add a new ARK (for example, to resolve to https://digital.lib.sfu.ca), issue the following request using curl:

`curl -v -X POST "http://127.0.0.1:8000/larkm" -H 'Content-Type: application/json' -d '{"shoulder": "s1", "identifier": "fde97fb3-634b-4232-b63e-e5128647efe7", "where": "https://digital.lib.sfu.ca"}'`

If you now visit `http://127.0.0.1:8000/ark:12345/s1fde97fb3-634b-4232-b63e-e5128647efe7`, you will be redirected to https://digital.lib.sfu.ca.

If you omit the `shoulder`, the configured default shoulder will be used. If you omit the `identifier`, larkm will mint one using a v4 UUID.

All responses to a POST will include in their body the values values provided in the POST request, plus any default values for missing body fields. The `where` value will be identical to the provided `ark_string` and cannot be populated on its own. Metadata values not provided will get the ERC ":at" ("the real value is at the given URL or identifier") value:

`{"ark":{"shoulder": "s1", "identifier": "fde97fb3-634b-4232-b63e-e5128647efe7", "ark_string":"ark:12345/s1fde97fb3-634b-4232-b63e-e5128647efe7","target":"https://digital.lib.sfu.ca", "who":":at", "when":":at", "where":"ark:12345/s1fde97fb3-634b-4232-b63e-e5128647efe7", "what":":at"}, "urls":{"local":"https://resolver.myorg.net/ark:12345/s1fde97fb3-634b-4232-b63e-e5128647efe7","global":"https://n2t.net/ark:99999/s1fde97fb3-634b-4232-b63e-e5128647efe7"}}`

Also included in the response are values for global and local `urls`.

### Updating an ARK's properties

You can update an existing ARK's ERC metadata, policy statement, or target. However, an ARK's `shoulder`, `identifier`, and `ark_string` are immutable and cannot be updated. `ark_string` is a required body field, and the ARK NAAN, shoulder, and identifier provided in the PUT request URL must match those in the "ark_string" body field.

Some sample queries:

`curl -v -X PUT "http://127.0.0.1:8000/larkm/ark:12345/s1fde97fb3-634b-4232-b63e-e5128647efe7" -H 'Content-Type: application/json' -d '{"ark_string": "ark:12345/s1fde97fb3-634b-4232-b63e-e5128647efe7", "target": "https://summit.sfu.ca"}'`

`curl -v -X PUT "http://127.0.0.1:8000/larkm/ark:12345/s1fde97fb3-634b-4232-b63e-e5128647efe7" -H 'Content-Type: application/json' -d '{"ark_string": "ark:12345/s1fde97fb3-634b-4232-b63e-e5128647efe7", "who": "Jordan, Mark", "when": "2020", "policy": "We will maintain this ARK for a long time."}'`

Including `where` in the request body will result in an HTTP `409` response with the messagte `'where\' is automatically assigned the value of the ark string and cannot be updated.`


### Deleting an ARK

Delete an ARK using a request like:

`curl -v -X DELETE "http://127.0.0.1:8000/larkm/ark:12345/s1fde97fb3-634b-4232-b63e-e5128647efe7"`

If the ARK was deleted, larkm returns a `204 No Content` response with no body. If the ARK was not found, larkm returns a `404` response with the body `{"detail":"ARK not found"}`.

### Getting larkm's configuration data

`curl -v "http://127.0.0.1:8000/larkm/config"`

Note that larkm returns only the subset of configuration data that clients need to create new ARKs, specifically the "default_shoulder", "allowed_shoulders", "committment_statement", and "erc_metadata_defaults" configuration data. Only clients whose IP addresses are listed in the `trusted_ips` configuration option may request configuration data.

## Shoulders

Following ARK best practice, larkm requires the use of [shoulders](https://wiki.lyrasis.org/display/ARKs/ARK+Identifiers+FAQ#ARKIdentifiersFAQ-shouldersWhatisashoulder?) in newly added ARKs. Shoulders allowed within your NAAN are defined in the "default_shoulder" and "allowed_shoulders" configuration settings. When a new ARK is added, larkm will validate that the ARK string starts with either the default shoulder or one of the allowed shoulders. Note however that larkm does not validate the [format of shoulders](https://wiki.lyrasis.org/display/ARKs/ARK+Shoulders+FAQ#ARKShouldersFAQ-HowdoIformatashoulder?).

### Private shoulders

In the `private_shoulders` configuration setting, you can define which IP addresses resolution requests for ARKs with specific shoulders can come from. This feature is useful for ARKs for non-public Web resources, or where you are using larkm to manage ARKs for resources that do not resolve to a public location, e.g. on a private fileshare or in a physical location. Requests from unregistered IP addresses will get a `403` HTTP response.

## Metadata support

larkm supports the [Electronic Resource Citation](https://www.dublincore.org/groups/kernel/spec/) (ERC) metadata format expressed in ANVL syntax. Note that larkm accepts the raw values provided by the client and does not validate or format the values against any schema.

`target` is not an ERC property. It is used internally by larkm to simplify resolution to an HTTP[S] URL. Generally speaking, larkm assigns the value of the `erc_where` property to it.

### Searching metadata

larkm supports fulltext indexing of ERC metadata and other ARK properties via the [Whoosh](https://pypi.org/project/Whoosh/) indexer. This feature is not intended as a general-purpose, end-user search interface but rather to be used for administrative purposes. Access to the `/larkm/search` endpoint is restricted to the IP addresses registered in the "trusted_ips" configuration setting.

A simple example search is:

`http://127.0.0.1:8000/larkm/search?q=erc_what:water`

If the search was successful, larkm returns a 200 HTTP status code. A successful result contains a JSON string with keys "num_results", "page", "page_size", and "arks".

```json
{
    "num_results": 2,
    "page": 1,
    "page_size": 20,
    "arks": [
      {
        "date_created": "2022-06-23 03:00:45",
        "date_modified": "2022-06-23 03:00:45",
        "shoulder": "s1",
        "identifier": "cea8e7f3-1c84-4919-a694-65bc9997d9fe",
        "ark_string": "ark:99999/s1cea8e7f3-1c84-4919-a694-65bc9997d9fe",
        "target": "http://example.com/15",
        "erc_who": "Derex Godfry",
        "erc_what": "5 Ways to Immediately Start Selling Water",
        "erc_when": ":at",
        "erc_where": "ark:99999/s1cea8e7f3-1c84-4919-a694-65bc9997d9fe",
        "policy": "We commit to keeping this ARK actionable until 2030."
      },
      {
        "date_created": "2022-06-23 03:00:45",
        "date_modified": "2022-06-23 03:00:45",
        "shoulder": "s1",
        "identifier": "714b3160-e138-49ed-969a-a514f034274f",
        "ark_string": "ark:99999/s1714b3160-e138-49ed-969a-a514f034274f",
        "target": "http://example.com/16",
        "erc_who": "Toriana Kondo",
        "erc_what": "Water in Crisis: The Coming Shortages",
        "erc_when": ":at",
        "erc_where": "ark:99999/s1714b3160-e138-49ed-969a-a514f034274f",
        "policy": ":at"
      }
    ]
  }
```

If no results were found, larkm returns a 200 HTTP status code and the same JSON structure, but with a `num_results` value of `0` and an empty `arks` list:

```json
{"num_results":0,"page":1,"page_size":"20","arks":[]}
```

If larkm cannot find the Whoosh index directory (or one is not configured), it returns a 204 (No content).

The request parameters for the `/larkm/search` endpoint are:

* `q`: the Whoosh query (see examples below). Must be URL-encoded. Available fields, and the type of value they can have, to include in a search query are:
   * `erc_what`: free text
   * `erc_who`: free text
   * `erc_when`: free text
   * `erc_where`: free text
   * `ark_string`: free text
   * `shoulder`: free text
   * `policy`: free text
   * `target`: free text
   * `date_created`: single date in `yyyy-mm-dd` format, or a date range in the form `[yyyy-mm-dd TO yyyy-mm-dd]`
   * `date_modified`: single date in `yyyy-mm-dd` format, or a date range in the form `[yyyy-mm-dd TO yyyy-mm-dd]`
* `page`: the page number. Optional; if omitted, the first page is returned.
* `page_size`: the number of ARKs to include in the page of results. Optional; default is 20.

Searching uses the [default Whoosh query language](https://whoosh.readthedocs.io/en/latest/querylang.html), which supports boolean operators "AND", "OR", and "NOT", phase searches, and wildcards. Some example queries (not URL-encoded for easy reading) are:

* q=`erc_what:vancouver`
* q=`erc_what:"Biggest trends in airliners"`
* q=`shoulder:s1 OR shoulder:n3`
* q=`policy:"commits only to ensuring"`
* q=`policy:"commits only to ensuring" AND erc_what:vancouver`
* q=`date_modified:2022-02-23`
* q=`date_created:[2022-02-20 TO 2022-02-28]`
* q=`ark_string:ark:99999/s1cea8e7f3-1c84-4919-a694-65bc9997d9fe`
* q=`erc_where:ark:99999/s1cea8e7f3-1c84-4919-a694-65bc9997d9fe`
* q=`erc_where:"ark:99999*"`
* q=`target:http://example.com`
* q=`target:"https://example.com*"`

### Building the search index

Updating the index is not done in realtime; instead, it is generated using the "index_arks.py" script provided in the "extras" directory, which indexes every row in the larkm sqlite3 database. This script would typically scheduled using cron but can be run manually. A typical cron entry looks like this:

```
* * * * * /usr/bin/python3 /path/to/larkm/extras/index_arks.py /path/to/larkm/larkm.json
```

If you run the indexer via cron, make sure the paths in `sqlite_db_path` and `whoosh_index_dir_path` configuration settings are absolute.

## Using the Names to Things global resolver

If you have a registered NAAN that points to the server running larkm, you can use the Names to Things global ARK resolver's domain redirection feature by replacing the hostname of the server larkm is running on with `https://n2t.net/`. For example, if the local server larkm is running on is `https://ids.myorg.ca`, and your insitution's NAAN is registered to use that hostname, you can use a local instance of larkm to manage ARKs like `https://n2t.net/ark:12345/s1fde97fb3-634b-4232-b63e-e5128647efe7` (using your NAAN instead of `12345`) and they will resolve through your local larkm running on `https://ids.myorg.ca` to their target URLs.

An advantage of doing this is that if your local resolver needs to be changed from `https://ids.myorg.ca/` to another host, assuming you update your NAAN record to use the new host, requests to `https://n2t.net/ark:12345/s1fde97fb3-634b-4232-b63e-e5128647efe7` will continue to resolve to their targets.

## API docs

Thanks to [OpenAPI](https://github.com/OAI/OpenAPI-Specification), you can see larkm's API docs by visiting `http://127.0.0.1:8000/docs#`.

## Logging

larkm provides basic logging of requests to its resolver endpoint (i.e., `/ark:foo/bar`). The path to the log is set in the "log_file_path" configuration option. To disable logging, use `false` as the value of this option. The log is a tab-delimited file containing a datestamp, the client's IP address, the requested ARK string, the corresponding target URL (or "ARK not found" if the requested ARK was not found, or "info" if the request was for the ARK's metadata), and the HTTP referer. If the referer is not available, the value in the TSV entry is "null". Errors and warnings are also logged.

## Scripts

The "extras" directory contains two sample scripts:

1. a script to test larkm's performance
1. a script to mint ARKs from a CSV file
1. a script to mint ARKs from the output of the [larkm Integration Drupal module](https://github.com/mjordan/larkm_integration)
1. a script to build the Whoosh search index from entries in the database

Instructions are at the top of each file.

## Development

* Run `larkm.py` and `test_larkm.py` through pycodestyle: `pycodestyle --show-source --show-pep8 --ignore=E124,E126,E127,E128,E402,E501,W504 *.py`
* To run tests:
   * you don't need to start the web server or create a database
   * within the larkm directory, copy `larkm.json.sample` to `larkm.json` (back up `larkm.json` first if you have custom values in it)
   * execute `pytest`

## License

MIT
