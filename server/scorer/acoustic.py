# scorer/acoustic.py
import numpy as np
from scipy import spatial
from config import SPEECHBRAIN_MODEL

CONFIDENCE_THRESHOLD = 0.85

FEATURE_DIM = 18

PHONE_FEATURES = {
    # 元音 (18维特征: 开闭-前后-圆唇-长短-紧张-舌位)
    'AA': [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    'AE': [0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    'AH': [0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    'AO': [0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    'AW': [0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    'AY': [0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    'EH': [0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    'ER': [0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    'EY': [0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    'IH': [0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0],
    'IY': [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0],
    'OW': [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0],
    'OY': [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0],
    'UH': [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0],
    'UW': [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0],
    # 辅音 (18维特征: 爆破-鼻-擦-破-边-通)
    'B':  [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0],
    'CH': [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0],
    'D':  [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0],
    'DH': [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0],
    'F':  [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0],
    'G':  [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0],
    'HH': [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
    'JH': [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0],
    'K':  [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0],
    'L':  [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
    'M':  [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0],
    'N':  [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0],
    'NG': [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0],
    'P':  [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0],
    'R':  [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
    'S':  [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0],
    'SH': [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0],
    'T':  [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0],
    'TH': [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0],
    'V':  [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0],
    'W':  [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
    'Y':  [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
    'Z':  [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0],
    'ZH': [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0],
}

def phone_similarity(phone1, phone2):
    """计算两个音素的相似度"""
    feat1 = PHONE_FEATURES.get(phone1, [0]*FEATURE_DIM)
    feat2 = PHONE_FEATURES.get(phone2, [0]*FEATURE_DIM)

    if phone1 == phone2:
        return 1.0

    sum1 = sum(feat1)
    sum2 = sum(feat2)

    if sum1 == 0 or sum2 == 0:
        return 0.0

    similarity = 1 - spatial.distance.cosine(feat1, feat2)
    return max(0.0, similarity)

def align_phones(target_phones, heard_phones):
    """动态规划对齐两个音素序列"""
    m, n = len(target_phones), len(heard_phones)

    dp = np.zeros((m + 1, n + 1))
    backtrack = np.zeros((m + 1, n + 1), dtype=int)

    for i in range(1, m + 1):
        dp[i][0] = dp[i-1][0] + 1
        backtrack[i][0] = 2

    for j in range(1, n + 1):
        dp[0][j] = dp[0][j-1] + 1
        backtrack[0][j] = 1

    for i in range(1, m + 1):
        for j in range(1, n + 1):
            match_cost = 1 - phone_similarity(target_phones[i-1], heard_phones[j-1])
            delete_cost = 1
            insert_cost = 1

            dp[i][j] = min(
                dp[i-1][j-1] + match_cost,
                dp[i-1][j] + delete_cost,
                dp[i][j-1] + insert_cost
            )

            if dp[i][j] == dp[i-1][j-1] + match_cost:
                backtrack[i][j] = 0
            elif dp[i][j] == dp[i-1][j] + delete_cost:
                backtrack[i][j] = 2
            else:
                backtrack[i][j] = 1

    alignment = []
    i, j = m, n

    while i > 0 or j > 0:
        if backtrack[i][j] == 0:
            alignment.append((target_phones[i-1], heard_phones[j-1]))
            i -= 1
            j -= 1
        elif backtrack[i][j] == 2:
            alignment.append((target_phones[i-1], None))
            i -= 1
        else:
            alignment.append((None, heard_phones[j-1]))
            j -= 1

    return list(reversed(alignment))

def score_word(target_phones: list, heard_phones: list = None, probability: float = 0.0) -> dict:
    if not target_phones:
        return {
            "heard_phones":   [],
            "results":        [],
            "correct_count":  0,
            "total_count":    0,
            "phone_accuracy": 0.0,
        }

    if not heard_phones or len(heard_phones) == 0:
        return estimate_from_confidence(target_phones, probability)

    alignment = align_phones(target_phones, heard_phones)

    results = []
    correct_count = 0
    total_count = len(target_phones)
    heard_result = []

    for target, heard in alignment:
        if target is not None:
            if heard is not None:
                similarity = phone_similarity(target, heard)
                correct = similarity >= 0.7
                heard_result.append(heard)
            else:
                similarity = 0.0
                correct = False
                heard_result.append(target)

            results.append({
                "phone":      target,
                "correct":    correct,
                "similarity": round(similarity, 2),
            })

            if correct:
                correct_count += 1

    phone_accuracy = round(correct_count / total_count * 100, 1) if total_count else 0.0

    return {
        "heard_phones":   heard_result,
        "results":        results,
        "correct_count":  correct_count,
        "total_count":    total_count,
        "phone_accuracy": phone_accuracy,
    }

def estimate_from_confidence(target_phones: list, probability: float) -> dict:
    total = len(target_phones)

    if probability >= CONFIDENCE_THRESHOLD:
        correct_count = total
        results = [{"phone": p, "correct": True, "similarity": 1.0} for p in target_phones]
    else:
        ratio = probability / CONFIDENCE_THRESHOLD
        correct_count = max(0, round(total * ratio))
        results = []
        for i, phone in enumerate(target_phones):
            correct = i < correct_count
            results.append({
                "phone":      phone,
                "correct":    correct,
                "similarity": round(0.9 if correct else 0.3, 2),
            })

    phone_accuracy = round(correct_count / total * 100, 1) if total else 0.0

    return {
        "heard_phones":   target_phones,
        "results":        results,
        "correct_count":  correct_count,
        "total_count":    total_count,
        "phone_accuracy": phone_accuracy,
    }
