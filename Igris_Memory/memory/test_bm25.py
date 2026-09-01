"""BM25 Retrieval Pipeline Smoke Test"""
import sys
sys.path.insert(0, ".")

print("=== BM25 Smoke Test ===\n")

# Test 1: Import BM25Index
from memory.retrieval import BM25Index
print("[1] BM25Index imported OK")

# Test 2: Create index and add documents
idx = BM25Index()
idx.add_document("JWT token 3 qismdan iborat header payload signature", {"source": "doc1"})
idx.add_document("Rate limiting 3 turi bor IP based User based Global", {"source": "doc2"})
idx.add_document("Authentication login jwt token handler", {"source": "doc3"})
idx.add_document("Database SQL query optimization performance", {"source": "doc4"})
idx.add_document("React component hooks useState useEffect", {"source": "doc5"})
print(f"[2] Added 5 documents OK")

# Test 3: Build index
idx.build()
stats = idx.get_stats()
print(f"[3] Index built: docs={stats['total_documents']}, terms={stats['unique_terms']}, avg_len={stats['avg_doc_length']:.1f}")

# Test 4: Search jwt/auth
results = idx.search("jwt token authentication", top_k=3)
print(f"[4] Search 'jwt token authentication': {len(results)} hits")
for r in results:
    src = r["metadata"]["source"]
    sc = r["score"]
    print(f"    score={sc:.3f} source={src}")

# Test 5: Search database/performance
results2 = idx.search("database performance", top_k=2)
print(f"[5] Search 'database performance': {len(results2)} hits")
for r in results2:
    src = r["metadata"]["source"]
    sc = r["score"]
    print(f"    score={sc:.3f} source={src}")

# Test 6: Query Rewriter
from memory.retrieval import QueryRewriter
rewriter = QueryRewriter()
rewrites = rewriter.rewrite("auth module test")
print(f"[6] QueryRewriter: {rewrites}")

keywords = rewriter.extract_keywords("How do I fix the authentication error?")
print(f"    Keywords: {keywords}")

# Test 7: LRU Cache
from memory.retrieval import SessionCache
cache = SessionCache(max_size=5, ttl_seconds=300)
cache.set("jwt", results)
cached = cache.get("jwt")
hit_count = len(cached) if cached else 0
print(f"[7] SessionCache: stored and retrieved {hit_count} items")

miss = cache.get("nonexistent")
print(f"    Miss test: {miss}")

# Test 8: Hybrid Search (BM25 only, no vector)
from memory.retrieval import HybridSearch
hybrid = HybridSearch()
hybrid.add_document("JWT token validation endpoint", {"source": "api/jwt"})
hybrid.add_document("User login authentication flow", {"source": "auth/login"})
hybrid.add_document("Error handling middleware", {"source": "middleware/error"})
hybrid.build()
hybrid_results = hybrid.search("jwt authentication", top_k=2, use_vector=False)
print(f"[8] HybridSearch (BM25 only): {len(hybrid_results)} results")
for r in hybrid_results:
    src = r["source"]
    sc = r["score"]
    print(f"    score={sc:.4f} source={src}")

# Test 9: Full RetrievalPipeline
from memory.retrieval import RetrievalPipeline
pipeline = RetrievalPipeline()
pipeline.hybrid.add_document("Python decorator pattern for retry logic", {"source": "patterns/retry.py"})
pipeline.hybrid.add_document("React useEffect cleanup function", {"source": "components/effect.md"})
pipeline.hybrid.add_document("JWT token expiry and refresh mechanism", {"source": "auth/jwt.json"})
pipeline.hybrid.add_document("Database index optimization tips", {"source": "db/index.md"})
pipeline.hybrid.build()
pipeline._loaded = True

search_results = pipeline.search("jwt token refresh", top_k=2)
print(f"[9] RetrievalPipeline: {len(search_results)} results")
for r in search_results:
    src = r.get("source", "unknown")
    sc = r.get("score", 0)
    print(f"    score={sc:.4f} source={src}")

print(f"\n    Cache stats: {pipeline.cache.get_stats()}")

print("\n=== ALL BM25 TESTS PASSED ===")
