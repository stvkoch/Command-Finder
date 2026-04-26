import sqlite3
from pathlib import Path

import sqlite_vec

from cf.config import DB_DIR, DB_PATH, EMBEDDING_DIM


def get_connection(db_path: Path | str = DB_PATH) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(f"""
        CREATE TABLE IF NOT EXISTS commands (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            synopsis TEXT NOT NULL,
            description TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS patterns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            command_id INTEGER NOT NULL REFERENCES commands(id) ON DELETE CASCADE,
            pattern_type TEXT NOT NULL,
            text TEXT NOT NULL,
            command_template TEXT NOT NULL,
            explanation TEXT,
            destructive INTEGER NOT NULL DEFAULT 0
        );

        CREATE VIRTUAL TABLE IF NOT EXISTS pattern_embeddings USING vec0(
            pattern_id INTEGER PRIMARY KEY,
            embedding FLOAT[{EMBEDDING_DIM}]
        );

        CREATE INDEX IF NOT EXISTS idx_patterns_command_id
            ON patterns(command_id);

        CREATE TABLE IF NOT EXISTS query_cache (
            query_text TEXT PRIMARY KEY,
            embedding BLOB NOT NULL
        );
    """)
    # Migrate older DBs that predate the destructive column.
    cols = {row[1] for row in conn.execute("PRAGMA table_info(patterns)")}
    if "destructive" not in cols:
        conn.execute(
            "ALTER TABLE patterns ADD COLUMN destructive INTEGER NOT NULL DEFAULT 0"
        )
    conn.commit()


def get_cached_query(conn: sqlite3.Connection, query: str) -> bytes | None:
    row = conn.execute(
        "SELECT embedding FROM query_cache WHERE query_text = ?", (query,)
    ).fetchone()
    return row[0] if row else None


def cache_query(conn: sqlite3.Connection, query: str, embedding_bytes: bytes) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO query_cache (query_text, embedding) VALUES (?, ?)",
        (query, embedding_bytes),
    )
    conn.commit()


def bulk_load_pragmas(conn: sqlite3.Connection) -> None:
    """Tune PRAGMAs for fast bulk inserts. Call before seeding."""
    conn.execute("PRAGMA synchronous=OFF")
    conn.execute("PRAGMA temp_store=MEMORY")
    conn.execute("PRAGMA cache_size=-64000")  # 64MB cache


def restore_pragmas(conn: sqlite3.Connection) -> None:
    """Restore safe PRAGMAs after bulk load."""
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA temp_store=DEFAULT")
    conn.execute("PRAGMA cache_size=-2000")


def insert_commands_batch(conn: sqlite3.Connection,
                          rows: list[tuple]) -> list[int]:
    """Batch insert commands. rows: [(name, category, synopsis, description), ...]"""
    conn.executemany(
        "INSERT INTO commands (name, category, synopsis, description) VALUES (?, ?, ?, ?)",
        rows,
    )
    # Retrieve the auto-generated IDs for the batch
    last_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    return list(range(last_id - len(rows) + 1, last_id + 1))


def insert_patterns_batch(conn: sqlite3.Connection,
                          rows: list[tuple]) -> list[int]:
    """Batch insert patterns. rows: [(command_id, type, text, template, explanation, destructive), ...]"""
    conn.executemany(
        "INSERT INTO patterns (command_id, pattern_type, text, command_template, explanation, destructive) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        rows,
    )
    last_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    return list(range(last_id - len(rows) + 1, last_id + 1))


def insert_embeddings_batch(conn: sqlite3.Connection,
                            rows: list[tuple]) -> None:
    """Batch insert embeddings. rows: [(pattern_id, embedding_bytes), ...]"""
    conn.executemany(
        "INSERT INTO pattern_embeddings (pattern_id, embedding) VALUES (?, ?)",
        rows,
    )


def search_similar(conn: sqlite3.Connection, query_embedding_bytes: bytes,
                   top_k: int = 10) -> list[dict]:
    rows = conn.execute("""
        SELECT
            p.command_template,
            p.text,
            p.explanation,
            c.name,
            c.description,
            c.synopsis,
            pe.distance,
            p.destructive
        FROM pattern_embeddings pe
        JOIN patterns p ON p.id = pe.pattern_id
        JOIN commands c ON c.id = p.command_id
        WHERE pe.embedding MATCH ?
          AND k = ?
        ORDER BY pe.distance
    """, (query_embedding_bytes, top_k)).fetchall()

    return [
        {
            "command_template": r[0],
            "pattern_text": r[1],
            "explanation": r[2],
            "command_name": r[3],
            "command_description": r[4],
            "synopsis": r[5],
            "distance": r[6],
            "destructive": bool(r[7]),
        }
        for r in rows
    ]


def get_stats(conn: sqlite3.Connection) -> dict:
    cmds = conn.execute("SELECT COUNT(*) FROM commands").fetchone()[0]
    pats = conn.execute("SELECT COUNT(*) FROM patterns").fetchone()[0]
    return {"commands": cmds, "patterns": pats}


def get_detailed_stats(conn: sqlite3.Connection) -> dict:
    cmds = conn.execute("SELECT COUNT(*) FROM commands").fetchone()[0]
    pats = conn.execute("SELECT COUNT(*) FROM patterns").fetchone()[0]
    cats = conn.execute("SELECT COUNT(DISTINCT category) FROM commands").fetchone()[0]
    cached = conn.execute("SELECT COUNT(*) FROM query_cache").fetchone()[0]
    embeds = conn.execute("SELECT COUNT(*) FROM pattern_embeddings").fetchone()[0]

    by_category = conn.execute("""
        SELECT c.category,
               COUNT(DISTINCT c.id) AS commands,
               COUNT(p.id) AS patterns
        FROM commands c
        LEFT JOIN patterns p ON p.command_id = c.id
        GROUP BY c.category
        ORDER BY c.category
    """).fetchall()

    return {
        "commands": cmds,
        "patterns": pats,
        "categories": cats,
        "cached_queries": cached,
        "embeddings": embeds,
        "embedding_dim": EMBEDDING_DIM,
        "by_category": [
            {"category": r[0], "commands": r[1], "patterns": r[2]}
            for r in by_category
        ],
    }


def clear_all(conn: sqlite3.Connection) -> None:
    conn.execute("DELETE FROM pattern_embeddings")
    conn.execute("DELETE FROM patterns")
    conn.execute("DELETE FROM commands")
    conn.execute("DELETE FROM query_cache")
    conn.commit()
