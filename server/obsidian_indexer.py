"""
Indexes the Obsidian vault into Qdrant.

Run once (or after vault changes):
    python -m server.obsidian_indexer

Collection: obsidian_vault
Model:      BAAI/bge-small-en-v1.5  (384 dims, multilingual capable, ~24 MB)
"""
from __future__ import annotations

import os
import re
import uuid
from pathlib import Path
from typing import Iterator

import yaml
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

load_dotenv()

VAULT_PATH    = Path(os.getenv("OBSIDIAN_VAULT_PATH", r"C:\Users\v27me\OneDrive\Desktop\Ideaverse"))
QDRANT_URL    = os.getenv("QDRANT_URL", "http://localhost:6333")
COLLECTION    = os.getenv("QDRANT_COLLECTION", "obsidian_vault")
EMBED_MODEL   = "BAAI/bge-small-en-v1.5"
VECTOR_SIZE   = 384
CHUNK_MAX     = 900   # chars — keeps each chunk inside LLM context budget
CHUNK_OVERLAP = 100


# ── Parsing ───────────────────────────────────────────────────────────────────

def _parse_frontmatter(text: str) -> tuple[dict, str]:
    if text.startswith("---"):
        end = text.find("---", 3)
        if end != -1:
            try:
                meta = yaml.safe_load(text[3:end]) or {}
            except Exception:
                meta = {}
            return meta, text[end + 3:].strip()
    return {}, text


def _split_sections(content: str) -> list[tuple[str, str]]:
    """Returns list of (heading, body) pairs. Unnamed intro gets heading ''."""
    parts = re.split(r"\n(#{1,3} .+)", content)
    sections: list[tuple[str, str]] = []
    intro = parts[0].strip()
    if intro:
        sections.append(("", intro))
    for i in range(1, len(parts) - 1, 2):
        heading = parts[i].strip().lstrip("#").strip()
        body    = parts[i + 1].strip() if i + 1 < len(parts) else ""
        if body:
            sections.append((heading, body))
    return sections


def _chunk_text(text: str) -> Iterator[str]:
    """Splits long text into overlapping chunks of ≤ CHUNK_MAX chars."""
    if len(text) <= CHUNK_MAX:
        yield text
        return
    start = 0
    while start < len(text):
        end = start + CHUNK_MAX
        yield text[start:end]
        start = end - CHUNK_OVERLAP


def _iter_chunks_for_file(file_path: Path) -> Iterator[dict]:
    """Yields payload dicts for every chunk in a single .md file."""
    rel   = file_path.relative_to(VAULT_PATH).as_posix()
    title = file_path.stem
    try:
        raw = file_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return
    meta, content = _parse_frontmatter(raw)
    tags = meta.get("tags", [])
    if isinstance(tags, str):
        tags = [tags]
    up = meta.get("up", "")
    for heading, body in _split_sections(content):
        for chunk in _chunk_text(body):
            chunk = chunk.strip()
            if len(chunk) < 30:
                continue
            section_label = f"{title} › {heading}" if heading else title
            yield {
                "id":      str(uuid.uuid4()),
                "text":    f"{section_label}\n\n{chunk}",
                "title":   title,
                "section": heading,
                "content": chunk,
                "path":    rel,
                "tags":    tags,
                "up":      str(up),
            }


def _iter_chunks(vault: Path) -> Iterator[dict]:
    """Yields payload dicts for every chunk across all .md files."""
    for md in vault.rglob("*.md"):
        yield from _iter_chunks_for_file(md)


def index_single_file(file_path: str | Path) -> int:
    """Index a single .md file into Qdrant. Returns number of chunks upserted."""
    path   = Path(file_path)
    client = QdrantClient(url=QDRANT_URL)
    delete_file_chunks(path)
    chunks = list(_iter_chunks_for_file(path))
    if not chunks:
        return 0
    _upsert_batch(client, chunks)
    return len(chunks)


def delete_file_chunks(file_path: str | Path) -> None:
    """Delete all Qdrant points whose payload.path equals the given vault-relative path."""
    from qdrant_client.models import FilterSelector, Filter, FieldCondition, MatchValue
    path = Path(file_path)
    rel  = path.relative_to(VAULT_PATH).as_posix()
    client = QdrantClient(url=QDRANT_URL)
    try:
        client.delete(
            collection_name=COLLECTION,
            points_selector=FilterSelector(
                filter=Filter(must=[FieldCondition(key="path", match=MatchValue(value=rel))])
            ),
        )
    except Exception:
        pass  # collection may not exist yet


def get_agent_files(agent_id: str) -> list[dict]:
    """Scan vault for .md files that have `agent: {agent_id}` in their frontmatter."""
    results: list[dict] = []
    for md in VAULT_PATH.rglob("*.md"):
        try:
            raw = md.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        meta, content = _parse_frontmatter(raw)
        if meta.get("agent") != agent_id:
            continue
        tags = meta.get("tags", [])
        if isinstance(tags, str):
            tags = [tags]
        results.append({
            "path":    md.relative_to(VAULT_PATH).as_posix(),
            "title":   md.stem,
            "preview": " ".join(content[:200].split()),
            "tags":    tags,
            "created": str(meta.get("created", "")),
        })
    return results


# ── Qdrant helpers ────────────────────────────────────────────────────────────

def _ensure_collection(client: QdrantClient) -> None:
    existing = {c.name for c in client.get_collections().collections}
    if COLLECTION not in existing:
        client.create_collection(
            collection_name=COLLECTION,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
        )
        print(f"[indexer] coleção '{COLLECTION}' criada")
    else:
        print(f"[indexer] coleção '{COLLECTION}' já existe — reindexando")
        client.delete_collection(COLLECTION)
        client.create_collection(
            collection_name=COLLECTION,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
        )


def _embed_batch(texts: list[str]) -> list[list[float]]:
    from fastembed import TextEmbedding
    model = TextEmbedding(model_name=EMBED_MODEL)
    return [v.tolist() for v in model.embed(texts)]


def _upsert_batch(client: QdrantClient, payloads: list[dict]) -> None:
    texts   = [p["text"] for p in payloads]
    vectors = _embed_batch(texts)
    points  = [
        PointStruct(
            id=p["id"],
            vector=v,
            payload={k: val for k, val in p.items() if k not in ("id", "text")},
            # payload includes: title, section, content, path, tags, up
        )
        for p, v in zip(payloads, vectors)
    ]
    client.upsert(collection_name=COLLECTION, points=points)


# ── Main ──────────────────────────────────────────────────────────────────────

def run(vault_path: Path | None = None, batch_size: int = 64) -> int:
    path   = vault_path or VAULT_PATH
    client = QdrantClient(url=QDRANT_URL)

    print(f"[indexer] vault: {path}")
    print(f"[indexer] qdrant: {QDRANT_URL}  coleção: {COLLECTION}")

    _ensure_collection(client)

    buffer: list[dict] = []
    total = 0

    for chunk in _iter_chunks(path):
        buffer.append(chunk)
        if len(buffer) >= batch_size:
            _upsert_batch(client, buffer)
            total += len(buffer)
            print(f"[indexer] {total} chunks indexados...")
            buffer.clear()

    if buffer:
        _upsert_batch(client, buffer)
        total += len(buffer)

    print(f"[indexer] OK — {total} chunks indexados em '{COLLECTION}'")
    return total


if __name__ == "__main__":
    run()
