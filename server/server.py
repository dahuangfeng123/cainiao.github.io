# server.py
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import tempfile
import asyncio
import time
import librosa
from contextlib import asynccontextmanager
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware

from scorer.asr      import transcribe, _executor as asr_executor
from scorer.phoneme  import word_to_phones, fluency_score, compare_phones
from scorer.acoustic import score_word
from scorer.tts      import generate_reference

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("[Server] Starting up...")
    yield
    print("[Server] Shutting down...")
    asr_executor.shutdown(wait=True)
    print("[Server] Cleanup complete")

app = FastAPI(title="Pronunciation Scorer", lifespan=lifespan)

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
    t0 = time.time()
    t_audio_load = t0
    t_asr = t0
    t_phones = t0
    t_acoustic = t0
    t_fluency = t0

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False, dir="temp") as f:
        f.write(await audio.read())
        audio_path = f.name

    try:
        # 音频时长
        y, sr    = librosa.load(audio_path, sr=None)
        t_audio_load = time.time()
        audio_load_ms = round((t_audio_load - t0) * 1000, 1)

        # faster-whisper 识别 + 词级时间戳（在线程池中运行）
        asr_result = await transcribe(audio_path)
        t_asr = time.time()
        asr_ms = round((t_asr - t_audio_load) * 1000, 1)
        heard_text = asr_result["text"]
        words      = asr_result["words"]

        # 目标文本的标准音素（CMU 字典）
        target_phones = word_to_phones(target)
        t_phones = time.time()
        phones_ms = round((t_phones - t_asr) * 1000, 1)

        print(f"[Score] target='{target}' target_phones={target_phones} heard='{heard_text}' words={words}")

        if words:
            # 获取识别到的单词及其置信度
            first_word   = words[0]
            heard_word   = first_word["word"]
            probability  = first_word["probability"]

            # 获取识别单词的音素
            heard_phones = word_to_phones(heard_word)

            print(f"[Score] heard_word='{heard_word}' heard_phones={heard_phones} probability={probability}")

            # 使用音素对齐进行声学打分
            acoustic = score_word(target_phones, heard_phones, probability)
            t_acoustic = time.time()
            acoustic_ms = round((t_acoustic - t_phones) * 1000, 1)

            # 检查是否是完整句子匹配
            word_correct = heard_text.lower().strip() == target.lower().strip()
        else:
            word_correct = False
            acoustic     = {
                "heard_phones":   [],
                "results":        [{"phone": p, "correct": False, "similarity": 0.0} for p in target_phones],
                "correct_count":  0,
                "total_count":    len(target_phones) if target_phones else 1,
                "phone_accuracy": 0.0,
            }
            t_acoustic = time.time()
            acoustic_ms = round((t_acoustic - t_phones) * 1000, 1)

        # 流利度
        fluency = fluency_score(words, duration)
        t_fluency = time.time()
        fluency_ms = round((t_fluency - t_acoustic) * 1000, 1)

        total_ms = round((t_fluency - t0) * 1000, 1)

        print(f"[Score] timing: audio_load={audio_load_ms}ms asr={asr_ms}ms phones={phones_ms}ms acoustic={acoustic_ms}ms fluency={fluency_ms}ms total={total_ms}ms")
        print(f"[Score] result: phone_accuracy={acoustic.get('phone_accuracy', 0)} fluency={fluency.get('fluency', 0)}")

        return JSONResponse({
            "target":        target,
            "heard":         heard_text,
            "word_correct":  word_correct,
            "target_phones": target_phones,
            "timing_ms": {
                "audio_load": audio_load_ms,
                "asr": asr_ms,
                "phones": phones_ms,
                "acoustic": acoustic_ms,
                "fluency": fluency_ms,
                "total": total_ms,
            },
            **acoustic,
            **fluency,
            "duration":      round(len(y) / sr, 3),
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
    t0 = time.time()

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False, dir="temp") as f:
        f.write(await audio.read())
        audio_path = f.name

    try:
        # 音频时长
        y, sr    = librosa.load(audio_path, sr=None)
        duration = round(len(y) / sr, 3)

        # faster-whisper 识别
        asr_result = await transcribe(audio_path)
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

        for i, w in enumerate(words[:5]):  # 分析前5个词
            heard_word = w["word"]
            heard_phones = word_to_phones(heard_word)
            if heard_phones:
                phone_results.append({
                    "word": heard_word,
                    "phones": heard_phones,
                    "probability": w["probability"]
                })

        total_ms = round((time.time() - t0) * 1000, 1)
        print(f"[ScoreSentence] target='{target}' heard='{heard_text}' word_accuracy={word_accuracy} timing={total_ms}ms")

        return JSONResponse({
            "target":         target,
            "heard":          heard_text,
            "word_accuracy":  word_accuracy,
            "phone_results":  phone_results,
            **fluency,
            "duration":       duration,
            "timing_ms":      total_ms,
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
