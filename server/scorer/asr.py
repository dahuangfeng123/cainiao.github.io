# scorer/asr.py
import asyncio
from concurrent.futures import ThreadPoolExecutor
from faster_whisper import WhisperModel
from config import WHISPER_MODEL, WHISPER_DEVICE, COMPUTE_TYPE

_model = None
_executor = ThreadPoolExecutor(max_workers=2)

def _get_model():
    global _model
    if _model is None:
        print(f"[ASR] Loading Whisper model: {WHISPER_MODEL} on {WHISPER_DEVICE}...")
        _model = WhisperModel(
            WHISPER_MODEL,
            device=WHISPER_DEVICE,
            compute_type=COMPUTE_TYPE,
        )
        print("[ASR] Whisper model loaded successfully")
    return _model

def _transcribe_sync(audio_path: str) -> dict:
    """同步推理函数（在线程池中运行）"""
    model = _get_model()
    segments, _ = model.transcribe(
        audio_path,
        language="en",
        word_timestamps=True,
    )

    words = []
    full_text_parts = []

    for seg in segments:
        for w in (seg.words or []):
            word = w.word.strip().lower()
            if word:
                words.append({
                    "word":        word,
                    "start":       round(w.start, 3),
                    "end":         round(w.end, 3),
                    "probability": round(w.probability, 3),
                })
                full_text_parts.append(word)

    return {
        "text":  " ".join(full_text_parts),
        "words": words,
    }

async def transcribe(audio_path: str) -> dict:
    """
    识别音频，返回识别文字和词级时间戳。
    使用线程池避免阻塞异步事件循环。
    返回格式：
    {
        "text": "apple",
        "words": [
            {"word": "apple", "start": 0.0, "end": 0.42, "probability": 0.95}
        ]
    }
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, _transcribe_sync, audio_path)
