# larkm: The Lightweight ARK Manager

# Overview

A simple [ARK](https://arks.org/) resolver. Currently only a proof of concept as we learn about locally mananging ARKs.

## Requirements

* Python 3.6+
* Uvicorn
* FastAPI
* To have your ARKs resolve from [N2T](http://n2t.net/), you will to register a NAAN (Name Assigning Authority Number) using [this form](https://goo.gl/forms/bmckLSPpbzpZ5dix1).

## Usage

Start the larkm app within Uvicorn:

1. `python3 -m uvicorn larkm:app --reload`
1. Use the ARK resolver by visiting `http://127.0.0.1:8000/ark:/19837/10` in your browser. You will be redirected to https://www.lib.sfu.ca.
1. Add a new ARK (for example, to resolve to https://digital.lib.sfu.ca) by issuing the following request using curl: `curl -v -X POST  "http://127.0.0.1:8000/larkm" -H 'Content-Type: application/json' -d '{"ark_string": "ark:/19837/12", "target": "https://digital.lib.sfu.ca"}'`
1. Visit the new ARK in your browser, and get redirected to the target URL.
1. If you have a registered NAAN that points to the server running larkm, you can see N2T's domain redirection in action by visiting `https://n2t.net/ark:/19837/10` (using your NAAN instead of `19837`). You should be redirected to the same target that visiting `http://127.0.0.1:8000/ark:/19837/10` redirected you to.

## API docs

Thanks to the magic of [OpenAPI](https://github.com/OAI/OpenAPI-Specification), you can see larkm's API docs by visiting http://127.0.0.1:8000/docs#.

## License

MIT

