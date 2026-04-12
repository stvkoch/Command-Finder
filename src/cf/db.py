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
            explanation TEXT
        );

        CREATE VIRTUAL TABLE IF NOT EXISTS pattern_embeddings USING vec0(
            pattern_id INTEGER PRIMARY KEY,
            embedding FLOAT[{EMBEDDING_DIM}]
        );
    """)
    conn.commit()


def insert_command(conn: sqlite3.Connection, name: str, category: str,
                   synopsis: str, description: str) -> int:
    cur = conn.execute(
        "INSERT INTO commands (name, category, synopsis, description) VALUES (?, ?, ?, ?)",
        (name, category, synopsis, description),
    )
    return cur.lastrowid


def insert_pattern(conn: sqlite3.Connection, command_id: int, pattern_type: str,
                   text: str, command_template: str, explanation: str | None = None) -> int:
    cur = conn.execute(
        "INSERT INTO patterns (command_id, pattern_type, text, command_template, explanation) "
        "VALUES (?, ?, ?, ?, ?)",
        (command_id, pattern_type, text, command_template, explanation),
    )
    return cur.lastrowid


def insert_embedding(conn: sqlite3.Connection, pattern_id: int, embedding_bytes: bytes) -> None:
    conn.execute(
        "INSERT INTO pattern_embeddings (pattern_id, embedding) VALUES (?, ?)",
        (pattern_id, embedding_bytes),
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
            pe.distance
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
        }
        for r in rows
    ]


def get_stats(conn: sqlite3.Connection) -> dict:
    cmds = conn.execute("SELECT COUNT(*) FROM commands").fetchone()[0]
    pats = conn.execute("SELECT COUNT(*) FROM patterns").fetchone()[0]
    return {"commands": cmds, "patterns": pats}


def clear_all(conn: sqlite3.Connection) -> None:
    conn.execute("DELETE FROM pattern_embeddings")
    conn.execute("DELETE FROM patterns")
    conn.execute("DELETE FROM commands")
    conn.commit()
