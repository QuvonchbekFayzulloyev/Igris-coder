"""
igris.core.embeddings
------------------------
Local-first embedding client via Ollama's /api/embed endpoint (the
current batch-capable endpoint -- not the older singular-prompt
/api/embeddings). Default model is nomic-embed-text: ~274MB download,
~137M parameters, loads into VRAM in about a second, runs even CPU-only
-- comfortably under any 8GB VRAM budget. 768-dimension output is the
safe default for this model. Verified against Ollama's model card and
current benchmarks as of mid-2026 (see the seeded project knowledge base
-- this fact is itself an entry in it).

Operational note baked into the default keep_alive: Ollama unloads an
idle model after ~5 minutes, which re-pays a ~1.3s cold-start reload on
the next call -- "10m" mirrors the chat client's own default so a
session's embedding calls don't keep re-paying that cost.
"""
from __future__ import annotations

import httpx


class EmbeddingClient:
    def __init__(self, config):
        self.host = config.get("embeddings.host") or config.get("ollama.host", "http://localhost:11434")
        self.model = config.get("embeddings.model", "nomic-embed-text")
        self.keep_alive = config.get("embeddings.keep_alive", "10m")
        self.timeout = config.get("embeddings.timeout_seconds", 60)

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Batch-embeds a list of strings in one call. Returns one vector per input, same order."""
        if not texts:
            return []
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                f"{self.host}/api/embed",
                json={"model": self.model, "input": texts, "keep_alive": self.keep_alive},
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("embeddings", []) or []

    async def embed_one(self, text: str) -> list[float]:
        vectors = await self.embed([text])
        return vectors[0] if vectors else []
