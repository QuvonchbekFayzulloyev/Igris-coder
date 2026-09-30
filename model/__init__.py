"""IGRIS-CODER Model — 400M Parameter Transformer Architecture."""

from .config import IgrisConfig, DEFAULT_CONFIG
from .model import IgrisModel, create_model, ModelOutput

__all__ = ["IgrisConfig", "DEFAULT_CONFIG", "IgrisModel", "create_model", "ModelOutput"]
