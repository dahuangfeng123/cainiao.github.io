from flask import Flask, request, Response, send_from_directory, jsonify
import io
import os
import time
import threading
import asyncio
import hashlib


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUDIO_CACHE_DIR = os.path.join(BASE_DIR, "data", "audio")

app = Flask(__name__)

# 确保缓存目录存在
os.makedirs(AUDIO_CACHE_DIR, exist_ok=True)

def audio_cache_id(text, voice, speed, model):
    key = f"{model}|{voice}|{speed:.2f}|{text}"
    return hashlib.md5(key.encode()).hexdigest()

def audio_cache_path(cache_id, model):
    ext = 'mp3' if model == 'edge' else 'wav'
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
                    print(f"Kokoro model files not found, skipping...")
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
    import numpy as np
    samples, sample_rate = kokoro.create(text, voice=voice, speed=speed, lang='en-us')
    buf = io.BytesIO()
    sf.write(buf, samples, sample_rate, format='WAV', subtype='PCM_16')
    buf.seek(0)
    return buf.read(), 'audio/wav'

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

def edge_tts_synthesize(text, voice, rate):
    import edge_tts
    async def gen():
        rate_str = f"+{int((rate - 1.0) * 100)}%" if rate >= 1.0 else f"{int((rate - 1.0) * 100)}%"
        communicate = edge_tts.Communicate(text, voice, rate=rate_str)
        buf = io.BytesIO()
        async for chunk in communicate.stream():
            if chunk['type'] == 'audio':
                buf.write(chunk['data'])
        return buf.getvalue()
    return asyncio.run(gen()), 'audio/mpeg'

# ========== 预热 ==========
@app.before_request
def warmup():
    get_kokoro()

# ========== TTS 路由 ==========
KOKORO_VOICES = [
    'af_heart', 'af_alloy', 'af_aoede', 'af_bella', 'af_jessica',
    'af_kore', 'af_nicole', 'af_nova', 'af_river', 'af_sarah', 'af_sky',
    'am_adam', 'am_echo', 'am_eric', 'am_fenrir', 'am_liam',
    'am_michael', 'am_onyx', 'am_puck', 'am_santa'
]

EDGE_VOICES = [
    'en-US-JennyNeural', 'en-US-GuyNeural', 'en-US-AriaNeural',
    'en-US-DavisNeural', 'en-US-AmberNeural', 'en-US-AndrewNeural',
    'en-US-EmmaNeural', 'en-US-BrianNeural',
    'en-GB-SoniaNeural', 'en-GB-RyanNeural', 'en-GB-LibbyNeural',
    'en-GB-ThomasNeural', 'en-AU-NatashaNeural', 'en-AU-WilliamNeural'
]

@app.route('/tts', methods=['POST'])
def tts():
    data = request.json
    text = data.get('text', '')
    model = data.get('model', 'kokoro')
    voice = data.get('voice', 'af_sarah')
    speed = float(data.get('speed', 1.0))

    start = time.time()

    # 检查缓存
    cache_id = audio_cache_id(text, voice, speed, model)
    cached = get_cached_audio(cache_id, model)
    if cached:
        elapsed = time.time() - start
        mimetype = 'audio/mpeg' if model == 'edge' else 'audio/wav'
        print(f"[Cache HIT] {cache_id} in {elapsed:.3f}s")
        with open(cached, 'rb') as f:
            audio_data = f.read()
        return Response(audio_data, mimetype=mimetype,
                        headers={'Access-Control-Allow-Origin': '*', 'X-Generation-Time': f'{elapsed:.3f}', 'X-Cache': 'HIT'})

    # 缓存未命中，生成音频
    if model == 'edge':
        if not _edge_tts_available:
            return jsonify({'error': 'Edge TTS not available'}), 503
        try:
            audio_data, mimetype = edge_tts_synthesize(text, voice, speed)
            # 保存缓存
            cache_path = audio_cache_path(cache_id, model)
            with open(cache_path, 'wb') as f:
                f.write(audio_data)
            elapsed = time.time() - start
            print(f"[Edge TTS] generated in {elapsed:.2f}s, cached as {cache_id}")
            return Response(audio_data, mimetype=mimetype,
                            headers={'Access-Control-Allow-Origin': '*', 'X-Generation-Time': f'{elapsed:.2f}', 'X-Cache': 'MISS'})
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    else:
        if not _kokoro_available:
            return jsonify({'error': 'Kokoro TTS not available'}), 503
        try:
            result = kokoro_tts(text, voice, speed)
            if result is None:
                return jsonify({'error': 'Kokoro model not loaded'}), 503
            audio_data, mimetype = result
            # 保存缓存
            cache_path = audio_cache_path(cache_id, model)
            with open(cache_path, 'wb') as f:
                f.write(audio_data)
            elapsed = time.time() - start
            print(f"[Kokoro TTS] generated in {elapsed:.2f}s, cached as {cache_id}")
            return Response(audio_data, mimetype=mimetype,
                            headers={'Access-Control-Allow-Origin': '*', 'X-Generation-Time': f'{elapsed:.2f}', 'X-Cache': 'MISS'})
        except Exception as e:
            return jsonify({'error': str(e)}), 500

@app.route('/voices', methods=['GET'])
def voices():
    model = request.args.get('model', 'kokoro')
    if model == 'edge':
        return jsonify({'model': 'edge', 'voices': EDGE_VOICES})
    return jsonify({'model': 'kokoro', 'voices': KOKORO_VOICES})

@app.route('/models', methods=['GET'])
def models():
    available = []
    if _kokoro_available:
        available.append({'id': 'kokoro', 'name': 'Kokoro (本地)', 'desc': '82M参数，离线运行，低延迟'})
    if _edge_tts_available:
        available.append({'id': 'edge', 'name': 'Edge TTS (云端)', 'desc': '微软云端，音质优秀，需联网'})
    return jsonify(available)

@app.route('/cache/stats', methods=['GET'])
def cache_stats():
    files = os.listdir(AUDIO_CACHE_DIR) if os.path.exists(AUDIO_CACHE_DIR) else []
    audio_files = [f for f in files if f.endswith(('.wav', '.mp3'))]
    total_size = sum(os.path.getsize(os.path.join(AUDIO_CACHE_DIR, f)) for f in audio_files)
    return jsonify({
        'count': len(audio_files),
        'size_mb': round(total_size / 1024 / 1024, 2),
        'dir': AUDIO_CACHE_DIR
    })

@app.route('/cache/clear', methods=['POST'])
def cache_clear():
    files = os.listdir(AUDIO_CACHE_DIR) if os.path.exists(AUDIO_CACHE_DIR) else []
    removed = 0
    for f in files:
        if f.endswith(('.wav', '.mp3')):
            os.remove(os.path.join(AUDIO_CACHE_DIR, f))
            removed += 1
    return jsonify({'removed': removed})

# ========== 页面路由 ==========
@app.route('/tingli')
def tingli():
    return send_from_directory(os.path.join(BASE_DIR, 'tingli'), 'tingli.html')

@app.route('/words.json')
def words_json():
    return send_from_directory(os.path.join(BASE_DIR, 'danci'), 'words.json')

@app.route('/danci')
def danci():
    return send_from_directory(os.path.join(BASE_DIR, 'danci'), 'danci.html')

@app.route('/danci-admin')
def danci_admin():
    return send_from_directory(os.path.join(BASE_DIR, 'danci'), 'admin.html')

@app.route('/math')
def math():
    return send_from_directory(os.path.join(BASE_DIR, 'math'), 'math.html')

@app.route('/math-admin')
def math_admin():
    return send_from_directory(os.path.join(BASE_DIR, 'math'), 'math-admin.html')

@app.route('/math.json')
def math_json():
    return send_from_directory(os.path.join(BASE_DIR, 'math'), 'math.json')

@app.route('/shici')
def shici():
    return send_from_directory(os.path.join(BASE_DIR, 'shici'), 'shici.html')

@app.route('/shici.json')
def shici_json():
    return send_from_directory(os.path.join(BASE_DIR, 'shici'), 'shici.json')

@app.route('/chaodai.json')
def chaodai_json():
    return send_from_directory(os.path.join(BASE_DIR, 'shici'), 'chaodai.json')

if __name__ == '__main__':
    print("MoringRead TTS Server starting on port 5003...")
    get_kokoro()
    check_edge_tts()
    print(f"Kokoro TTS: {'✅' if _kokoro_available else '❌'}")
    print(f"Edge TTS:   {'✅' if _edge_tts_available else '❌'}")
    print("Server ready!")
    app.run(port=5003, threaded=True)
