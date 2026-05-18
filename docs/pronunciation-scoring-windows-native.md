# Windows 原生安装指南
> WhisperX + Kokoro + FastAPI，Python 3.12，uv 管理环境
> GTX 960M 2G 显存优化版，跳过 pyannote 轻量装法

---

## 一、创建项目

打开 PowerShell 或 CMD：

```powershell
uv init pronunciation-scorer --python 3.12
cd pronunciation-scorer
uv python pin 3.12
```

---

## 二、安装 PyTorch（CUDA 版）

第一步，恢复 PyPI 为主源，PyTorch 作为补充源。 编辑 pyproject.toml，在文件末尾加上：

[[tool.uv.index]]
name = "pytorch"
url = "https://download.pytorch.org/whl/cu118"
explicit = true

第二步，指定 torch 和 torchaudio 从 PyTorch 源拉。 在 pyproject.toml 里加：
[tool.uv.sources]
torch = { index = "pytorch" }
torchaudio = { index = "pytorch" }

GTX 960M 是 Maxwell 架构，最高支持 CUDA 11.x，用 cu118：

```powershell
uv add torch==2.4.1 torchaudio==2.4.1
```

验证显卡是否识别：

```powershell
uv run python -c "import torch; print('CUDA:', torch.cuda.is_available()); print('GPU:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU only')"
```

期望输出：
```
CUDA: True
GPU: NVIDIA GeForce GTX 960M
```

> 如果显示 `CUDA: False`，检查 Windows 侧 NVIDIA 驱动版本，GTX 960M 需要驱动 ≥ 452.39。
> 驱动版本查看：右键桌面 → NVIDIA 控制面板 → 帮助 → 系统信息。

---

## 三、安装 WhisperX（轻量版）

WhisperX 完整安装会拉 pyannote，在 Windows 上依赖编译复杂。我们分步装，跳过 pyannote：

**第一步，装 openai-whisper：**
```powershell
uv add openai-whisper
```

**第二步，装 whisperx 核心：**
```powershell
uv add whisperx
```

**第三步，手动补装 whisperx 实际需要的依赖：**
```powershell
uv add faster-whisper transformers pandas nltk
```

验证：
```powershell
uv run python -c "import whisperx; print('WhisperX OK')"
```

首次加载模型（会下载 ~140MB，需要等一会儿）：
```powershell
uv run python -c "
import whisperx
model = whisperx.load_model('base', device='cuda', compute_type='float16')
print('Model loaded OK')
"
```

> 如果报 `float16` 错误，把 `compute_type` 改成 `'int8'`，960M 在 float16 有时不稳定。

---

## 四、安装 Kokoro

```powershell
uv add kokoro-onnx soundfile scipy
```

首次运行会自动下载模型文件（~300MB）：

```powershell
uv run python -c "
from kokoro_onnx import Kokoro
k = Kokoro('kokoro-v0_19.onnx', 'voices.bin')
samples, sr = k.create('hello world', voice='af', speed=1.0, lang='en-us')
print(f'Kokoro OK: {sr}Hz, {len(samples)} samples')
"
```

---

## 五、安装 FastAPI 和其他依赖

```powershell
uv add fastapi uvicorn python-multipart librosa numpy
```

---

## 六、完整 pyproject.toml 参考

安装完成后 `pyproject.toml` 应包含：

```toml
[project]
name = "pronunciation-scorer"
version = "0.1.0"
requires-python = "==3.12.*"
dependencies = [
    "torch==2.1.2",
    "torchaudio==2.1.2",
    "openai-whisper",
    "whisperx",
    "faster-whisper",
    "transformers",
    "pandas",
    "nltk",
    "kokoro-onnx",
    "soundfile",
    "scipy",
    "fastapi",
    "uvicorn",
    "python-multipart",
    "librosa",
    "numpy",
]

[tool.uv.sources]
torch = { index = "pytorch-cu118" }
torchaudio = { index = "pytorch-cu118" }

[[tool.uv.index]]
name = "pytorch-cu118"
url = "https://download.pytorch.org/whl/cu118"
explicit = true
```

---

## 七、项目结构

```
pronunciation-scorer/
├── pyproject.toml
├── uv.lock
├── config.py
├── server.py
├── scorer/
│   ├── __init__.py
│   ├── asr.py        # WhisperX 识别 + 对齐
│   ├── phoneme.py    # 音素对/错判断
│   └── tts.py        # Kokoro 标准音生成
└── temp/             # 临时音频文件
```

创建目录：
```powershell
mkdir scorer
mkdir temp
New-Item scorer\__init__.py -ItemType File
```

---

## 八、核心代码

### config.py

```python
# config.py
WHISPER_MODEL   = "base"        # tiny / base / small，960M 建议 base
WHISPER_DEVICE  = "cuda"        # 改成 "cpu" 可强制用 CPU
COMPUTE_TYPE    = "int8"        # 960M 用 int8 更稳定，有其他显卡可试 float16
ALIGN_LANGUAGE  = "en"

KOKORO_MODEL    = "kokoro-v0_19.onnx"
KOKORO_VOICES   = "voices.bin"
KOKORO_VOICE    = "af"
KOKORO_SPEED    = 0.9           # 略慢，方便学习者跟读
```

### scorer/asr.py

```python
# scorer/asr.py
import whisperx
from config import WHISPER_MODEL, WHISPER_DEVICE, COMPUTE_TYPE, ALIGN_LANGUAGE

_model       = None
_align_model = None
_metadata    = None

def _get_model():
    global _model
    if _model is None:
        _model = whisperx.load_model(
            WHISPER_MODEL,
            device=WHISPER_DEVICE,
            compute_type=COMPUTE_TYPE,
        )
    return _model

def _get_align_model():
    global _align_model, _metadata
    if _align_model is None:
        _align_model, _metadata = whisperx.load_align_model(
            language_code=ALIGN_LANGUAGE,
            device=WHISPER_DEVICE,
        )
    return _align_model, _metadata

def transcribe_and_align(audio_path: str) -> dict:
    """
    返回：
    {
        "text": "apple",
        "words": [
            {"word": "apple", "start": 0.0, "end": 0.4, "score": 0.92}
        ]
    }
    """
    model = _get_model()
    audio = whisperx.load_audio(audio_path)

    # 第一步：识别
    result = model.transcribe(audio, language="en")

    # 第二步：词级对齐
    align_model, metadata = _get_align_model()
    aligned = whisperx.align(
        result["segments"],
        align_model,
        metadata,
        audio,
        WHISPER_DEVICE,
        return_char_alignments=False,
    )

    words = []
    for seg in aligned.get("word_segments", []):
        words.append({
            "word":  seg.get("word", "").strip().lower(),
            "start": round(seg.get("start", 0.0), 3),
            "end":   round(seg.get("end", 0.0), 3),
            "score": round(seg.get("score", 0.0), 3),
        })

    full_text = " ".join(w["word"] for w in words)
    return {"text": full_text, "words": words}
```

### scorer/phoneme.py

```python
# scorer/phoneme.py
# 用 CMU Pronouncing Dictionary 把单词拆成音素，再对比
import nltk
from nltk.corpus import cmudict
from difflib import SequenceMatcher

# 首次运行自动下载 CMU 字典（~3MB）
nltk.download("cmudict", quiet=True)
_cmu = cmudict.dict()

def word_to_phones(word: str) -> list[str]:
    """把英语单词转换为音素列表，找不到返回空列表"""
    entries = _cmu.get(word.lower(), [])
    if not entries:
        return []
    # 去掉音素末尾的数字（重音标记），如 AE1 → AE
    return [p.rstrip("012") for p in entries[0]]

def compare_phones(target_word: str, heard_word: str) -> dict:
    """
    比较目标单词和识别单词的音素，返回对/错结果。
    """
    target_phones = word_to_phones(target_word)
    heard_phones  = word_to_phones(heard_word)

    if not target_phones:
        return {
            "target_phones": [],
            "heard_phones":  heard_phones,
            "results":       [],
            "correct_count": 0,
            "total_count":   0,
            "phone_accuracy": 0.0,
        }

    # 用 SequenceMatcher 做音素序列对齐
    matcher = SequenceMatcher(None, target_phones, heard_phones)
    matched = set()
    for block in matcher.get_matching_blocks():
        for i in range(block.size):
            matched.add(block.a + i)   # target_phones 里匹配到的索引

    results = []
    for i, phone in enumerate(target_phones):
        results.append({
            "phone":   phone,
            "correct": i in matched,
        })

    correct_count = sum(1 for r in results if r["correct"])
    total_count   = len(results)
    phone_accuracy = round(correct_count / total_count * 100, 1) if total_count else 0.0

    return {
        "target_phones":  target_phones,
        "heard_phones":   heard_phones,
        "results":        results,        # 每个音素对/错
        "correct_count":  correct_count,
        "total_count":    total_count,
        "phone_accuracy": phone_accuracy, # 0~100
    }

def fluency_score(words: list[dict], audio_duration: float) -> dict:
    """根据词级对齐结果计算流利度"""
    if not words:
        return {"fluency": 0, "pause_ratio": 1.0}
    speech_time = sum(w["end"] - w["start"] for w in words)
    pause_ratio = round(1.0 - speech_time / audio_duration, 3) if audio_duration > 0 else 1.0
    fluency     = round(max(0.0, 100.0 - pause_ratio * 80), 1)
    return {
        "fluency":     fluency,      # 0~100
        "pause_ratio": pause_ratio,  # 停顿占比
    }
```

### scorer/tts.py

```python
# scorer/tts.py
import soundfile as sf
import tempfile
import os
from kokoro_onnx import Kokoro
from config import KOKORO_MODEL, KOKORO_VOICES, KOKORO_VOICE, KOKORO_SPEED

_kokoro = None

def _get_kokoro():
    global _kokoro
    if _kokoro is None:
        _kokoro = Kokoro(KOKORO_MODEL, KOKORO_VOICES)
    return _kokoro

def generate_reference(text: str) -> str:
    """生成标准发音 WAV，返回临时文件路径"""
    k = _get_kokoro()
    samples, sr = k.create(text, voice=KOKORO_VOICE, speed=KOKORO_SPEED, lang="en-us")
    f = tempfile.NamedTemporaryFile(suffix=".wav", delete=False, dir="temp")
    sf.write(f.name, samples, sr)
    return f.name
```

### server.py

```python
# server.py
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
import tempfile, os, librosa

from scorer.asr     import transcribe_and_align
from scorer.phoneme import compare_phones, fluency_score
from scorer.tts     import generate_reference

app = FastAPI(title="Pronunciation Scorer")

# 允许前端跨域调用
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/score")
async def score(
    audio:  UploadFile = File(...),
    target: str        = Form(...),
):
    # 保存上传的录音到临时文件
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False, dir="temp") as f:
        f.write(await audio.read())
        audio_path = f.name

    try:
        # 获取音频时长
        y, sr      = librosa.load(audio_path, sr=None)
        duration   = round(len(y) / sr, 3)

        # 识别 + 词级对齐
        asr_result = transcribe_and_align(audio_path)
        heard_text = asr_result["text"]
        words      = asr_result["words"]

        # 取识别出的第一个词和目标词做音素对比
        heard_word = words[0]["word"] if words else ""
        phone_result = compare_phones(target, heard_word)

        # 流利度
        fluency = fluency_score(words, duration)

        # 整体词级是否正确
        word_correct = heard_word.lower() == target.lower()

        return JSONResponse({
            "target":        target,
            "heard":         heard_text,
            "word_correct":  word_correct,
            **phone_result,
            **fluency,
            "duration":      duration,
        })

    finally:
        os.unlink(audio_path)


@app.get("/reference")
def reference(word: str):
    """获取 Kokoro 生成的标准发音"""
    path = generate_reference(word)
    return FileResponse(
        path,
        media_type="audio/wav",
        headers={"Content-Disposition": f"inline; filename={word}.wav"},
        background=None,
    )


@app.get("/health")
def health():
    return {"status": "ok"}
```

---

## 九、启动服务

```powershell
uv run uvicorn server:app --reload --port 8000
```

---

## 十、测试接口

健康检查：
```powershell
curl http://localhost:8000/health
```

获取标准发音（浏览器直接打开）：
```
http://localhost:8000/reference?word=apple
```

上传录音打分：
```powershell
curl -X POST http://localhost:8000/score `
  -F "audio=@recording.wav" `
  -F "target=apple"
```

返回示例：
```json
{
  "target": "apple",
  "heard": "apple",
  "word_correct": true,
  "target_phones": ["AE", "P", "AH", "L"],
  "heard_phones":  ["AE", "P", "AH", "L"],
  "results": [
    {"phone": "AE", "correct": true},
    {"phone": "P",  "correct": true},
    {"phone": "AH", "correct": true},
    {"phone": "L",  "correct": true}
  ],
  "correct_count": 4,
  "total_count": 4,
  "phone_accuracy": 100.0,
  "fluency": 91.2,
  "pause_ratio": 0.11,
  "duration": 0.82
}
```

---

## 常见问题

**`whisperx` 报 `No module named 'pyannote'`**
正常，轻量装法跳过了 pyannote，不影响识别和对齐功能。

**`compute_type float16 not supported`**
在 `config.py` 把 `COMPUTE_TYPE` 改为 `"int8"`，960M 在 Windows 下 float16 不稳定。

**Kokoro 模型下载失败**
手动从 Hugging Face 下载两个文件放到项目根目录：
- `kokoro-v0_19.onnx`
- `voices.bin`

下载地址：`https://huggingface.co/hexgrad/Kokoro-82M`

**录音格式不是 WAV**
前端录音建议输出 WAV 16kHz 单声道，或在 server.py 里用 ffmpeg 转换：
```python
import subprocess
subprocess.run(["ffmpeg", "-i", input_path, "-ar", "16000", "-ac", "1", output_path])
```
