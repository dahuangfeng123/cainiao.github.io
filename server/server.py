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


def is_sentence(text: str) -> bool:
    """判断是否为句子（包含空格且长度超过一定阈值）"""
    words = text.strip().split()
    return len(words) > 1


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

    target_clean = target.strip()
    is_sent = is_sentence(target_clean)

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False, dir="temp") as f:
        f.write(await audio.read())
        audio_path = f.name

    try:
        # 音频时长
        y, sr    = librosa.load(audio_path, sr=None)
        duration = round(len(y) / sr, 3)
        t_audio_load = time.time()
        audio_load_ms = round((t_audio_load - t0) * 1000, 1)

        # faster-whisper 识别 + 词级时间戳
        asr_result = await transcribe(audio_path)
        t_asr = time.time()
        asr_ms = round((t_asr - t_audio_load) * 1000, 1)
        heard_text = asr_result["text"]
        words      = asr_result["words"]

        print(f"[Score] target='{target_clean}' is_sentence={is_sent} heard='{heard_text}' words={len(words)}")

        if is_sent:
            # 句子模式：逐词匹配
            acoustic = score_sentence_phones(target_clean, words)
        else:
            # 单词模式：使用第一个识别到的词
            if words:
                first_word   = words[0]
                heard_word   = first_word["word"]
                probability  = first_word["probability"]
                target_phones = word_to_phones(target_clean)
                heard_phones = word_to_phones(heard_word)
                print(f"[Score] heard_word='{heard_word}' heard_phones={heard_phones} probability={probability}")
                acoustic = score_word(target_phones, heard_phones, probability)
            else:
                acoustic = {
                    "heard_phones":   [],
                    "results":        [{"phone": p, "correct": False, "similarity": 0.0} for p in word_to_phones(target_clean)],
                    "correct_count":  0,
                    "total_count":    len(word_to_phones(target_clean)) if word_to_phones(target_clean) else 1,
                    "phone_accuracy": 0.0,
                }

        t_acoustic = time.time()
        acoustic_ms = round((t_acoustic - t_asr) * 1000, 1)

        # 流利度
        fluency = fluency_score(words, duration)
        t_fluency = time.time()
        fluency_ms = round((t_fluency - t_acoustic) * 1000, 1)

        total_ms = round((t_fluency - t0) * 1000, 1)

        # 单词正确性
        word_correct = heard_text.lower().strip() == target_clean.lower().strip()

        print(f"[Score] timing: audio_load={audio_load_ms}ms asr={asr_ms}ms acoustic={acoustic_ms}ms fluency={fluency_ms}ms total={total_ms}ms")
        print(f"[Score] result: phone_accuracy={acoustic.get('phone_accuracy', 0)} fluency={fluency.get('fluency', 0)}")

        return JSONResponse({
            "target":        target_clean,
            "heard":         heard_text,
            "word_correct":  word_correct,
            "is_sentence":   is_sent,
            "target_phones": acoustic.get("target_phones", []),
            "timing_ms": {
                "audio_load": audio_load_ms,
                "asr": asr_ms,
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


def score_sentence_phones(target: str, asr_words: list) -> dict:
    """
    句子级音素打分：对比目标句子和识别结果中每个词的音素。
    """
    target_words = target.lower().split()
    heard_words_text = [w["word"].lower() for w in asr_words]

    all_results = []
    total_correct = 0
    total_phones = 0
    heard_phones_all = []

    for target_word in target_words:
        target_phones = word_to_phones(target_word)

        if not target_phones:
            continue

        # 找匹配的识别词
        heard_word = None
        heard_phones = []
        for hw in heard_words_text:
            if hw == target_word:
                heard_word = hw
                heard_phones = word_to_phones(hw)
                break

        if not heard_word:
            # 尝试找相似词
            for hw in heard_words_text:
                if target_word in hw or hw in target_word:
                    heard_word = hw
                    heard_phones = word_to_phones(hw)
                    break

        if heard_phones:
            result = score_word(target_phones, heard_phones, 1.0)
            all_results.extend(result["results"])
            total_correct += result["correct_count"]
            heard_phones_all.extend(result["heard_phones"])
        else:
            # 没找到匹配，全部标记为错误
            for p in target_phones:
                all_results.append({"phone": p, "correct": False, "similarity": 0.0})

        total_phones += len(target_phones)

    # 去重 target_phones
    unique_target_phones = []
    seen = set()
    for r in all_results:
        if r["phone"] not in seen:
            unique_target_phones.append(r["phone"])
            seen.add(r["phone"])

    phone_accuracy = round(total_correct / total_phones * 100, 1) if total_phones > 0 else 0.0

    return {
        "heard_phones":   heard_phones_all,
        "results":        all_results,
        "correct_count":  total_correct,
        "total_count":    total_phones,
        "phone_accuracy": phone_accuracy,
        "target_phones":  unique_target_phones,
    }


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

        # 音素级分析
        phone_results = []
        for i, w in enumerate(words[:5]):
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
