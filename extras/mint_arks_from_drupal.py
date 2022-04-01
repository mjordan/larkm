import os
import csv
import requests
import json
from datetime import datetime

"""
Sample script to create ARKs from the output of the larkm_integration
Drupal module (https://github.com/mjordan/larkm_integration). See that
module's README for more information.

By default, this output is a JSON list containing objects with the keys
'title', 'uuid', and 'nid'. If you add data to the View for 'who', 'when',
and 'policy' ARK metadata, you will need to modify the code below that
populates those ARK fields.
"""

# You will need to set these variables.
drupal_host = 'https://mydrupalhost.org'
larkm_host = 'http://mylarkmhost.org'
shoulder = 'x1'
delete_todays_data = False

# You shouldn't need to modify anything below this line.
dt = datetime.now()
today = dt.strftime('%Y%m%d')
today_json_file_path = f'nodes_{today}.json'

drupal_endpoint = drupal_host.rstrip('/') +  '/larkm_daily_nodes?_format=json&created_date=' + today
r = requests.get(drupal_endpoint)
with open(today_json_file_path, 'w') as output_file:
    output_file.write(r.text)

with open(today_json_file_path, 'r') as input_file:
  records = json.load(input_file)

for record in records:
    larkm_host = larkm_host.rstrip('/')
    endpoint = f'{larkm_host}/larkm'
    headers = {'Content-Type': 'application/json'}
    target = f"{drupal_host.rstrip('/')}/node/{record['nid']}"
    data = {"target": target, "what": record['title']}
    if 'uuid' in record and len(record['uuid']) > 0:
        data['identifier'] = record['uuid']
    # Data for these ARK fields are not included in the Drupal View
    # by default. If you want to populate them, you will need to modify
    # the View to include the source Drupal fields, and modify the code
    # here to map those values to 'who', 'when', and 'policy' ARK fields.
    # If left unused, larkm will provide default values (see larkm's
    # README for more information).
    if 'who' in record and len(record['who']) > 0:
        data['who'] = record['who']
    if 'when' in record and len(record['when']) > 0:
        data['when'] = record['when']
    if 'policy' in record:
        data['policy'] = record['policy']

    r = requests.post(endpoint, json=data, headers=headers)
    # For POST (create ARK) requests, if the provided UUID is already
    # in use, larkm returns a response code of 409.
    if r.status_code != 201:
        print(f"Could not mint ARK for node {record['nid']}. Response code is {r.status_code}.")

if delete_todays_data:
    os.remove(today_json_file_path)
