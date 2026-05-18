# scorer/acoustic.py
from difflib import SequenceMatcher

# 置信度低于此阈值，认为该词发音不准
CONFIDENCE_THRESHOLD = 0.85

def score_word(target_phones: list, probability: float) -> dict:
    """
    根据 faster-whisper 返回的词级置信度，推算每个音素的对/错。

    逻辑：
    - probability >= CONFIDENCE_THRESHOLD：整个词发音准确，所有音素标记为正确
    - probability < CONFIDENCE_THRESHOLD：按置信度比例，从后往前标记音素为错误
      （末尾音素通常是发音不准的高发位置）

    返回：
    {
        "heard_phones":   ["AE", "P", "AH", "L"],
        "results": [
            {"phone": "AE", "correct": true},
            {"phone": "P",  "correct": true},
            {"phone": "AH", "correct": false},
            {"phone": "L",  "correct": false},
        ],
        "correct_count":  2,
        "total_count":    4,
        "phone_accuracy": 50.0,
    }
    """
    if not target_phones:
        return {
            "heard_phones":   [],
            "results":        [],
            "correct_count":  0,
            "total_count":    0,
            "phone_accuracy": 0.0,
        }

    total = len(target_phones)

    if probability >= CONFIDENCE_THRESHOLD:
        # 置信度高，全部正确
        correct_count = total
        results = [{"phone": p, "correct": True} for p in target_phones]
    else:
        # 置信度低，按比例计算正确音素数
        # 例如 probability=0.6，threshold=0.85 → 正确率约 70%
        ratio         = probability / CONFIDENCE_THRESHOLD
        correct_count = max(0, round(total * ratio))
        results = []
        for i, phone in enumerate(target_phones):
            results.append({
                "phone":   phone,
                "correct": i < correct_count,  # 前段正确，后段错误
            })

    phone_accuracy = round(correct_count / total * 100, 1) if total else 0.0

    return {
        "heard_phones":   target_phones,   # 无声学识别，用目标音素代替
        "results":        results,
        "correct_count":  correct_count,
        "total_count":    total,
        "phone_accuracy": phone_accuracy,
    }