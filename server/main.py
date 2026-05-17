# server.py
from flask import Flask, request, Response, jsonify
import edge_tts, asyncio, io

app = Flask(__name__)

@app.route('/tts', methods=['POST'])
def tts():
    data = request.json
    text  = data.get('text', '')
    voice = data.get('voice', 'en-US-JennyNeural')
    rate  = data.get('rate', '+0%')
    pitch = data.get('pitch', '+0Hz')

    async def gen():
        communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
        buf = io.BytesIO()
        async for chunk in communicate.stream():
            if chunk['type'] == 'audio':
                buf.write(chunk['data'])
        return buf.getvalue()

    audio = asyncio.run(gen())
    return Response(audio, mimetype='audio/mpeg',
                    headers={'Access-Control-Allow-Origin': '*'})

@app.route('/voices', methods=['GET'])
def voices():
    async def get_voices():
        return await edge_tts.list_voices()
    return jsonify(asyncio.run(get_voices()))

if __name__ == '__main__':
    app.run(port=5003)