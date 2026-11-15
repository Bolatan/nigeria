import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from rag import ask

app = FastAPI()


class Question(BaseModel):
    question: str = Field(min_length=3, max_length=500)


@app.post("/api/ask")
def ask_endpoint(body: Question):
    try:
        return ask(body.question)
    except Exception as e:  # keep details in Vercel logs, not in the browser
        print("ask failed:", repr(e))
        raise HTTPException(status_code=500, detail="Could not answer right now. Please try again.")


# ---- Polling units and directions ----
import polling_units as pu
from directions import route


@app.get("/api/pu/areas")
def pu_areas():
    return pu.areas()


@app.get("/api/pu/unmapped")
def pu_unmapped():
    return pu.unmapped()


@app.get("/api/pu/search")
def pu_search(q: str = "", state: str = "", lga: str = "", ward: str = ""):
    return pu.search(q, state, lga, ward)


@app.get("/api/pu/nearby")
def pu_nearby(lat: float, lon: float, km: float = 5):
    return pu.nearby(lat, lon, min(km, 25))


@app.get("/api/route")
def api_route(from_lat: float, from_lon: float, to_lat: float, to_lon: float, mode: str = "driving"):
    if mode not in ("driving", "walking"):
        raise HTTPException(status_code=400, detail="mode must be driving or walking")
    try:
        return route(from_lat, from_lon, to_lat, to_lon, mode)
    except Exception as e:
        print("route failed:", repr(e))
        raise HTTPException(status_code=502, detail="Could not get directions right now. Please try again.")


# ---- One-time admin: build the search index from the browser (needs ADMIN_TOKEN) ----
import hmac

from openai import RateLimitError

from fastapi import Header

import rag


def require_admin(token):
    expected = os.getenv("ADMIN_TOKEN", "").strip()
    token = token.strip()
    if not expected:
        raise HTTPException(status_code=403, detail="ADMIN_TOKEN is not set on this deployment. Add it in Vercel, then redeploy.")
    if not token:
        raise HTTPException(status_code=403, detail="Enter your ADMIN_TOKEN in the box first.")
    if not hmac.compare_digest(token.encode(), expected.encode()):
        raise HTTPException(status_code=403, detail="That token does not match ADMIN_TOKEN on this deployment. It must match exactly.")


@app.post("/api/admin/check")
def admin_check(x_admin_token: str = Header("")):
    """Confirms CHAT_MODEL, EMBED_MODEL and both keys by making one tiny real call to each."""
    require_admin(x_admin_token)
    out = {"chat_model": rag.CHAT_MODEL, "embed_model": rag.EMBED_MODEL}
    try:
        out["available_chat_models"] = sorted(m.id for m in rag.llm().models.list())
    except Exception as e:
        out["available_chat_models"] = f"Could not list models ({type(e).__name__})"
    try:
        rag.llm().chat.completions.create(model=rag.CHAT_MODEL, max_tokens=5, messages=[{"role": "user", "content": "Say OK"}])
        out["chat"] = "OK"
    except Exception as e:
        out["chat"] = f"FAILED: {type(e).__name__}: {str(e)[:300]}"
    try:
        out["embeddings"] = f"OK ({len(rag.embed(['test'])[0])} dimensions)"
    except Exception as e:
        out["embeddings"] = f"FAILED: {type(e).__name__}: {str(e)[:300]}"
    return out


@app.post("/api/admin/embed")
def admin_embed(start: int = 0, size: int = 16, x_admin_token: str = Header("")):
    require_admin(x_admin_token)
    total, a, n = len(rag.chunks()[0]), max(start, 0), min(max(size, 1), 100)
    try:
        vectors = rag.embed_chunks(a, n)
    except RateLimitError:
        raise HTTPException(status_code=429, detail="Rate limited by the embedding service.")
    except Exception as e:
        print("embed failed:", repr(e))
        raise HTTPException(status_code=502, detail=f"Embedding failed ({type(e).__name__}). See the Vercel logs.")
    return {"done": min(a + n, total), "total": total, "vectors": vectors,
            "embed_model": rag.EMBED_MODEL, "hash": rag.fingerprint()}
