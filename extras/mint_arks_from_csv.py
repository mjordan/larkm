import csv
import json
import requests

"""
Input CSV must contain a 'target' column and a 'title' column.
Optional columns are 'who', 'when', 'policy', and 'uuid'. If 'uuid'
is present, its value will be used as the identifier string in the ARK.

Columns present in the input CSV other than those named above will be
written to the output CSV. This allows you to include columns such as
"node_id" so the output CSV can be used to update items in the target
website.

Usage: 1) Make sure the IP address of the machine running this script is
present in larkm's "trusted_ips" configuration option. 2) Change the six
variables below to your own values. 3) Run python mint_arks_from_csv.py.
"""

input_filename = "input.csv"
output_filename = "output.csv"
larkm_host = "http://localhost:8000/"
# Leave shoulder empty if you want to use larkm's default shoulder.
shoulder = ""
# You must provide a NAAN.
naan = "99999"
# Leave api_key empty if larkm is not configured to use API keys.
api_key = "myapikey"

# Set to True to confirm that the ARK was created successfully by
# requesting a redirection to the "target" value in the input CSV.
# If this is set to True, your output CSV will contain a column with
# the header "test_resolution" containing the result of the request.
confirm_arks = True

####################
# Create the ARKs. #
####################

# Open input CSV.
input_csv_reader_file_handle = open(input_filename, "r", encoding="utf-8", newline="")
input_csv_reader = csv.DictReader(input_csv_reader_file_handle)
input_csv_reader_fieldnames = input_csv_reader.fieldnames
input_csv_reader_fieldnames.append("ark_local_resolver")
input_csv_reader_fieldnames.append("ark_n2t_resolver")
if confirm_arks is True:
    input_csv_reader_fieldnames.append("test_resolution")

# Write out CSV with columns from input CSV plus ARKs.
writer_file_handle = open(output_filename, "w+", newline="")
writer = csv.DictWriter(writer_file_handle, fieldnames=input_csv_reader_fieldnames)
writer.writeheader()

for row in input_csv_reader:
    larkm_host = larkm_host.rstrip("/")
    endpoint = f"{larkm_host}/larkm"
    if len(api_key) == 0:
        headers = {"Content-Type": "application/json"}
    else:
        headers = {"Content-Type": "application/json", "Authorization": api_key}
    data = {"target": row["target"], "naan": naan, "what": row["title"]}
    if "uuid" in row and len(row["uuid"]) > 0:
        data["identifier"] = row["uuid"]
    if "who" in row and len(row["who"]) > 0:
        data["who"] = row["who"]
    if "when" in row and len(row["when"]) > 0:
        data["when"] = row["when"]
    if "policy" in row:
        data["policy"] = row["policy"]
    if len(shoulder) > 0:
        data["shoulder"] = shoulder

    r = requests.post(endpoint, json=data, headers=headers)
    if r.status_code == 201:
        body = json.loads(r.text)
        row["ark_local_resolver"] = f'{larkm_host}/{body["ark"]["ark_string"]}'
        row["ark_n2t_resolver"] = f'https://n2t.net/{body["ark"]["ark_string"]}'

        if confirm_arks is True:
            cr = requests.get(row["ark_local_resolver"], allow_redirects=False)
            if cr.headers.get('location') == row["target"]:
                row["test_resolution"] = "confirmed"
            else:
                row["test_resolution"] = "ARK not resolving"
    else:
        print(f"Could not mint ARK. Response code is {r.status_code}.")
        row["ark_local_resolver"] = "error"
        row["ark_n2t_resolver"] = "error"

    writer.writerow(row)

writer_file_handle.close()

print(f"Your CSV containing ARKs is at {output_filename}.")
