# IGRIS Brick Knowledge System

Atomic semantic primitives (bricks) + knowledge rules for fast code resolution.

## How It Works

1. **Bricks** = Atomic meaning units (words, functions, types)
   - Each brick knows its form in every language (uz, en, code)
   - ~50 bricks currently, target ~4000

2. **Knowledge** = Connection rules
   - Grammar rules: SOV -> SVO
   - Code patterns: verb+noun -> function(argument)
   - Type constraints: square_matrix -> np.linalg.inv

3. **Resolver** = Single graph traversal (<10ms)
   - Input: "matritsani teskari top"
   - Bricks: [matrix, inverse, find]
   - Rule: VERB+NOUN -> function(argument)
   - Output: `np.linalg.inv(matrix)`

4. **Chains** = Domain pathways (math, code, data, uz, sys)
   - Heals missing chains from available ones
   - Weighted combination for best coverage

## Running

```bash
cd igris_brick_knowledge
pip install -r requirements.txt
python igris_agent.py
```

## Example

```
Query> matritsani teskari top
Status: ✓
Confidence: 0.902
Chains: ['chain_math']
Output:
np.linalg.inv(data)
```

## Stats

```
Query> stats
=== Statistics ===
Bricks: 50
Chains: 5
  chain_math: math (16 bricks, 0 hits)
  chain_code: code (12 bricks, 0 hits)
  chain_data: data (9 bricks, 0 hits)
  chain_uz: uz (7 bricks, 0 hits)
  chain_sys: system (6 bricks, 0 hits)
```
