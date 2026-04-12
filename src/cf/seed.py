import json
import sys
from pathlib import Path

from cf.config import DATA_DIR
from cf.db import (
    clear_all,
    get_connection,
    init_db,
    insert_command,
    insert_embedding,
    insert_pattern,
)
from cf.embeddings import encode_batch, to_bytes


def load_seed_files(data_dir: Path = DATA_DIR) -> list[dict]:
    files = sorted(data_dir.glob("*.json"))
    if not files:
        print(f"No seed files found in {data_dir}", file=sys.stderr)
        return []
    all_data = []
    for f in files:
        with open(f) as fh:
            data = json.load(fh)
            all_data.append(data)
        print(f"  Loaded {f.name}: {len(data['commands'])} commands", file=sys.stderr)
    return all_data


def seed_database(db_path=None, force: bool = False) -> dict:
    from cf.config import DB_PATH
    db_path = db_path or DB_PATH

    conn = get_connection(db_path)
    init_db(conn)

    if force:
        print("Clearing existing data...", file=sys.stderr)
        clear_all(conn)

    print("Loading seed files...", file=sys.stderr)
    all_data = load_seed_files()
    if not all_data:
        return {"commands": 0, "patterns": 0}

    # Collect all patterns with their metadata
    all_patterns = []  # (category, cmd_data, pattern_data)
    for category_data in all_data:
        category = category_data["category"]
        for cmd in category_data["commands"]:
            for pat in cmd["patterns"]:
                all_patterns.append((category, cmd, pat))

    # Batch encode all pattern texts
    texts = [p[2]["text"] for p in all_patterns]
    print(f"Encoding {len(texts)} patterns...", file=sys.stderr)
    embeddings = encode_batch(texts)

    # Insert into database
    print("Inserting into database...", file=sys.stderr)
    cmd_cache = {}  # (category, name) -> command_id
    cmd_count = 0
    pat_count = 0

    for i, (category, cmd, pat) in enumerate(all_patterns):
        cache_key = (category, cmd["name"])
        if cache_key not in cmd_cache:
            cmd_id = insert_command(
                conn, cmd["name"], category, cmd["synopsis"], cmd["description"]
            )
            cmd_cache[cache_key] = cmd_id
            cmd_count += 1

        pat_id = insert_pattern(
            conn,
            cmd_cache[cache_key],
            pat["type"],
            pat["text"],
            pat["command"],
            pat.get("explanation"),
        )
        insert_embedding(conn, pat_id, to_bytes(embeddings[i]))
        pat_count += 1

    conn.commit()
    conn.close()
    print(f"Done: {cmd_count} commands, {pat_count} patterns indexed.", file=sys.stderr)
    return {"commands": cmd_count, "patterns": pat_count}
