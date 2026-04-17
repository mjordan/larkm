import os
import sys
import csv
import json
import argparse
import sqlite3
import uuid

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
variables below to your own values. 3) Run python mint_arks_from_csv.py
with the desired command-line arguments.
"""

parser = argparse.ArgumentParser()
parser.add_argument(
    "--input_csv",
    help="Relative or absolute path to your input CSV. Defaults to input.csv.",
    default="input.csv",
)
parser.add_argument(
    "--output_csv",
    help="Relative or absolute path to your output CSV. Defaults to output.csv.",
    default="output.csv",
)
parser.add_argument(
    "--larkm_host",
    help="Hostname of the server running larkm, includig the leading https://. Trailing slash is optional. Defaults to http://localhost:8000/.",
    required=True,
)
parser.add_argument(
    "--larkm_db_file_path",
    help="The path to the larkm SQLite3 database file.",
)
parser.add_argument(
    "--naan",
    help="The shoulder to use in the ARKs. Required.",
    required=True,
)
parser.add_argument(
    "--shoulder",
    help="The NAAN to use in the ARKs. Defaults to larkm's default shoulder.",
    default="",
)
parser.add_argument(
    "--larkm_api_key",
    help="An API key registered with larkm.",
)
parser.add_argument(
    "--larkm_api_key_file_path",
    help="Path to a file containing An API key registered with larkm. File should only have a single line, containing the key.",
)
parser.add_argument(
    "--confirm_arks",
    help='Whether or not to to confirm that the ARK was created successfully by requesting a redirection to the "target" value in the input CSV.',
    action="store_true",
)
args = parser.parse_args()

####################
# Create the ARKs. #
####################

# Either the --larkm_api_key or the --larkm_api_key_file_path arguments is required,
# unless the user has specified the path to the larkm SQLite db.
if args.larkm_api_key is None and args.larkm_api_key_file_path is not None:
    if os.path.exists(args.larkm_api_key_file_path) is True:
        with open(args.larkm_api_key_file_path) as f:
            api_key = f.readline().strip()
    else:
        sys.exit(f'Error: API key file "{args.larkm_api_key_file_path}" not found.')
elif args.larkm_api_key_file_path is None and args.larkm_api_key is not None:
    api_key = args.larkm_api_key
else:
    if args.larkm_db_file_path is None:
        sys.exit(
            "Either the --larkm_api_key or the --larkm_api_key_file_path arguments is required."
        )

if args.larkm_db_file_path is not None:
    persister = "local_db"
    if os.path.exists(args.larkm_db_file_path) is False:
        sys.exit(f'Error: larkm database file "{args.larkm_db_file_path}" not found.')
    else:
        con = sqlite3.connect(args.larkm_db_file_path)
else:
    persister = "rest"

# Open input CSV.
input_csv_reader_file_handle = open(args.input_csv, "r", encoding="utf-8", newline="")
input_csv_reader = csv.DictReader(input_csv_reader_file_handle)
input_csv_reader_fieldnames = input_csv_reader.fieldnames
input_csv_reader_fieldnames.append("ark_local_resolver")
input_csv_reader_fieldnames.append("ark_n2t_resolver")
if args.confirm_arks is True:
    input_csv_reader_fieldnames.append("test_resolution")

# Write out CSV with columns from input CSV plus ARKs.
writer_file_handle = open(args.output_csv, "w+", newline="", encoding="utf-8")
writer = csv.DictWriter(writer_file_handle, fieldnames=input_csv_reader_fieldnames)
writer.writeheader()

for row in input_csv_reader:
    data = {"target": row["target"], "naan": args.naan, "what": row["title"]}
    if "uuid" in row and len(row["uuid"]) > 0:
        data["identifier"] = row["uuid"]
    else:
        data["identifier"] = str(uuid.uuid4())
    if "uuid" in row and len(row["uuid"]) > 0:
        data["identifier"] = row["uuid"]
    if "who" in row and len(row["who"]) > 0:
        data["who"] = row["who"]
    if "when" in row and len(row["when"]) > 0:
        data["when"] = row["when"]
    if "policy" in row:
        data["policy"] = row["policy"]
    if len(args.shoulder) > 0:
        data["shoulder"] = args.shoulder

    if persister == "rest":
        larkm_host = args.larkm_host.rstrip("/")
        endpoint = f"{larkm_host}/larkm"
        if len(api_key) == 0:
            headers = {"Content-Type": "application/json"}
        else:
            headers = {"Content-Type": "application/json", "Authorization": api_key}

        try:
            r = requests.post(endpoint, json=data, headers=headers)
            if r.status_code == 201:
                body = json.loads(r.text)
                row["ark_local_resolver"] = f'{larkm_host}/{body["ark"]["ark_string"]}'
                row["ark_n2t_resolver"] = f'https://n2t.net/{body["ark"]["ark_string"]}'

                try:
                    if args.confirm_arks is True:
                        cr = requests.get(
                            row["ark_local_resolver"], allow_redirects=False
                        )
                        if cr.headers.get("location") == row["target"]:
                            row["test_resolution"] = "confirmed"
                        else:
                            row["test_resolution"] = "ARK not resolving"
                except Exception as e:
                    print(
                        f'Sorry, there was a problem confirming the ARK, error connecting to {row["ark_local_resolver"]}: {e}'
                    )

                print(
                    f'ARK for "{row["title"]}" ({row["target"]}) registered with larkm.'
                )
            else:
                print(
                    f"Could not mint ARK. Response code is {r.status_code}, response body is {r.text}."
                )
                row["ark_local_resolver"] = "error"
                row["ark_n2t_resolver"] = "error"
        except Exception as e:
            print(f"Sorry, there was a problem connecting to {endpoint}: {e}")
            continue
    if persister == "local_db":
        # policy column is required if we're persisting ARKs directly to the database, since
        # larkm adds the default policy statement if there is none provided.
        if "policy" not in row or row["policy"] is None:
            sys.exit(
                'If you are using the "--larkm_db_file_path" option, your input CSV must contain values in the "policy" column.'
            )

        # First check to see if the target is already registered. larkm doesn't allow
        # multiple ARKs to use the same target, other than an empty target.
        if len(row["target"].strip()) > 0:
            try:
                con.row_factory = sqlite3.Row
                cur = con.cursor()
                cur.execute(
                    "select ark_string from arks where target = :a_s",
                    {"a_s": row["target"]},
                )
                records = cur.fetchall()
                if len(records) > 0:
                    ark_strings = []
                    for record in records:
                        ark_strings.append(record["ark_string"])
                    if len(ark_strings) > 0 and record["ark_string"] in ark_strings:
                        print(
                            f'WARNING: Target {row["target"]} is already used by ARK {record["ark_string"]}. Ark not created.'
                        )
                        continue
            except sqlite3.DatabaseError as e:
                print(e)
                continue

        identifier = data["identifier"].replace("-", "")[:12]
        ark_string = f"ark:{args.naan}/{args.shoulder}{identifier}"
        larkm_host = args.larkm_host.rstrip("/")

        columns = ["title", "who", "when", "policy", "uuid"]
        for column in columns:
            if column not in row or len(row[column]) == 0:
                data[column] = ":at"
            else:
                data[column] = row[column]

            # We allow empty targets.
            data["target"] = row["target"]
        try:
            ark_data = (
                data["shoulder"],
                data["identifier"],
                ark_string,
                row["target"],
                data["who"],
                data["what"],
                data["when"],
                ark_string,
                data["policy"],
            )
            cur = con.cursor()
            cur.execute(
                "insert into arks values (datetime(), datetime(), ?,?,?,?,?,?,?,?,?)",
                ark_data,
            )
            con.commit()
            row["ark_local_resolver"] = f"{larkm_host}/{ark_string}"
            row["ark_n2t_resolver"] = f"https://n2t.net/{ark_string}"
            print(f'ARK for "{row["title"]}" ({row["target"]}) added to the database.')

            if args.confirm_arks is True:
                try:
                    cr = requests.get(row["ark_local_resolver"], allow_redirects=False)
                    if cr.headers.get("location") == row["target"]:
                        row["test_resolution"] = "confirmed"
                    else:
                        row["test_resolution"] = "ARK not resolving"
                except Exception as e:
                    print(
                        f'Sorry, there was a problem confirming the ARK, error connecting to {row["ark_local_resolver"]}: {e}'
                    )

        except sqlite3.DatabaseError as e:
            print(e)
            continue

    try:
        writer.writerow(row)
    except Exception as e:
        print(e)

if persister == "local_db":
    con.close()

writer_file_handle.close()

print(f"Your CSV containing ARKs is at {args.output_csv}.")
