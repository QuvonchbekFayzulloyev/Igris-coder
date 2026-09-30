"""IGRIS-CODER Model Configuration — 400M Parameter Transformer.

Target: ~400M dense parameters, <=6GB VRAM training, <=2GB Q4 inference.
Architecture: Modern Llama-3 style (GQA, SwiGLU, RoPE, Flash Attention 2).
"""

from dataclasses import dataclass


@dataclass
class IgrisConfig:
    """Model architecture configuration."""

    # Vocabulary
    vocab_size: int = 32000
    bos_token_id: int = 1
    eos_token_id: int = 2
    pad_token_id: int = 0

    # Architecture
    n_layers: int = 20
    d_model: int = 1024
    n_heads: int = 16
    n_kv_heads: int = 4  # GQA 4:1
    d_ff: int = 2816  # SwiGLU 2.75x
    rope_theta: float = 10000.0
    rms_norm_eps: float = 1e-6
    max_position_embeddings: int = 4096

    # Training
    tie_word_embeddings: bool = True
    use_flash_attention: bool = True
    gradient_checkpointing: bool = True
    dropout: float = 0.0  # pretraining; 0.1 for SFT

    # Special tokens
    special_tokens: tuple = (
        "<|system|>", "<|user|>", "<|assistant|>",
        "<|think|>", "<|/think|>",
        "<|calc|>", "<|python|>", "<|clarify|>",
        "<|critique|>", "<|marker|>", "<|fix|>",
    )

    @property
    def head_dim(self) -> int:
        return self.d_model // self.n_heads

    @property
    def kv_head_dim(self) -> int:
        return self.d_model // self.n_heads

    def vocab_size_with_special(self) -> int:
        return self.vocab_size + len(self.special_tokens)

    def memory_estimate_gb(self) -> dict:
        """Estimate VRAM usage during training (bf16 + AdamW)."""
        params = self._count_params()
        return {
            "model_params_bf16_gb": params * 2 / 1e9,
            "gradients_bf16_gb": params * 2 / 1e9,
            "optimizer_fp32_gb": params * 8 / 1e9,
            "total_estimate_gb": params * 12 / 1e9 + 3.0,  # +activations
        }

    def _count_params(self) -> int:
        """Rough parameter count."""
        embed = self.vocab_size * self.d_model
        attn = self.n_layers * (self.d_model * self.d_model * 3 +  # Q, K, V
                                 self.d_model * self.d_model)  # O
        ffn = self.n_layers * (self.d_model * self.d_ff * 3)  # SwiGLU
        norm = self.n_layers * self.d_model * 2  # RMSNorm
        return embed + attn + ffn + norm


# Default config
DEFAULT_CONFIG = IgrisConfig()
