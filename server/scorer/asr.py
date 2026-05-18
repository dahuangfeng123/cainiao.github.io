# scorer/asr.py
from faster_whisper import WhisperModel
from config import WHISPER_MODEL, WHISPER_DEVICE, COMPUTE_TYPE

_model = None

def _get_model():
    global _model
    if _model is None:
        _model = WhisperModel(
            WHISPER_MODEL,
            device=WHISPER_DEVICE,
            compute_type=COMPUTE_TYPE,
        )
    return _model

def transcribe(audio_path: str) -> dict:
    """
    识别音频，返回识别文字和词级时间戳。
    返回格式：
    {
        "text": "apple",
        "words": [
            {"word": "apple", "start": 0.0, "end": 0.42, "probability": 0.95}
        ]
    }
    """
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