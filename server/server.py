# server.py — FastAPI unified server (TTS + Scoring + Pages)
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

import tempfile
import asyncio
import time
import io
import hashlib
import base64
import threading
import json
import librosa
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager

from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import JSONResponse, FileResponse, Response, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware

from scorer.asr import transcribe, _executor as asr_executor, _get_model as asr_load_model
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


import re
def split_text(text, max_chars=150):
    """将长文本分割成短片段，每段最多max_chars个字符。
    
    关键：先按换行符拆分，确保每个chunk不含换行符。
    Kokoro内部按换行切分输入并期望音素化行数一致，
    如果chunk内嵌换行会导致 "input/output lines must be equal" 错误。
    """
    # 先按换行符切分，保证每个chunk是单行
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    
    chunks = []
    for line in lines:
        # 对每行再按句子边界切分
        sentences = re.split(r'([.!?]+[\s]+)', line)
        current = ""
        for part in sentences:
            if len(current) + len(part) <= max_chars:
                current += part
            else:
                if current.strip():
                    chunks.append(current.strip())
                # 如果单个part超过max_chars，强制截断
                if len(part) > max_chars:
                    for i in range(0, len(part), max_chars):
                        chunk = part[i:i+max_chars].strip()
                        if chunk:
                            chunks.append(chunk)
                    current = ""
                else:
                    current = part
        
        if current.strip():
            chunks.append(current.strip())
    
    if not chunks:
        chunks = [text[:max_chars].replace('\n', ' ')]
    
    return chunks


def kokoro_tts_batch(text, voice, speed, max_workers=4):
    """并行生成多个文本片段的TTS"""
    kokoro = get_kokoro()
    if kokoro is None:
        return None
    
    chunks = split_text(text, max_chars=150)
    print(f"[Kokoro Batch] splitting into {len(chunks)} chunks")
    
    if len(chunks) == 1:
        samples, sample_rate = kokoro.create(chunks[0], voice=voice, speed=speed, lang="en-us")
        buf = io.BytesIO()
        import soundfile as sf
        sf.write(buf, samples, sample_rate, format="WAV", subtype="PCM_16")
        buf.seek(0)
        return buf.read(), "audio/wav"
    
    results = []
    failed_chunks = []
    
    def generate_chunk(chunk_text):
        try:
            samples, sample_rate = kokoro.create(chunk_text, voice=voice, speed=speed, lang="en-us")
            return samples, sample_rate
        except Exception as e:
            print(f"[Kokoro Batch] Error generating chunk: {e}")
            print(f"[Kokoro Batch] Failed chunk text: {repr(chunk_text[:100])}")
            return None
    
    try:
        with ThreadPoolExecutor(max_workers=min(max_workers, len(chunks))) as executor:
            futures = list(executor.map(generate_chunk, chunks))
        
        for i, r in enumerate(futures):
            if r is None:
                # 单个chunk失败时，尝试对该chunk逐行再试一次
                chunk_text = chunks[i]
                sub_lines = [l.strip() for l in chunk_text.split('\n') if l.strip()]
                if len(sub_lines) > 1:
                    print(f"[Kokoro Batch] Retrying chunk {i} as {len(sub_lines)} sub-lines")
                    for line in sub_lines:
                        try:
                            retry_result = kokoro.create(line, voice=voice, speed=speed, lang="en-us")
                            results.append(retry_result)
                        except Exception as e2:
                            print(f"[Kokoro Batch] Sub-line also failed: {e2}")
                            failed_chunks.append(line)
                else:
                    # 单行也失败，用静音占位（0.3秒），避免整体崩溃
                    print(f"[Kokoro Batch] Single line chunk failed, inserting silence placeholder")
                    import numpy as np
                    silence_samples = np.zeros(int(results[0][1] * 0.3)) if results else np.zeros(7200)
                    silence_sr = results[0][1] if results else 24000
                    results.append((silence_samples, silence_sr))
            else:
                results.append(r)
    except Exception as e:
        print(f"[Kokoro Batch] ThreadPoolExecutor error: {e}")
        return None
    
    if not results:
        return None
    
    import soundfile as sf
    import numpy as np
    
    all_samples = []
    sample_rate = results[0][1]
    for samples, sr in results:
        all_samples.append(samples)
    
    combined = np.concatenate(all_samples)
    buf = io.BytesIO()
    sf.write(buf, combined, sample_rate, format="WAV", subtype="PCM_16")
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
    asr_load_model()
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


# ========== Timestamp TTS Helper Functions ==========
def text_to_sentences(text):
    """将文本分割成句子，优先按换行符切分，标点跟随前一句"""
    if '\n' in text:
        return [line.strip() for line in text.split('\n') if line.strip()]
    
    result = []
    parts = re.split(r'([.!?。！？]+)', text)
    current = ""
    for part in parts:
        current += part
        if part and part[-1] in '.!?。！？':
            if current.strip():
                result.append(current.strip())
            current = ""
    if current.strip():
        result.append(current.strip())
    return result

def estimate_sentence_duration(text, speed=1.0):
    """估算句子的发音时长（基于字符数）- 已废弃，保留用于兼容"""
    chars_per_second = 12
    base_duration = len(text) / chars_per_second / speed
    return max(base_duration, 0.5)

# ========== TTS Routes ==========
@app.post("/tts/timestamp")
async def tts_with_timestamp(request_body: dict):
    text = request_body.get("text", "")
    model = request_body.get("model", "kokoro")
    voice = request_body.get("voice", "af_sarah")
    speed = float(request_body.get("speed", 1.0))
    
    sentences = text_to_sentences(text)
    if not sentences:
        return JSONResponse({"error": "No text provided"}, status_code=400)
    
    # 生成完整音频
    cache_id = audio_cache_id(text, voice, speed, model)
    cached = get_cached_audio(cache_id, model)
    
    if cached:
        mimetype = "audio/mpeg" if model == "edge" else "audio/wav"
        with open(cached, "rb") as f:
            audio_data = f.read()
    else:
        if model == "edge":
            if not _edge_tts_available:
                return JSONResponse({"error": "Edge TTS not available"}, status_code=503)
            try:
                audio_data, mimetype = await edge_tts_synthesize(text, voice, speed)
                cache_path = audio_cache_path(cache_id, model)
                with open(cache_path, "wb") as f:
                    f.write(audio_data)
            except Exception as e:
                return JSONResponse({"error": str(e)}, status_code=500)
        else:
            if not _kokoro_available:
                return JSONResponse({"error": "Kokoro TTS not available"}, status_code=503)
            try:
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(None, kokoro_tts_batch, text, voice, speed)
                if result is None:
                    return JSONResponse({"error": "Kokoro model not loaded"}, status_code=503)
                audio_data, mimetype = result
                cache_path = audio_cache_path(cache_id, model)
                with open(cache_path, "wb") as f:
                    f.write(audio_data)
            except Exception as e:
                return JSONResponse({"error": str(e)}, status_code=500)
    
    # 计算时间戳（基于实际音频时长）
    import soundfile as sf
    import numpy as np
    
    audio_buf = io.BytesIO(audio_data)
    samples, sample_rate = sf.read(audio_buf)
    actual_duration = len(samples) / sample_rate
    
    # 按字符数比例分配时间
    total_chars = sum(len(s) for s in sentences)
    timestamps = []
    current_time = 0.0
    for i, sentence in enumerate(sentences):
        ratio = len(sentence) / total_chars if total_chars > 0 else 1.0 / len(sentences)
        duration = actual_duration * ratio
        timestamps.append({
            "index": i,
            "text": sentence,
            "start": round(current_time, 3),
            "end": round(current_time + duration, 3)
        })
        current_time += duration
    
    return JSONResponse({
        "audio": base64.b64encode(audio_data).decode('utf-8'),
        "mimetype": mimetype,
        "timestamps": timestamps,
        "duration": round(actual_duration, 3)
    })

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
            result = await loop.run_in_executor(None, kokoro_tts_batch, text, voice, speed)
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


@app.post("/tts/stream")
async def tts_stream(request_body: dict):
    text = request_body.get("text", "")
    model = request_body.get("model", "kokoro")
    voice = request_body.get("voice", "af_sarah")
    speed = float(request_body.get("speed", 1.0))
    start = time.time()

    cache_id = audio_cache_id(text, voice, speed, model)
    cached = get_cached_audio(cache_id, model)
    if cached:
        print(f"[Cache HIT] streaming {cache_id}")
        def iter_file():
            with open(cached, "rb") as f:
                chunk = f.read(4096)
                while chunk:
                    yield chunk
                    chunk = f.read(4096)
        mimetype = "audio/mpeg" if model == "edge" else "audio/wav"
        return StreamingResponse(
            iter_file(),
            media_type=mimetype,
            headers={
                "Access-Control-Allow-Origin": "*",
                "X-Cache": "HIT",
                "Transfer-Encoding": "chunked",
            },
        )

    if model == "edge":
        if not _edge_tts_available:
            return JSONResponse({"error": "Edge TTS not available"}, status_code=503)
        try:
            import edge_tts
            rate_str = f"+{int((speed - 1.0) * 100)}%" if speed >= 1.0 else f"{int((speed - 1.0) * 100)}%"
            communicate = edge_tts.Communicate(text, voice, rate=rate_str)
            
            async def stream_audio():
                buffer = b""
                async for chunk in communicate.stream():
                    if chunk["type"] == "audio":
                        buffer += chunk["data"]
                        if len(buffer) >= 4096:
                            yield buffer
                            buffer = b""
                if buffer:
                    yield buffer
            
            print(f"[Edge TTS] streaming started")
            return StreamingResponse(
                stream_audio(),
                media_type="audio/mpeg",
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "X-Cache": "MISS",
                },
            )
        except Exception as e:
            print(f"[Edge TTS Error] {e}")
            return JSONResponse({"error": str(e)}, status_code=500)
    else:
        if not _kokoro_available:
            return JSONResponse({"error": "Kokoro TTS not available"}, status_code=503)
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, kokoro_tts, text, voice, speed)
            if result is None:
                return JSONResponse({"error": "Kokoro model not loaded"}, status_code=503)
            audio_data, mimetype = result
            
            def iter_audio():
                for i in range(0, len(audio_data), 4096):
                    yield audio_data[i:i+4096]
            
            cache_path = audio_cache_path(cache_id, model)
            with open(cache_path, "wb") as f:
                f.write(audio_data)
            
            elapsed = time.time() - start
            print(f"[Kokoro TTS] generated in {elapsed:.2f}s, streaming")
            return StreamingResponse(
                iter_audio(),
                media_type=mimetype,
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "X-Cache": "MISS",
                    "Transfer-Encoding": "chunked",
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


generation_state = {
    "running": False,
    "paused": False,
    "current": 0,
    "total": 0,
    "completed": 0,
    "failed": 0,
    "message": "",
}
generation_lock = threading.Lock()


@app.get("/tts/generate/status")
def get_generation_status():
    return generation_state


@app.post("/tts/generate/stop")
def stop_generation():
    global generation_state
    with generation_lock:
        generation_state["running"] = False
        generation_state["paused"] = False
        generation_state["message"] = "已停止"
    return {"status": "stopped"}


@app.post("/tts/generate/pause")
def pause_generation():
    global generation_state
    with generation_lock:
        generation_state["paused"] = True
        generation_state["message"] = "已暂停"
    return {"status": "paused"}


@app.post("/tts/generate/resume")
def resume_generation():
    global generation_state
    with generation_lock:
        generation_state["paused"] = False
        generation_state["message"] = "继续生成"
    return {"status": "resumed"}


@app.post("/tts/generate/batch")
async def batch_generate_tts(request_body: dict):
    global generation_state
    
    articles = request_body.get("articles", [])
    voice = request_body.get("voice", "af_sarah")
    speed = float(request_body.get("speed", 1.0))
    model = request_body.get("model", "kokoro")
    
    if not articles:
        return JSONResponse({"error": "No articles provided"}, status_code=400)
    
    with generation_lock:
        if generation_state["running"]:
            return JSONResponse({"error": "Generation already running"}, status_code=409)
        
        generation_state["running"] = True
        generation_state["paused"] = False
        generation_state["current"] = 0
        generation_state["total"] = len(articles)
        generation_state["completed"] = 0
        generation_state["failed"] = 0
        generation_state["message"] = "开始生成"
    
    async def generate_stream():
        global generation_state
        completed = 0
        failed = 0
        
        for i, article in enumerate(articles):
            while True:
                with generation_lock:
                    if not generation_state["running"]:
                        yield f'data: {json.dumps({"status": "stopped", "completed": completed, "failed": failed, "total": len(articles), "message": "生成已停止"})}\n\n'
                        return
                    if not generation_state["paused"]:
                        break
                await asyncio.sleep(0.5)
            
            text = article.get("text", "")
            title = article.get("title", f"Article {i+1}")
            
            with generation_lock:
                generation_state["current"] = i + 1
                generation_state["message"] = f"正在生成: {title}"
            
            cache_id = audio_cache_id(text, voice, speed, model)
            cached_path = get_cached_audio(cache_id, model)
            
            if cached_path:
                data = {"status": "cached", "index": i, "title": title, "completed": completed, "failed": failed, "total": len(articles), "message": f"{title} - 已缓存，跳过"}
                yield f'data: {json.dumps(data)}\n\n'
                completed += 1
                with generation_lock:
                    generation_state["completed"] = completed
                continue
            
            try:
                if model == "edge":
                    import edge_tts
                    rate_str = f"+{int((speed - 1.0) * 100)}%" if speed >= 1.0 else f"{int((speed - 1.0) * 100)}%"
                    communicate = edge_tts.Communicate(text, voice, rate=rate_str)
                    
                    audio_bytes = b""
                    async for chunk in communicate.stream():
                        if chunk["type"] == "audio":
                            audio_bytes += chunk["data"]
                    
                    cache_path = audio_cache_path(cache_id, model)
                    with open(cache_path, "wb") as f:
                        f.write(audio_bytes)
                else:
                    result = await asyncio.get_event_loop().run_in_executor(None, kokoro_tts, text, voice, speed)
                    if result is None:
                        raise Exception("Kokoro TTS failed")
                    audio_bytes, _ = result
                    cache_path = audio_cache_path(cache_id, model)
                    with open(cache_path, "wb") as f:
                        f.write(audio_bytes)
                
                completed += 1
                with generation_lock:
                    generation_state["completed"] = completed
                
                data = {"status": "success", "index": i, "title": title, "completed": completed, "failed": failed, "total": len(articles), "message": f"{title} - 生成成功"}
                yield f'data: {json.dumps(data)}\n\n'
                
            except Exception as e:
                failed += 1
                with generation_lock:
                    generation_state["failed"] = failed
                
                data = {"status": "error", "index": i, "title": title, "completed": completed, "failed": failed, "total": len(articles), "message": f"{title} - 生成失败: {str(e)}"}
                yield f'data: {json.dumps(data)}\n\n'
        
        with generation_lock:
            generation_state["running"] = False
            generation_state["message"] = "生成完成"
        
        data = {"status": "finished", "completed": completed, "failed": failed, "total": len(articles), "message": f"生成完成！成功: {completed}, 失败: {failed}"}
        yield f'data: {json.dumps(data)}\n\n'
    
    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={
            "Access-Control-Allow-Origin": "*",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


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
        audio_load_s = round(t_audio_load - t0, 2)

        asr_result = await transcribe(audio_path)
        t_asr = time.time()
        asr_s = round(t_asr - t_audio_load, 2)
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
        acoustic_s = round(t_acoustic - t_asr, 2)

        # 流利度
        fluency = fluency_score(words, duration)
        t_fluency = time.time()
        fluency_s = round(t_fluency - t_acoustic, 2)

        total_s = round(t_fluency - t0, 2)

        # 单词正确性
        word_correct = heard_text.lower().strip() == target_clean.lower().strip()

        print(
            f"[Score] timing: audio_load={audio_load_s}s asr={asr_s}s acoustic={acoustic_s}s fluency={fluency_s}s total={total_s}s"
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
                "timing": {
                    "audio_load": audio_load_s,
                    "asr": asr_s,
                    "acoustic": acoustic_s,
                    "fluency": fluency_s,
                    "total": total_s,
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

        total_s = round(time.time() - t0, 2)
        print(
            f"[ScoreSentence] target='{target}' heard='{heard_text}' word_accuracy={word_accuracy} timing={total_s}s"
        )

        return JSONResponse(
            {
                "target": target,
                "heard": heard_text,
                "word_accuracy": word_accuracy,
                "phone_results": phone_results,
                **fluency,
                "duration": duration,
                "timing": total_s,
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


@app.get("/tingli2")
def tingli2():
    return FileResponse(os.path.join(BASE_DIR, "tingli", "tingli2.html"))


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


# ========== Favicon Route ==========
@app.get("/favicon.ico")
async def favicon():
    favicon_path = os.path.join(BASE_DIR, "favicon.ico")
    if os.path.exists(favicon_path):
        return FileResponse(favicon_path, media_type="image/x-icon")
    return Response(content=b'', media_type='image/x-icon')

# ========== Entry Point ==========
if __name__ == "__main__":
    import uvicorn

    print("MoringRead Unified Server starting on port 5003...")
    uvicorn.run(app, host="0.0.0.0", port=5003)
