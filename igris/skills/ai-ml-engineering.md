---
name: ai-ml-engineering
description: Governs AI/ML engineering tasks: model selection, training pipelines, evaluation, deployment. Covers neural networks, transformers, computer vision, NLP, reinforcement learning, edge deployment.
pipeline_stage: Execution
triggers: [ai, ml, model, train, neural, network, transformer, inference, deploy, dataset, feature, accuracy, loss, optimizer, tensorflow, pytorch, onnx, tflite, quantization, pruning]
defers_to: [hardware-robotics]
used_by: [reprompt-loop, skill-loader]
---

## Scope
Applies when the user requests AI/ML engineering work: building models,
training pipelines, evaluation frameworks, or deployment configurations.

## Procedure
1. **Understand the problem**: classification, regression, generation, detection, etc.
2. **Select model architecture** based on constraints:
   - GPU memory (4-6GB): use quantized models, MobileNet, EfficientNet-Lite, DistilBERT
   - Edge deployment: TFLite, ONNX Runtime, TensorRT
   - Cloud: full PyTorch/TensorFlow models
3. **Data pipeline**: always specify data loading, preprocessing, augmentation
4. **Training loop**: include validation, early stopping, checkpointing
5. **Evaluation**: metrics, confusion matrix, ROC curves, inference benchmarks
6. **Deployment**: export format, serving framework, monitoring

## Constraints
- Never assume GPU availability -- always ask or default to CPU-compatible
- Always include a requirements.txt or environment specification
- Always specify the Python version and key library versions
- Include memory estimates for model inference
- For edge deployment, always include quantization steps

## Templates
- `templates/ml_project/` - ML project structure
- `templates/notebook/` - Jupyter notebook structure
- `templates/training_config/` - YAML training configuration

## Anti-patterns
- Using large models without checking GPU memory constraints
- Skipping validation set evaluation
- Not saving training curves and metrics
- Ignoring data leakage between train/test splits
- Deploying without quantization for edge devices
