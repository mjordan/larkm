# larkm: A Lightweight ARK Manager

# Overview

larkm is a simple [ARK](https://arks.org/) manager that can:

* resolve ARKs to their target URLs
* support both "modern" ARKs with no trailing `/` after the "ark:" namespace (e.g. `ark:12345`) and "classic" ARKs with the trailing `/` (e.g. `ark:/12345`). New ARKs are created without the trailing `/`, following current practice.
* mint ARKs using the first 12 alphanumeric characters from UUID (v4) strings
* persist new ARKs to an sqlite database
* validate NAANs and ARK shoulders against configuration
* provide [commitment statements](https://arks.org/about/best-practices/) with defaults (optionally) configured per shoulder
* update the ERC/Kernel metadata and target URLs of existing ARKs (but not change NAANs, shoulders, or commitment statements) of existing ARKs
* allow fulltext indexing of ERC metadata, commitment statements, shoulders, targets, and other ARK properties
* delete ARKs
* log requests for ARK resolution
* support multiple NAANs (organizations)

ARK resolution is provided via requests to larkm's host followed by an ARK (e.g. `https://myhost.net/ark:12345/s1f4eca6e0a8ab`). Other operations are provided through standard REST requests to larkm's management endpoint (`/larkm`). This REST interface allows creating, persisting, updating, and deleting ARKs, and can expose a subset of larkm's configuration data to trusted clients. Access to the REST endpoints can be controlled by registering the IP addresses of trused clients and using API keys, as explained in the "Configuration" section below. Even though larkm is designed to be REST-first, a [simple GUI application](https://github.com/mjordan/larkm_manager) for managing ARKs in larkm is available.

larkm is considered "lightweight" because it supports only a subset of ARK functionality, focusing on providing ways to manage ARKs locally and on using ARKs as persistent, resolvable identifiers. ARK features such as suffix passthrough and ARK qualifiers are currently out of scope.

## Requirements

* Python 3.10+ (tested on Python 3.10-3.14)
* [FastAPI](https://fastapi.tiangolo.com/)
* [Uvicorn](https://www.uvicorn.org/) or some other ASGI web server
* [Whoosh](https://pypi.org/project/Whoosh/) for fulltext indexing of metadata
* To have your ARKs resolve from [N2T](http://n2t.net/), you will to register a NAAN (Name Assigning Authority Number) using [this form](https://forms.gle/2a8HQUNJRAcvq5UGA).

For running tests locally, you will also need:

* [pytest](https://pypi.org/project/pytest/)
* [httpx](https://pypi.org/project/httpx/)

## Installation

1. `git clone https://github.com/mjordan/larkm.git`
2. `pip install .` (alternatively, using your preferred `pip` options)
3. copy the database template to the desired location or create a database from scratch

larkm provides an empty sqlite database that you can use, `larkm_template.db` in the extras directory.

If you want to create your own, run the following commands:

1. `sqlite3 path/to/mydb.db`
1. within sqlite, run `CREATE TABLE arks(date_created TEXT NOT NULL, date_modified TEXT NOT NULL, shoulder TEXT NOT NULL, identifier TEXT NOT NULL, ark_string TEXT NOT NULL, target TEXT NOT NULL, erc_who TEXT NOT NULL, erc_what TEXT NOT NULL, erc_when TEXT NOT NULL, erc_where TEXT NOT NULL, policy TEXT NOT NULL); CREATE INDEX ark_string_idx on arks(ark_string); CREATE INDEX target_lookup_idx on arks(ark_string, target);`
1. `.quit`

## Usage

### Configuration

larkm uses a JSON configuration file in the same directory as `larkm.py` named `larkm.json`. Copy the sample configuration file, `extreas/larkm.json.sample`, to `larkm.json` in the `larkm` base directory, make any changes you need, and restart larkm to load the new configuration.

If you want to put your configuration file in a different location, create an environment variable `LARKM_CONFIG_FILE_PATH` that contains the abolute path to the config file. larkm will check this environment variable first, and if it is not set or is set an is empty, will use the default location described above.

larkm's configuration file groups configuration settings by NAAN. Within the configuration file, each top-level key contains the configuration settings for a single NAAN. Within each NAAN's configuration are the following key:value pairs:

* "naan": the NAAN that serves as the key to the other configuration settings. This is identical to its parent NAAN key.
* "default_shoulder": the ARK shoulder applied to new ARKs if one is not provided.
* "allowed_shoulders": a list of shoulders that are allowed in new ARKs provided by clients. If your default shoulder is the only one currently used by your NAAN, provide an empty list for "allowed_shoulders" (e.g. `[]`).
* "commitment_statements": a mapping from shoulders to text expressing your institution's commitment to maintaining the ARKs.
* "constrain_commitment_statements": either "yes" or "no", indicating whether ARKs are allowed to use commitment statements other than those defined in the "commitment_statements" list.
* "erc_metadata_defaults": a definition of default values for [ERC properties](https://www.dublincore.org/groups/kernel/spec/) if the properties are not specified when the ARK is created.
* "sqlite_db_path": absolute or relative (to larkm.py) path to larkm's sqlite3 database file. Must exist and be writable by the process running larkm.
* "log_file_path": absolute or relative (to larkm.py) path to the log file. Must exist and be writable by the process running larkm.
* "resolver_hosts": definition of the resolvers to return to clients in requests for `/larkm/config` and in the JSON response body when creating or updating ARKs. This setting has nothing to do with the resolution of an incoming ARK to its target URL. Configurations should specify three separate resolver hosts: a "global" host, a "local" host, and a "erc_where" host, which is the one used in the ARK's "where" property (this one should duplicate either the "global" or "local" host).
* "whoosh_index_dir_path": absolute or relative (to larkm.py) path to the Whoosh index data directory. Leave empty ("") if you are not indexing ARK data. Must exist and be writable by the process running larkm.
* "trusted_ips": list of client IP addresses that can create, update, delete, and search ARKs; leave empty to allow access from all IPs (e.g. during testing). Note that requests to resolve an ARK is open to all clients. Entries must be specific IP addresses; ranges are not supported.
* "api_keys": list of strings used as API keys. Clients must pass their API key in a "Authorization" header, e.g. `Authorization: myapikey`. API keys can be any length or can contain any characters other than spaces. The last four characters of API keys are logged in events that require keys, so it's important that the last four characters of all keys are unique.

The following sample JSON file contains configuration for two NAANs, "99999" and "12345", each with their own configuration specifics:

```json
{
  "99999": {
    "naan": "99999",
    "default_shoulder": "s1",
    "allowed_shoulders": [
      "s2",
      "s3",
      "x9"
    ],
    "commitment_statements": {
      "s1": "ACME University commits to maintain ARKs that have 's1' as a shoulder for a long time.",
      "s3": "ACME University commits to maintain ARKs that have 's3' as a shoulder until the end of 2025.",
      "default": "ACME University is providing access to this ARK."
    },
    "constrain_commitment_statements": "no",
    "erc_metadata_defaults": {
      "who": ":at",
      "what": ":at",
      "when": ":at"
    },
    "sqlite_db_path": "fixtures/larkmtest.db",
    "log_file_path": "/tmp/larkm.log",
    "resolver_hosts": {
      "global": "https://n2t.net/",
      "local": "https://resolver.myorg.net",
      "erc_where": "https://n2t.net/",
    },
    "whoosh_index_dir_path": "fixtures/index_dir",
    "trusted_ips": [],
    "api_keys": [
      "myapikey",
      "the-other-api-Key"
    ]
  },
  "12345": {
    "naan": "12345",
    "default_shoulder": "s1",
    "allowed_shoulders": [
      "s2",
      "s3",
      "x9"
    ],
    "commitment_statements": {
      "s1": "Awesome University commits to maintain ARKs that have 's1' as a shoulder in perpetuity.",
      "s3": "Awesome University commits to maintain ARKs that have 's3' as a shoulder in perpetuity.",
      "default": "Default commitment statement."
    },
    "constrain_commitment_statements": "yes",
    "erc_metadata_defaults": {
      "who": ":at",
      "what": ":at",
      "when": ":at"
    },
    "sqlite_db_path": "/data/larkm.db",
    "log_file_path": "/logs/larkm.log",
    "resolver_hosts": {
      "global": "https://n2t.net/",
      "local": "https://resolver.myorg.org",
      "erc_where": "https://resolver.myorg.org",
    },
    "whoosh_index_dir_path": "whoosh/index_dir",
    "trusted_ips": [],
    "api_keys": [
      "myapikey"
    ]
  }
}
```

### Restricting access to larkm's REST interface

Requests to larkm's REST interface at `/larkm` are allowed if:

1. The client's IP address is registered in the `trusted_ips` configuration setting, and
1. The client provides an "Authorization" request header containing an API key registered in the `api_keys` configuration setting.

Both of these conditions must be met (unless `trusted_ips` is empty, e.g. during testing). If both conditions are not met, clients will receive a `403` response.

Requests for simple ARK resolution, including requests that contain `?info`, are not restricted. For all operations that require an API key, the last four characters of the API key are logged.

### Starting larkm

To start larkm with the local Uvicorn web server, in a terminal run `python3 -m uvicorn larkm:app`

### Resolving an ARK

Visit `http://127.0.0.1:8000/ark:12345/x9062cdde7f9d6` using `curl -Lv`. You will see a redirect to `https://example.com/foo`.

To see the configured metadata and commitment statement for the ARK instead of resolving to its target, append `?info` to the end of the ARK, e.g., `http://127.0.0.1:8000/ark:12345/x9062cdde7f9d6?info`.

### Creating a new ARK

REST clients creating ARKs:

* May (and normally do) provide a `target` value in the JSON request body (for the exception, see "ARKs with no resolvable URL target" below).
* Must provide a `naan` value in the JSON request body.
* May provide a `shoulder` value in the JSON request body.
   * If a shoulder is not provided, larkm will use its default shoulder.
* May provide a `policy` (commitment statement) value in the JSON request body.
   * If a commitment statement is not provided, larkm will use the commitment statement configured to correspond to the provided shoulder or to a configured default commitment statement.
   * If "constrain_commitment_statements" is configured to be "yes", only configured committment statements may be used.
* May provide in the JSON request body either 1) a UUIDv4 identifier value or 2) the first 12 characters (minus the hypen at position 9) of a v4 UUID.
   * If an identifier is not provided, larkm will generate one using the first 12 characters (minus the hypen at position 9) of a v4 UUID as the identifier.
   * If an identifier is provided, it must not contain a shoulder.
   * If the identifier that is provided is already in use, larkm will respond to the `POST` request with an `409` status code acommpanied by the body `{"detail":"Identifier <identifier> already in use."}`.
* May provide simple ERC metadata (see below for more info) in the JSON request body.

To add a new ARK (for example, to resolve to https://digital.lib.sfu.ca), issue the following request (the configured default NAAN is `12345`):

`curl -v -X POST "http://127.0.0.1:8000/larkm" -H 'Content-Type: application/json' -d '{"naan": "12345", "shoulder": "s1", "identifier": "fde97fb3-634b-4232-b63e-e5128647efe7", "target": "https://digital.lib.sfu.ca"}'`

If you now visit `http://127.0.0.1:8000/ark:12345/s1fde97fb3634b`, you will be redirected to https://digital.lib.sfu.ca. Larkm has used the first 12 characters from the UUID provided in the "identifer" field in the request body as the ID portion of the new ARK. You can also provide only the first 12 characters of a UUID v4 (with no hyphen) in the request's "identifier" field, instead of a full UUID, but in most cases it's simpler to provide a full UUID. If you provide a short ID, it will be validated as a truncated UUID v4.

If you omit the `shoulder`, the configured default shoulder will be used. If you omit the `identifier`, larkm will mint one using the first 12 characters (minus the hypen at position 9) of a v4 UUID it generates.

All responses to a POST will include in their body the values values provided in the POST request, plus any default values for missing body fields. The `where` value will be populuated with the "erc_where" resolver hostname plus the provided `ark_string` (in other words, a fully resolvable version of the ARK) and cannot be populated directly. Metadata values not provided will get the ERC ":at" (signifying "the real value is at the given URL or identifier") value:

`{"ark":{"shoulder": "s1", "identifier": "fde97fb3-634b-4232-b63e-e5128647efe7", "ark_string":"ark:45454/s1fde97fb3634b","target":"https://digital.lib.sfu.ca", "who":":at", "when":":at", "where":"https://resolver.myorg.net/ark:12345/s1fde97fb3634b", "what":":at"}, "urls":{"local":"https://resolver.myorg.net/ark:12345/s1fde97fb3634b","global":"https://n2t.net/ark:99999/s1fde97fb3634b"}}`

Also included in the response are values for global and local `urls`, but not the erc_where URL since it is available in the `where` property in the ERC metadata.


### Retrieving all of an ARK's properties

The presence of the `?info` parameter returns only an ARK's ERC metadata, but it is possible for authenticated clients to request all of the data associated with an ARK. The most common use case for this ability is to populate a CRUD form in an external management tool.

To get all of the data associated with an ARK, authenticated clients can issue a GET request to the `/larkm/` endpoint specifying the ARK string, e.g., `/larkm/ark:/99999/s1cea8e7f31c84`. The JSON response will contain all of the ARK's properties:

```json
{
  "date_created": "2022-06-23 03:00:45",
  "date_modified": "2022-06-23 03:00:45",
  "shoulder": "s1",
  "identifier": "cea8e7f31c84",
  "ark_string": "ark:99999/s1cea8e7f31c84",
  "target": "http://example.com/15",
  "erc_who": "Derex Godfry",
  "erc_what": "5 Ways to Immediately Start Selling WATER",
  "erc_when": ":at",
  "erc_where": "https://resolver.myorg.net/ark:99999/s1cea8e7f31c84",
  "policy": "ACME University commits to maintain ARKs that have 's1' as a shoulder indefinitely."
}
```

### Updating an ARK's properties

You can update an existing ARK's ERC metadata and target. However, an ARK's `naan`, `shoulder`, `identifier`, `ark_string`, and commitment policay statement are immutable and cannot be updated, as is the `where` ERC property (see below). Note that `ark_string` is a required body field and must be identical to the ARK string used in the `/larkm/` REST endpoint. Other ARK oroperties included in the request body will be updated. The old and new values for updated properties are logged, creating a simple audit trail.

Some sample queries:

`curl -v -X PATCH "http://127.0.0.1:8000/larkm/ark:12345/s1fde97fb3634b" -H 'Content-Type: application/json' -d '{"ark_string": "ark:12345/s1fde97fb3634b", "target": "https://summit.sfu.ca/item/982674"}'`

`curl -v -X PATCH "http://127.0.0.1:8000/larkm/ark:12345/s1fde97fb3634b" -H 'Content-Type: application/json' -d '{"ark_string": "ark:12345/s1fde97fb3634b", "who": "Jordan, Mark", "when": "2020", "policy": "We will maintain this ARK for a long time."}'`

Including `where` in the request body will result in an HTTP `409` response with the message `where` is automatically assigned the value of the resolvable ARK and cannot be updated directly.

Note that while you can provide a full 32-character UUID as the "identifier" when you create an ARK, you cannot use the same UUID identifier in the request URL to update that ARK. You can only use the exact ARK string to update an ARK.


### Deleting an ARK

Delete an ARK using a request like:

`curl -v -X DELETE "http://127.0.0.1:8000/larkm/ark:12345/s1fde97fb3634b"`

If the ARK was deleted, larkm returns a `204 No Content` response with no body. If the ARK was not found, larkm returns a `404` response with the body `{"detail":"ARK not found"}`.

As when  updating an ARK, when deleting, you cannot use an UUID identifier to delete that ARK. You must use the exact ARK string.

### Getting larkm's configuration data

`curl -v "http://127.0.0.1:8000/larkm/config/99999"`

The "99999" here represents that NAAN's entry in the configuration file. This parameter is required since larkm only returns the configuration data for the specified NAAN, regardless of how many NAAN configurations are present in the configuration file. Note that larkm returns only the subset of configuration data that clients need to create new ARKs, specifically the "default_shoulder", "allowed_shoulders", "commitment_statement", and "erc_metadata_defaults" configuration data. Only clients whose IP addresses are listed in the `trusted_ips` configuration option may request configuration data, but that data will never include potentially sensitive configuration settings such as file paths, etc.

## Shoulders

Following ARK best practice, larkm requires the use of [shoulders](https://wiki.lyrasis.org/display/ARKs/ARK+Identifiers+FAQ#ARKIdentifiersFAQ-shouldersWhatisashoulder?) in newly added ARKs. Shoulders allowed within your NAAN are defined in the "default_shoulder" and "allowed_shoulders" configuration settings. When a new ARK is added, larkm will validate that the ARK string starts with either the default shoulder or one of the allowed shoulders. Note however that larkm does not validate the [format of shoulders](https://wiki.lyrasis.org/display/ARKs/ARK+Shoulders+FAQ#ARKShouldersFAQ-HowdoIformatashoulder?).


## Metadata support

larkm supports the [Electronic Resource Citation](https://www.dublincore.org/groups/kernel/spec/) (ERC) metadata format expressed in ANVL syntax. Note that larkm accepts the raw values provided by the client and does not validate or format the values against any schema. larkm also does not explicitly support multiple values in its implementation of ERC metadata; each property has a cardinality of one so if multiple values are required, larkm implementors should establish local conventions on how to represent multiple values (e.g. separated by a `|`).

`target` is not an ERC property. It is used internally by larkm to simplify resolution to an HTTP[S] URL.

## ARKs with no resolvable URL target

Not all things that an ARK can identify live on the Web. For example, you may want to create an ARK that identifies a concept or idea, in effect creating a durable HTTP-addressable identifier for that concept or idea.

To do this using larkm, all you need to do is not give an ARK a target. When clients request an ARK of this type, larkm returns the ERC metadata, equivalent to the data it returns when a client requests an ARK with a target but appends `?info` to the end of the ARK URL.

## Support for multiple NAANs

larkm supports using a single codebase and configuration file for managing ARKs that belong to multiple NAANs. It does this by looking for configured NAANs as top-level keys in the configuration file, and within each of those NAAN-specific configurations, allowing for independent configuration settings. All operations, including creating/updating/deleting ARKs, resolving ARKs, logging, and searching, are restricted to ARKs that contain the provided NAAN.

This ability allows multiple organizations that each have their own NAAN use the same instance of larkm.

### Searching metadata

larkm supports fulltext indexing of ERC metadata and other ARK properties via the [Whoosh](https://pypi.org/project/Whoosh/) indexer. This feature is not intended as a general-purpose, public search interface but rather to be used for administrative purposes. Access to the `/larkm/search` endpoint is restricted to the IP addresses registered in the "trusted_ips" configuration setting and requires an API key. Query strings must be URL-encoded.

A simple example search, including the required `naan` and `q` query parameters, is:

`http://127.0.0.1:8000/larkm/search?naan=99999&q=erc_what:water`

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
        "identifier": "cea8e7f31c84",
        "ark_string": "ark:99999/s1cea8e7f31c84",
        "target": "http://example.com/15",
        "erc_who": "Derex Godfry",
        "erc_what": "5 Ways to Immediately Start Selling Water",
        "erc_when": ":at",
        "erc_where": "ark:99999/s1cea8e7f31c84",
        "policy": "We commit to keeping this ARK actionable until 2030."
      },
      {
        "date_created": "2022-06-23 03:00:45",
        "date_modified": "2022-06-23 03:00:45",
        "shoulder": "s1",
        "identifier": "714b3160e138",
        "ark_string": "ark:99999/s1714b3160e138",
        "target": "http://example.com/16",
        "erc_who": "Toriana Kondo",
        "erc_what": "Water in Crisis: The Coming Shortages",
        "erc_when": ":at",
        "erc_where": "ark:99999/s1714b3160e138",
        "policy": ":at"
      }
    ]
  }
```

If no results were found, larkm returns a 200 HTTP status code and the same JSON structure, but with a `num_results` value of `0` and an empty `arks` list:

```json
{"num_results":0,"page":1,"page_size":"20","arks":[]}
```

If larkm cannot find the Whoosh index directory (or one is not configured), it returns a 204 (No content) to the requesting client.

The request parameters for the `/larkm/search` endpoint are:

* `naan`: the NAAN used to filter ARKs in the result set.
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

Searching uses the [default Whoosh query language](https://whoosh.readthedocs.io/en/latest/querylang.html), which supports boolean operators "AND", "OR", and "NOT", phase searches, grouping, and wildcards. Some example queries (not URL-encoded for easy reading) are:

* q=`erc_what:vancouver`
* q=`erc_what:"Biggest trends in airliners"`
* q=`shoulder:s1 OR shoulder:n3`
* q=`policy:"commits only to ensuring"`
* q=`policy:"commits only to ensuring" AND erc_what:vancouver`
* q=`date_modified:2022-02-23`
* q=`date_created:[2022-02-20 TO 2022-02-28]`
* q=`ark_string:ark:99999/s1cea8e7f31c84`
* q=`erc_where:ark:99999/s1cea8e7f31c84`
* q=`erc_where:"ark:99999/s1*"`
* q=`target:http://example.com`
* q=`target:"https://example.com*"`

Note that the `naan` is a separate request parameter and should not included as a keyword within the `q` parameter. Internaly, larkm adds it to the `q` query string, i.e., `naan:{naan} AND ({q})` to limit results to ARKs that contain the specified NAAN. Also note that the `erc_where` value in returned records contain the ARK string only, not a resolver hostname.

### Building the search index

Updating the index is not done in realtime; instead, it is generated using the "index_arks.py" script provided in the "extras" directory, which indexes every row in the larkm sqlite3 database. This script would typically scheduled using cron but can be run manually. The script takes two command-line arguments, the path to the larkm configuration file, and the NAAN used to limit which ARKs are indexed. A typical cron entry looks like this:

```
* * * * * /usr/bin/python3 /path/to/larkm/extras/index_arks.py /path/to/larkm/larkm.json 99999
```

where `/path/to/larkm/larkm.json` is the path to the configuration file and `99999` is the NAAN that defines the configuration used by the indexing script. Also note that ff you run the indexer via cron, make sure the paths in `sqlite_db_path` and `whoosh_index_dir_path` configuration settings are absolute.

## Using the Names to Things global resolver

If you have a registered NAAN that points to the server running larkm, you can use the Names to Things global ARK resolver's domain redirection feature by replacing the hostname of the server larkm is running on with `https://n2t.net/`. For example, if the local server larkm is running on is `https://ids.myorg.ca`, and your insitution's NAAN is registered to use that hostname, you can use a local instance of larkm to manage ARKs like `https://n2t.net/ark:12345/s1fde97fb3634b` (using your NAAN instead of `12345`) and they will resolve through your local larkm running on `https://ids.myorg.ca` to their target URLs.

An advantage of doing this is that if your local resolver needs to be changed from `https://ids.myorg.ca/` to another host, assuming you update your NAAN record to use the new host, requests to `https://n2t.net/ark:12345/s1fde97fb3634b` will continue to resolve invisibly to their targets.

## API docs

Thanks to [OpenAPI](https://github.com/OAI/OpenAPI-Specification), you can see larkm's API docs by visiting `http://127.0.0.1:8000/docs#`.

## Logging

larkm provides logging of requests to its resolver endpoint (i.e., `/ark:foo/bar`). The path to the log is set in the "log_file_path" configuration option. To disable logging, use `false` as the value of this option. The log is a tab-delimited file containing a datestamp, the client's IP address, the last four characters of the API key that performed the operation ("null" if there was no API key), and the HTTP referer (or "null" if none is available), the requested ARK string (or other URL path/query string), and a description of the event being logged.

Updates to ARKs are also logged, showing the original version of the updated properties and the new versions. ARK deletions are also logged.

Errors and warnings are also logged.

## Scripts

The "extras" directory contains three utility scripts:

1. a script to test larkm's performance
1. a script to mint ARKs from a CSV file
1. a script to build the Whoosh search index from entries in the database

Instructions are at the top of each file.

## Integrations

- [larkm Manager](https://github.com/mjordan/larkm_manager), a very basic GUI for the larkm ARK manager/resolver that allows creating, editing, and deleting ARKs.
- [Islandora Workbench larkm scripts](https://github.com/mjordan/islandora_workbench_larkm_scripts), a set of Workbench hook scripts to assign ARKs to objects created during Workbench "create" tasks and to automate population of larkm with those ARKs.

## Development

* Run `larkm.py` and `test_larkm.py` through `black`.
* To run tests:
   * you don't need to start the web server or create a database
   * within the larkm directory, execute `LARKM_CONFIG_FILE_PATH="fixtures/larkm.json.tests" pytest`

## License

MIT
