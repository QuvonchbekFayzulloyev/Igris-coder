# Chunking Patterns

## Natural Split Points (priority order)
1. `\n\n` — paragraph boundaries (best coherence)
2. `\n` — line boundaries  
3. `. ` — sentence boundaries (fallback)

## Chunk Shape
Each chunk is a puzzle piece:
```
[chunk i] → summary + connector_next → [chunk i+1]
```

## Validation
- **Security scan**: regex patterns for keys/tokens before any chunk
- **Coherence check**: each chunk >300 chars, has connector links
- **Quality score**: 0.0–1.0 based on content density, security, size

## Streaming Contract
1. chunk events arrive in order (index 0..total-1)
2. UI appends `content` progressively 
3. `total` field tells UI how many to expect
4. Final `final` event still sent with complete response
