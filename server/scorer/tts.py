# scorer/tts.py
import os
import tempfile
import soundfile as sf
from kokoro_onnx import Kokoro
from config import KOKORO_MODEL, KOKORO_VOICES, KOKORO_VOICE, KOKORO_SPEED

_kokoro = None

def _get_kokoro():
    import os
    print("当前工作目录:", os.getcwd())
    print("模型文件存在:", os.path.exists(KOKORO_MODEL))
    print("voices文件存在:", os.path.exists(KOKORO_VOICES))
    global _kokoro
    if _kokoro is None:
        _kokoro = Kokoro(KOKORO_MODEL, KOKORO_VOICES)
    return _kokoro

def generate_reference(text: str, out_dir: str = "temp") -> str:
    """
    用 Kokoro 生成标准发音 WAV，返回文件路径。
    """
    os.makedirs(out_dir, exist_ok=True)
    k = _get_kokoro()
    samples, sr = k.create(text, voice=KOKORO_VOICE, speed=KOKORO_SPEED, lang="en-us")
    f = tempfile.NamedTemporaryFile(suffix=".wav", delete=False, dir=out_dir)
    sf.write(f.name, samples, sr)
    return f.name