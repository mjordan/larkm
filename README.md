# larkm: The Lightweight ARK Manager

# Overview

larkm is a simple [ARK](https://arks.org/) resolver that can:

* persist new ARKs
* resolve ARKs to their target URLs
* update the target URLs of existing ARKs
* provide the target URLs of ARKs it manages, and provide the ARK associated with a URL.

ARK resolution is provided via requests to larkm's host followed by an ARK (e.g. `https://myhost.net/ark:/9999/abcd`) and the other operations are provided through standard REST requests to larkm's management endpoint (`/larkm`).

larkm is currently only a proof of concept as we learn about locally mananging ARKs. Features such as minting new ARKs, persisting to a database, access control for the REST interface, and tests are yet to come.

## Requirements

* Python 3.6+
* [FastAPI](https://fastapi.tiangolo.com/)
* [Uvicorn](https://www.uvicorn.org/) for demo/testing, or some other ASGI web server for production uses.
* To have your ARKs resolve from [N2T](http://n2t.net/), you will to register a NAAN (Name Assigning Authority Number) using [this form](https://goo.gl/forms/bmckLSPpbzpZ5dix1).

## Usage

### Starting larkm

To start the larkm app within local Uvicorn we server, in a terminal run `python3 -m uvicorn larkm:app`

### Resolving an ARK

Visit `http://127.0.0.1:8000/ark:/19837/10` in your browser. You will be redirected to https://www.lib.sfu.ca.

### Adding a new ARK

To add a new ARK (for example, to resolve to https://digital.lib.sfu.ca), issue the following request using curl:

`curl -v -X POST "http://127.0.0.1:8000/larkm" -H 'Content-Type: application/json' -d '{"ark_string": "ark:/19837/12", "target": "https://digital.lib.sfu.ca"}'`

If you now visit `http://127.0.0.1:8000/ark:/19837/12` in your web browser, you will be redirected to https://digital.lib.sfu.ca.

### Updating the target URL associated with an ARK

Update an ARK using a request like:

`curl -v -X PUT "http://127.0.0.1:8000/larkm/ark:/19837/12" -H 'Content-Type: application/json' -d '{"ark_string": "ark:/19837/12", "target": "https://summit.sfu.ca"}'`

## API docs

Thanks to the magic of [OpenAPI](https://github.com/OAI/OpenAPI-Specification), you can see larkm's API docs by visiting http://127.0.0.1:8000/docs#.

## Using Names to Things' redirection service

If you have a registered NAAN that points to the server running larkm, you can see use the Names to Things domain redirection feature by replacing the hostname of the server larkm is running on with `https://n2t.net/`. For example, if your the local server larkm is runnin on is `https://ids.myorg.ca`, and your insitution's NAAN is registered to use that hostname, you can use a local instance of larkm to manage ARKs like `https://n2t.net/ark:/19837/10` (using your NAAN instead of `19837`) and they will resolve through your local larkm running on `https://ids.myorg.ca` to their target URLs.

## License

MIT