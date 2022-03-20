import requests
import random
import time
import json

"""Simple timer script to test larkm's performance. Usage: python performance.py"""

number_requests = 10

# Create some ARKs.
start_create_timer = time.perf_counter()
ark_strings = []
for create in range(number_requests):
    url = f'http://localhost:8000/larkm'
    headers = {'Content-Type': 'application/json'}
    rand_string = random.randint(1, number_requests)
    data = {"target": f'https://example.com/{rand_string}', "policy": "cheers"}
    r = requests.post(url, json=data, headers=headers)
    body = json.loads(r.text)
    ark_strings.append(body['ark']['ark_string'])

stop_create_timer = time.perf_counter()

print(f"Created {number_requests} ARKs in {stop_create_timer - start_create_timer:0.4f} seconds.")

# Resolve the ARKs.
start_resolve_timer = time.perf_counter()

for ark_string in ark_strings:
    url = f'http://localhost:8000/{ark_string}?info'
    r = requests.get(url)

stop_resolve_timer = time.perf_counter()

print(f"Resolved {number_requests} ARKs in {stop_resolve_timer - start_resolve_timer:0.4f} seconds.")

# Update the ARKs.
start_update_timer = time.perf_counter()

for ark_string in ark_strings:
    url = f'http://localhost:8000/larkm/{ark_string}'
    headers = {'Content-Type': 'application/json'}
    data = {"ark_string": ark_string, "policy": "foo"}
    r = requests.put(url, json=data, headers=headers)

stop_update_timer = time.perf_counter()

print(f"Updated {number_requests} ARKs in {stop_update_timer - start_update_timer:0.4f} seconds.")
