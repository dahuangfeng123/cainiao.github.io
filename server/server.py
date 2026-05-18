# server.py — FastAPI unified server (TTS + Scoring + Pages)
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

import tempfile
import asyncio
import time
import io
import hashlib
import threading
import librosa
from contextlib import asynccontextmanager

from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import JSONResponse, FileResponse, Response
from fastapi.middleware.cors import CORSMiddleware

from scorer.asr import transcribe, _executor as asr_executor
from scorer.phoneme import word_to_phones, fluency_score, compare_phones
from scorer.acoustic import score_word

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUDIO_CACHE_DIR = os.path.join(BASE_DIR, "data", "audio")
TEMP_DIR = os.path.join(BASE_DIR, "temp")

os.makedirs(AUDIO_CACHE_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)


# ========== Audio Cache ==========
def audio_cache_id(text, voice, speed, model):
    key = f"{model}|{voice}|{speed:.2f}|{text}"
    return hashlib.md5(key.encode()).hexdigest()


def audio_cache_path(cache_id, model):
    ext = "mp3" if model == "edge" else "wav"
    return os.path.join(AUDIO_CACHE_DIR, f"{cache_id}.{ext}")


def get_cached_audio(cache_id, model):
    path = audio_cache_path(cache_id, model)
    if os.path.exists(path):
        return path
    return None


# ========== Kokoro TTS ==========
_kokoro = None
_kokoro_lock = threading.Lock()
_kokoro_available = False


def get_kokoro():
    global _kokoro, _kokoro_available
    if _kokoro is not None:
        return _kokoro
    try:
        from kokoro_onnx import Kokoro

        with _kokoro_lock:
            if _kokoro is None:
                model_path = os.path.join(BASE_DIR, "server", "kokoro-v1.0.onnx")
                voices_path = os.path.join(BASE_DIR, "server", "voices-v1.0.bin")
                if not os.path.exists(model_path) or not os.path.exists(voices_path):
                    print("Kokoro model files not found, skipping...")
                    return None
                print(f"Loading Kokoro model from {model_path}...")
                start = time.time()
                _kokoro = Kokoro(model_path, voices_path)
                _kokoro_available = True
                print(f"Kokoro model loaded in {time.time() - start:.2f}s")
        return _kokoro
    except ImportError:
        print("kokoro_onnx not installed, Kokoro TTS unavailable")
        return None


def kokoro_tts(text, voice, speed):
    kokoro = get_kokoro()
    if kokoro is None:
        return None
    import soundfile as sf

    samples, sample_rate = kokoro.create(text, voice=voice, speed=speed, lang="en-us")
    buf = io.BytesIO()
    sf.write(buf, samples, sample_rate, format="WAV", subtype="PCM_16")
    buf.seek(0)
    return buf.read(), "audio/wav"


# ========== Edge TTS ==========
_edge_tts_available = False


def check_edge_tts():
    global _edge_tts_available
    try:
        import edge_tts

        _edge_tts_available = True
    except ImportError:
        print("edge_tts not installed, Edge TTS unavailable")
        _edge_tts_available = False


async def edge_tts_synthesize(text, voice, rate):
    import edge_tts

    rate_str = (
        f"+{int((rate - 1.0) * 100)}%"
        if rate >= 1.0
        else f"{int((rate - 1.0) * 100)}%"
    )
    communicate = edge_tts.Communicate(text, voice, rate=rate_str)
    buf = io.BytesIO()
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            buf.write(chunk["data"])
    return buf.getvalue(), "audio/mpeg"


# ========== Voice Lists ==========
KOKORO_VOICES = [
    "af_heart",
    "af_alloy",
    "af_aoede",
    "af_bella",
    "af_jessica",
    "af_kore",
    "af_nicole",
    "af_nova",
    "af_river",
    "af_sarah",
    "af_sky",
    "am_adam",
    "am_echo",
    "am_eric",
    "am_fenrir",
    "am_liam",
    "am_michael",
    "am_onyx",
    "am_puck",
    "am_santa",
]

EDGE_VOICES = [
    "en-US-JennyNeural",
    "en-US-GuyNeural",
    "en-US-AriaNeural",
    "en-US-DavisNeural",
    "en-US-AmberNeural",
    "en-US-AndrewNeural",
    "en-US-EmmaNeural",
    "en-US-BrianNeural",
    "en-GB-SoniaNeural",
    "en-GB-RyanNeural",
    "en-GB-LibbyNeural",
    "en-GB-ThomasNeural",
    "en-AU-NatashaNeural",
    "en-AU-WilliamNeural",
]


# ========== FastAPI App ==========
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("[Server] Starting up...")
    get_kokoro()
    check_edge_tts()
    print(f"Kokoro TTS: {'✅' if _kokoro_available else '❌'}")
    print(f"Edge TTS:   {'✅' if _edge_tts_available else '❌'}")
    print("[Server] Ready!")
    yield
    print("[Server] Shutting down...")
    asr_executor.shutdown(wait=True)
    print("[Server] Cleanup complete")


app = FastAPI(title="MoringRead Server", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ========== TTS Routes ==========
@app.post("/tts")
async def tts(request_body: dict):
    text = request_body.get("text", "")
    model = request_body.get("model", "kokoro")
    voice = request_body.get("voice", "af_sarah")
    speed = float(request_body.get("speed", 1.0))

    start = time.time()

    cache_id = audio_cache_id(text, voice, speed, model)
    cached = get_cached_audio(cache_id, model)
    if cached:
        elapsed = time.time() - start
        mimetype = "audio/mpeg" if model == "edge" else "audio/wav"
        print(f"[Cache HIT] {cache_id} in {elapsed:.3f}s")
        with open(cached, "rb") as f:
            audio_data = f.read()
        return Response(
            audio_data,
            media_type=mimetype,
            headers={
                "Access-Control-Allow-Origin": "*",
                "X-Generation-Time": f"{elapsed:.3f}",
                "X-Cache": "HIT",
            },
        )

    if model == "edge":
        if not _edge_tts_available:
            return JSONResponse({"error": "Edge TTS not available"}, status_code=503)
        try:
            audio_data, mimetype = await edge_tts_synthesize(text, voice, speed)
            cache_path = audio_cache_path(cache_id, model)
            with open(cache_path, "wb") as f:
                f.write(audio_data)
            elapsed = time.time() - start
            print(f"[Edge TTS] generated in {elapsed:.2f}s, cached as {cache_id}")
            return Response(
                audio_data,
                media_type=mimetype,
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "X-Generation-Time": f"{elapsed:.2f}",
                    "X-Cache": "MISS",
                },
            )
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)
    else:
        if not _kokoro_available:
            return JSONResponse(
                {"error": "Kokoro TTS not available"}, status_code=503
            )
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, kokoro_tts, text, voice, speed)
            if result is None:
                return JSONResponse(
                    {"error": "Kokoro model not loaded"}, status_code=503
                )
            audio_data, mimetype = result
            cache_path = audio_cache_path(cache_id, model)
            with open(cache_path, "wb") as f:
                f.write(audio_data)
            elapsed = time.time() - start
            print(f"[Kokoro TTS] generated in {elapsed:.2f}s, cached as {cache_id}")
            return Response(
                audio_data,
                media_type=mimetype,
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "X-Generation-Time": f"{elapsed:.2f}",
                    "X-Cache": "MISS",
                },
            )
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/voices")
def voices(model: str = "kokoro"):
    if model == "edge":
        return {"model": "edge", "voices": EDGE_VOICES}
    return {"model": "kokoro", "voices": KOKORO_VOICES}


@app.get("/models")
def models():
    available = []
    if _kokoro_available:
        available.append(
            {
                "id": "kokoro",
                "name": "Kokoro (本地)",
                "desc": "82M参数，离线运行，低延迟",
            }
        )
    if _edge_tts_available:
        available.append(
            {
                "id": "edge",
                "name": "Edge TTS (云端)",
                "desc": "微软云端，音质优秀，需联网",
            }
        )
    return available


@app.get("/cache/stats")
def cache_stats():
    files = (
        os.listdir(AUDIO_CACHE_DIR) if os.path.exists(AUDIO_CACHE_DIR) else []
    )
    audio_files = [f for f in files if f.endswith((".wav", ".mp3"))]
    total_size = sum(
        os.path.getsize(os.path.join(AUDIO_CACHE_DIR, f)) for f in audio_files
    )
    return {
        "count": len(audio_files),
        "size_mb": round(total_size / 1024 / 1024, 2),
        "dir": AUDIO_CACHE_DIR,
    }


@app.post("/cache/clear")
def cache_clear():
    files = (
        os.listdir(AUDIO_CACHE_DIR) if os.path.exists(AUDIO_CACHE_DIR) else []
    )
    removed = 0
    for f in files:
        if f.endswith((".wav", ".mp3")):
            os.remove(os.path.join(AUDIO_CACHE_DIR, f))
            removed += 1
    return {"removed": removed}


# ========== Scoring Routes ==========
def is_sentence(text: str) -> bool:
    words = text.strip().split()
    return len(words) > 1


@app.post("/score")
async def score(
    audio: UploadFile = File(...),
    target: str = Form(...),
):
    t0 = time.time()

    target_clean = target.strip()
    is_sent = is_sentence(target_clean)

    with tempfile.NamedTemporaryFile(
        suffix=".wav", delete=False, dir=TEMP_DIR
    ) as f:
        f.write(await audio.read())
        audio_path = f.name

    try:
        y, sr = librosa.load(audio_path, sr=None)
        duration = round(len(y) / sr, 3)
        t_audio_load = time.time()
        audio_load_ms = round((t_audio_load - t0) * 1000, 1)

        asr_result = await transcribe(audio_path)
        t_asr = time.time()
        asr_ms = round((t_asr - t_audio_load) * 1000, 1)
        heard_text = asr_result["text"]
        words = asr_result["words"]

        print(
            f"[Score] target='{target_clean}' is_sentence={is_sent} heard='{heard_text}' words={len(words)}"
        )

        if is_sent:
            acoustic = score_sentence_phones(target_clean, words)
        else:
            if words:
                first_word = words[0]
                heard_word = first_word["word"]
                probability = first_word["probability"]
                target_phones = word_to_phones(target_clean)
                heard_phones = word_to_phones(heard_word)
                print(
                    f"[Score] heard_word='{heard_word}' heard_phones={heard_phones} probability={probability}"
                )
                acoustic = score_word(target_phones, heard_phones, probability)
            else:
                acoustic = {
                    "heard_phones": [],
                    "results": [
                        {"phone": p, "correct": False, "similarity": 0.0}
                        for p in word_to_phones(target_clean)
                    ],
                    "correct_count": 0,
                    "total_count": (
                        len(word_to_phones(target_clean))
                        if word_to_phones(target_clean)
                        else 1
                    ),
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

        print(
            f"[Score] timing: audio_load={audio_load_ms}ms asr={asr_ms}ms acoustic={acoustic_ms}ms fluency={fluency_ms}ms total={total_ms}ms"
        )
        print(
            f"[Score] result: phone_accuracy={acoustic.get('phone_accuracy', 0)} fluency={fluency.get('fluency', 0)}"
        )

        return JSONResponse(
            {
                "target": target_clean,
                "heard": heard_text,
                "word_correct": word_correct,
                "is_sentence": is_sent,
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
                "duration": round(len(y) / sr, 3),
            }
        )

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
                all_results.append(
                    {"phone": p, "correct": False, "similarity": 0.0}
                )

        total_phones += len(target_phones)

    # 去重 target_phones
    unique_target_phones = []
    seen = set()
    for r in all_results:
        if r["phone"] not in seen:
            unique_target_phones.append(r["phone"])
            seen.add(r["phone"])

    phone_accuracy = (
        round(total_correct / total_phones * 100, 1) if total_phones > 0 else 0.0
    )

    return {
        "heard_phones": heard_phones_all,
        "results": all_results,
        "correct_count": total_correct,
        "total_count": total_phones,
        "phone_accuracy": phone_accuracy,
        "target_phones": unique_target_phones,
    }


@app.post("/score_sentence")
async def score_sentence(
    audio: UploadFile = File(...),
    target: str = Form(...),
):
    """
    句子级别的发音打分。
    - audio:  WAV 格式录音文件
    - target: 目标句子
    """
    t0 = time.time()

    with tempfile.NamedTemporaryFile(
        suffix=".wav", delete=False, dir=TEMP_DIR
    ) as f:
        f.write(await audio.read())
        audio_path = f.name

    try:
        y, sr = librosa.load(audio_path, sr=None)
        duration = round(len(y) / sr, 3)

        # faster-whisper 识别
        asr_result = await transcribe(audio_path)
        heard_text = asr_result["text"]
        words = asr_result["words"]

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
        # 音素级分析
        word_accuracy = (
            round(word_matches / len(target_words) * 100, 1)
            if target_words
            else 0.0
        )

        phone_results = []
        for i, w in enumerate(words[:5]):
            heard_word = w["word"]
            hp = word_to_phones(heard_word)
            if hp:
                phone_results.append(
                    {
                        "word": heard_word,
                        "phones": hp,
                        "probability": w["probability"],
                    }
                )

        total_ms = round((time.time() - t0) * 1000, 1)
        print(
            f"[ScoreSentence] target='{target}' heard='{heard_text}' word_accuracy={word_accuracy} timing={total_ms}ms"
        )

        return JSONResponse(
            {
                "target": target,
                "heard": heard_text,
                "word_accuracy": word_accuracy,
                "phone_results": phone_results,
                **fluency,
                "duration": duration,
                "timing_ms": total_ms,
            }
        )

    finally:
        os.unlink(audio_path)


@app.get("/reference")
async def reference(word: str):
    if not _kokoro_available:
        return JSONResponse({"error": "Kokoro TTS not available"}, status_code=503)
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, kokoro_tts, word, "af_heart", 0.9)
        if result is None:
            return JSONResponse({"error": "Kokoro model not loaded"}, status_code=503)
        audio_data, mimetype = result
        return Response(
            audio_data,
            media_type=mimetype,
            headers={
                "Content-Disposition": f"inline; filename={word}.wav",
            },
        )
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# ========== Page Routes ==========
@app.get("/tingli")
def tingli():
    return FileResponse(os.path.join(BASE_DIR, "tingli", "tingli.html"))


@app.get("/words.json")
def words_json():
    return FileResponse(os.path.join(BASE_DIR, "danci", "words.json"))


@app.get("/danci")
def danci():
    return FileResponse(os.path.join(BASE_DIR, "danci", "danci.html"))


@app.get("/danci-admin")
def danci_admin():
    return FileResponse(os.path.join(BASE_DIR, "danci", "admin.html"))


@app.get("/math")
def math():
    return FileResponse(os.path.join(BASE_DIR, "math", "math.html"))


@app.get("/math-admin")
def math_admin():
    return FileResponse(os.path.join(BASE_DIR, "math", "math-admin.html"))


@app.get("/math.json")
def math_json():
    return FileResponse(os.path.join(BASE_DIR, "math", "math.json"))


@app.get("/shici")
def shici():
    return FileResponse(os.path.join(BASE_DIR, "shici", "shici.html"))


@app.get("/shici.json")
def shici_json():
    return FileResponse(os.path.join(BASE_DIR, "shici", "shici.json"))


@app.get("/chaodai.json")
def chaodai_json():
    return FileResponse(os.path.join(BASE_DIR, "shici", "chaodai.json"))


# ========== Health ==========
@app.get("/health")
def health():
    return {
        "status": "ok",
        "kokoro": _kokoro_available,
        "edge_tts": _edge_tts_available,
    }


# ========== Entry Point ==========
if __name__ == "__main__":
    import uvicorn

    print("MoringRead Unified Server starting on port 5003...")
    uvicorn.run(app, host="0.0.0.0", port=5003)
