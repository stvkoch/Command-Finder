import json
import sys
from pathlib import Path

from cf.config import DATA_DIR
from cf.db import (
    bulk_load_pragmas,
    clear_all,
    get_connection,
    init_db,
    insert_commands_batch,
    insert_embeddings_batch,
    insert_patterns_batch,
    restore_pragmas,
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

    # ── Phase 1: Flatten and collect ─────────────────────────
    # Build ordered lists for batch operations
    cmd_rows = []       # (name, category, synopsis, description)
    cmd_keys = []       # tracks which command each row belongs to
    cmd_seen = {}       # (category, name) -> index in cmd_rows
    pat_meta = []       # (cmd_index, type, text, template, explanation, destructive)

    for category_data in all_data:
        category = category_data["category"]
        for cmd in category_data["commands"]:
            key = (category, cmd["name"])
            if key not in cmd_seen:
                cmd_seen[key] = len(cmd_rows)
                cmd_rows.append((cmd["name"], category, cmd["synopsis"], cmd["description"]))
            cmd_idx = cmd_seen[key]
            for pat in cmd["patterns"]:
                pat_meta.append((
                    cmd_idx,
                    pat["type"],
                    pat["text"],
                    pat["command"],
                    pat.get("explanation"),
                    1 if pat.get("destructive") else 0,
                ))

    # ── Phase 2: Encode embeddings (cached) ──────────────────
    texts = [p[2] for p in pat_meta]
    print(f"Encoding {len(texts)} patterns...", file=sys.stderr)
    embeddings = encode_batch(texts)

    # ── Phase 3: Batch insert into DB ────────────────────────
    print("Inserting into database...", file=sys.stderr)
    bulk_load_pragmas(conn)

    # Insert all commands in one batch
    cmd_ids = insert_commands_batch(conn, cmd_rows)

    # Build pattern rows with resolved command IDs
    pat_rows = [
        (cmd_ids[cm_idx], ptype, text, tmpl, expl, destructive)
        for cm_idx, ptype, text, tmpl, expl, destructive in pat_meta
    ]
    pat_ids = insert_patterns_batch(conn, pat_rows)

    # Build embedding rows with resolved pattern IDs
    emb_rows = [
        (pat_ids[i], to_bytes(embeddings[i]))
        for i in range(len(pat_ids))
    ]
    insert_embeddings_batch(conn, emb_rows)

    conn.commit()
    restore_pragmas(conn)
    conn.close()

    cmd_count = len(cmd_rows)
    pat_count = len(pat_meta)
    print(f"Done: {cmd_count} commands, {pat_count} patterns indexed.", file=sys.stderr)
    return {"commands": cmd_count, "patterns": pat_count}
