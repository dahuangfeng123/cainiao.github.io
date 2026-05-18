# server.py
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import tempfile
import librosa
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware

from scorer.asr      import transcribe
from scorer.phoneme  import word_to_phones, fluency_score, compare_phones
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
    - target: 目标文本，可以是单词或句子
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

        # 目标文本的标准音素（CMU 字典）
        target_phones = word_to_phones(target)

        if words:
            # 获取识别到的第一个单词及其置信度
            first_word   = words[0]
            heard_word   = first_word["word"]
            probability  = first_word["probability"]
            word_correct = heard_word.lower() == target.lower()
            
            # 获取识别单词的音素
            heard_phones = word_to_phones(heard_word)
            
            # 使用音素对齐进行声学打分
            acoustic = score_word(target_phones, heard_phones, probability)
        else:
            word_correct = False
            acoustic     = {
                "heard_phones":   [],
                "results":        [{"phone": p, "correct": False, "similarity": 0.0} for p in target_phones],
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


@app.post("/score_sentence")
async def score_sentence(
    audio:  UploadFile = File(...),
    target: str        = Form(...),
):
    """
    句子级别的发音打分。
    - audio:  WAV 格式录音文件
    - target: 目标句子
    """
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False, dir="temp") as f:
        f.write(await audio.read())
        audio_path = f.name

    try:
        # 音频时长
        y, sr    = librosa.load(audio_path, sr=None)
        duration = round(len(y) / sr, 3)

        # faster-whisper 识别
        asr_result = transcribe(audio_path)
        heard_text = asr_result["text"]
        words      = asr_result["words"]

        # 流利度
        fluency = fluency_score(words, duration)

        # 单词级匹配
        target_words = [w.strip().lower() for w in target.split() if w.strip()]
        heard_words = [w["word"].lower() for w in words]
        
        # 计算单词准确率
        word_matches = 0
        for target_word in target_words:
            if target_word in heard_words:
                word_matches += 1
        
        word_accuracy = round(word_matches / len(target_words) * 100, 1) if target_words else 0.0

        # 音素级分析（取前几个词）
        phone_results = []
        total_correct = 0
        total_phones = 0
        
        for i, w in enumerate(words[:5]):  # 分析前5个词
            heard_word = w["word"]
            heard_phones = word_to_phones(heard_word)
            if heard_phones:
                phone_results.append({
                    "word": heard_word,
                    "phones": heard_phones,
                    "probability": w["probability"]
                })

        return JSONResponse({
            "target":         target,
            "heard":          heard_text,
            "word_accuracy":  word_accuracy,
            "phone_results":  phone_results,
            **fluency,
            "duration":       duration,
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
