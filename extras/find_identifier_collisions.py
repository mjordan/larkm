"""Script to see how many UUID-based strings (of a configurable length)
can be generated before a duplicate is generated.
"""

import uuid
import logging
import concurrent.futures

max_workers = 1

identifiers = list()
max_number_identifiers = 100000000
identifier_length = 12

logging.basicConfig(
    filename="identifier_collisions.log",
    level=logging.INFO,
    format="%(asctime)s - %(message)s",
    datefmt="%d-%b-%y %H:%M:%S",
)


def generate_identifier():
    uuid_string = str(uuid.uuid4())
    identifier = uuid_string.replace("-", "")
    identifier = identifier[:12]
    if identifier not in identifiers:
        identifiers.append(identifier)
        print(f"Adding {identifier} to list of {len(identifiers)} identifiers.")
    else:
        message = f"Found duplicate identifier {identifier} at {len(identifiers)} identifiers."
        logging.info(message)


if __name__ == "__main__":
    logging.info(f"Script started using {max_workers} thread(s).")
    if max_workers > 1:
        executor = concurrent.futures.ProcessPoolExecutor(max_workers=max_workers)
        futures = [
            executor.submit(generate_identifier)
            for attempt in range(max_number_identifiers)
        ]
        executor.shutdown()
    else:
        for attempt in range(max_number_identifiers):
            generate_identifier()
