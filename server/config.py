# config.py
import os

_BASE = os.path.dirname(os.path.abspath(__file__))

# Kokoro
KOKORO_MODEL  = os.path.join(_BASE, "kokoro-v1.0.onnx")
KOKORO_VOICES = os.path.join(_BASE, "voices-v1.0.bin")
KOKORO_VOICE  = "af_heart"
KOKORO_SPEED  = 0.9

# faster-whisper
WHISPER_MODEL  = "base"
WHISPER_DEVICE = "cpu"
COMPUTE_TYPE   = "float32"


# SpeechBrain 音素识别模型
SPEECHBRAIN_MODEL = os.path.join(_BASE, "speechbrain-asr")