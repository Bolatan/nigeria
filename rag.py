"""Shared RAG core. The search index is a file shipped with the app (data/index.json): no database."""
import array
import base64
import hashlib
import json
import math
import operator
import os

from openai import OpenAI

import ingest

# Chat uses API_BASE / API_KEY / CHAT_MODEL. Embeddings use EMBED_API_BASE / EMBED_API_KEY / EMBED_MODEL
# (they default to the chat provider). Set them separately if the chat provider has no embeddings (e.g. Meta Llama API).
API_BASE = os.getenv("API_BASE", "https://api.together.xyz/v1")
CHAT_MODEL = os.getenv("CHAT_MODEL", "meta-llama/Llama-3.3-70B-Instruct-Turbo")
EMBED_MODEL = os.getenv("EMBED_MODEL", "BAAI/bge-base-en-v1.5")
EMBED_BASE = os.getenv("EMBED_API_BASE", API_BASE)

ROOT = os.path.dirname(os.path.abspath(__file__))
SOURCE = os.path.join(ROOT, "data", "constitution.md")
INDEX = os.path.join(ROOT, "data", "index.json")

SYSTEM = (
    "You explain the Constitution of the Federal Republic of Nigeria (1999, as amended) "
    "in simple English. Use ONLY the context provided. Use short sentences and everyday words, "
    "as if explaining to a secondary-school student. Name the sections you rely on, like (Section 33). "
    "If the context does not answer the question, say you could not find it in the text. "
    "End with: 'This is a plain-English guide, not legal advice.'"
)

_llm = _emb = _chunks = _index = None


def llm():
    global _llm
    if _llm is None:
        _llm = OpenAI(base_url=API_BASE, api_key=os.environ["API_KEY"])
    return _llm


def embedder():
    global _emb
    if _emb is None:
        _emb = OpenAI(base_url=EMBED_BASE, api_key=os.getenv("EMBED_API_KEY") or os.environ["API_KEY"])
    return _emb


def embed(texts):
    return [d.embedding for d in embedder().embeddings.create(model=EMBED_MODEL, input=texts).data]


def chunks():
    """(ids, docs, metas), rebuilt from data/constitution.md the same way every time."""
    global _chunks
    if _chunks is None:
        _chunks = ingest.build_chunks(ingest.read(SOURCE))
    return _chunks


def fingerprint():
    ids, docs, _ = chunks()
    return hashlib.sha256("\n".join(i + d for i, d in zip(ids, docs)).encode()).hexdigest()[:16]


def _unit(v):
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return array.array("f", (x / n for x in v))


def embed_chunks(start, size):
    """Embed chunks[start:start+size]; returns base64 float32 unit vectors (used by /admin.html and ingest.py)."""
    docs = chunks()[1][start:start + size]
    return [base64.b64encode(_unit(v).tobytes()).decode() for v in embed(docs)] if docs else []


def index():
    global _index
    if _index is None:
        with open(INDEX, encoding="utf-8") as f:
            d = json.load(f)
        if d.get("embed_model") != EMBED_MODEL:
            raise RuntimeError(f"Index was built with {d.get('embed_model')} but EMBED_MODEL is {EMBED_MODEL}. Rebuild it at /admin.html.")
        if d.get("hash") != fingerprint() or len(d["vectors"]) != len(chunks()[0]):
            raise RuntimeError("data/index.json does not match data/constitution.md. Rebuild it at /admin.html.")
        vecs = []
        for b in d["vectors"]:
            a = array.array("f")
            a.frombytes(base64.b64decode(b))
            vecs.append(a)
        _index = vecs
    return _index


def ask(question, k=5):
    try:
        vecs = index()
    except FileNotFoundError:
        return {"answer": "The search index has not been built yet. Open /admin.html once to build it.", "sources": []}
    q = _unit(embed([question])[0])
    if len(q) != len(vecs[0]):
        raise RuntimeError("Embedding size changed. Rebuild the index at /admin.html.")
    best = sorted(((sum(map(operator.mul, q, v)), i) for i, v in enumerate(vecs)), reverse=True)[:k]
    _, docs, metas = chunks()
    context = "\n\n".join(f"[{metas[i]['ref']}]\n{docs[i]}" for _, i in best)
    out = llm().chat.completions.create(
        model=CHAT_MODEL,
        temperature=0.2,
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}"},
        ],
    )
    sources = [{"ref": metas[i]["ref"], "chapter": metas[i].get("chapter", ""), "text": docs[i]} for _, i in best]
    return {"answer": out.choices[0].message.content, "sources": sources}
