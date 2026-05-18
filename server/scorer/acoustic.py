# scorer/acoustic.py
import numpy as np
from scipy import spatial
from config import SPEECHBRAIN_MODEL

# 置信度低于此阈值，认为该词发音不准
CONFIDENCE_THRESHOLD = 0.85

# 预定义的英语音素到发音特征的映射（简化版）
PHONE_FEATURES = {
    # 元音
    'AA': [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],  # 后元音
    'AE': [0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],  # 前低元音
    'AH': [0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0],  # 中元音
    'AO': [0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0],  # 后圆唇元音
    'AW': [0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0],  # 双元音
    'AY': [0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0],  # 双元音
    'EH': [0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0],  # 前中元音
    'ER': [0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0],  # 卷舌元音
    'EY': [0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0],  # 双元音
    'IH': [0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0],  # 前高元音
    'IY': [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0],  # 前高元音
    'OW': [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],  # 后圆唇元音
    'OY': [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0],  # 双元音
    'UH': [0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0],  # 后高元音
    'UW': [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],  # 后高圆唇元音
    # 辅音（简化）
    'B':  [1, 0, 0, 0, 0, 0],
    'CH': [0, 1, 0, 0, 0, 0],
    'D':  [1, 0, 0, 0, 0, 0],
    'DH': [0, 0, 1, 0, 0, 0],
    'F':  [0, 0, 0, 1, 0, 0],
    'G':  [1, 0, 0, 0, 0, 0],
    'HH': [0, 0, 0, 0, 1, 0],
    'JH': [0, 1, 0, 0, 0, 0],
    'K':  [1, 0, 0, 0, 0, 0],
    'L':  [0, 0, 0, 0, 0, 1],
    'M':  [1, 0, 0, 0, 0, 0],
    'N':  [1, 0, 0, 0, 0, 0],
    'NG': [1, 0, 0, 0, 0, 0],
    'P':  [1, 0, 0, 0, 0, 0],
    'R':  [0, 0, 0, 0, 0, 1],
    'S':  [0, 0, 0, 1, 0, 0],
    'SH': [0, 0, 0, 1, 0, 0],
    'T':  [1, 0, 0, 0, 0, 0],
    'TH': [0, 0, 0, 1, 0, 0],
    'V':  [0, 0, 0, 1, 0, 0],
    'W':  [0, 0, 0, 0, 0, 1],
    'Y':  [0, 0, 0, 0, 0, 1],
    'Z':  [0, 0, 0, 1, 0, 0],
    'ZH': [0, 0, 0, 1, 0, 0],
}

def phone_similarity(phone1, phone2):
    """计算两个音素的相似度"""
    feat1 = PHONE_FEATURES.get(phone1, [0]*12)
    feat2 = PHONE_FEATURES.get(phone2, [0]*12)
    
    # 余弦相似度
    if sum(feat1) == 0 or sum(feat2) == 0:
        return 0.5 if phone1 == phone2 else 0.0
    
    similarity = 1 - spatial.distance.cosine(feat1, feat2)
    return similarity

def align_phones(target_phones, heard_phones):
    """动态规划对齐两个音素序列"""
    m, n = len(target_phones), len(heard_phones)
    
    # 创建得分矩阵
    dp = np.zeros((m + 1, n + 1))
    backtrack = np.zeros((m + 1, n + 1), dtype=int)  # 0: match, 1: insert, 2: delete
    
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
    
    # 回溯找到对齐路径
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
    """
    基于音素对齐进行声学打分。
    
    参数：
    - target_phones: 目标单词的标准音素列表
    - heard_phones: 识别到的音素列表（如果有）
    - probability: ASR 词级置信度
    
    返回：
    {
        "heard_phones":   ["AE", "P", "AH", "L"],
        "results": [
            {"phone": "AE", "correct": true, "similarity": 0.98},
            {"phone": "P",  "correct": true, "similarity": 1.0},
            {"phone": "AH", "correct": false, "similarity": 0.3},
            {"phone": "L",  "correct": true, "similarity": 0.95},
        ],
        "correct_count":  3,
        "total_count":    4,
        "phone_accuracy": 75.0,
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
    
    # 如果没有识别到音素，使用词置信度进行估算
    if not heard_phones or len(heard_phones) == 0:
        return estimate_from_confidence(target_phones, probability)
    
    # 音素对齐
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
                heard_result.append(target)  # 用目标音素填充
            
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
    """
    当没有音素识别结果时，基于词置信度估算打分。
    
    逻辑：
    - probability >= CONFIDENCE_THRESHOLD：整个词发音准确，所有音素标记为正确
    - probability < CONFIDENCE_THRESHOLD：按置信度比例，从后往前标记音素为错误
      （末尾音素通常是发音不准的高发位置）
    """
    total = len(target_phones)
    
    if probability >= CONFIDENCE_THRESHOLD:
        # 置信度高，全部正确
        correct_count = total
        results = [{"phone": p, "correct": True, "similarity": 1.0} for p in target_phones]
    else:
        # 置信度低，按比例计算正确音素数
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
