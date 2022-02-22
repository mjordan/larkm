# larkm: A Lightweight ARK Manager

# Overview

larkm is a simple [ARK](https://arks.org/) manager that can:

* persist new ARKs
* mint ARKs using UUID (v4) strings
* validate ARK shoulders
* resolve ARKs to their target URLs
* update the target URLs of existing ARKs
* provide the target URLs of ARKs it manages, and provide the ARK associated with a URL.
* delete ARKs

ARK resolution is provided via requests to larkm's host followed by an ARK (e.g. `https://myhost.net/ark:/99999/876543`) and the other operations are provided through standard REST requests to larkm's management endpoint (`/larkm`).

larkm is currently only a proof of concept as we learn about locally mananging ARKs. Features such as support for [policy statements](https://arks.org/about/best-practices/), persisting to a database, access control for the REST interface, and automated code tests are yet to come.

It is considered "lightweight" because it supports only a subset of ARK functionality, focusing on providing ways to manage ARKs locally and on ARKs as persistent, resolvable identifiers. ARK features such as suffix passthrough and metadata management are currently out of scope.

## Requirements

* Python 3.6+
* [FastAPI](https://fastapi.tiangolo.com/)
* [Uvicorn](https://www.uvicorn.org/) for demo/testing, or some other ASGI web server for production uses.
* To have your ARKs resolve from [N2T](http://n2t.net/), you will to register a NAAN (Name Assigning Authority Number) using [this form](https://goo.gl/forms/bmckLSPpbzpZ5dix1).

## Usage

### Configuration

larkm uses a JSON configuration file in the same directory as `larkm.py` named `larkm.json`. Copy the sample configuration file, `larkm.json.sample`, to `larkm.json`, make any changes you need, and you are good to go. Currently, there are three config settings, "NAAN" (which is your insitution's Name Assigning Authority Number), "default_shoulder" (the ARK shoulder applied to new ARKs if one is not provided), and "allowed_shoulders" (a list of shoulders that are allowed in new ARKs provided by clients). If your default shoulder is the only one currently used by your NAAN, provide an empty list for "allowed_shoulders" (e.g. `[]`).

```json
{
  "NAAN": "99999",
  "default_shoulder": "s1",
  "allowed_shoulders": ["x1", "z9"]
}
```

### Starting larkm

To start the larkm app within local Uvicorn we server, in a terminal run `python3 -m uvicorn larkm:app`

### Resolving an ARK

Visit `http://127.0.0.1:8000/ark:/99999/x910` in your browser. You will be redirected to https://www.lib.sfu.ca.

### Creating a new ARK

To add a new ARK (for example, to resolve to https://digital.lib.sfu.ca), issue the following request using curl:

`curl -v -X POST "http://127.0.0.1:8000/larkm" -H 'Content-Type: application/json' -d '{"ark_string": "ark:/99999/x912", "target": "https://digital.lib.sfu.ca"}'`

If you now visit `http://127.0.0.1:8000/ark:/99999/x912` in your web browser, you will be redirected to https://digital.lib.sfu.ca.

In this case, the client provides a full ARK string (including the shoulder), including the NAAN and identifier. If you want larkm to mint a new ARK using the NAAN defined in your configuration file and a UUID (v4) as the identifier, remove "ark_string" from your request body:

`curl -v -X POST "http://127.0.0.1:8000/larkm" -H 'Content-Type: application/json' -d '{"target": "https://digital.lib.sfu.ca"}'`

In the previous request, the ARK string will include the default shoulder. If you want larkm to mint an ARK but use a different shoulder, include the shoulder in your request body, like this:

`curl -v -X POST "http://127.0.0.1:8000/larkm" -H 'Content-Type: application/json' -d '{"shoulder": "x1", "target": "https://digital.lib.sfu.ca"}'`

If the provided shoulder is not present in your configuration settings, or the provided ARK string does not begin with one of the configured shoulders, larkm will return a 422 HTTP response.

All responses to a PUT will include in their body the "shoulder, "ark_string" and "target":

`{"ark":{"shoulder": "x1", "ark_string":"ark:/99999/x1fb5a9ce4-7092-4eaa-8897-d2ba21eea159","target":"https://digital.lib.sfu.ca"}}`

### Updating the target URL associated with an ARK

Update an ARK using a request like:

`curl -v -X PUT "http://127.0.0.1:8000/larkm/ark:/99999/x912" -H 'Content-Type: application/json' -d '{"ark_string": "ark:/99999/12", "target": "https://summit.sfu.ca"}'`

Note that the ARK string in the request URL and in the "ark_string" body field must be identical.

### Getting the target URL for an ARK, or an ARK of a URL

If you want to know the target URL associated with an ARK without resolving to that URL, do this:

`curl "http://127.0.0.1:8000/larkm?ark_string=ark:/99999/x912"`

If you want the ARK for a URL, do this:

`curl "http://127.0.0.1:8000/larkm?target=https://www.lib.sfu.ca"`

In both cases, larkm will return a JSON response body that looks like this:

`{"ark_string": "ark:/99999/x912", "target": "https://www.lib.sfu.ca"}`

or a 404 if the ARK or URL you used in your request wasn't found.

### Deleting an ARK

Delete an ARK using a request like:

`curl -v -X DELETE "http://127.0.0.1:8000/larkm/ark:/99999/x912"`

If the ARK was deleted, larkm returns a `204 No Content` response with no body. If the ARK was not found, larkm returns a `404` response with the body `{"detail":"ARK not found"}`.

## API docs

Thanks to [OpenAPI](https://github.com/OAI/OpenAPI-Specification), you can see larkm's API docs by visiting http://127.0.0.1:8000/docs#.

## Shoulders

Following ARK best practice, larkm requires the use of [shoulders](https://wiki.lyrasis.org/display/ARKs/ARK+Identifiers+FAQ#ARKIdentifiersFAQ-shouldersWhatisashoulder?) in newly added ARKs. Shoulders allowed within your NAAN are defined in the "default_shoulder" and "allowed_shoulders" configuration settings. When a new ARK is added, larkm will validate that the ARK string starts with either the default shoulder or one of the allowed shoulders. Note however that larkm does not validate the [format of shoulders](https://wiki.lyrasis.org/display/ARKs/ARK+Shoulders+FAQ#ARKShouldersFAQ-HowdoIformatashoulder?).

## Using Names to Things' redirection service

If you have a registered NAAN that points to the server running larkm, you can use the Names to Things global ARK resolver's domain redirection feature by replacing the hostname of the server larkm is running on with `https://n2t.net/`. For example, if your the local server larkm is runnin on is `https://ids.myorg.ca`, and your insitution's NAAN is registered to use that hostname, you can use a local instance of larkm to manage ARKs like `https://n2t.net/ark:/99999/x910` (using your NAAN instead of `99999`) and they will resolve through your local larkm running on `https://ids.myorg.ca` to their target URLs.

An advantage of doing this is that if your local resolver needs to be changed from `https://ids.myorg.ca/` to another host, assuming you update your NAAN record to use the new host, requests to `https://n2t.net/ark:/99999/x910` will continue to resolve to their targets.

## License

MIT