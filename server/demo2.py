from flask import Flask, request, Response, send_from_directory
from kokoro_onnx import Kokoro
import soundfile as sf
import numpy as np
import io
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

app = Flask(__name__)
kokoro = Kokoro(os.path.join(BASE_DIR, "server", "kokoro-v1.0.onnx"),
                os.path.join(BASE_DIR, "server", "voices-v1.0.bin"))

@app.route('/tts', methods=['POST'])
def tts():
    data = request.json
    text  = data.get('text', '')
    voice = data.get('voice', 'af_sarah')
    speed = float(data.get('speed', 1.0))

    samples, sample_rate = kokoro.create(text, voice=voice, speed=speed, lang='en-us')

    buf = io.BytesIO()
    sf.write(buf, samples, sample_rate, format='WAV')
    buf.seek(0)

    return Response(buf.read(), mimetype='audio/wav',
                    headers={'Access-Control-Allow-Origin': '*'})

@app.route('/voices', methods=['GET'])
def voices():
    return {'voices': [
        'af_sarah', 'af_bella', 'af_nicole', 'af_sky',
        'am_adam', 'am_michael', 'bf_emma', 'bm_george'
    ]}

@app.route('/tingli')
def tingli():
    return send_from_directory(os.path.join(BASE_DIR, 'tingli'), 'tingli.html')

@app.route('/tingli2')
def tingli2():
    return send_from_directory(os.path.join(BASE_DIR, 'tingli'), 'tingli2.html')

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
    print("Kokoro TTS server starting on port 5003...")
    app.run(port=5003)
