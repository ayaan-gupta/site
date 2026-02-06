"""
RAG over IRW dataset cards: embed user query and dataset descriptions,
retrieve top-k datasets by semantic similarity so the agent can recommend
the best data for the user's project.
"""
import json
import os
from pathlib import Path

# Optional: OpenAI embeddings for semantic search; fallback to keyword search
try:
    from openai import OpenAI
    _OPENAI_AVAILABLE = True
except ImportError:
    _OPENAI_AVAILABLE = False

DATA_DIR = Path(__file__).resolve().parent / "data"
METADATA_PATH = DATA_DIR / "irw_metadata.json"
CARDS_PATH = DATA_DIR / "irw_cards.json"
SAMPLE_METADATA = DATA_DIR / "irw_metadata.sample.json"
SAMPLE_CARDS = DATA_DIR / "irw_cards.sample.json"


def _load_json(path: Path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_metadata():
    """Load full dataset metadata (for tools)."""
    if METADATA_PATH.exists():
        return _load_json(METADATA_PATH)
    if SAMPLE_METADATA.exists():
        return _load_json(SAMPLE_METADATA)
    return []


def load_cards():
    """Load dataset cards (table + card text) for RAG."""
    if CARDS_PATH.exists():
        return _load_json(CARDS_PATH)
    if SAMPLE_CARDS.exists():
        return _load_json(SAMPLE_CARDS)
    return []


def _keyword_search(query: str, cards: list, top_k: int = 10) -> list:
    """Fallback: simple keyword overlap scoring (no embeddings)."""
    q_lower = query.lower().split()
    scored = []
    for item in cards:
        card_lower = item["card"].lower()
        score = sum(1 for w in q_lower if len(w) > 2 and w in card_lower)
        scored.append((score, item))
    scored.sort(key=lambda x: -x[0])
    return [item for _, item in scored[:top_k] if scored[0][0] > 0] or [item for _, item in scored[:top_k]]


def _embed_openai(texts: list[str], client: "OpenAI") -> list[list[float]]:
    """Embed texts with OpenAI text-embedding-3-small."""
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=texts,
    )
    by_id = {e.index: e.embedding for e in response.data}
    return [by_id[i] for i in range(len(texts))]


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    import math
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def retrieve(
    query: str,
    top_k: int = 10,
    use_embeddings: bool = True,
    openai_api_key: str | None = None,
) -> list[dict]:
    """
    Retrieve top-k datasets most relevant to the user's project description.
    Uses OpenAI embeddings if available and use_embeddings=True; else keyword search.
    Returns list of { "table": str, "card": str, "score"?: float }.
    """
    cards = load_cards()
    if not cards:
        return []

    if use_embeddings and _OPENAI_AVAILABLE and (openai_api_key or os.environ.get("OPENAI_API_KEY")):
        client = OpenAI(api_key=openai_api_key or os.environ.get("OPENAI_API_KEY"))
        card_texts = [c["card"] for c in cards]
        try:
            card_embeddings = _embed_openai(card_texts, client)
            query_embeddings = _embed_openai([query], client)
            q_emb = query_embeddings[0]
            scored = [
                (_cosine_similarity(q_emb, c_emb), cards[i])
                for i, c_emb in enumerate(card_embeddings)
            ]
            scored.sort(key=lambda x: -x[0])
            return [
                {**item, "score": round(score, 4)}
                for score, item in scored[:top_k]
            ]
        except Exception:
            pass  # fallback to keyword

    # Keyword fallback
    results = _keyword_search(query, cards, top_k)
    return [{"table": r["table"], "card": r["card"]} for r in results]
