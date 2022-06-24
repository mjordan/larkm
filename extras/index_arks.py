"""Processes all rows in a table.

   Usage: python index_arks.py path/to/larkm.json
"""

import sys
import os
import os.path
import sqlite3
import json
from uuid import uuid4
from whoosh.fields import Schema, TEXT, ID
from whoosh import index

larkm_config_file = sys.argv[1]
with open(larkm_config_file, "r") as config_file:
    config = json.load(config_file)

schema = Schema(identifier=ID(stored=True),
                date_created=TEXT,
                date_modified=TEXT,
                shoulder=TEXT,
                ark_string=TEXT,
                target=TEXT,
                erc_who=TEXT,
                erc_what=TEXT,
                erc_when=TEXT,
                erc_where=TEXT,
                policy=TEXT
                )

if not os.path.exists(config['whoose_index_dir_path']):
    os.mkdir(config['whoose_index_dir_path'])

idx = index.create_in(config['whoose_index_dir_path'], schema)

writer = idx.writer()

conn = sqlite3.connect(config['sqlite_db_path'])
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

cursor.execute("SELECT Count() FROM arks")
num_rows = cursor.fetchone()[0]

page_size = 100
offset = 0
while offset < num_rows:
    cursor.execute("SELECT * FROM arks LIMIT ? OFFSET ?", [page_size, offset])
    rows = cursor.fetchall()
    offset = offset + page_size
    for row in rows:
        writer.add_document(
            identifier=row['identifier'],
            date_created=row['date_created'],
            date_modified=row['date_modified'],
            shoulder=row['shoulder'],
            ark_string=row['ark_string'],
            target=row['target'],
            erc_who=row['erc_who'],
            erc_what=row['erc_what'],
            erc_when=row['erc_when'],
            erc_where=row['erc_where'],
            policy=row['policy']
        )

writer.commit()
conn.close()
