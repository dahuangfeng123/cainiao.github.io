# server.py
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import tempfile
import librosa
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware

from scorer.asr      import transcribe
from scorer.phoneme  import word_to_phones, fluency_score
from scorer.acoustic import score_word
from scorer.tts      import generate_reference

app = FastAPI(title="Pronunciation Scorer")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs("temp", exist_ok=True)


@app.post("/score")
async def score(
    audio:  UploadFile = File(...),
    target: str        = Form(...),
):
    """
    上传录音，返回音素级打分结果。
    - audio:  WAV 格式录音文件
    - target: 目标单词，如 apple
    """
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False, dir="temp") as f:
        f.write(await audio.read())
        audio_path = f.name

    try:
        # 音频时长
        y, sr    = librosa.load(audio_path, sr=None)
        duration = round(len(y) / sr, 3)

        # faster-whisper 识别 + 词级时间戳
        asr_result = transcribe(audio_path)
        heard_text = asr_result["text"]
        words      = asr_result["words"]

        # 目标词的标准音素（CMU 字典）
        target_phones = word_to_phones(target)

        if words:
            first_word   = words[0]
            probability  = first_word["probability"]
            word_correct = first_word["word"].lower() == target.lower()
            acoustic     = score_word(target_phones, probability)
        else:
            word_correct = False
            acoustic     = {
                "heard_phones":   [],
                "results":        [{"phone": p, "correct": False} for p in target_phones],
                "correct_count":  0,
                "total_count":    len(target_phones),
                "phone_accuracy": 0.0,
            }

        # 流利度
        fluency = fluency_score(words, duration)

        return JSONResponse({
            "target":        target,
            "heard":         heard_text,
            "word_correct":  word_correct,
            "target_phones": target_phones,
            **acoustic,
            **fluency,
            "duration":      duration,
        })

    finally:
        os.unlink(audio_path)


@app.get("/reference")
def reference(word: str):
    """获取 Kokoro 生成的标准发音音频。"""
    path = generate_reference(word)
    return FileResponse(
        path,
        media_type="audio/wav",
        headers={"Content-Disposition": f"inline; filename={word}.wav"},
    )


@app.get("/health")
def health():
    return {"status": "ok"}