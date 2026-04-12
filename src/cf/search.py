from dataclasses import dataclass

from cf.db import get_connection, init_db, search_similar
from cf.embeddings import encode_text, to_bytes


@dataclass
class SearchResult:
    command_template: str
    pattern_text: str
    explanation: str | None
    command_name: str
    command_description: str
    synopsis: str
    distance: float


def search(query: str, top_k: int = 10, db_path=None) -> list[SearchResult]:
    from cf.config import DB_PATH
    db_path = db_path or DB_PATH

    embedding = encode_text(query)
    embedding_bytes = to_bytes(embedding)

    conn = get_connection(db_path)
    init_db(conn)
    raw = search_similar(conn, embedding_bytes, top_k=top_k * 2)
    conn.close()

    # Deduplicate: keep best (lowest distance) match per command_template
    seen = {}
    for r in raw:
        key = r["command_template"]
        if key not in seen or r["distance"] < seen[key]["distance"]:
            seen[key] = r

    # Sort by distance, take top_k
    results = sorted(seen.values(), key=lambda r: r["distance"])[:top_k]

    return [
        SearchResult(
            command_template=r["command_template"],
            pattern_text=r["pattern_text"],
            explanation=r["explanation"],
            command_name=r["command_name"],
            command_description=r["command_description"],
            synopsis=r["synopsis"],
            distance=r["distance"],
        )
        for r in results
    ]
