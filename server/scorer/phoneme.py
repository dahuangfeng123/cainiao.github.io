# scorer/phoneme.py
import nltk
from nltk.corpus import cmudict
from difflib import SequenceMatcher

# 首次运行自动下载 CMU 字典（~3MB）
nltk.download("cmudict", quiet=True)
_cmu = cmudict.dict()

def word_to_phones(word: str) -> list:
    """把英语单词转换为音素列表，找不到返回空列表。"""
    entries = _cmu.get(word.lower(), [])
    if not entries:
        return []
    # 去掉重音标记数字，如 AE1 → AE
    return [p.rstrip("012") for p in entries[0]]

def compare_phones(target_word: str, heard_word: str) -> dict:
    """
    比较目标单词和识别单词的音素，返回每个音素对/错。
    返回格式：
    {
        "target_phones": ["AE", "P", "AH", "L"],
        "heard_phones":  ["AE", "P", "AH", "L"],
        "results": [
            {"phone": "AE", "correct": true},
            {"phone": "P",  "correct": true},
            {"phone": "AH", "correct": true},
            {"phone": "L",  "correct": true},
        ],
        "correct_count":  4,
        "total_count":    4,
        "phone_accuracy": 100.0,
    }
    """
    target_phones = word_to_phones(target_word)
    heard_phones  = word_to_phones(heard_word)

    if not target_phones:
        return {
            "target_phones":  [],
            "heard_phones":   heard_phones,
            "results":        [],
            "correct_count":  0,
            "total_count":    0,
            "phone_accuracy": 0.0,
        }

    # SequenceMatcher 对齐两个音素序列，找出匹配的位置
    matcher = SequenceMatcher(None, target_phones, heard_phones)
    matched = set()
    for block in matcher.get_matching_blocks():
        for i in range(block.size):
            matched.add(block.a + i)

    results = [
        {"phone": phone, "correct": i in matched}
        for i, phone in enumerate(target_phones)
    ]

    correct_count  = sum(1 for r in results if r["correct"])
    total_count    = len(results)
    phone_accuracy = round(correct_count / total_count * 100, 1) if total_count else 0.0

    return {
        "target_phones":  target_phones,
        "heard_phones":   heard_phones,
        "results":        results,
        "correct_count":  correct_count,
        "total_count":    total_count,
        "phone_accuracy": phone_accuracy,
    }

def fluency_score(words: list, audio_duration: float) -> dict:
    """
    根据词级时间戳计算流利度。
    返回格式：
    {
        "fluency":     91.2,   # 0~100
        "pause_ratio": 0.11,   # 停顿占总时长比例
    }
    """
    if not words:
        return {"fluency": 0.0, "pause_ratio": 1.0}

    speech_time = sum(w["end"] - w["start"] for w in words)
    pause_ratio = round(1.0 - speech_time / audio_duration, 3) if audio_duration > 0 else 1.0
    fluency     = round(max(0.0, 100.0 - pause_ratio * 80), 1)

    return {
        "fluency":     fluency,
        "pause_ratio": pause_ratio,
    }