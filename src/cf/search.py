from dataclasses import dataclass

from cf.db import cache_query, get_cached_query, get_connection, init_db, search_similar

# Common stopwords to strip for cache key normalization
_STOPWORDS = frozenset({
    "a", "an", "the", "in", "on", "at", "to", "for", "of", "with", "by",
    "from", "is", "are", "was", "were", "be", "been", "do", "does", "did",
    "and", "or", "but", "not", "no", "it", "its", "this", "that", "my",
    "i", "me", "how", "what", "which", "who", "can", "will", "should",
    "all", "each", "every", "some", "any", "into", "using", "via",
})


def _normalize_query(query: str) -> str:
    """Normalize query for cache key: lowercase, strip stopwords, sort tokens."""
    tokens = query.lower().split()
    meaningful = [t for t in tokens if t not in _STOPWORDS]
    # Fallback: if everything was a stopword, keep original tokens
    if not meaningful:
        meaningful = tokens
    return " ".join(sorted(meaningful))


@dataclass
class SearchResult:
    command_template: str
    pattern_text: str
    explanation: str | None
    command_name: str
    command_description: str
    synopsis: str
    distance: float
    destructive: bool = False


def search(query: str, top_k: int = 10, db_path=None) -> list[SearchResult]:
    from cf.config import DB_PATH
    db_path = db_path or DB_PATH

    conn = get_connection(db_path)
    init_db(conn)

    # Normalize query for cache lookup: "list process by port" -> "list port process"
    cache_key = _normalize_query(query)

    # Check query cache before loading the model
    cached = get_cached_query(conn, cache_key)
    if cached is not None:
        embedding_bytes = cached
    else:
        # Cache miss: load model, encode the ORIGINAL query (not normalized)
        from cf.embeddings import encode_text, to_bytes
        embedding = encode_text(query)
        embedding_bytes = to_bytes(embedding)
        cache_query(conn, cache_key, embedding_bytes)

    raw = search_similar(conn, embedding_bytes, top_k=top_k * 2)
    conn.close()

    # Deduplicate: keep best (lowest distance) match per command_template.
    # OR the destructive flag across dupes so any destructive marker wins.
    seen = {}
    for r in raw:
        key = r["command_template"]
        prior = seen.get(key)
        if prior is None or r["distance"] < prior["distance"]:
            seen[key] = r
        if prior is not None and r.get("destructive"):
            seen[key]["destructive"] = True

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
            destructive=r.get("destructive", False),
        )
        for r in results
    ]
