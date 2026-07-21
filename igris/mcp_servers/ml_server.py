"""MCP surface for ML/AI engineering tasks.

Provides tools for:
- Model selection based on constraints (GPU memory, task, latency)
- Training pipeline generation (PyTorch, TensorFlow, JAX)
- Evaluation metrics computation
- Dataset preprocessing suggestions
- Hyperparameter tuning suggestions
- Model export (ONNX, TFLite, TensorRT)
- Edge deployment configuration
- ML pipeline diagram generation (data flow, model architecture)
"""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("ml_engineering")

# ---------------------------------------------------------------------------
# Model selection
# ---------------------------------------------------------------------------

_MODEL_CATALOG = {
    "image_classification": {
        "efficientnet_lite0": {"params": "3.5M", "gpu_mb": 200, "latency_ms": 15, "top1": 75.1, "edge": True},
        "efficientnet_lite4": {"params": "13M", "gpu_mb": 500, "latency_ms": 40, "top1": 80.4, "edge": True},
        "mobilenet_v3_small": {"params": "2.5M", "gpu_mb": 150, "latency_ms": 10, "top1": 67.4, "edge": True},
        "mobilenet_v3_large": {"params": "5.4M", "gpu_mb": 300, "latency_ms": 20, "top1": 75.2, "edge": True},
        "resnet18": {"params": "11M", "gpu_mb": 400, "latency_ms": 25, "top1": 69.8, "edge": False},
        "resnet50": {"params": "25M", "gpu_mb": 900, "latency_ms": 50, "top1": 76.2, "edge": False},
        "vit_base": {"params": "86M", "gpu_mb": 2800, "latency_ms": 120, "top1": 81.1, "edge": False},
    },
    "object_detection": {
        "yolov8n": {"params": "3.2M", "gpu_mb": 200, "latency_ms": 25, "map50": 37.3, "edge": True},
        "yolov8s": {"params": "11.2M", "gpu_mb": 500, "latency_ms": 45, "map50": 44.9, "edge": True},
        "yolov8m": {"params": "25.9M", "gpu_mb": 1000, "latency_ms": 80, "map50": 50.2, "edge": False},
        "ssd_mobilenet": {"params": "6.8M", "gpu_mb": 300, "latency_ms": 30, "map50": 32.0, "edge": True},
        "faster_rcnn": {"params": "41M", "gpu_mb": 1500, "latency_ms": 100, "map50": 42.1, "edge": False},
    },
    "nlp": {
        "distilbert": {"params": "66M", "gpu_mb": 500, "latency_ms": 35, "glue": 77.0, "edge": False},
        "bert_base": {"params": "110M", "gpu_mb": 800, "latency_ms": 65, "glue": 78.3, "edge": False},
        "bert_tiny": {"params": "4.4M", "gpu_mb": 100, "latency_ms": 8, "glue": 65.0, "edge": True},
        "mobilebert": {"params": "25M", "gpu_mb": 300, "latency_ms": 20, "glue": 75.0, "edge": True},
        "gpt2_small": {"params": "124M", "gpu_mb": 900, "latency_ms": 50, "edge": False},
        "phi2": {"params": "2.7B", "gpu_mb": 4000, "latency_ms": 200, "edge": False},
        "tinyllama": {"params": "1.1B", "gpu_mb": 2000, "latency_ms": 100, "edge": False},
        "qwen2_5_1_5b": {"params": "1.5B", "gpu_mb": 2500, "latency_ms": 120, "edge": False},
    },
    "audio": {
        "wav2vec2_base": {"params": "95M", "gpu_mb": 700, "latency_ms": 80, "edge": False},
        "whisper_tiny": {"params": "39M", "gpu_mb": 300, "latency_ms": 30, "edge": True},
        "whisper_base": {"params": "74M", "gpu_mb": 500, "latency_ms": 50, "edge": False},
    },
    "timeseries": {
        "informer": {"params": "11M", "gpu_mb": 400, "latency_ms": 35, "edge": False},
        "patchtst": {"params": "8M", "gpu_mb": 300, "latency_ms": 25, "edge": True},
    },
}


@mcp.tool()
async def recommend_model(
    task: str = "",
    gpu_memory_gb: int = 4,
    edge_deployment: bool = False,
    max_latency_ms: int = 50,
    priority: str = "accuracy",  # accuracy | speed | memory
) -> str:
    """Recommend ML models based on constraints.

    Args:
        task: image_classification, object_detection, nlp, audio, timeseries
        gpu_memory_gb: available GPU memory (4-6 typical)
        edge_deployment: whether model runs on edge device
        max_latency_ms: maximum inference latency
        priority: optimization priority

    Returns recommended models with explanations.
    """
    if task not in _MODEL_CATALOG:
        return f"ERROR: Unknown task '{task}'. Available: {list(_MODEL_CATALOG.keys())}"

    models = _MODEL_CATALOG[task]
    gpu_mb = gpu_memory_gb * 1024
    candidates = []

    for name, info in models.items():
        if info["gpu_mb"] > gpu_mb * 0.8:
            continue
        if edge_deployment and not info.get("edge", False):
            continue
        if info.get("latency_ms", 999) > max_latency_ms:
            continue

        score = 0
        if priority == "accuracy":
            score = info.get("top1", info.get("map50", info.get("glue", 0)))
        elif priority == "speed":
            score = 100 - info.get("latency_ms", 99)
        elif priority == "memory":
            score = gpu_mb / info["gpu_mb"] * 10

        candidates.append((score, name, info))

    candidates.sort(key=lambda x: x[0], reverse=True)

    if not candidates:
        return (
            f"No models found matching constraints for '{task}':\n"
            f"  GPU: {gpu_memory_gb}GB, Edge: {edge_deployment}, "
            f"Max latency: {max_latency_ms}ms\n"
            f"Try: larger GPU, no edge requirement, or higher latency"
        )

    lines = [
        f"## Recommended Models for {task}",
        f"GPU: {gpu_memory_gb}GB | Edge: {edge_deployment} | Latency: <{max_latency_ms}ms\n",
        "| Rank | Model | Params | GPU (MB) | Latency (ms) | Key Metric |",
        "|------|-------|--------|----------|--------------|------------|",
    ]

    for i, (score, name, info) in enumerate(candidates[:5], 1):
        metric = f"Top-1: {info.get('top1', '')}%" if 'top1' in info else \
                 f"mAP50: {info.get('map50', '')}" if 'map50' in info else \
                 f"GLUE: {info.get('glue', '')}" if 'glue' in info else ""
        lines.append(f"| {i} | {name} | {info['params']} | {info['gpu_mb']} | {info.get('latency_ms', '?')} | {metric} |")

    lines.append("")
    if candidates:
        best = candidates[0][1]
        lines.append(f"### Recommended: {best}")
        lines.append(
            f"Best fit for your {gpu_memory_gb}GB GPU with {'edge' if edge_deployment else 'server'} deployment."
        )

    return "\n".join(lines)


@mcp.tool()
async def generate_training_script(
    framework: str = "pytorch",
    model_name: str = "",
    task: str = "classification",
    num_classes: int = 10,
    batch_size: int = 32,
    epochs: int = 50,
    learning_rate: float = 0.001,
    mixed_precision: bool = True,
    distributed: bool = False,
    use_wandb: bool = False,
    dataset: str = "",
) -> str:
    """Generate a training script for the given framework and model.

    Returns a complete Python training script.
    """
    if framework == "pytorch":
        return _generate_pytorch_script(model_name, task, num_classes, batch_size,
                                         epochs, learning_rate, mixed_precision, dataset)
    elif framework == "tensorflow":
        return _generate_tensorflow_script(model_name, task, num_classes, batch_size,
                                            epochs, learning_rate, mixed_precision, dataset)
    else:
        return f"ERROR: Unsupported framework '{framework}'. Use: pytorch, tensorflow"


def _generate_pytorch_script(
    model: str, task: str, num_classes: int, batch_size: int,
    epochs: int, lr: float, amp: bool, dataset: str
) -> str:
    return f'''"""
{model} training script for {task}
Auto-generated by igris ML pipeline

Usage:
    python train.py
"""
import os
import time
import json
from pathlib import Path

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, Dataset
from torch.cuda.amp import autocast, GradScaler


class Config:
    model_name = "{model}"
    num_classes = {num_classes}
    batch_size = {batch_size}
    epochs = {epochs}
    lr = {lr}
    mixed_precision = {str(amp).lower()}
    device = "cuda" if torch.cuda.is_available() else "cpu"
    checkpoint_dir = Path("checkpoints")
    log_dir = Path("logs")
    num_workers = 4


config = Config()
config.checkpoint_dir.mkdir(exist_ok=True)
config.log_dir.mkdir(exist_ok=True)

print(f"Device: {{config.device}}")
print(f"Model: {model}")
print(f"Batch: {batch_size}, Epochs: {epochs}, LR: {lr}")


def build_model():
    """Build model for {task} with {num_classes} classes."""
    import timm
    model = timm.create_model("{model}", pretrained=True, num_classes=config.num_classes)
    return model.to(config.device)


def get_dataloaders():
    """Create train and validation dataloaders."""
    # TODO: Replace with actual dataset
    train_dataset = None  # YourDataset(split="train")
    val_dataset = None  # YourDataset(split="val")

    train_loader = DataLoader(
        train_dataset, batch_size=config.batch_size, shuffle=True,
        num_workers=config.num_workers, pin_memory=True,
    )
    val_loader = DataLoader(
        val_dataset, batch_size=config.batch_size, shuffle=False,
        num_workers=config.num_workers, pin_memory=True,
    )
    return train_loader, val_loader


def train_epoch(model, loader, criterion, optimizer, scaler):
    model.train()
    total_loss = 0
    correct = 0
    total = 0

    for batch_idx, (inputs, targets) in enumerate(loader):
        inputs, targets = inputs.to(config.device), targets.to(config.device)

        optimizer.zero_grad()

        if config.mixed_precision and scaler:
            with autocast():
                outputs = model(inputs)
                loss = criterion(outputs, targets)
            scaler.scale(loss).backward()
            scaler.step(optimizer)
            scaler.update()
        else:
            outputs = model(inputs)
            loss = criterion(outputs, targets)
            loss.backward()
            optimizer.step()

        total_loss += loss.item()
        _, predicted = outputs.max(1)
        total += targets.size(0)
        correct += predicted.eq(targets).sum().item()

        if batch_idx % 10 == 0:
            print(f"  Batch {{batch_idx}}: loss={{loss.item():.4f}}")

    return total_loss / len(loader), 100.0 * correct / total


@torch.no_grad()
def validate(model, loader, criterion):
    model.eval()
    total_loss = 0
    correct = 0
    total = 0

    for inputs, targets in loader:
        inputs, targets = inputs.to(config.device), targets.to(config.device)
        outputs = model(inputs)
        loss = criterion(outputs, targets)

        total_loss += loss.item()
        _, predicted = outputs.max(1)
        total += targets.size(0)
        correct += predicted.eq(targets).sum().item()

    return total_loss / len(loader), 100.0 * correct / total


def main():
    model = build_model()
    train_loader, val_loader = get_dataloaders()
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.AdamW(model.parameters(), lr=config.lr)
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=config.epochs)
    scaler = GradScaler() if config.mixed_precision else None

    best_acc = 0
    history = {{"train_loss": [], "train_acc": [], "val_loss": [], "val_acc": []}}

    for epoch in range(1, config.epochs + 1):
        print(f"\\nEpoch {{epoch}}/{{config.epochs}}")
        t0 = time.time()

        train_loss, train_acc = train_epoch(model, train_loader, criterion, optimizer, scaler)
        val_loss, val_acc = validate(model, val_loader, criterion)
        scheduler.step()

        history["train_loss"].append(train_loss)
        history["train_acc"].append(train_acc)
        history["val_loss"].append(val_loss)
        history["val_acc"].append(val_acc)

        elapsed = time.time() - t0
        print(f"  Train: loss={{train_loss:.4f}} acc={{train_acc:.2f}}%")
        print(f"  Val:   loss={{val_loss:.4f}} acc={{val_acc:.2f}}%")
        print(f"  Time: {{elapsed:.1f}}s, LR: {{scheduler.get_last_lr()[0]:.2e}}")

        if val_acc > best_acc:
            best_acc = val_acc
            checkpoint = {{
                "epoch": epoch,
                "model_state_dict": model.state_dict(),
                "optimizer_state_dict": optimizer.state_dict(),
                "val_acc": val_acc,
                "config": {{
                    "model": "{model}",
                    "num_classes": {num_classes},
                    "batch_size": {batch_size},
                }},
            }}
            torch.save(checkpoint, config.checkpoint_dir / "best_model.pth")
            print(f"  * New best model saved (acc={{val_acc:.2f}}%)")

    # Save training history
    with open(config.log_dir / "history.json", "w") as f:
        json.dump(history, f, indent=2)

    print(f"\\nTraining complete! Best validation accuracy: {{best_acc:.2f}}%")


if __name__ == "__main__":
    main()
'''


def _generate_tensorflow_script(
    model: str, task: str, num_classes: int, batch_size: int,
    epochs: int, lr: float, amp: bool, dataset: str
) -> str:
    return f'''"""
{model} training script for {task}
Auto-generated by igris ML pipeline

Usage:
    python train.py
"""
import os
import json
from pathlib import Path

import tensorflow as tf


class Config:
    model_name = "{model}"
    num_classes = {num_classes}
    input_shape = (224, 224, 3)
    batch_size = {batch_size}
    epochs = {epochs}
    lr = {lr}
    mixed_precision = {str(amp).lower()}
    checkpoint_dir = Path("checkpoints")
    log_dir = Path("logs")


config = Config()
config.checkpoint_dir.mkdir(exist_ok=True)
config.log_dir.mkdir(exist_ok=True)

if config.mixed_precision:
    tf.keras.mixed_precision.set_global_policy("mixed_float16")


def build_model():
    base = tf.keras.applications.{model}(
        weights="imagenet", include_top=False, input_shape=config.input_shape
    )
    base.trainable = False

    inputs = tf.keras.Input(shape=config.input_shape)
    x = base(inputs, training=False)
    x = tf.keras.layers.GlobalAveragePooling2D()(x)
    x = tf.keras.layers.Dropout(0.2)(x)
    outputs = tf.keras.layers.Dense(config.num_classes, activation="softmax")(x)

    model = tf.keras.Model(inputs, outputs)
    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=config.lr),
        loss="sparse_categorical_crossentropy",
        metrics=["accuracy"],
    )
    return model


def main():
    model = build_model()
    model.summary()

    callbacks = [
        tf.keras.callbacks.ModelCheckpoint(
            str(config.checkpoint_dir / "best_model.keras"),
            monitor="val_accuracy", save_best_only=True,
        ),
        tf.keras.callbacks.EarlyStopping(
            monitor="val_accuracy", patience=10, restore_best_weights=True,
        ),
        tf.keras.callbacks.ReduceLROnPlateau(
            monitor="val_loss", factor=0.5, patience=5, min_lr=1e-6,
        ),
    ]

    # TODO: Replace with actual dataset
    # history = model.fit(train_dataset, validation_data=val_dataset,
    #                     epochs=config.epochs, callbacks=callbacks)

    print(f"Training configured for {{config.epochs}} epochs")


if __name__ == "__main__":
    main()
'''


@mcp.tool()
async def suggest_export_format(
    model_name: str = "",
    target_device: str = "edge",  # edge | mobile | server | browser
    framework: str = "pytorch",
    quantize: bool = True,
) -> str:
    """Suggest model export format and provide conversion commands."""
    suggestions = {
        "edge": {
            "format": "ONNX",
            "file_ext": ".onnx",
            "runtime": "ONNX Runtime",
            "reason": "Widest hardware support, GPU acceleration via TensorRT",
        },
        "mobile": {
            "format": "TFLite",
            "file_ext": ".tflite",
            "runtime": "TensorFlow Lite",
            "reason": "Optimized for ARM, GPU/NPU delegation",
        },
        "browser": {
            "format": "WebAssembly / TFJS",
            "file_ext": ".wasm / .json",
            "runtime": "TensorFlow.js / ONNX.js",
            "reason": "Runs in browser JavaScript engines",
        },
        "server": {
            "format": "TorchScript / ONNX",
            "file_ext": ".pt / .onnx",
            "runtime": "PyTorch / ONNX Runtime + TensorRT",
            "reason": "Best server-side throughput",
        },
    }

    config = suggestions.get(target_device, suggestions["edge"])

    lines = [
        f"## Export: {model_name or 'model'} -> {config['format']}",
        f"Target: {target_device}",
        f"Runtime: {config['runtime']}",
        f"Reason: {config['reason']}",
        "",
        "### Conversion Commands",
    ]

    if framework == "pytorch":
        if config["format"] == "ONNX":
            lines.append(
                f"```python\n"
                f"import torch\n"
                f"model = torch.load('{model_name or 'model'}.pt')\n"
                f"model.eval()\n"
                f"dummy_input = torch.randn(1, 3, 224, 224)\n"
                f"torch.onnx.export(model, dummy_input, '{model_name or 'model'}.onnx',\n"
                f"    input_names=['input'], output_names=['output'],\n"
                f"    dynamic_axes={{{{'input': {{0: 'batch_size'}}, 'output': {{0: 'batch_size'}}}}}})\n"
                f"```"
            )
            if quantize:
                lines.append(
                    f"### Quantization (INT8)\n"
                    f"```python\n"
                    f"import onnxruntime as ort\n"
                    f"from onnxruntime.quantization import quantize_dynamic, QuantType\n"
                    f"quantize_dynamic('{model_name or 'model'}.onnx', "
                    f"'{model_name or 'model'}_int8.onnx', "
                    f"weight_type=QuantType.QInt8)\n"
                    f"```"
                )
        elif config["format"] == "TFLite":
            lines.append(
                f"```python\n"
                f"import torch\n"
                f"import tensorflow as tf\n"
                f"# PyTorch -> ONNX -> TFLite\n"
                f"# Step 1: Export to ONNX first\n"
                f"# Step 2: Convert to TFLite\n"
                f"converter = tf.lite.TFLiteConverter.from_saved_model('saved_model')\n"
                f"converter.optimizations = [tf.lite.Optimize.DEFAULT]\n"
                f"converter.target_spec.supported_types = [tf.float16]\n"
                f"tflite_model = converter.convert()\n"
                f"with open('{model_name or 'model'}.tflite', 'wb') as f:\n"
                f"    f.write(tflite_model)\n"
                f"```"
            )
    elif framework == "tensorflow":
        if config["format"] == "TFLite":
            lines.append(
                f"```python\n"
                f"import tensorflow as tf\n"
                f"converter = tf.lite.TFLiteConverter.from_keras_model(model)\n"
                f"{'converter.optimizations = [tf.lite.Optimize.DEFAULT]' if quantize else ''}\n"
                f"tflite_model = converter.convert()\n"
                f"with open('{model_name or 'model'}.tflite', 'wb') as f:\n"
                f"    f.write(tflite_model)\n"
                f"```"
            )

    return "\n".join(lines)


@mcp.tool()
async def estimate_inference_cost(
    model_params_m: float = 100,
    batch_size: int = 1,
    sequence_length: int = 512,
    precision: str = "fp16",  # fp32, fp16, int8
) -> str:
    """Estimate inference compute and memory requirements.

    Args:
        model_params_m: model parameters in millions
        batch_size: inference batch size
        sequence_length: input sequence length (for transformers)
        precision: fp32, fp16, or int8

    Returns memory, FLOPs, and latency estimates.
    """
    params = model_params_m * 1e6

    # Memory estimates
    bits = {"fp32": 32, "fp16": 16, "int8": 8}
    bits_per_param = bits.get(precision, 16)
    model_memory_bytes = params * bits_per_param / 8
    activation_memory = batch_size * sequence_length * params * 2 / 1e9  # rough

    # FLOPs estimate (approximate for transformers)
    flops_per_token = 6 * params
    total_flops = batch_size * sequence_length * flops_per_token

    # Latency estimate (rough)
    tflops = 5.0  # typical 4GB GPU
    latency_ms = total_flops / (tflops * 1e12) * 1000

    return (
        f"Inference Cost Estimate:\n"
        f"  Model: {model_params_m}M params\n"
        f"  Precision: {precision} ({bits_per_param}-bit)\n"
        f"  Batch: {batch_size}, Sequence: {sequence_length}\n\n"
        f"  Model memory: {model_memory_bytes/1e6:.1f}MB\n"
        f"  Peak memory: {(model_memory_bytes + activation_memory*1e9)/1e6:.0f}MB\n"
        f"  FLOPs per inference: {total_flops/1e9:.1f}G\n"
        f"  Estimated latency: {latency_ms:.0f}ms (at {tflops} TFLOPS)\n\n"
        f"  {'Can fit in 4-6GB GPU' if model_memory_bytes < 3e9 else 'WARNING: May not fit in 4-6GB GPU'}"
    )


if __name__ == "__main__":
    mcp.run()