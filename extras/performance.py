import requests
import random
import time
import json
import sys

"""Simple timer script to test larkm's performance.

Usage: python performance.py 1000

where 1000 is the number of ARKs you want the script to operate on. If you want to
run multiple instances of this script at the same time to test concurrent load on
larkm, in Linux run:

python performance.py 1000 &
python performance.py 1000 &
python performance.py 1000 &

etc.

Since this script hits a larkm endpoint, you will need to create a config file for this
test and launch an instance of larkm accessible at the location specified in the larkm_url
variable below. You will probably need to wipe your larkm database between runs of this script.

"""

number_requests = int(sys.argv[1])
larkm_url = "http://localhost:8000/larkm"
naan = "12345"
api_key = "myapikey"

# Create some ARKs.
start_create_timer = time.perf_counter()
ark_strings = []
for create in range(number_requests):
    headers = {"Content-Type": "application/json", "Authorization": api_key}
    rand_string = random.randint(1, 10000000)
    data = {
        "naan": naan,
        "target": f"https://example.com/{rand_string}",
        "policy": "cheers",
    }
    r = requests.post(larkm_url, json=data, headers=headers)
    if r.status_code == 201:
        body = json.loads(r.text)
        ark_strings.append(body["ark"]["ark_string"])
    else:
        print(f"Response from larkm was {r.status_code}, {r.text}")

stop_create_timer = time.perf_counter()

print(
    f"Created {number_requests} ARKs in {stop_create_timer - start_create_timer:0.4f} seconds."
)

# Resolve the ARKs.
start_resolve_timer = time.perf_counter()

for ark_string in ark_strings:
    url = f"http://localhost:8000/{ark_string}"
    r = requests.get(url, allow_redirects=False)

stop_resolve_timer = time.perf_counter()

print(
    f"Resolved {number_requests} ARKs in {stop_resolve_timer - start_resolve_timer:0.4f} seconds."
)

# Update the ARKs.
start_update_timer = time.perf_counter()

for ark_string in ark_strings:
    url = f"http://localhost:8000/larkm/{ark_string}"
    headers = {"Content-Type": "application/json", "Authorization": api_key}
    data = {"ark_string": ark_string, "policy": "foo"}
    r = requests.patch(url, json=data, headers=headers)

stop_update_timer = time.perf_counter()

print(
    f"Updated {number_requests} ARKs in {stop_update_timer - start_update_timer:0.4f} seconds."
)
