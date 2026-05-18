# config.py
import os

_BASE = os.path.dirname(os.path.abspath(__file__))

# Kokoro
KOKORO_MODEL  = os.path.join(_BASE, "kokoro-v1.0.onnx")
KOKORO_VOICES = os.path.join(_BASE, "voices-v1.0.bin")
KOKORO_VOICE  = "af_heart"
KOKORO_SPEED  = 0.9

# faster-whisper - 升级到更大的模型以提高准确度
# 可选模型: tiny, base, small, medium, large, large-v2, large-v3
WHISPER_MODEL  = "medium"  # 从 base 升级到 medium
WHISPER_DEVICE = "auto"    # 自动检测 GPU/CPU
COMPUTE_TYPE   = "int8"    # 使用 INT8 量化加速


# SpeechBrain 音素识别模型
SPEECHBRAIN_MODEL = os.path.join(_BASE, "speechbrain-asr")
