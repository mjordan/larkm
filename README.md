# larkm: A Lightweight ARK Manager

# Overview

larkm is a simple [ARK](https://arks.org/) manager that can:

* persist new ARKs
* mint ARKs using UUID (v4) strings
* validate ARK shoulders
* resolve ARKs to their target URLs
* update the target URLs, ERC/Kernel metadata, and policy statements of existing ARKs
* provide the target URLs of ARKs it manages, and provide the ARK associated with a URL
* provide [committment statements](https://arks.org/about/best-practices/) that are specific to shoulders
* delete ARKs

ARK resolution is provided via requests to larkm's host followed by an ARK (e.g. `https://myhost.net/ark:/12345/876543`) and the other operations are provided through standard REST requests to larkm's management endpoint (`/larkm`).

larkm is currently a proof of concept as we learn about locally mananging ARKs. Features such as access control for the REST interface and persisting ARKs to a database are yet to come.

It is considered "lightweight" because it supports only a subset of ARK functionality, focusing on providing ways to manage ARKs locally and on using ARKs as persistent, resolvable identifiers. ARK features such as suffix passthrough and ARK qualifiers are currently out of scope.

## Requirements

* Python 3.6+
* [FastAPI](https://fastapi.tiangolo.com/)
* [Uvicorn](https://www.uvicorn.org/) for demo/testing, or some other ASGI web server for production uses.
* To have your ARKs resolve from [N2T](http://n2t.net/), you will to register a NAAN (Name Assigning Authority Number) using [this form](https://goo.gl/forms/bmckLSPpbzpZ5dix1).

## Usage

### Configuration

larkm uses a JSON configuration file in the same directory as `larkm.py` named `larkm.json`. Copy the sample configuration file, `larkm.json.sample`, to `larkm.json`, make any changes you need, and you are good to go.

Currently, there are four config settings:

* "NAAN", which is your insitution's Name Assigning Authority Number.
* "default_shoulder", the ARK shoulder applied to new ARKs if one is not provided).
* "allowed_shoulders", a list of shoulders that are allowed in new ARKs provided by clients). If your default shoulder is the only one currently used by your NAAN, provide an empty list for "allowed_shoulders" (e.g. `[]`).
* "committment_statement", a mapping from shoulders to text expressing your institution's committment to maintaining the ARKs.

```json
{
  "NAAN": "12345",
  "default_shoulder": "s1",
  "allowed_shoulders": ["s8", "s9", "x9"],
  "committment_statement": {
       "s1": "ACME University commits to maintain ARKs that have 's1' as a shoulder for a long time.",
       "s8": "ACME University commits to maintain ARKs that have 's8' as a shoulder until the end of 2025.",
       "default": "Default committment statement."
  }
}
```

## Metadata

larkm supports the [Electronic Resource Citation](https://www.dublincore.org/groups/kernel/spec/) (ERC) metadata format expressed in ANVL syntax. Note that larkm accepts the raw values provided by the client and does not validate or format the values in any way.

### Starting larkm

To start the larkm app within local Uvicorn we server, in a terminal run `python3 -m uvicorn larkm:app`

### Resolving an ARK

Visit `http://127.0.0.1:8000/ark:/12345/x910` in your browser. You will be redirected to https://www.lib.sfu.ca.

To see the configured committment statement for the ARK instead of resolving to its target, append `?info` to the end of the ARK, e.g., `http://127.0.0.1:8000/ark:/12345/x910?info`.

### Creating a new ARK

REST clients can provide a `shoulder` and/or an `identifer` value in the requst body. If either of these is not provided, larkm will provide it. If an identifier is provided, it should not contain a shoulder. Clients must always provide a `target`.  Clients cannot provide a NAAN.

To add a new ARK (for example, to resolve to https://digital.lib.sfu.ca), issue the following request using curl:

`curl -v -X POST "http://127.0.0.1:8000/larkm" -H 'Content-Type: application/json' -d '{shoulder": "s1", "identifier": "222222", "target": "https://digital.lib.sfu.ca"}'`

If you now visit `http://127.0.0.1:8000/ark:/12345/s1222222` in your web browser, you will be redirected to https://digital.lib.sfu.ca.

If you omit the `shoulder`, the configured default shoulder will be used. If you omit the `identifier`, larkm will mint one using a v4 UUID.

All responses to a POST will include in their body `shoulder`, `identifier` and `target` and metadata and `policy` values provided in the POST request. The `where` value will be identical to the provided`target` value. Metadata values not provided will get the ERC ":at" ("the real value is at the given URL or identifier") value:

`{"ark":{"shoulder": "x1", "identifier": "fb5a9ce4-7092-4eaa-8897-d2ba21eea159"", "ark_string":"ark:/12345/x1fb5a9ce4-7092-4eaa-8897-d2ba21eea159","target":"https://digital.lib.sfu.ca", "who":":at", "when":":at", "where":"https://digital.lib.sfu.ca", "what":":at"}}`

Values provided in the request body for `what`, `who`, `when`, and `policy` will be returned in the response:

`curl -v -X POST "http://127.0.0.1:8000/larkm" -H 'Content-Type: application/json' -d '{shoulder": "s1", "target": "https://digital.lib.sfu.ca", "who": "Jordan, Mark", "when": "2020", "policy": "We commit to maintaining this ARK for a long time."}'`

will return

`{"ark":{"shoulder": "x1", "identifier": "8dfdf979-c977-4060-affd-f7a8aa87ae89", "ark_string":"ark:/12345/8dfdf979-c977-4060-affd-f7a8aa87ae89","target":"https://digital.lib.sfu.ca", "who":"Jordan, Mark", "when":"2020", "where":"https://digital.lib.sfu.ca", "policy":"We commit to maintaining this ARK for a long time."}}`

### Updating an ARK's target URL and metadata

You can update an existing ARK's target, metadata, or policy statement. However, an ARK's `shoulder`, `identifier`, and `ark_string` cannot be updated. `ark_string` is a required body field, and the ARK NAAN, shoulder, and identifier provided in the PUT request URL must match those in the "ark_string" body field.

Some sample queries:

`curl -v -X PUT "http://127.0.0.1:8000/larkm/ark:/12345/s912" -H 'Content-Type: application/json' -d '{"ark_string": "ark:/12345/s912", "target": "https://summit.sfu.ca"}'`

`curl -v -X PUT "http://127.0.0.1:8000/larkm/ark:/12345/s912" -H 'Content-Type: application/json' -d '{"ark_string": "ark:/12345/s912", "who": "Jordan, Mark", "when": "2020", "policy": "We will maintain this ARK for a long time."}'`

### Getting the target URL for an ARK, or an ARK of a URL

If you want to know the target URL associated with an ARK without resolving to that URL, do this:

`curl "http://127.0.0.1:8000/larkm?ark_string=ark:/12345/x912"`

If you want the ARK for a URL, do this:

`curl "http://127.0.0.1:8000/larkm?target=https://www.lib.sfu.ca"`

In both cases, larkm will return a JSON response body that looks like this:

`{"ark_string": "ark:/12345/x912", "target": "https://www.lib.sfu.ca"}`

or a 404 if the ARK or URL you used in your request wasn't found.

### Deleting an ARK

Delete an ARK using a request like:

`curl -v -X DELETE "http://127.0.0.1:8000/larkm/ark:/12345/x912"`

If the ARK was deleted, larkm returns a `204 No Content` response with no body. If the ARK was not found, larkm returns a `404` response with the body `{"detail":"ARK not found"}`.

## API docs

Thanks to [OpenAPI](https://github.com/OAI/OpenAPI-Specification), you can see larkm's API docs by visiting http://127.0.0.1:8000/docs#.

## Shoulders

Following ARK best practice, larkm requires the use of [shoulders](https://wiki.lyrasis.org/display/ARKs/ARK+Identifiers+FAQ#ARKIdentifiersFAQ-shouldersWhatisashoulder?) in newly added ARKs. Shoulders allowed within your NAAN are defined in the "default_shoulder" and "allowed_shoulders" configuration settings. When a new ARK is added, larkm will validate that the ARK string starts with either the default shoulder or one of the allowed shoulders. Note however that larkm does not validate the [format of shoulders](https://wiki.lyrasis.org/display/ARKs/ARK+Shoulders+FAQ#ARKShouldersFAQ-HowdoIformatashoulder?).

## Using Names to Things' global resolver

If you have a registered NAAN that points to the server running larkm, you can use the Names to Things global ARK resolver's domain redirection feature by replacing the hostname of the server larkm is running on with `https://n2t.net/`. For example, if your the local server larkm is runnin on is `https://ids.myorg.ca`, and your insitution's NAAN is registered to use that hostname, you can use a local instance of larkm to manage ARKs like `https://n2t.net/ark:/12345/x910` (using your NAAN instead of `12345`) and they will resolve through your local larkm running on `https://ids.myorg.ca` to their target URLs.

An advantage of doing this is that if your local resolver needs to be changed from `https://ids.myorg.ca/` to another host, assuming you update your NAAN record to use the new host, requests to `https://n2t.net/ark:/12345/x910` will continue to resolve to their targets.

## Development

* Run `larkm.py` and `test_larkm.py` through pycodestyle: `pycodestyle --show-source --show-pep8 --ignore=E402,W504 --max-line-length=200 *.py`
* To run tests:
   * you don't need to start the web server
   * within the larkm directory, copy `larkm.json.sample` to `larkm.json` (back up `larkm.json` first if you have custom values in it)
   * execute `pytest`

## License

MIT