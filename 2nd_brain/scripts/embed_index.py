#!/usr/bin/env python3
"""IGRIS 2nd Brain Semantic Search — Local Embedding Index.

Requires: sentence-transformers, faiss-cpu, numpy
Optional: for semantic search over Wiki notes
"""

import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    from sentence_transformers import SentenceTransformer
    import faiss
    import numpy as np
    HAS_DEPS = True
except ImportError:
    HAS_DEPS = False


class WikiSemanticIndex:
    def __init__(self, model_name: str = "all-MiniLM-L6-v2", root: str = "."):
        if not HAS_DEPS:
            raise ImportError(
                "Install: pip install sentence-transformers faiss-cpu numpy"
            )
        self.root = Path(root)
        self.wiki_dir = self.root / "Wiki"
        self.model = SentenceTransformer(model_name)
        self.index = None
        self.doc_map: Dict[int, str] = {}
        self.embeddings_path = self.root / "Wiki" / ".embeddings.npy"
        self.docmap_path = self.root / "Wiki" / ".docmap.json"

    def index_wiki(self):
        """Index all compiled Wiki notes."""
        notes = list(self.wiki_dir.rglob("*.md"))
        notes = [n for n in notes if n.name not in ("index.md", ".embeddings.npy", ".docmap.json")]

        if not notes:
            print("No Wiki notes found.")
            return

        print(f"Indexing {len(notes)} notes...")
        texts = []
        self.doc_map = {}
        for i, note in enumerate(notes):
            content = note.read_text(encoding="utf-8")
            # Strip frontmatter for embedding
            if content.startswith("---"):
                end = content.find("---", 3)
                if end > 0:
                    content = content[end + 3:]
            texts.append(content[:2000])  # Limit length
            self.doc_map[i] = str(note.relative_to(self.root))

        embeddings = self.model.encode(texts, show_progress_bar=True)
        self.index = faiss.IndexFlatIP(embeddings.shape[1])
        self.index.add(np.array(embeddings).astype("float32"))

        # Save index
        np.save(str(self.embeddings_path), np.array(embeddings))
        with open(self.docmap_path, "w", encoding="utf-8") as f:
            json.dump(self.doc_map, f, ensure_ascii=False)

        print(f"Indexed {len(notes)} notes.")

    def load_index(self) -> bool:
        """Load saved index."""
        if not self.embeddings_path.exists() or not self.docmap_path.exists():
            return False

        embeddings = np.load(str(self.embeddings_path))
        self.index = faiss.IndexFlatIP(embeddings.shape[1])
        self.index.add(embeddings.astype("float32"))

        with open(self.docmap_path, "r", encoding="utf-8") as f:
            self.doc_map = {int(k): v for k, v in json.load(f).items()}

        return True

    def search(self, query: str, k: int = 5) -> List[Tuple[str, float]]:
        """Search Wiki notes by semantic similarity."""
        if self.index is None:
            if not self.load_index():
                print("No index found. Run 'index_wiki' first.")
                return []

        embedding = self.model.encode([query])
        scores, indices = self.index.search(np.array(embedding).astype("float32"), k)

        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx in self.doc_map:
                results.append((self.doc_map[idx], float(score)))
        return results


def main():
    if not HAS_DEPS:
        print("Install dependencies: pip install sentence-transformers faiss-cpu numpy")
        sys.exit(1)

    import argparse
    parser = argparse.ArgumentParser(description="Wiki Semantic Search Index")
    parser.add_argument("command", choices=["index", "search"])
    parser.add_argument("--root", default=".")
    parser.add_argument("--query", help="Search query")
    parser.add_argument("--k", type=int, default=5, help="Top-k results")
    args = parser.parse_args()

    index = WikiSemanticIndex(root=args.root)

    if args.command == "index":
        index.index_wiki()
    elif args.command == "search":
        if not args.query:
            print("--query required")
            sys.exit(1)
        results = index.search(args.query, args.k)
        for path, score in results:
            print(f"  [{score:.3f}] {path}")


if __name__ == "__main__":
    main()
