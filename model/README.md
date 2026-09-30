# IGRIS-CODER Model

400M parameter transformer for code generation, data analysis, and multilingual Q&A.

## Architecture

| Spec | Value |
|------|-------|
| Parameters | ~400M dense |
| Architecture | Llama-3 style |
| Layers | 20 |
| Hidden Dim | 1024 |
| FFN Dim | 2816 (SwiGLU) |
| Attention Heads | 16 query / 4 KV (GQA 4:1) |
| Context Length | 4096 native (YaRN to 32K) |
| Vocab Size | 32,000 |
| Position Encoding | RoPE (theta=10000) |
| Normalization | RMSNorm (pre-norm) |
| Activation | SwiGLU |
| VRAM Training | <=6GB |
| VRAM Inference | <=2GB Q4 |

## Quick Start

```python
from model import create_model

model = create_model()
print(model.summary())
```

## Directory Structure

```
model/
├── config.py       # Model configuration
├── model.py        # Model architecture (skeleton)
├── tokenizer/      # Custom 32k BPE tokenizer
├── checkpoints/    # Sharded checkpoints
├── finetuned/      # SFT + DPO checkpoints
└── exports/        # GGUF Q4/Q8, ONNX
```

## Status

- [x] Configuration defined
- [x] Architecture skeleton
- [ ] PyTorch implementation
- [ ] Tokenizer training
- [ ] Pretraining pipeline
- [ ] SFT pipeline
- [ ] DPO pipeline
- [ ] Export to GGUF
