# Data Manager Skill

Validates, chunks, and streams input/output data for security, accuracy, size, and quality control.

## Trigger
When the user asks about data quality, security validation, output chunking, or progressive streaming.

## Pipeline Stage
`data_stream` — runs after preview, before performance optimization.

## Tools
`read`, `write`, `bash`, `terminal`

## Workflow

### 1. Input Validation
- Check for sensitive data (API keys, tokens, passwords)
- Verify size constraints (<1MB)
- Validate format correctness
- Log validation report

### 2. Output Chunking
- Split large responses into coherent chunks (2KB max per chunk)
- Each chunk has a summary and connectors to neighbors
- Validate each chunk independently
- Quality score per chunk

### 3. Progressive Streaming
- Send validated chunks immediately via `chunk` WebSocket event
- User sees partial results instead of waiting for full completion
- Chunks assemble like puzzle pieces into complete response

## Quality Rules
- Each chunk must be self-contained (understandable alone)
- Chunks must fit precisely (connector_prev + connector_next)
- Sensitive data is blocked before any chunk is sent
- Empty or too-small chunks (<300 chars) are merged
